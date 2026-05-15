#!/usr/bin/env python3
"""
International referee stats scraper - fetches card statistics from transfermarkt
for all major European leagues.

Usage:
  python3 scrape_referees_international.py --all
  python3 scrape_referees_international.py --league bundesliga
  python3 scrape_referees_international.py --lookup "Felix Zwayer"
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from random import uniform

import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFEREES_DIR = os.path.join(BASE_DIR, 'referees')
CACHE_FILE = os.path.join(REFEREES_DIR, 'referee_stats_cache.json')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

LEAGUES = {
    # Domestic leagues (transfermarkt.es for Spanish, .com for others)
    'laliga':         {'name': 'LaLiga',             'country': 'Spain',   'tm_url': 'https://www.transfermarkt.es/laliga/schiedsrichter/wettbewerb/ES1/saison_id/2025'},
    'segunda':        {'name': 'LaLiga Hypermotion', 'country': 'Spain',   'tm_url': 'https://www.transfermarkt.es/laliga2/schiedsrichter/wettbewerb/ES2/saison_id/2025'},
    'bundesliga':     {'name': 'Bundesliga',         'country': 'Germany', 'tm_url': 'https://www.transfermarkt.com/bundesliga/schiedsrichter/wettbewerb/L1/saison_id/2025'},
    'serie-a':        {'name': 'Serie A',            'country': 'Italy',   'tm_url': 'https://www.transfermarkt.com/serie-a/schiedsrichter/wettbewerb/IT1/saison_id/2025'},
    'premier-league': {'name': 'Premier League',     'country': 'England', 'tm_url': 'https://www.transfermarkt.com/premier-league/schiedsrichter/wettbewerb/GB1/saison_id/2025'},
    'ligue-1':        {'name': 'Ligue 1',            'country': 'France',  'tm_url': 'https://www.transfermarkt.com/ligue-1/schiedsrichter/wettbewerb/FR1/saison_id/2025'},
    # European competitions
    'champions':         {'name': 'Champions League',    'country': 'Europe', 'tm_url': 'https://www.transfermarkt.com/uefa-champions-league/schiedsrichter/pokalwettbewerb/CL/saison_id/2025'},
    'europa-league':     {'name': 'Europa League',       'country': 'Europe', 'tm_url': 'https://www.transfermarkt.com/europa-league/schiedsrichter/pokalwettbewerb/EL/saison_id/2025'},
    'conference-league': {'name': 'Conference League',   'country': 'Europe', 'tm_url': 'https://www.transfermarkt.com/europa-conference-league/schiedsrichter/pokalwettbewerb/ECLQ/saison_id/2025'},
}

DOMESTIC_LEAGUES = ['laliga', 'segunda', 'bundesliga', 'serie-a', 'premier-league', 'ligue-1']
EUROPEAN_LEAGUES = ['champions', 'europa-league', 'conference-league']


def get_verdict(yc_per_match):
    """Calculate verdict based on yellow cards per match."""
    if yc_per_match >= 4.5:
        return "ALTO — pick de tarjetas viable (≥ 4.5 TA/p)"
    elif yc_per_match >= 3.5:
        return "MEDIO — evaluar con contexto (3.5-4.5 TA/p)"
    else:
        return "BAJO — no pick de tarjetas (< 3.5 TA/p)"


def scrape_league_referees(league_key):
    """Scrape all referees for a league from transfermarkt."""
    league = LEAGUES.get(league_key)
    if not league:
        return []

    try:
        resp = requests.get(league['tm_url'], headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [{league_key}] HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, 'lxml')
        table = soup.select_one('table.items')
        if not table:
            print(f"  [{league_key}] No referee table found")
            return []

        referees = []
        for row in table.select('tbody tr'):
            cells = row.select('td')
            if len(cells) < 8:
                continue

            name = cells[2].get_text(strip=True) if len(cells) > 2 else ''
            if not name:
                continue

            try:
                matches = int(cells[5].get_text(strip=True) or '0')
                yellows = int(cells[6].get_text(strip=True) or '0')
                reds = int(cells[7].get_text(strip=True) or '0')
                penalties = int(cells[9].get_text(strip=True) or '0') if len(cells) > 9 else 0
            except (ValueError, IndexError):
                continue

            if matches == 0:
                continue

            ypm = round(yellows / matches, 2)
            referees.append({
                'name': name,
                'matches_season': matches,
                'yellow_cards_total': yellows,
                'red_cards_total': reds,
                'penalties_total': penalties,
                'yellow_cards_per_match': ypm,
                'red_cards_per_match': round(reds / matches, 2),
                'penalties_per_match': round(penalties / matches, 2),
                'verdict': get_verdict(ypm),
            })

        return referees

    except Exception as e:
        print(f"  [{league_key}] Error: {e}")
        return []


def scrape_all(league_keys=None):
    """Scrape referees for multiple leagues."""
    if league_keys is None:
        league_keys = list(LEAGUES.keys())

    os.makedirs(REFEREES_DIR, exist_ok=True)
    all_data = {}

    for key in league_keys:
        league = LEAGUES.get(key)
        if not league:
            continue

        print(f"\n  [{league['name']}]")
        referees = scrape_league_referees(key)
        time.sleep(uniform(1.5, 3.0))

        if referees:
            # Sort by yellow cards per match (descending)
            referees.sort(key=lambda r: -r['yellow_cards_per_match'])

            avg_ypm = round(sum(r['yellow_cards_per_match'] for r in referees) / len(referees), 2)
            alto = sum(1 for r in referees if r['yellow_cards_per_match'] >= 4.5)

            all_data[key] = {
                'name': league['name'],
                'country': league['country'],
                'total_referees': len(referees),
                'avg_yellow_cards_per_match': avg_ypm,
                'alto_count': alto,
                'referees': referees,
            }

            print(f"    {len(referees)} referees | avg {avg_ypm} TA/P | {alto} ALTO")
            for r in referees[:3]:
                print(f"      {r['name']:30s} | {r['matches_season']:2d} matches | {r['yellow_cards_per_match']:.1f} TA/P | {r['verdict'].split(' — ')[0]}")
        else:
            print(f"    No data")

    # Save
    date_str = datetime.now().strftime('%Y-%m-%d')
    output = {
        'scraped_at': datetime.now().isoformat(),
        'total_leagues': len(all_data),
        'total_referees': sum(d['total_referees'] for d in all_data.values()),
        'leagues': all_data,
    }

    fname = f'international_referee_stats_{date_str}.json'
    fpath = os.path.join(REFEREES_DIR, fname)
    with open(fpath, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Also update the cache for quick lookups
    cache = {}
    for league_key, league_data in all_data.items():
        for ref in league_data['referees']:
            norm = _normalize_name(ref['name'])
            cache[norm] = {
                **ref,
                '_league': league_key,
                '_cached_at': datetime.now().isoformat(),
            }
    cache['_bulk_international'] = datetime.now().isoformat()
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved: referees/{fname}")
    print(f"  Cache: {len(cache)-1} referees in referee_stats_cache.json")
    return output


def lookup_referee(name, league_keys=None):
    """Look up a specific referee's stats."""
    # Check cache first
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        norm = _normalize_name(name)
        if norm in cache:
            ref = cache[norm]
            print(f"\n  {ref.get('name', name)}")
            print(f"  League: {ref.get('_league', '?')}")
            print(f"  Matches: {ref.get('matches_season', '?')}")
            print(f"  TA/P: {ref.get('yellow_cards_per_match', '?')}")
            print(f"  Verdict: {ref.get('verdict', '?')}")
            return ref

        # Fuzzy match
        best = None
        best_ratio = 0
        for k, v in cache.items():
            if k.startswith('_'):
                continue
            ratio = SequenceMatcher(None, norm, k).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = v
        if best and best_ratio > 0.6:
            print(f"\n  Closest match: {best.get('name', '?')} (similarity: {best_ratio:.2f})")
            print(f"  League: {best.get('_league', '?')}")
            print(f"  TA/P: {best.get('yellow_cards_per_match', '?')}")
            print(f"  Verdict: {best.get('verdict', '?')}")
            return best

    print(f"  Not found in cache. Run --all first to populate the database.")
    return None


def _normalize_name(name):
    name = name.strip().lower()
    nfkd = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def main():
    parser = argparse.ArgumentParser(description='International Referee Stats Scraper')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--all', action='store_true', help='All leagues')
    group.add_argument('--domestic', action='store_true', help='Domestic leagues only')
    group.add_argument('--european', action='store_true', help='UEFA competitions only')
    group.add_argument('--league', '-l', choices=list(LEAGUES.keys()), help='Specific league')
    group.add_argument('--lookup', help='Look up a specific referee')
    args = parser.parse_args()

    if args.lookup:
        lookup_referee(args.lookup)
        return

    print(f"\n{'='*60}")
    print(f"  International Referee Stats")
    print(f"{'='*60}")

    if args.all:
        keys = list(LEAGUES.keys())
    elif args.domestic:
        keys = DOMESTIC_LEAGUES
    elif args.european:
        keys = EUROPEAN_LEAGUES
    elif args.league:
        keys = [args.league]
    else:
        keys = list(LEAGUES.keys())  # default: all

    result = scrape_all(keys)

    print(f"\n{'='*60}")
    print(f"  Total: {result['total_referees']} referees across {result['total_leagues']} leagues")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
