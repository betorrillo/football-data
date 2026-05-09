#!/usr/bin/env python3
"""
Scrape minute-by-minute match events (goals, cards) from ESPN API.
Builds per-team timing stats for "first 10 min", "first half", etc.

Usage:
  python3 scripts/scrape_match_events.py          # All leagues
  python3 scripts/scrape_match_events.py --league laliga
"""

import argparse
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_DIR = os.path.join(BASE_DIR, "stats", "events")
MATCHES_DIR = os.path.join(BASE_DIR, "matches")

TODAY = datetime.now().strftime("%Y-%m-%d")
CURRENT_SEASON = "2025-26"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

LEAGUES = {
    "laliga":     {"espn_id": "esp.1",  "name": "LaLiga"},
    "segunda":    {"espn_id": "esp.2",  "name": "Segunda Division"},
    "epl":        {"espn_id": "eng.1",  "name": "Premier League"},
    "bundesliga": {"espn_id": "ger.1",  "name": "Bundesliga"},
    "seriea":     {"espn_id": "ita.1",  "name": "Serie A"},
    "ligue1":     {"espn_id": "fra.1",  "name": "Ligue 1"},
}


def fetch_json(url):
    """Fetch URL and parse JSON."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return None


def get_season_match_ids(espn_id):
    """Get all completed match IDs for current season from ESPN scoreboard API."""
    match_ids = []
    # ESPN scoreboard by date — scan from Aug 2025 to today
    start = datetime(2025, 8, 1)
    end = datetime.now()
    delta = end - start

    # Scan week by week to reduce requests
    current = start
    while current <= end:
        date_str = current.strftime("%Y%m%d")
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{espn_id}/scoreboard?dates={date_str}"
        data = fetch_json(url)
        if data and "events" in data:
            for event in data["events"]:
                status = event.get("status", {}).get("type", {}).get("name", "")
                if status == "STATUS_FULL_TIME" or status == "STATUS_FINAL":
                    eid = event.get("id")
                    if eid:
                        match_ids.append(eid)
        current += timedelta(days=1)
        # Small delay every 10 days
        if (current - start).days % 10 == 0:
            time.sleep(0.5)

    return list(set(match_ids))  # deduplicate


def get_match_events(espn_id, event_id):
    """Get events for a single match from ESPN summary API."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{espn_id}/summary?event={event_id}"
    data = fetch_json(url)
    if not data:
        return None

    result = {
        "event_id": event_id,
        "home": "",
        "away": "",
        "goals": [],
        "cards": [],
    }

    # Get team names
    header = data.get("header", {})
    competitions = header.get("competitions", [{}])
    if competitions:
        competitors = competitions[0].get("competitors", [])
        for c in competitors:
            if c.get("homeAway") == "home":
                result["home"] = c.get("team", {}).get("displayName", "")
            elif c.get("homeAway") == "away":
                result["away"] = c.get("team", {}).get("displayName", "")

    # Parse key events
    key_events = data.get("keyEvents", [])
    if not key_events:
        # Try commentary or plays
        key_events = data.get("plays", [])

    for event in key_events:
        etype = event.get("type", {}).get("text", "")
        minute = event.get("clock", {}).get("displayValue", "")
        team_data = event.get("team", {})
        team_name = team_data.get("displayName", "")

        # Parse minute from "45'+2" or "67'" format
        min_val = parse_minute(minute)
        if min_val is None:
            continue

        if "Goal" in etype or etype == "Goal":
            result["goals"].append({
                "team": team_name,
                "minute": min_val,
                "type": etype,
            })
        elif "Yellow" in etype or "Red" in etype or "Card" in etype:
            card_type = "yellow" if "Yellow" in etype else "red"
            result["cards"].append({
                "team": team_name,
                "minute": min_val,
                "type": card_type,
            })

    # Also try roster/boxscore for more detailed data
    boxscore = data.get("boxscore", {})
    if boxscore and not result["goals"]:
        # Try to extract from boxscore players
        for team_data in boxscore.get("teams", []):
            team_info = team_data.get("team", {})
            team_name = team_info.get("displayName", "")
            for player in team_data.get("statistics", []):
                # ESPN boxscore format varies
                pass

    return result


def parse_minute(minute_str):
    """Parse minute string like '45' or '45+2' or '67' to integer."""
    if not minute_str:
        return None
    minute_str = str(minute_str).replace("'", "").strip()
    if "+" in minute_str:
        parts = minute_str.split("+")
        try:
            return int(parts[0]) + int(parts[1])
        except (ValueError, IndexError):
            try:
                return int(parts[0])
            except ValueError:
                return None
    try:
        return int(minute_str)
    except ValueError:
        return None


