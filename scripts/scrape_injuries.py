#!/usr/bin/env python3
"""
Scrape current injuries from Transfermarkt verletztespieler pages.
Saves to injuries/{league}_{date}.json

Usage:
  python3 scripts/scrape_injuries.py
"""

import json
import os
import re
import urllib.request
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INJURIES_DIR = os.path.join(BASE_DIR, "injuries")
TODAY = datetime.now().strftime("%Y-%m-%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

LEAGUES = {
    "laliga":     {"tm_comp": "ES1", "name": "LaLiga"},
    "segunda":    {"tm_comp": "ES2", "name": "Segunda Division"},
    "epl":        {"tm_comp": "GB1", "name": "Premier League"},
    "bundesliga": {"tm_comp": "L1",  "name": "Bundesliga"},
    "seriea":     {"tm_comp": "IT1", "name": "Serie A"},
    "ligue1":     {"tm_comp": "FR1", "name": "Ligue 1"},
    "portugal":   {"tm_comp": "PO1", "name": "Primeira Liga"},
}


def fetch_url(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  FAILED: {url} -> {e}")
        return None


def parse_injuries(html):
    """Parse Transfermarkt verletztespieler page."""
    # Find row boundaries
    starts = [m.start() for m in re.finditer(r'<tr[^>]*class="[^"]*(?:odd|even)[^"]*"', html)]
    starts.append(len(html))

    players = []
    for i in range(len(starts) - 1):
        block = html[starts[i]:starts[i + 1]]

        # Player name from hauptlink
        name_match = re.search(r'class="[^"]*hauptlink[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>', block)
        name = name_match.group(1).strip() if name_match else ""
        if not name:
            continue

        # Team from title attribute of team link
        team_titles = re.findall(r'title="([^"]+)"', block)
        # Team name is usually the 2nd unique title (after player name)
        team = ""
        for t in team_titles:
            if t != name and len(t) > 2 and not any(c in t.lower() for c in ["profil", "spieler"]):
                # Skip country names (short, single word without spaces often)
                # Team names usually have FC, CF, Real, etc.
                team = t
                break

        # Position
        positions = ["Goalkeeper", "Centre-Back", "Left-Back", "Right-Back",
                     "Defensive Midfield", "Central Midfield", "Attacking Midfield",
                     "Right Winger", "Left Winger", "Centre-Forward", "Second Striker",
                     "Right Midfield", "Left Midfield"]
        position = ""
        for pos in positions:
            if pos in block:
                position = pos
                break

        # Injury type
        injury_keywords = [
            "Knee", "Muscle", "Ankle", "Torn", "Cruciate", "Hamstring", "Thigh",
            "Calf", "Back", "Groin", "Shoulder", "Foot", "Hip", "Concussion",
            "Strain", "Fracture", "Surgery", "Illness", "Unknown", "Metatarsal",
            "Achilles", "Meniscus", "Suspended", "Yellow card", "Red card",
            "Shin", "Abdominal", "Rib", "Neck", "Wrist", "Elbow", "Quad",
            "Adductor", "Ligament", "Cartilage", "Bruise", "Knock",
        ]
        injury = "Unknown"
        for kw in injury_keywords:
            pattern = rf'<td[^>]*>\s*({re.escape(kw)}[^<]*)</td>'
            match = re.search(pattern, block, re.IGNORECASE)
            if match:
                injury = match.group(1).strip()
                break

        # Since date
        date_match = re.search(r'(\w{3} \d{1,2}, \d{4})', block)
        since = date_match.group(1) if date_match else ""

        players.append({
            "player": name,
            "team": team,
            "position": position,
            "injury": injury,
            "since": since,
            "status": "out",
        })

    return players


def scrape_league(league_key, league_info):
    """Scrape injuries for one league."""
    comp = league_info["tm_comp"]
    url = f"https://www.transfermarkt.com/{league_key}/verletztespieler/wettbewerb/{comp}/plus/1"
    html = fetch_url(url)
    if not html:
        return []
    return parse_injuries(html)


def group_by_team(players):
    """Group injury list by team."""
    teams = {}
    for p in players:
        team = p.get("team", "Unknown")
        if team not in teams:
            teams[team] = []
        teams[team].append({k: v for k, v in p.items() if k != "team"})
    return teams


def main():
    print(f"Injury Scraper — {TODAY}")
    print("=" * 50)
    os.makedirs(INJURIES_DIR, exist_ok=True)

    total_injured = 0

    all_leagues_data = {}

    for league_key, league_info in LEAGUES.items():
        print(f"\n{league_info['name']}...", end=" ", flush=True)
        try:
            players = scrape_league(league_key, league_info)
        except Exception as e:
            print(f"ERROR: {e}")
            continue
        by_team = group_by_team(players)

        league_output = {
            "generated": TODAY,
            "source": "transfermarkt.com",
            "league": league_info["name"],
            "total_injured": len(players),
            "teams_affected": len(by_team),
            "teams": by_team,
        }

        path = os.path.join(INJURIES_DIR, f"{league_key}_{TODAY}.json")
        with open(path, "w") as f:
            json.dump(league_output, f, indent=2)

        all_leagues_data[league_key] = league_output
        total_injured += len(players)
        print(f"{len(players)} injured across {len(by_team)} teams")

        # Print notable injuries
        for p in players[:5]:
            print(f"    {p['team']:25s} | {p['player']:25s} | {p['position']:20s} | {p['injury']}")
        if len(players) > 5:
            print(f"    ... and {len(players)-5} more")

    # Build consolidated all_injuries file for Drive
    consolidated = {
        "generated": TODAY,
        "source": "transfermarkt.com",
        "total_injured": total_injured,
        "leagues_scraped": len(all_leagues_data),
        "leagues": all_leagues_data,
    }
    all_path = os.path.join(INJURIES_DIR, f"all_injuries_{TODAY}.json")
    with open(all_path, "w") as f:
        json.dump(consolidated, f, indent=2)
    print(f"\nConsolidated: {all_path}")

    # Clean old files
    for league_key in LEAGUES:
        files = sorted([f for f in os.listdir(INJURIES_DIR)
                       if f.startswith(f"{league_key}_") and f.endswith(".json")])
        for old in files[:-1]:
            os.remove(os.path.join(INJURIES_DIR, old))
    # Clean old consolidated files
    all_files = sorted([f for f in os.listdir(INJURIES_DIR)
                       if f.startswith("all_injuries_") and f.endswith(".json")])
    for old in all_files[:-1]:
        os.remove(os.path.join(INJURIES_DIR, old))

    print(f"\n{'='*50}")
    print(f"COMPLETE — {total_injured} injuries total across {len(all_leagues_data)} leagues")


if __name__ == "__main__":
    main()
