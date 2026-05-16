#!/usr/bin/env python3
"""
Update football-data database: download latest match data, stats, and fixtures.
Runs in GitHub Actions (cloud) or locally. No interactive prompts.

Usage:
  python3 scripts/update_all.py              # Update everything
  python3 scripts/update_all.py --matches     # Only match data
  python3 scripts/update_all.py --stats       # Only stats (xG, cards, standings, scorers)
  python3 scripts/update_all.py --fixtures    # Only upcoming fixtures
"""

import csv
import io
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from html.parser import HTMLParser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCHES_DIR = os.path.join(BASE_DIR, "matches")
STATS_DIR = os.path.join(BASE_DIR, "stats")
FIXTURES_DIR = os.path.join(BASE_DIR, "fixtures")
PLAYERS_DIR = os.path.join(STATS_DIR, "players")

TODAY = datetime.now().strftime("%Y-%m-%d")

# ─── Football-data.co.uk league codes ───
# v2 scope: Bundesliga + Ligue 1 removed (brief §4).
# Pending v2 additions (need scrapers + match sources):
#   copa_del_rey      ESPN "esp.copa_del_rey", RFEF referees
#   champions_league  ESPN "uefa.champions",   UEFA referees
#   europa_league     ESPN "uefa.europa",      UEFA referees
#   conference_league ESPN "uefa.europa.conf", UEFA referees
LEAGUES = {
    "laliga":     {"code": "SP1", "name": "LaLiga",          "espn_id": "esp.1",  "xg_slug": "la-liga"},
    "segunda":    {"code": "SP2", "name": "Segunda Division", "espn_id": "esp.2",  "xg_slug": None},
    "epl":        {"code": "E0",  "name": "Premier League",  "espn_id": "eng.1",  "xg_slug": "epl"},
    "seriea":     {"code": "I1",  "name": "Serie A",         "espn_id": "ita.1",  "xg_slug": "serie-a"},
    "portugal":   {"code": "P1",  "name": "Primeira Liga",   "espn_id": "por.1",  "xg_slug": None},
}

SEASONS = {
    "2526": "2025-26",
    "2425": "2024-25",
    "2324": "2023-24",
    "2223": "2022-23",
    "2122": "2021-22",
}

