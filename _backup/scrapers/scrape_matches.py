#!/usr/bin/env python3
"""
Auto-discover today's matches from bet365 competition listing pages.

Usage:
  python3 scrape_matches.py --all              # All 10 competitions
  python3 scrape_matches.py --domestic          # National leagues only
  python3 scrape_matches.py --european          # UEFA competitions only
  python3 scrape_matches.py --league bundesliga # Specific league
  python3 scrape_matches.py --tomorrow          # Tomorrow's matches
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

import requests
from cdp_client import CDPClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MATCHES_DIR = os.path.join(BASE_DIR, 'matches')
CDP_PORT = 9222

COMPETITIONS = {
    # España
    'laliga':            {'name': 'LaLiga',              'country': 'spain',   'prefix': 'la-liga',                    'url': 'https://www.bet365.com/#/AC/B1/C1/D1002/E120757998/G40/', 'group': 'domestic'},
    'segunda':           {'name': 'LaLiga Hypermotion',  'country': 'spain',   'prefix': 'laliga-hypermotion',         'url': 'https://www.bet365.com/#/AC/B1/C1/D1002/E120794896/G40/', 'group': 'domestic'},
    # Big 4
    'bundesliga':        {'name': 'Bundesliga',          'country': 'germany', 'prefix': 'alemania--bundesliga-i',     'url': 'https://www.bet365.com/#/AC/B1/C1/D1002/E120439499/G40/', 'group': 'domestic'},
    'serie-a':           {'name': 'Serie A',             'country': 'italy',   'prefix': 'italia--serie-a',            'url': 'https://www.bet365.com/#/AC/B1/C1/D1002/E92269709/G40/',  'group': 'domestic'},
    'premier-league':    {'name': 'Premier League',      'country': 'england', 'prefix': 'inglaterra--premier-league', 'url': 'https://www.bet365.com/#/AC/B1/C1/D1002/E91422157/G40/',  'group': 'domestic'},
    'ligue-1':           {'name': 'Ligue 1',             'country': 'france',  'prefix': 'france-ligue-1',            'url': 'https://www.bet365.com/#/AC/B1/C1/D1002/E120498572/G40/', 'group': 'domestic'},
    # UEFA
    'champions':         {'name': 'Champions League',    'country': 'europe',  'prefix': 'champions-league',           'url': 'https://www.bet365.com/#/AC/B1/C1/D1002/E94400598/G40/',  'group': 'european'},
    'europa-league':     {'name': 'Europa League',       'country': 'europe',  'prefix': 'europa-league',             'url': 'https://www.bet365.com/#/AC/B1/C1/D1002/E123393868/G40/', 'group': 'european'},
    'conference-league': {'name': 'Conference League',   'country': 'europe',  'prefix': 'conference-league',          'url': 'https://www.bet365.com/#/AC/B1/C1/D1002/E128898427/G40/', 'group': 'european'},
}

JS_EXTRACT_MATCHES = r"""
(() => {
    const matches = [];
    const seen = new Set();

    // Strategy 1: Find match containers with participant details
    document.querySelectorAll('[class*="rcl-ParticipantFixtureDetails"]').forEach(el => {
        const teamEls = el.querySelectorAll('[class*="rcl-ParticipantFixtureDetailsTeam_TeamNa"]');
        const timeEl = el.querySelector('[class*="rcl-ParticipantFixtureDetails_TimeAndSco"]');

        if (teamEls.length >= 2) {
            const home = teamEls[0].textContent.trim();
            const away = teamEls[1].textContent.trim();
            const time = timeEl ? timeEl.textContent.trim() : '';
            const key = home + away;

            if (!seen.has(key) && home && away) {
                seen.add(key);
                matches.push({ home, away, time, match: home + ' vs ' + away });
            }
        }
    });

    // Strategy 2: Broader search
    if (matches.length === 0) {
        const teams = [];
        document.querySelectorAll('[class*="Participant"] [class*="Name"], [class*="Team"]').forEach(el => {
            const text = el.textContent.trim();
            if (text && text.length > 2 && text.length < 40 && !teams.includes(text)) {
                teams.push(text);
            }
        });
        for (let i = 0; i < teams.length - 1; i += 2) {
            const key = teams[i] + teams[i+1];
            if (!seen.has(key)) {
                seen.add(key);
                matches.push({ home: teams[i], away: teams[i+1], time: '', match: teams[i] + ' vs ' + teams[i+1] });
            }
        }
    }

    return JSON.stringify({
        matches,
        url: window.location.href,
        total: matches.length,
    });
})()
"""

JS_CLICK_MATCH_AND_GET_URL = """
((homeTeam, awayTeam) => {
    const els = document.querySelectorAll('[class*="rcl-ParticipantFixtureDetails"]');
    for (const el of els) {
        const text = el.textContent;
        if (text.includes(homeTeam) && text.includes(awayTeam)) {
            el.click();
            return 'clicked';
        }
    }
    for (const el of document.querySelectorAll('[class*="Participant"]')) {
        if (el.textContent.includes(homeTeam)) {
            el.click();
            return 'clicked_fallback';
        }
    }
    return 'not_found';
})
"""


def discover_matches(competition, target_date=None):
    """Open bet365 competition listing and extract all matches."""
    comp = COMPETITIONS.get(competition)
    if not comp:
        print(f"  Unknown competition: {competition}")
        return []

    if target_date is None:
        target_date = datetime.now().strftime('%Y-%m-%d')

    print(f"\n  [{comp['name']}] Discovering matches...")

    # Create new tab
    try:
        resp = requests.put(f'http://localhost:{CDP_PORT}/json/new?https://www.bet365.com/', timeout=10)
        tab = resp.json()
    except Exception as e:
        print(f"  ERROR: Chrome not available: {e}")
        return []

    time.sleep(4)
    cdp = CDPClient(tab['webSocketDebuggerUrl'])
    if not cdp.connect():
        print(f"  ERROR: CDP connection failed")
        return []

    try:
        # Navigate to competition listing
        hash_part = comp['url'].split('#')[1]
        cdp.evaluate(f'window.location.hash = "#{hash_part}"')
        time.sleep(6)

        # Extract matches
        raw = cdp.evaluate(JS_EXTRACT_MATCHES)
        data = json.loads(raw) if raw else {'matches': []}
        matches = data.get('matches', [])

        print(f"  Found {len(matches)} matches on listing page")

        if not matches:
            cdp.evaluate('window.scrollBy(0, 500)')
            time.sleep(2)
            raw = cdp.evaluate(JS_EXTRACT_MATCHES)
            data = json.loads(raw) if raw else {'matches': []}
            matches = data.get('matches', [])
            print(f"  After scroll: {len(matches)} matches")

        # Click each match to get URL
        enriched = []
        for match in matches:
            home = match['home']
            away = match['away']

            cdp.evaluate(f'({JS_CLICK_MATCH_AND_GET_URL})("{home}", "{away}")')
            time.sleep(2)

            match_url = cdp.evaluate('window.location.href') or ''
            match_hash = match_url.split('#')[1] if '#' in match_url else ''

            if match_hash and '/E' in match_hash:
                scrape_url = f"https://www.bet365.com/#{match_hash}"
                if '/I' not in match_hash:
                    scrape_url += '/I99/'

                enriched.append({
                    **match,
                    'url': scrape_url,
                    'competition': comp['name'],
                    'country': comp['country'],
                    'prefix': comp['prefix'],
                    'date': target_date,
                })
                print(f"    {home} vs {away} ({match.get('time','')}) -> {match_hash[:50]}")

            cdp.evaluate('window.history.back()')
            time.sleep(2)

        return enriched

    finally:
        cdp.disconnect()
        requests.put(f'http://localhost:{CDP_PORT}/json/close/{tab["id"]}', timeout=5)


def save_matches(all_matches, target_date):
    """Save discovered matches to JSON."""
    os.makedirs(MATCHES_DIR, exist_ok=True)

    by_comp = {}
    for m in all_matches:
        comp = m.get('competition', 'unknown')
        by_comp.setdefault(comp, []).append(m)

    saved_files = []
    for comp, matches in by_comp.items():
        comp_slug = comp.lower().replace(' ', '-')
        fname = f"{comp_slug}_{target_date}.json"
        fpath = os.path.join(MATCHES_DIR, fname)

        output = {
            'competition': comp,
            'date': target_date,
            'scraped_at': datetime.now().isoformat(),
            'total_matches': len(matches),
            'matches': matches,
        }

        with open(fpath, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        saved_files.append(fname)
        print(f"  Saved: matches/{fname} ({len(matches)} matches)")

    # Save flat URL list
    urls_file = os.path.join(MATCHES_DIR, 'today_urls.txt')
    with open(urls_file, 'w') as f:
        f.write(f"# Matches for {target_date}\n")
        for m in all_matches:
            if m.get('url'):
                f.write(f"# {m['match']} ({m.get('time','')}) [{m.get('competition','')}]\n")
                f.write(f"{m['url']}\n")

    print(f"  URL list: matches/today_urls.txt ({len(all_matches)} URLs)")
    return saved_files


def get_competitions_for_group(group):
    """Get competition keys by group."""
    if group == 'all':
        return list(COMPETITIONS.keys())
    elif group == 'domestic':
        return [k for k, v in COMPETITIONS.items() if v['group'] == 'domestic']
    elif group == 'european':
        return [k for k, v in COMPETITIONS.items() if v['group'] == 'european']
    else:
        return [group] if group in COMPETITIONS else []


def main():
    parser = argparse.ArgumentParser(description='Discover matches from bet365')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--all', action='store_true', help='All 10 competitions')
    group.add_argument('--domestic', action='store_true', help='National leagues only')
    group.add_argument('--european', action='store_true', help='UEFA competitions only')
    group.add_argument('--league', '-l', choices=list(COMPETITIONS.keys()), help='Specific league')
    parser.add_argument('--tomorrow', action='store_true')
    args = parser.parse_args()

    target_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d') if args.tomorrow else datetime.now().strftime('%Y-%m-%d')

    # Determine which competitions to discover
    if args.all:
        comps = get_competitions_for_group('all')
    elif args.domestic:
        comps = get_competitions_for_group('domestic')
    elif args.european:
        comps = get_competitions_for_group('european')
    elif args.league:
        comps = [args.league]
    else:
        comps = ['laliga', 'segunda']  # default

    print(f"\n{'='*60}")
    print(f"  Match Discovery - {target_date}")
    print(f"  Competitions: {', '.join(comps)}")
    print(f"{'='*60}")

    all_matches = []
    for comp in comps:
        try:
            matches = discover_matches(comp, target_date)
            all_matches.extend(matches)
        except Exception as e:
            print(f"  ERROR in {comp}: {e}")

    if all_matches:
        save_matches(all_matches, target_date)

    print(f"\n{'='*60}")
    print(f"  Total: {len(all_matches)} matches discovered")
    for m in all_matches:
        print(f"    {m['match']:40s} | {m.get('time',''):5s} | {m['competition']}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
