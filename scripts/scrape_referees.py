#!/usr/bin/env python3
"""
Scrape referee statistics from Transfermarkt.
Gets career totals per referee: matches, yellow cards, red cards, penalties.
Calculates per-match averages and verdict (ALTO/MEDIO/BAJO).

Usage:
  python3 scripts/scrape_referees.py
"""

import json
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFEREES_DIR = os.path.join(BASE_DIR, "referees")
TODAY = datetime.now().strftime("%Y-%m-%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

# v2 scope: Bundesliga + Ligue 1 removed.
# Pending v2 additions: europa_league, conference_league (Transfermarkt comp codes
# UEL=EL, UCOL=Conference); copa_del_rey overlaps with LaLiga/Segunda referees.
LEAGUES = {
    "laliga":    {"tm_comp": "ES1", "name": "LaLiga"},
    "segunda":   {"tm_comp": "ES2", "name": "Segunda Division"},
    "epl":       {"tm_comp": "GB1", "name": "Premier League"},
    "seriea":    {"tm_comp": "IT1", "name": "Serie A"},
    "champions": {"tm_comp": "CL",  "name": "Champions League"},
    "portugal":  {"tm_comp": "PO1", "name": "Primeira Liga"},
}


def fetch_url(url, delay=0.5):
    try:
        time.sleep(delay)  # Be polite to Transfermarkt
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  FAILED: {url} -> {e}")
        return None


def get_league_referee_list(comp_id):
    """Get list of referees for a competition from Transfermarkt."""
    url = f"https://www.transfermarkt.com/wettbewerb/schiedsrichter/wettbewerb/{comp_id}/plus/1"
    html = fetch_url(url)
    if not html:
        return []

    # Find referee profile links: /name/profil/schiedsrichter/ID
    refs = re.findall(
        r'href="/([^/]+)/profil/schiedsrichter/(\d+)"[^>]*>([^<]+)<',
        html
    )

    # Deduplicate
    seen = set()
    unique = []
    for slug, ref_id, name in refs:
        if ref_id not in seen:
            seen.add(ref_id)
            unique.append({"slug": slug, "id": ref_id, "name": name.strip()})

    return unique


def get_referee_career_stats(slug, ref_id, name):
    """Get career stats for a referee from their bilanz page."""
    url = f"https://www.transfermarkt.com/{slug}/bilanz/schiedsrichter/{ref_id}/plus/1"
    html = fetch_url(url)
    if not html:
        return None

    # Find the main stats table (table with club rows)
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
    if not tables:
        return None

    # Find the table with match data (has Club, Appearances, W, D, L, YC, etc.)
    stats_table = None
    for t in tables:
        if 'Appearances' in t or 'appearances' in t.lower() or re.search(r'<th.*?title="Yellow cards"', t, re.DOTALL):
            stats_table = t
            break

    if not stats_table:
        # Try the largest table
        stats_table = max(tables, key=len)

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', stats_table, re.DOTALL)

    total_matches = 0
    total_yc_for = 0
    total_yc_opp = 0
    total_2yc_for = 0
    total_2yc_opp = 0
    total_rc_for = 0
    total_rc_opp = 0
    total_pk_for = 0
    total_pk_opp = 0

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        # Expected: ['', 'Club', 'MP', 'W', 'D', 'L', 'YC_for', '2YC_for', 'RC_for', 'PK_for', 'YC_opp', '2YC_opp', 'RC_opp', 'PK_opp']
        if len(clean) >= 13 and clean[2].isdigit():
            total_matches += int(clean[2])
            total_yc_for += int(clean[6]) if clean[6].isdigit() else 0
            total_2yc_for += int(clean[7]) if clean[7].isdigit() else 0
            total_rc_for += int(clean[8]) if clean[8].isdigit() else 0
            total_pk_for += int(clean[9]) if clean[9].isdigit() else 0
            total_yc_opp += int(clean[10]) if clean[10].isdigit() else 0
            total_2yc_opp += int(clean[11]) if clean[11].isdigit() else 0
            total_rc_opp += int(clean[12]) if clean[12].isdigit() else 0
            if len(clean) > 13:
                total_pk_opp += int(clean[13]) if clean[13].isdigit() else 0

    if total_matches == 0:
        return None

    total_yc = total_yc_for + total_yc_opp
    total_rc = total_rc_for + total_rc_opp + total_2yc_for + total_2yc_opp
    total_pk = total_pk_for + total_pk_opp

    yc_pm = round(total_yc / total_matches, 2)
    rc_pm = round(total_rc / total_matches, 2)
    pk_pm = round(total_pk / total_matches, 2)

    # Verdict based on total cards (YC + 2YC + RC) per match
    total_cards_pm = round((total_yc + total_2yc_for + total_2yc_opp + total_rc_for + total_rc_opp) / total_matches, 2)

    if total_cards_pm >= 5.0:
        verdict = "MUY ALTO"
    elif total_cards_pm >= 4.5:
        verdict = "ALTO"
    elif total_cards_pm >= 3.5:
        verdict = "MEDIO"
    else:
        verdict = "BAJO"

    return {
        "name": name,
        "transfermarkt_id": ref_id,
        "career_matches": total_matches,
        "career_yc": total_yc,
        "career_yc_per_match": yc_pm,
        "career_rc": total_rc,
        "career_rc_per_match": rc_pm,
        "career_pk": total_pk,
        "career_pk_per_match": pk_pm,
        "career_total_cards_per_match": total_cards_pm,
        "verdict": verdict,
    }


def process_league(league_key, league_info):
    """Process a single league — fetch referee list and stats. Thread-safe."""
    print(f"\n{league_info['name']}...")
    ref_list = get_league_referee_list(league_info["tm_comp"])
    print(f"  [{league_key}] Found {len(ref_list)} referees, fetching stats...")

    refs_with_stats = []
    for ref in ref_list:
        stats = get_referee_career_stats(ref["slug"], ref["id"], ref["name"])
        if stats:
            refs_with_stats.append(stats)
            v = stats["verdict"]
            print(f"    [{league_key}] {stats['name']}: {stats['career_matches']}mp, {stats['career_yc_per_match']} YC/m → {v}")

    # Sort by cards per match descending
    refs_with_stats.sort(key=lambda x: -x["career_total_cards_per_match"])

    output = {
        "generated": TODAY,
        "source": "transfermarkt.com",
        "league": league_info["name"],
        "referees": refs_with_stats,
        "total": len(refs_with_stats),
    }

    path = os.path.join(REFEREES_DIR, f"stats_{league_key}_{TODAY}.json")
    with open(path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  [{league_key}] {len(refs_with_stats)} referees saved")

    return league_key, refs_with_stats


def main():
    print(f"Referee Scraper — {TODAY}")
    print("=" * 50)
    os.makedirs(REFEREES_DIR, exist_ok=True)

    all_referees = {}

    # Process 2 leagues in parallel (conservative to avoid Transfermarkt blocks)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(process_league, key, info): key
            for key, info in LEAGUES.items()
        }
        for future in as_completed(futures):
            try:
                league_key, refs = future.result()
                all_referees[league_key] = refs
            except Exception as e:
                league_key = futures[future]
                print(f"  ERROR processing {league_key}: {e}")
                all_referees[league_key] = []

    # Combined file
    combined = {
        "generated": TODAY,
        "source": "transfermarkt.com",
        "leagues": {},
        "grand_total": 0,
    }
    for k, v in all_referees.items():
        combined["leagues"][k] = {"referees": v, "total": len(v)}
        combined["grand_total"] += len(v)

    with open(os.path.join(REFEREES_DIR, f"all_referees_{TODAY}.json"), "w") as f:
        json.dump(combined, f, indent=2)

    # Clean old files
    for league_key in list(LEAGUES.keys()) + ["all_referees"]:
        prefix = f"stats_{league_key}_" if league_key != "all_referees" else f"{league_key}_"
        files = sorted([f for f in os.listdir(REFEREES_DIR) if f.startswith(prefix) and f.endswith(".json")])
        for old in files[:-1]:
            os.remove(os.path.join(REFEREES_DIR, old))

    print(f"\n{'='*50}")
    print(f"COMPLETE — {combined['grand_total']} referees across {len(all_referees)} leagues")


if __name__ == "__main__":
    main()