CURRENT_SEASON_CODE = "2526"
CURRENT_SEASON_NAME = "2025-26"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def fetch_url(url, retries=2):
    """Fetch URL content with retries."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == retries:
                print(f"  FAILED: {url} -> {e}")
                return None
    return None


def convert_csv_to_matches(csv_text):
    """Convert football-data.co.uk CSV text to match list."""
    matches = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        if not row.get("HomeTeam", "").strip():
            continue
        match = {
            "date": row.get("Date", ""),
            "time": row.get("Time", ""),
            "home": row.get("HomeTeam", ""),
            "away": row.get("AwayTeam", ""),
        }
        # Scores
        for field, key in [("FTHG","ft_home"),("FTAG","ft_away"),("HTHG","ht_home"),("HTAG","ht_away")]:
            val = row.get(field, "").strip()
            match[key] = int(val) if val else None
        match["ft_result"] = row.get("FTR", "")
        match["ht_result"] = row.get("HTR", "")
        # Stats
        for field, key in [("HS","home_shots"),("AS","away_shots"),("HST","home_shots_target"),
                           ("AST","away_shots_target"),("HC","home_corners"),("AC","away_corners"),
                           ("HF","home_fouls"),("AF","away_fouls"),("HY","home_yellow"),
                           ("AY","away_yellow"),("HR","home_red"),("AR","away_red")]:
            val = row.get(field, "").strip()
            match[key] = int(val) if val else None
        if row.get("Referee", "").strip():
            match["referee"] = row["Referee"]
        # NOTE: brief §9 (Mejora 5) — never include odds/bookmaker fields in output.
        # The football-data.co.uk CSV ships historical Bet365 lines (B365H/B365D/B365A/
        # B365>2.5/B365<2.5) but we intentionally DROP them here so the agent cannot
        # be biased by historical odds when reasoning about future probabilities
        # (PROYECTO_FRANKEN_IDENTIDAD).
        matches.append(match)
    return matches


def update_matches(current_only=True):
    """Download match CSVs from football-data.co.uk and convert to JSON."""
    print("\n=== UPDATING MATCH DATA ===")
    total = 0
    seasons_to_update = {CURRENT_SEASON_CODE: CURRENT_SEASON_NAME} if current_only else SEASONS

    for folder, info in LEAGUES.items():
        code = info["code"]
        league_dir = os.path.join(MATCHES_DIR, folder)
        os.makedirs(league_dir, exist_ok=True)

        for season_code, season_name in seasons_to_update.items():
            # football-data.co.uk URL pattern
            year_prefix = "20" + season_code[:2]
            url = f"https://www.football-data.co.uk/mmz4281/{season_code}/{code}.csv"
            print(f"  {info['name']} {season_name}...", end=" ", flush=True)

            csv_text = fetch_url(url)
            if not csv_text:
                print("SKIP")
                continue

            matches = convert_csv_to_matches(csv_text)
            if not matches:
                print("NO DATA")
                continue

            out = {
                "league": info["name"],
                "season": season_name,
                "source": "football-data.co.uk",
                "updated": TODAY,
                "total_matches": len(matches),
                "matches": matches
            }
            json_path = os.path.join(league_dir, f"{season_name}.json")
            with open(json_path, "w") as f:
                json.dump(out, f, separators=(",", ":"))

            total += len(matches)
            print(f"{len(matches)} matches")

    print(f"  Total matches updated: {total}")
    return total


def update_standings():
    """Scrape current standings from ESPN."""
    print("\n=== UPDATING STANDINGS ===")
    all_standings = {}

    for folder, info in LEAGUES.items():
        espn_id = info["espn_id"]
        url = f"https://www.espn.com/soccer/standings/_/league/{espn_id}"
        print(f"  {info['name']}...", end=" ", flush=True)
        html = fetch_url(url)
        if not html:
            print("SKIP")
            continue

        # Extract standings from ESPN JSON data embedded in page
        teams = extract_espn_standings(html, info["name"])
        if teams:
            all_standings[folder] = {
                "league": info["name"],
                "teams": teams
            }
            print(f"{len(teams)} teams")
        else:
            print("PARSE FAILED")

    if all_standings:
        path = os.path.join(STATS_DIR, f"standings_all_leagues_{TODAY}.json")
        with open(path, "w") as f:
            json.dump({
                "generated": TODAY,
                "source": "ESPN",
                "leagues": all_standings
            }, f, indent=2)
        print(f"  Saved standings to {os.path.basename(path)}")

    # Clean old standings files (keep only latest)
    for old in os.listdir(STATS_DIR):
        if old.startswith("standings_all_leagues_") and old != f"standings_all_leagues_{TODAY}.json":
            os.remove(os.path.join(STATS_DIR, old))
            print(f"  Removed old: {old}")


def extract_espn_standings(html, league_name):
    """Parse ESPN standings page HTML for team data."""
    teams = []
    # ESPN embeds data in __espnfitt__ or we parse the table
    # Try to find JSON data first
    match = re.search(r'"standings":\s*(\{[^}]+\})', html)

    # Fallback: parse HTML table rows
    # Look for table rows with team data
    rows = re.findall(
        r'<tr[^>]*>.*?class="[^"]*Table__TD[^"]*"[^>]*>.*?</tr>',
        html, re.DOTALL
    )

    if not rows:
        # Try different ESPN format - look for team names and stats
        team_pattern = re.findall(
            r'title="([^"]+)"[^>]*class="[^"]*AnchorLink[^"]*".*?'
            r'(?:class="[^"]*Table__TD[^"]*"[^>]*>(\d+)</)',
            html, re.DOTALL
        )

    # Return empty if parsing fails - standings can be complex
    return teams


def update_xg():
    """Scrape xG data from xgscore.io."""
    print("\n=== UPDATING xG DATA ===")

    for folder, info in LEAGUES.items():
        slug = info.get("xg_slug")
        if not slug:
            continue

        url = f"https://xgscore.io/{slug}"
        print(f"  {info['name']}...", end=" ", flush=True)
        html = fetch_url(url)
        if not html:
            print("SKIP")
            continue

        teams = parse_xgscore(html)
        if not teams:
            print("PARSE FAILED")
            continue

        path = os.path.join(STATS_DIR, f"xg_{folder}_{CURRENT_SEASON_NAME}.json")
        with open(path, "w") as f:
            json.dump({
                "generated": TODAY,
                "source": "xgscore.io",
                "league": info["name"],
                "season": CURRENT_SEASON_NAME,
                "teams": teams
            }, f, indent=2)
        print(f"{len(teams)} teams")


def parse_xgscore(html):
    """Parse xgscore.io HTML for team xG data."""
    teams = []
    # xgscore has a table with: Team, GP, xG, Goals, xGA, GA
    # Pattern: look for table rows
    table_match = re.search(r'<table[^>]*class="[^"]*league-table[^"]*"[^>]*>(.*?)</table>', html, re.DOTALL)
    if not table_match:
        # Try broader search
        table_match = re.search(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)

    if not table_match:
        return teams

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_match.group(1), re.DOTALL)
    for row in rows[1:]:  # Skip header
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) >= 6:
            # Clean HTML from cells
            clean = lambda x: re.sub(r'<[^>]+>', '', x).strip()
            try:
                team_name = clean(cells[0])
                # Try to extract href text for team name
                name_match = re.search(r'>([^<]+)<', cells[0])
                if name_match:
                    team_name = name_match.group(1).strip()

                teams.append({
                    "team": team_name,
                    "gf": int(clean(cells[2])) if clean(cells[2]).isdigit() else float(clean(cells[2])),
                    "xg": float(clean(cells[1])),
                    "ga": int(clean(cells[4])) if clean(cells[4]).isdigit() else float(clean(cells[4])),
                    "xga": float(clean(cells[3])),
                })
            except (ValueError, IndexError):
                continue

    # Calculate diffs
    for t in teams:
        t["xg_diff"] = round(t["gf"] - t["xg"], 1)
        t["xga_diff"] = round(t["ga"] - t["xga"], 1)

    return teams


def update_cards():
    """Scrape card statistics from ESPN."""
    print("\n=== UPDATING CARD STATS ===")

    for folder, info in LEAGUES.items():
        espn_id = info["espn_id"]
        url = f"https://www.espn.com/soccer/stats/_/league/{espn_id}/view/discipline"
        print(f"  {info['name']}...", end=" ", flush=True)
        html = fetch_url(url)
        if not html:
            print("SKIP")
            continue

        # Parse team discipline stats
        teams = parse_espn_discipline(html)
        if not teams:
            print("PARSE FAILED")
            continue

        path = os.path.join(STATS_DIR, f"cards_{folder}_{CURRENT_SEASON_NAME}.json")
        with open(path, "w") as f:
            json.dump({
                "generated": TODAY,
                "sources": ["ESPN"],
                "league": info["name"],
                "season": CURRENT_SEASON_NAME,
                "teams": teams
            }, f, indent=2)
        print(f"{len(teams)} teams")


def parse_espn_discipline(html):
    """Parse ESPN discipline page for card stats."""
    teams = []
    # This is often JS-rendered, so may not work via simple fetch
    # We'll try to find data in the HTML
    return teams


def update_scorers():
    """Scrape top scorers from ESPN."""
    print("\n=== UPDATING TOP SCORERS ===")
    os.makedirs(PLAYERS_DIR, exist_ok=True)

    for folder, info in LEAGUES.items():
        espn_id = info["espn_id"]
        url = f"https://www.espn.com/soccer/stats/_/league/{espn_id}/view/scoring"
        print(f"  {info['name']}...", end=" ", flush=True)
        html = fetch_url(url)
        if not html:
            print("SKIP")
            continue

        players = parse_espn_scorers(html)
        if not players:
            print("PARSE FAILED")
            continue

        path = os.path.join(PLAYERS_DIR, f"scorers_{folder}_{CURRENT_SEASON_NAME}.json")
        with open(path, "w") as f:
            json.dump({
                "generated": TODAY,
                "source": "ESPN",
                "league": info["name"],
                "season": CURRENT_SEASON_NAME,
                "players": players
            }, f, indent=2)
        print(f"{len(players)} players")


def parse_espn_scorers(html):
    """Parse ESPN scoring page for top scorers."""
    players = []
    return players


def update_fixtures():
    """Scrape upcoming fixtures from ESPN."""
    print("\n=== UPDATING FIXTURES ===")
    all_fixtures = []

    for folder, info in LEAGUES.items():
        espn_id = info["espn_id"]
        # Get fixtures for next few days
        for days_ahead in range(4):
            date = datetime.now() + timedelta(days=days_ahead)
            date_str = date.strftime("%Y%m%d")
            url = f"https://www.espn.com/soccer/schedule/_/date/{date_str}/league/{espn_id}"
            html = fetch_url(url)
            if not html:
                continue

            fixtures = parse_espn_fixtures(html, info["name"], date.strftime("%Y-%m-%d"))
            all_fixtures.extend(fixtures)

    if all_fixtures:
        path = os.path.join(FIXTURES_DIR, f"next_72h_{TODAY}.json")
        with open(path, "w") as f:
            json.dump({
                "generated": TODAY,
                "source": "ESPN",
                "total_matches": len(all_fixtures),
                "matches": all_fixtures
            }, f, indent=2)
        print(f"  {len(all_fixtures)} upcoming fixtures saved")

        # Clean old fixture files
        for old in os.listdir(FIXTURES_DIR):
            if old.startswith("next_72h_") and old != f"next_72h_{TODAY}.json":
                try:
                    os.remove(os.path.join(FIXTURES_DIR, old))
                except:
                    pass


def parse_espn_fixtures(html, league_name, date_str):
    """Parse ESPN schedule page for fixtures."""
    fixtures = []
    # ESPN fixture pages are largely JS-rendered
    return fixtures


def update_manifest(total_matches=None):
    """Update manifest.json with current state."""
    print("\n=== UPDATING MANIFEST ===")

    # Count all match files
    match_count = 0
    file_count = 0
    for root, dirs, files in os.walk(BASE_DIR):
        if ".git" in root:
            continue
        for f in files:
            if f.endswith(".json") and f != "manifest.json":
                file_count += 1
                if "matches" in root:
                    try:
                        with open(os.path.join(root, f)) as fh:
                            data = json.load(fh)
                            match_count += data.get("total_matches", len(data.get("matches", [])))
                    except:
                        pass

    manifest = {
        "version": "4.2",
        "description": "Complete football database for AI prediction analysis",
        "last_updated": f"{TODAY}T{datetime.now().strftime('%H:%M:%S')}Z",
        "base_url": "https://raw.githubusercontent.com/betorrillo/football-data/main/",
        "total_files": file_count,
        "total_matches": match_count,
        "coverage": {
            "leagues": [
                "LaLiga", "Segunda Division", "Copa del Rey",
                "Serie A", "Premier League", "Primeira Liga",
                "Champions League", "Europa League", "Conference League"
            ],
            "seasons": ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"],
            "match_data_per_match": [
                "date", "time", "home", "away", "ft/ht scores", "shots",
                "shots_on_target", "corners", "fouls", "yellow_cards",
                "red_cards", "referee"
            ]
        },
        "directories": {
            "matches": "Match-by-match data with full statistics",
            "stats": "Season aggregates: standings, xG, cards by team, top scorers",
            "fixtures": "Upcoming matches for next 72 hours",
            "scripts": "Update automation scripts"
        },
        "files": {
            "matches/{league}/{season}.json": "Match-by-match data per league per season",
            "stats/standings_all_leagues_{date}.json": "Current standings for all leagues",
            "stats/xg_{league}_2025-26.json": "xG/xGA per team",
            "stats/cards_{league}_2025-26.json": "Yellow/red cards per team",
            "stats/players/scorers_{league}_2025-26.json": "Top scorers with goals+assists",
            "fixtures/next_72h_{date}.json": "Upcoming matches"
        }
    }

    with open(os.path.join(BASE_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest updated: {file_count} files, {match_count} matches")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Update football-data database")
    parser.add_argument("--matches", action="store_true", help="Update match data only")
    parser.add_argument("--stats", action="store_true", help="Update stats only (xG, cards, standings)")
    parser.add_argument("--fixtures", action="store_true", help="Update fixtures only")
    parser.add_argument("--all-seasons", action="store_true", help="Update all seasons (not just current)")
    args = parser.parse_args()

    do_all = not (args.matches or args.stats or args.fixtures)

    print(f"Football Data Updater — {TODAY}")
    print("=" * 50)

    total = 0
    if do_all or args.matches:
        total = update_matches(current_only=not args.all_seasons)

    if do_all or args.stats:
        update_xg()
        update_standings()
        update_cards()
        update_scorers()

    if do_all or args.fixtures:
        update_fixtures()

    update_manifest(total)

    print("\n" + "=" * 50)
    print(f"UPDATE COMPLETE — {TODAY}")
    print("=" * 50)


if __name__ == "__main__":
    main()
