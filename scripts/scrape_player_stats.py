#!/usr/bin/env python3
"""
Scrape individual player statistics from Transfermarkt.
Fetches top scorers page per league with goals, assists, penalties, minutes.
Calculates per-90 stats for each player.

Usage:
  python3 scripts/scrape_player_stats.py              # All leagues
  python3 scripts/scrape_player_stats.py --league laliga
"""

import argparse
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
TM_SEASON_ID = "2025"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

LEAGUES = {
    "laliga":     {"tm_comp": "ES1", "tm_name": "laliga",          "name": "LaLiga"},
    "segunda":    {"tm_comp": "ES2", "tm_name": "segunda-division", "name": "Segunda Division"},
    "epl":        {"tm_comp": "GB1", "tm_name": "premier-league",  "name": "Premier League"},
    "bundesliga": {"tm_comp": "L1",  "tm_name": "1-bundesliga",    "name": "Bundesliga"},
    "seriea":     {"tm_comp": "IT1", "tm_name": "serie-a",         "name": "Serie A"},
    "ligue1":     {"tm_comp": "FR1", "tm_name": "ligue-1",         "name": "Ligue 1"},
}


def fetch_url(url, retries=2):
    """Fetch URL with retries."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == retries:
                print(f"  FAILED: {url} -> {e}")
                return None
            time.sleep(3)
    return None


def parse_minutes(val):
    """Parse TM minutes format like \"2.397'\" to int 2397."""
    val = val.replace("'", "").replace(".", "").replace(",", "").strip()
    if val == "-" or not val:
        return 0
    try:
        return int(val)
    except ValueError:
        return 0


def safe_int(val):
    """Parse integer, return 0 on failure."""
    val = str(val).strip().replace(".", "").replace(",", "")
    if val == "-" or not val:
        return 0
    try:
        return int(val)
    except ValueError:
        return 0


def scrape_scorers(tm_name, tm_comp):
    """Scrape top scorers from TM torschuetzenliste page.

    TM table columns (14 cells per row):
    [0] Rank
    [1] (player image)
    [2] Player name (hauptlink)
    [3] Position
    [4] (nationality flag)
    [5] Age
    [6] Team (link with title)
    [7] MP (matches played)
    [8] Assists
    [9] Penalties scored
    [10] Minutes played (format: 2.397')
    [11] Minutes per goal
    [12] Goals per match ratio
    [13] Goals (linked number)
    """
    url = f"https://www.transfermarkt.com/{tm_name}/torschuetzenliste/wettbewerb/{tm_comp}/saison_id/{TM_SEASON_ID}/altersklasse/alle/detailpos//plus/1"
    html = fetch_url(url)
    if not html:
        return []

    # Find row boundaries
    starts = [m.start() for m in re.finditer(r'<tr[^>]*class="[^"]*(?:odd|even)[^"]*"', html)]
    starts.append(len(html))

    players = []
    for i in range(len(starts) - 1):
        row = html[starts[i]:starts[i + 1]]
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
        vals = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]

        if len(vals) < 14:
            continue

        name = vals[2]
        if not name:
            continue

        # Extract team from title attribute in cell 6
        team = ""
        if len(cells) > 6:
            team_match = re.search(r'title="([^"]+)"', cells[6])
            if team_match:
                team = team_match.group(1)

        position = vals[3]
        mp = safe_int(vals[7])
        assists = safe_int(vals[8])
        penalties = safe_int(vals[9])
        minutes = parse_minutes(vals[10])
        goals = safe_int(vals[13])

        # Calculate per-90
        per90 = {}
        if minutes >= 90:
            nineties = minutes / 90
            per90 = {
                "goals": round(goals / nineties, 2),
                "assists": round(assists / nineties, 2),
                "g_a": round((goals + assists) / nineties, 2),
            }

        players.append({
            "player": name,
            "team": team,
            "position": position,
            "mp": mp,
            "min": minutes,
            "goals": goals,
            "assists": assists,
            "penalties": penalties,
            "per90": per90,
        })

    return players


def scrape_league(league_key, league_info):
    """Scrape player stats for one league."""
    print(f"\n  {league_info['name']}...", end=" ", flush=True)

    players = scrape_scorers(league_info["tm_name"], league_info["tm_comp"])
    print(f"{len(players)} players")

    if not players:
        return []

    # Sort by goals
    players.sort(key=lambda x: (-x["goals"], -x["assists"]))

    # Save
    output = {
        "generated": TODAY,
        "source": "transfermarkt.com",
        "league": league_info["name"],
        "season": CURRENT_SEASON,
        "total_players": len(players),
        "players": players,
    }

    path = os.path.join(PLAYERS_DIR, f"player_stats_{league_key}_{CURRENT_SEASON}.json")
    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    # Print top 5
    for p in players[:5]:
        per90 = p.get("per90", {})
        print(f"    {p['team']:22s} | {p['player']:22s} | G={p['goals']:2d} A={p['assists']:2d} "
              f"P={p['penalties']} | {p['min']}min | g/90={per90.get('goals', '-')}")

    return players


def main():
    parser = argparse.ArgumentParser(description="Scrape player stats from Transfermarkt")
    parser.add_argument("--league", type=str, help="Specific league (e.g., laliga)")
    args = parser.parse_args()

    print(f"Player Stats Scraper — {TODAY}")
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
            time.sleep(3)

    print(f"\n{'='*50}")
    print(f"COMPLETE — {total_players} players across {len(leagues_to_scrape)} leagues")


if __name__ == "__main__":
    main()
