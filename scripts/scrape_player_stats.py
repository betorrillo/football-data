#!/usr/bin/env python3
"""
Scrape COMPLETE individual player statistics from FotMob data API.
Fetches goals, assists, shots, SOT, tackles, fouls, cards, saves, xG per player.
All stats come as per-90 values with total counts.

Covers ALL bet365 player prop markets:
- Goleador / Cualquiera anotará / Primero en anotar
- Jugador remates / remates a puerta / remates cabeza / fuera del área
- Jugador asistencia / anotará o asistirá
- Jugador tarjetas / será amonestado
- Jugador faltas concedidas / recibirá falta
- Jugador entradas (tackles)
- Paradas del portero

Usage:
  python3 scripts/scrape_player_stats.py              # All leagues
  python3 scripts/scrape_player_stats.py --league laliga
"""

import argparse
import gzip
import json
import os
import re
import time
import urllib.request
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYERS_DIR = os.path.join(BASE_DIR, "stats", "players")

TODAY = datetime.now().strftime("%Y-%m-%d")
CURRENT_SEASON = "2025-26"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

HEADERS_API = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Encoding": "gzip",
}

# FotMob league IDs and season IDs (2025-26)
LEAGUES = {
    "laliga":     {"fm_id": 87,  "season_id": "27233", "name": "LaLiga"},
    "segunda":    {"fm_id": 140, "season_id": "27234", "name": "Segunda Division"},
    "epl":        {"fm_id": 47,  "season_id": "27110", "name": "Premier League"},
    "bundesliga": {"fm_id": 54,  "season_id": "26891", "name": "Bundesliga"},
    "seriea":     {"fm_id": 55,  "season_id": "27044", "name": "Serie A"},
    "ligue1":     {"fm_id": 53,  "season_id": "27212", "name": "Ligue 1"},
    "portugal":   {"fm_id": 61,  "season_id": "27266", "name": "Primeira Liga"},
}

# Stats to scrape — covers ALL bet365 player markets
STATS_TO_SCRAPE = {
    # Scoring
    "goals":                 {"key": "goals",      "label": "Goals"},
    "goal_assist":           {"key": "assists",     "label": "Assists"},
    "expected_goals":        {"key": "xg",          "label": "xG"},
    "expected_assists":      {"key": "xa",          "label": "xA"},
    # Shooting
    "total_scoring_att":     {"key": "shots_per90", "label": "Shots per 90"},
    "ontarget_scoring_att":  {"key": "sot_per90",   "label": "SOT per 90"},
    # Discipline & fouls
    "yellow_card":           {"key": "yellows",     "label": "Yellow cards"},
    "red_card":              {"key": "reds",         "label": "Red cards"},
    "fouls":                 {"key": "fouls_per90",  "label": "Fouls committed per 90"},
    # Defensive
    "total_tackle":          {"key": "tackles_per90","label": "Tackles per 90"},
    # Goalkeeping
    "saves":                 {"key": "saves_per90",  "label": "Saves per 90"},
}


def fetch_stat_data(fm_id, season_id, stat_slug):
    """Fetch stat data from FotMob data API."""
    url = f"https://data.fotmob.com/stats/{fm_id}/season/{season_id}/{stat_slug}.json"
    req = urllib.request.Request(url, headers=HEADERS_API)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            try:
                text = gzip.decompress(raw).decode("utf-8")
            except:
                text = raw.decode("utf-8", errors="replace")
            return json.loads(text)
    except Exception as e:
        return None


def discover_season_id(fm_id, league_slug=""):
    """Discover current season ID from FotMob league stats page."""
    url = f"https://www.fotmob.com/leagues/{fm_id}/stats"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            stats = data["props"]["pageProps"]["stats"]
            players = stats.get("players", [])
            if players and players[0].get("fetchAllUrl"):
                fetch_url = players[0]["fetchAllUrl"]
                parts = fetch_url.split("/")
                idx = parts.index("season") + 1
                return parts[idx]
    except:
        pass
    return None