def load_existing_events(league_key):
    """Load existing event data to avoid re-scraping."""
    path = os.path.join(EVENTS_DIR, f"match_events_{league_key}_{CURRENT_SEASON}.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    # Index by event_id
    return {m["event_id"]: m for m in data.get("matches", [])}


def build_team_event_stats(matches):
    """Build per-team aggregated timing stats from match events."""
    teams = {}

    for match in matches:
        home = match.get("home", "")
        away = match.get("away", "")
        if not home or not away:
            continue

        for team_name in [home, away]:
            if team_name not in teams:
                teams[team_name] = {
                    "mp": 0,
                    "goals_scored_1h": 0, "goals_scored_2h": 0,
                    "goals_conceded_1h": 0, "goals_conceded_2h": 0,
                    "goals_first_10": 0, "goals_conceded_first_10": 0,
                    "goals_last_10": 0, "goals_conceded_last_10": 0,
                    "cards_1h": 0, "cards_2h": 0,
                    "cards_first_30": 0,
                    "opponent_cards_1h": 0, "opponent_cards_2h": 0,
                    "first_goal_minutes": [],
                    "first_card_minutes": [],
                    "matches_with_goal_first_10": 0,
                    "matches_with_goal_conceded_first_10": 0,
                }

        teams[home]["mp"] += 1
        teams[away]["mp"] += 1

        # Process goals
        goals = match.get("goals", [])
        home_first_goal = None
        away_first_goal = None

        for g in sorted(goals, key=lambda x: x.get("minute", 99)):
            minute = g.get("minute", 99)
            goal_team = g.get("team", "")

            # Determine who scored — fuzzy match
            is_home_goal = (goal_team == home or home.lower() in goal_team.lower() or goal_team.lower() in home.lower())
            is_away_goal = (goal_team == away or away.lower() in goal_team.lower() or goal_team.lower() in away.lower())

            if is_home_goal:
                if minute <= 45:
                    teams[home]["goals_scored_1h"] += 1
                    teams[away]["goals_conceded_1h"] += 1
                else:
                    teams[home]["goals_scored_2h"] += 1
                    teams[away]["goals_conceded_2h"] += 1
                if minute <= 10:
                    teams[home]["goals_first_10"] += 1
                    teams[away]["goals_conceded_first_10"] += 1
                if minute >= 80:
                    teams[home]["goals_last_10"] += 1
                    teams[away]["goals_conceded_last_10"] += 1
                if home_first_goal is None:
                    home_first_goal = minute

            elif is_away_goal:
                if minute <= 45:
                    teams[away]["goals_scored_1h"] += 1
                    teams[home]["goals_conceded_1h"] += 1
                else:
                    teams[away]["goals_scored_2h"] += 1
                    teams[home]["goals_conceded_2h"] += 1
                if minute <= 10:
                    teams[away]["goals_first_10"] += 1
                    teams[home]["goals_conceded_first_10"] += 1
                if minute >= 80:
                    teams[away]["goals_last_10"] += 1
                    teams[home]["goals_conceded_last_10"] += 1
                if away_first_goal is None:
                    away_first_goal = minute

        # Track first goal minute
        if home_first_goal is not None:
            teams[home]["first_goal_minutes"].append(home_first_goal)
        if away_first_goal is not None:
            teams[away]["first_goal_minutes"].append(away_first_goal)

        # Track matches with goal in first 10
        match_has_goal_first_10 = any(g.get("minute", 99) <= 10 for g in goals)
        if match_has_goal_first_10:
            for g in goals:
                if g.get("minute", 99) <= 10:
                    goal_team = g.get("team", "")
                    if home.lower() in goal_team.lower() or goal_team.lower() in home.lower():
                        teams[home]["matches_with_goal_first_10"] += 1
                        teams[away]["matches_with_goal_conceded_first_10"] += 1
                    elif away.lower() in goal_team.lower() or goal_team.lower() in away.lower():
                        teams[away]["matches_with_goal_first_10"] += 1
                        teams[home]["matches_with_goal_conceded_first_10"] += 1
                    break  # Only count once per match

        # Process cards
        cards = match.get("cards", [])
        home_first_card = None
        away_first_card = None

        for c in sorted(cards, key=lambda x: x.get("minute", 99)):
            minute = c.get("minute", 99)
            card_team = c.get("team", "")

            is_home_card = (card_team == home or home.lower() in card_team.lower() or card_team.lower() in home.lower())
            is_away_card = (card_team == away or away.lower() in card_team.lower() or card_team.lower() in away.lower())

            if is_home_card:
                if minute <= 45:
                    teams[home]["cards_1h"] += 1
                    teams[away]["opponent_cards_1h"] += 1
                else:
                    teams[home]["cards_2h"] += 1
                    teams[away]["opponent_cards_2h"] += 1
                if minute <= 30:
                    teams[home]["cards_first_30"] += 1
                if home_first_card is None:
                    home_first_card = minute
            elif is_away_card:
                if minute <= 45:
                    teams[away]["cards_1h"] += 1
                    teams[home]["opponent_cards_1h"] += 1
                else:
                    teams[away]["cards_2h"] += 1
                    teams[home]["opponent_cards_2h"] += 1
                if minute <= 30:
                    teams[away]["cards_first_30"] += 1
                if away_first_card is None:
                    away_first_card = minute

        if home_first_card is not None:
            teams[home]["first_card_minutes"].append(home_first_card)
        if away_first_card is not None:
            teams[away]["first_card_minutes"].append(away_first_card)

    # Calculate percentages and averages
    result = {}
    for team_name, t in teams.items():
        mp = t["mp"]
        if mp == 0:
            continue

        first_goal_avg = round(sum(t["first_goal_minutes"]) / len(t["first_goal_minutes"]), 1) if t["first_goal_minutes"] else None
        first_card_avg = round(sum(t["first_card_minutes"]) / len(t["first_card_minutes"]), 1) if t["first_card_minutes"] else None

        result[team_name] = {
            "mp": mp,
            "goals_scored_1h": t["goals_scored_1h"],
            "goals_scored_2h": t["goals_scored_2h"],
            "goals_conceded_1h": t["goals_conceded_1h"],
            "goals_conceded_2h": t["goals_conceded_2h"],
            "goals_first_10": t["goals_first_10"],
            "goals_first_10_pct": round(t["matches_with_goal_first_10"] / mp * 100, 1),
            "goals_conceded_first_10": t["goals_conceded_first_10"],
            "goals_conceded_first_10_pct": round(t["matches_with_goal_conceded_first_10"] / mp * 100, 1),
            "goals_last_10": t["goals_last_10"],
            "goals_last_10_pct": round(t["goals_last_10"] / mp * 100, 1),
            "cards_1h": t["cards_1h"],
            "cards_2h": t["cards_2h"],
            "cards_first_30": t["cards_first_30"],
            "cards_first_30_pct": round(t["cards_first_30"] / mp * 100, 1),
            "opponent_cards_1h": t["opponent_cards_1h"],
            "opponent_cards_2h": t["opponent_cards_2h"],
            "first_goal_avg_min": first_goal_avg,
            "first_card_avg_min": first_card_avg,
            "matches_with_first_goal_data": len(t["first_goal_minutes"]),
            "matches_with_first_card_data": len(t["first_card_minutes"]),
        }

    return result


def scrape_league_events(league_key, league_info, full_scan=False):
    """Scrape match events for a league. By default only checks last 14 days."""
    espn_id = league_info["espn_id"]
    print(f"\n{'='*40}")
    print(f"{league_info['name']}")
    print(f"{'='*40}")

    # Load existing data
    existing = load_existing_events(league_key)
    print(f"  Existing events: {len(existing)} matches")

    # Load our match data to get the list of matches we need events for
    match_file = os.path.join(MATCHES_DIR, league_key, f"{CURRENT_SEASON}.json")
    if not os.path.exists(match_file):
        print(f"  No match file found for {league_key}")
        return []

    with open(match_file) as f:
        our_matches = json.load(f).get("matches", [])

    # Only process completed matches
    completed = [m for m in our_matches if m.get("ft_home") is not None]
    print(f"  Completed matches in our data: {len(completed)}")

    # Get ESPN event IDs by date
    all_events = list(existing.values())
    new_count = 0

    # Scan dates from our match data
    dates_seen = set()
    for m in completed:
        date_str = m.get("date", "")
        if not date_str:
            continue
        # Convert DD/MM/YYYY to YYYYMMDD
        try:
            parts = date_str.split("/")
            if len(parts) == 3:
                espn_date = f"{parts[2]}{parts[1]}{parts[0]}"
                dates_seen.add(espn_date)
        except (IndexError, ValueError):
            continue

    if full_scan:
        dates_sorted = sorted(dates_seen)
        print(f"  FULL SCAN: {len(dates_sorted)} match dates to check")
    else:
        # Only scan recent dates (last 14 days) — older matches are already cached
        cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y%m%d")
        dates_sorted = sorted([d for d in dates_seen if d >= cutoff])
        dates_skipped = len(dates_seen) - len(dates_sorted)
        print(f"  Unique match dates: {len(dates_seen)} total, checking {len(dates_sorted)} recent (skipped {dates_skipped} cached)")

    batch_count = 0
    for date_str in dates_sorted:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{espn_id}/scoreboard?dates={date_str}"
        data = fetch_json(url)

        if not data or "events" not in data:
            continue

        for event in data["events"]:
            eid = event.get("id")
            if not eid or eid in existing:
                continue

            status = event.get("status", {}).get("type", {}).get("name", "")
            if status not in ("STATUS_FULL_TIME", "STATUS_FINAL"):
                continue

            # Get detailed events for this match
            match_data = get_match_events(espn_id, eid)
            if match_data:
                all_events.append(match_data)
                existing[eid] = match_data
                new_count += 1

            batch_count += 1
            if batch_count % 5 == 0:
                time.sleep(1)

        # Delay between date requests
        time.sleep(0.3)

        # Progress
        if len(dates_sorted) > 20 and dates_sorted.index(date_str) % 20 == 0:
            pct = round(dates_sorted.index(date_str) / len(dates_sorted) * 100)
            print(f"    Progress: {pct}% ({len(all_events)} events so far, {new_count} new)")

    print(f"  Total events: {len(all_events)} ({new_count} new)")

    # Save raw match events
    output = {
        "generated": TODAY,
        "source": "ESPN API",
        "league": league_info["name"],
        "season": CURRENT_SEASON,
        "total_matches": len(all_events),
        "matches": all_events,
    }

    path = os.path.join(EVENTS_DIR, f"match_events_{league_key}_{CURRENT_SEASON}.json")
    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    # Build team stats
    team_stats = build_team_event_stats(all_events)
    stats_path = os.path.join(EVENTS_DIR, f"team_event_stats_{league_key}_{CURRENT_SEASON}.json")
    with open(stats_path, "w") as f:
        json.dump({
            "generated": TODAY,
            "source": "ESPN API (derived)",
            "league": league_info["name"],
            "season": CURRENT_SEASON,
            "total_teams": len(team_stats),
            "teams": team_stats,
        }, f, indent=2)

    print(f"  Team event stats: {len(team_stats)} teams")
    # Print sample
    for team_name in list(team_stats.keys())[:3]:
        t = team_stats[team_name]
        print(f"    {team_name}: goals 1H={t['goals_scored_1h']} 2H={t['goals_scored_2h']}, "
              f"first10={t['goals_first_10_pct']}%, cards_1H={t['cards_1h']}")

    return all_events


def main():
    parser = argparse.ArgumentParser(description="Scrape match events from ESPN")
    parser.add_argument("--league", type=str, help="Specific league to scrape")
    parser.add_argument("--full", action="store_true", help="Full season scan (slow, ~20min). Default: last 14 days only")
    args = parser.parse_args()

    print(f"Match Events Scraper — {TODAY}")
    print(f"Mode: {'FULL SCAN' if args.full else 'INCREMENTAL (last 14 days)'}")
    print("=" * 50)
    os.makedirs(EVENTS_DIR, exist_ok=True)

    leagues_to_scrape = {}
    if args.league:
        if args.league in LEAGUES:
            leagues_to_scrape = {args.league: LEAGUES[args.league]}
        else:
            print(f"Unknown league: {args.league}. Available: {', '.join(LEAGUES.keys())}")
            return
    else:
        leagues_to_scrape = LEAGUES

    total_events = 0

    # Process 2 leagues in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(scrape_league_events, key, info, args.full): key
            for key, info in leagues_to_scrape.items()
        }
        for future in as_completed(futures):
            league_key = futures[future]
            try:
                events = future.result()
                total_events += len(events)
            except Exception as e:
                print(f"  ERROR processing {league_key}: {e}")

    print(f"\n{'='*50}")
    print(f"COMPLETE — {total_events} match events across {len(leagues_to_scrape)} leagues")


if __name__ == "__main__":
    main()
