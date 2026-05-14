#!/usr/bin/env python3
"""
Fetch football data from football-data.org v4 API (free tier).
Provides: matches, standings, scorers, fixtures for 6 major leagues + Champions League.

Free tier: 10 requests/minute. This script spaces requests 6s apart.
No dependencies beyond stdlib — runs on GitHub Actions out of the box.

Usage:
  python3 scripts/fetch_football_data_api.py --all           # Everything
  python3 scripts/fetch_football_data_api.py --standings      # Just standings
  python3 scripts/fetch_football_data_api.py --matches        # Recent results
  python3 scripts/fetch_football_data_api.py --scorers        # Top scorers
  python3 scripts/fetch_football_data_api.py --fixtures       # Upcoming matches
  python3 scripts/fetch_football_data_api.py --competition PL # Single league
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(BASE_DIR, "data", "api")
TODAY = datetime.now().strftime("%Y-%m-%d")

# football-data.org API config
API_BASE = "https://api.football-data.org/v4"
API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "056abcd1654e4b8bacbcdeb61fa1afc0")

# Free-tier competitions we care about
COMPETITIONS = {
    "PD":  {"name": "LaLiga",          "country": "Spain"},
    "PL":  {"name": "Premier League",  "country": "England"},
    "BL1": {"name": "Bundesliga",      "country": "Germany"},
    "SA":  {"name": "Serie A",         "country": "Italy"},
    "FL1": {"name": "Ligue 1",         "country": "France"},
    "CL":  {"name": "Champions League","country": "Europe"},
    "PPL": {"name": "Primeira Liga",  "country": "Portugal"},
    "EL":  {"name": "Europa League",  "country": "Europe"},
    "ECL": {"name": "Conference League","country": "Europe"},
}

# Rate limiting
MIN_INTERVAL = 6.5  # seconds between requests (10 req/min limit)
_last_request_time = 0


def api_request(endpoint, params=None):
    """Make rate-limited API request."""
    global _last_request_time

    # Rate limit
    elapsed = time.time() - _last_request_time
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)

    url = f"{API_BASE}{endpoint}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    headers = {
        "X-Auth-Token": API_KEY,
        "User-Agent": "football-data-updater/1.0",
    }

    req = urllib.request.Request(url, headers=headers)
    _last_request_time = time.time()

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            remaining = resp.headers.get("X-Requests-Available-Minute", "?")
            data = json.loads(resp.read().decode("utf-8"))
            print(f"  OK: {endpoint} (remaining: {remaining}/min)")
            return data
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"  RATE LIMITED — waiting 60s...")
            time.sleep(60)
            return api_request(endpoint, params)  # retry once
        print(f"  ERROR {e.code}: {endpoint} -> {e.reason}")
        return None
    except Exception as e:
        print(f"  FAILED: {endpoint} -> {e}")
        return None


def save_json(data, filename):
    """Save JSON data to API directory."""
    os.makedirs(API_DIR, exist_ok=True)
    filepath = os.path.join(API_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    size_kb = os.path.getsize(filepath) / 1024
    print(f"  Saved: {filename} ({size_kb:.1f} KB)")
    return filepath


# ─── Fetch functions ───

def fetch_matches(competitions):
    """Fetch recent match results (last 7 days)."""
    print("\n=== Fetching match results ===")
    date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    date_to = TODAY

    all_matches = {}
    for code, info in competitions.items():
        print(f"\n  [{code}] {info['name']}...")
        data = api_request(f"/competitions/{code}/matches", {
            "dateFrom": date_from,
            "dateTo": date_to,
            "status": "FINISHED",
        })
        if data and "matches" in data:
            matches = []
            for m in data["matches"]:
                matches.append({
                    "id": m.get("id"),
                    "matchday": m.get("matchday"),
                    "date": m.get("utcDate", "")[:10],
                    "time": m.get("utcDate", "")[11:16],
                    "status": m.get("status"),
                    "home_team": m["homeTeam"]["name"],
                    "home_short": m["homeTeam"].get("shortName", ""),
                    "home_tla": m["homeTeam"].get("tla", ""),
                    "away_team": m["awayTeam"]["name"],
                    "away_short": m["awayTeam"].get("shortName", ""),
                    "away_tla": m["awayTeam"].get("tla", ""),
                    "ft_home": m.get("score", {}).get("fullTime", {}).get("home"),
                    "ft_away": m.get("score", {}).get("fullTime", {}).get("away"),
                    "ht_home": m.get("score", {}).get("halfTime", {}).get("home"),
                    "ht_away": m.get("score", {}).get("halfTime", {}).get("away"),
                    "winner": m.get("score", {}).get("winner"),
                    "referees": [
                        {"name": r.get("name"), "nationality": r.get("nationality")}
                        for r in m.get("referees", [])
                    ],
                })
            all_matches[code] = {
                "competition": info["name"],
                "date_range": f"{date_from} to {date_to}",
                "count": len(matches),
                "matches": matches,
            }
            print(f"    -> {len(matches)} matches")
        else:
            print(f"    -> No data")
            all_matches[code] = {"competition": info["name"], "count": 0, "matches": []}

    save_json(all_matches, f"matches_{TODAY}.json")
    return all_matches


def fetch_standings(competitions):
    """Fetch current league standings."""
    print("\n=== Fetching standings ===")

    all_standings = {}
    for code, info in competitions.items():
        print(f"\n  [{code}] {info['name']}...")
        data = api_request(f"/competitions/{code}/standings")
        if data and "standings" in data:
            tables = {}
            for standing in data["standings"]:
                table_type = standing.get("type", "TOTAL")
                table = []
                for row in standing.get("table", []):
                    table.append({
                        "position": row.get("position"),
                        "team": row["team"]["name"],
                        "team_short": row["team"].get("shortName", ""),
                        "team_tla": row["team"].get("tla", ""),
                        "played": row.get("playedGames"),
                        "won": row.get("won"),
                        "draw": row.get("draw"),
                        "lost": row.get("lost"),
                        "goals_for": row.get("goalsFor"),
                        "goals_against": row.get("goalsAgainst"),
                        "goal_diff": row.get("goalDifference"),
                        "points": row.get("points"),
                        "form": row.get("form"),
                    })
                tables[table_type] = table

            all_standings[code] = {
                "competition": info["name"],
                "season": data.get("season", {}).get("id"),
                "matchday": data.get("season", {}).get("currentMatchday"),
                "tables": tables,
            }
            total = tables.get("TOTAL", [])
            print(f"    -> {len(total)} teams, matchday {all_standings[code].get('matchday')}")
        else:
            print(f"    -> No data")

    save_json(all_standings, f"standings_{TODAY}.json")
    return all_standings


def fetch_scorers(competitions):
    """Fetch top scorers per competition."""
    print("\n=== Fetching top scorers ===")

    all_scorers = {}
    for code, info in competitions.items():
        print(f"\n  [{code}] {info['name']}...")
        data = api_request(f"/competitions/{code}/scorers", {"limit": 30})
        if data and "scorers" in data:
            scorers = []
            for s in data["scorers"]:
                player = s.get("player", {})
                team = s.get("team", {})
                scorers.append({
                    "name": player.get("name"),
                    "nationality": player.get("nationality"),
                    "position": player.get("position"),
                    "date_of_birth": player.get("dateOfBirth"),
                    "team": team.get("name"),
                    "team_short": team.get("shortName", ""),
                    "goals": s.get("goals"),
                    "assists": s.get("assists"),
                    "penalties": s.get("penalties"),
                    "played_matches": s.get("playedMatches"),
                })
            all_scorers[code] = {
                "competition": info["name"],
                "count": len(scorers),
                "scorers": scorers,
            }
            if scorers:
                top = scorers[0]
                print(f"    -> {len(scorers)} scorers, top: {top['name']} ({top['goals']} goals)")
        else:
            print(f"    -> No data")

    save_json(all_scorers, f"scorers_{TODAY}.json")
    return all_scorers


def fetch_fixtures(competitions):
    """Fetch upcoming fixtures (next 14 days)."""
    print("\n=== Fetching upcoming fixtures ===")
    date_from = TODAY
    date_to = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    all_fixtures = {}
    for code, info in competitions.items():
        print(f"\n  [{code}] {info['name']}...")
        data = api_request(f"/competitions/{code}/matches", {
            "dateFrom": date_from,
            "dateTo": date_to,
            "status": "SCHEDULED,TIMED",
        })
        if data and "matches" in data:
            fixtures = []
            for m in data["matches"]:
                fixtures.append({
                    "id": m.get("id"),
                    "matchday": m.get("matchday"),
                    "date": m.get("utcDate", "")[:10],
                    "time": m.get("utcDate", "")[11:16],
                    "home_team": m["homeTeam"]["name"],
                    "home_short": m["homeTeam"].get("shortName", ""),
                    "away_team": m["awayTeam"]["name"],
                    "away_short": m["awayTeam"].get("shortName", ""),
                    "referees": [
                        {"name": r.get("name"), "nationality": r.get("nationality")}
                        for r in m.get("referees", [])
                    ],
                })
            all_fixtures[code] = {
                "competition": info["name"],
                "date_range": f"{date_from} to {date_to}",
                "count": len(fixtures),
                "fixtures": fixtures,
            }
            print(f"    -> {len(fixtures)} upcoming fixtures")
        else:
            print(f"    -> No data")
            all_fixtures[code] = {"competition": info["name"], "count": 0, "fixtures": []}

    save_json(all_fixtures, f"fixtures_api_{TODAY}.json")
    return all_fixtures


# ─── Main ───

def main():
    args = sys.argv[1:]

    # Parse --competition flag
    comps = COMPETITIONS
    if "--competition" in args:
        idx = args.index("--competition")
        if idx + 1 < len(args):
            code = args[idx + 1].upper()
            if code in COMPETITIONS:
                comps = {code: COMPETITIONS[code]}
                print(f"Single competition mode: {code} ({COMPETITIONS[code]['name']})")
            else:
                print(f"Unknown competition: {code}. Available: {', '.join(COMPETITIONS.keys())}")
                sys.exit(1)

    do_all = "--all" in args or len([a for a in args if a.startswith("--") and a not in ("--competition",)]) == 0

    print(f"football-data.org API fetcher — {TODAY}")
    print(f"Competitions: {', '.join(comps.keys())}")
    print(f"API calls needed: ~{len(comps) * sum([do_all or '--matches' in args, do_all or '--standings' in args, do_all or '--scorers' in args, do_all or '--fixtures' in args])} requests")
    print(f"Estimated time: ~{len(comps) * sum([do_all or '--matches' in args, do_all or '--standings' in args, do_all or '--scorers' in args, do_all or '--fixtures' in args]) * 6.5 / 60:.1f} minutes")
    print("=" * 50)

    results = {}

    if do_all or "--matches" in args:
        results["matches"] = fetch_matches(comps)

    if do_all or "--standings" in args:
        results["standings"] = fetch_standings(comps)

    if do_all or "--scorers" in args:
        results["scorers"] = fetch_scorers(comps)

    if do_all or "--fixtures" in args:
        results["fixtures"] = fetch_fixtures(comps)

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    if "matches" in results:
        total = sum(v.get("count", 0) for v in results["matches"].values())
        print(f"  Matches (last 7 days): {total}")
    if "standings" in results:
        print(f"  Standings: {len(results['standings'])} leagues")
    if "scorers" in results:
        total = sum(v.get("count", 0) for v in results["scorers"].values())
        print(f"  Top scorers: {total}")
    if "fixtures" in results:
        total = sum(v.get("count", 0) for v in results["fixtures"].values())
        print(f"  Upcoming fixtures: {total}")
    print("=" * 50)


if __name__ == "__main__":
    main()