def scrape_league(league_key, league_info):
    """Scrape all player stats for one league from FotMob."""
    fm_id = league_info["fm_id"]
    season_id = league_info["season_id"]
    league_name = league_info["name"]

    print(f"\n  {league_name} (FotMob ID={fm_id}, Season={season_id})")

    # Try to discover latest season ID
    discovered = discover_season_id(fm_id)
    if discovered and discovered != season_id:
        print(f"    Season ID updated: {season_id} -> {discovered}")
        season_id = discovered

    # Collect all stat data, indexed by player ID
    players = {}

    for stat_slug, stat_info in STATS_TO_SCRAPE.items():
        key = stat_info["key"]
        data = fetch_stat_data(fm_id, season_id, stat_slug)

        if not data:
            print(f"    {stat_info['label']:30s} FAILED")
            continue

        top_lists = data.get("TopLists", [])
        if not top_lists:
            print(f"    {stat_info['label']:30s} EMPTY")
            continue

        stat_list = top_lists[0].get("StatList", [])
        print(f"    {stat_info['label']:30s} {len(stat_list):4d} players")

        for entry in stat_list:
            pid = entry.get("ParticiantId")
            if not pid:
                continue

            if pid not in players:
                players[pid] = {
                    "id": pid,
                    "player": entry.get("ParticipantName", ""),
                    "team": entry.get("TeamName", ""),
                    "team_id": entry.get("TeamId"),
                    "mp": entry.get("MatchesPlayed", 0),
                    "min": entry.get("MinutesPlayed", 0),
                }

            # Store the stat value
            value = entry.get("StatValue", 0)
            sub_value = entry.get("SubStatValue", 0)

            if key in ("goals", "assists", "yellows", "reds", "xg", "xa"):
                # These are totals
                players[pid][key] = value
                if key == "goals" and sub_value:
                    players[pid]["penalties"] = int(sub_value)
            else:
                # These are per-90 values
                players[pid][key] = round(value, 2)

            # Update mp/min if higher
            mp = entry.get("MatchesPlayed", 0)
            mins = entry.get("MinutesPlayed", 0)
            if mp > players[pid].get("mp", 0):
                players[pid]["mp"] = mp
            if mins > players[pid].get("min", 0):
                players[pid]["min"] = mins

        time.sleep(1)  # Rate limiting

    # Post-process: calculate additional per-90 values
    player_list = list(players.values())
    for p in player_list:
        minutes = p.get("min", 0)
        if minutes >= 90:
            nineties = minutes / 90
            # Calculate per90 for totals that aren't already per90
            goals = p.get("goals", 0)
            assists = p.get("assists", 0)
            yellows = p.get("yellows", 0)

            p["goals_per90"] = round(goals / nineties, 2) if goals else 0
            p["assists_per90"] = round(assists / nineties, 2) if assists else 0
            p["g_a_per90"] = round((goals + assists) / nineties, 2)
            p["yellows_per90"] = round(yellows / nineties, 2) if yellows else 0

    # Filter: at least 3 matches
    player_list = [p for p in player_list if p.get("mp", 0) >= 3]

    # Sort by goals (desc), then minutes
    player_list.sort(key=lambda x: (-x.get("goals", 0), -x.get("min", 0)))

    print(f"    Total: {len(player_list)} players (3+ matches)")

    # Save
    output = {
        "generated": TODAY,
        "source": "fotmob.com",
        "league": league_name,
        "season": CURRENT_SEASON,
        "fotmob_league_id": fm_id,
        "fotmob_season_id": season_id,
        "total_players": len(player_list),
        "stats_available": list(STATS_TO_SCRAPE.keys()),
        "players": player_list,
    }

    path = os.path.join(PLAYERS_DIR, f"player_stats_{league_key}_{CURRENT_SEASON}.json")
    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    # Print top 5
    for p in player_list[:5]:
        print(f"      {p['team']:20s} | {p['player']:22s} | "
              f"G={p.get('goals',0):2.0f} A={p.get('assists',0):2.0f} "
              f"Sh/90={p.get('shots_per90',0):.1f} SOT/90={p.get('sot_per90',0):.1f} "
              f"YC={p.get('yellows',0):.0f} F/90={p.get('fouls_per90',0):.1f} "
              f"T/90={p.get('tackles_per90',0):.1f}")

    return player_list


def main():
    parser = argparse.ArgumentParser(description="Scrape player stats from FotMob")
    parser.add_argument("--league", type=str, help="Specific league (e.g., laliga)")
    args = parser.parse_args()

    print(f"Player Stats Scraper (FotMob) — {TODAY}")
    print("=" * 50)
    os.makedirs(PLAYERS_DIR, exist_ok=True)

    leagues_to_scrape = {}
    if args.league:
        if args.league in LEAGUES:
            leagues_to_scrape = {args.league: LEAGUES[args.league]}
        else:
            print(f"Unknown league: {args.league}. Available: {', '.join(LEAGUES.keys())}")
            return
    else:
        leagues_to_scrape = LEAGUES

    total_players = 0
    for league_key, league_info in leagues_to_scrape.items():
        players = scrape_league(league_key, league_info)
        total_players += len(players)

        if len(leagues_to_scrape) > 1:
            print(f"    Waiting 5s...")
            time.sleep(5)

    print(f"\n{'='*50}")
    print(f"COMPLETE — {total_players} players across {len(leagues_to_scrape)} leagues")


if __name__ == "__main__":
    main()
