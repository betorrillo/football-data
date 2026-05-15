#!/usr/bin/env python3
"""
Referee designation scraper - finds which referee is assigned to each match.
Crosses designations with referee stats to produce match-ready analysis.

Sources:
  - Spain: RFEF PDFs (via Chrome CDP)
  - International: Transfermarkt matchday pages
  - Champions/Europa/Conference: UEFA.com or Transfermarkt

Usage:
  python3 scrape_designations.py --all
  python3 scrape_designations.py --domestic
  python3 scrape_designations.py --european
  python3 scrape_designations.py --league bundesliga
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

# Transfermarkt league codes for matchday pages
TM_LEAGUES = {
    'laliga':         {'tm_code': 'ES1', 'tm_name': 'laliga',          'name': 'LaLiga',             'site': 'es'},
    'segunda':        {'tm_code': 'ES2', 'tm_name': 'laliga2',         'name': 'LaLiga Hypermotion', 'site': 'es'},
    'bundesliga':     {'tm_code': 'L1',  'tm_name': 'bundesliga',      'name': 'Bundesliga',         'site': 'com'},
    'serie-a':        {'tm_code': 'IT1', 'tm_name': 'serie-a',         'name': 'Serie A',            'site': 'com'},
    'premier-league': {'tm_code': 'GB1', 'tm_name': 'premier-league',  'name': 'Premier League',     'site': 'com'},
    'ligue-1':        {'tm_code': 'FR1', 'tm_name': 'ligue-1',         'name': 'Ligue 1',            'site': 'com'},
    'champions':      {'tm_code': 'CL',  'tm_name': 'uefa-champions-league',    'name': 'Champions League',  'site': 'com', 'cup': True},
    'europa-league':  {'tm_code': 'EL',  'tm_name': 'europa-league',            'name': 'Europa League',     'site': 'com', 'cup': True},
    'conference-league': {'tm_code': 'ECLQ', 'tm_name': 'europa-conference-league', 'name': 'Conference League', 'site': 'com', 'cup': True},
}


def load_referee_stats():
    """Load cached referee stats for cross-referencing."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def get_verdict(ypm):
    if ypm >= 4.5:
        return "ALTO — pick de tarjetas viable (≥ 4.5 TA/p)"
    elif ypm >= 3.5:
        return "MEDIO — evaluar con contexto (3.5-4.5 TA/p)"
    else:
        return "BAJO — no pick de tarjetas (< 3.5 TA/p)"


def _normalize(name):
    name = name.strip().lower()
    nfkd = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def find_referee_stats(referee_name, stats_cache):
    """Look up referee stats from cache using fuzzy matching."""
    norm = _normalize(referee_name)

    # Exact match
    if norm in stats_cache and not norm.startswith('_'):
        entry = stats_cache[norm]
        return {k: v for k, v in entry.items() if not k.startswith('_')}

    # Fuzzy match
    best = None
    best_ratio = 0
    for key, entry in stats_cache.items():
        if key.startswith('_'):
            continue
        ratio = SequenceMatcher(None, norm, key).ratio()
        if ratio > best_ratio and ratio > 0.55:
            best_ratio = ratio
            best = entry

    if best:
        return {k: v for k, v in best.items() if not k.startswith('_')}
    return None


# ===================================================================
# Source: Transfermarkt matchday pages
# ===================================================================

def scrape_designations_transfermarkt(league_key):
    """Scrape referee assignments from transfermarkt matchday page.

    Transfermarkt shows the referee for each match when it's been assigned.
    We scrape the current/next matchday and extract the referee name per match.
    """
    league = TM_LEAGUES.get(league_key)
    if not league:
        return None

    site = league['site']  # 'es' or 'com'
    tm_name = league['tm_name']
    tm_code = league['tm_code']
    is_cup = league.get('cup', False)

    # Build the matchday URL
    if is_cup:
        # Cup competitions use different URL pattern
        url = f"https://www.transfermarkt.{site}/{tm_name}/gesamtspielplan/pokalwettbewerb/{tm_code}/saison_id/2025"
    else:
        url = f"https://www.transfermarkt.{site}/{tm_name}/spieltag/wettbewerb/{tm_code}/saison_id/2025"

    print(f"  Fetching: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            return None

        soup = BeautifulSoup(resp.text, 'lxml')

        # Find the current matchday section
        designations = []

        # Parse match rows - transfermarkt shows matches in table rows
        # with referee info when assigned
        for row in soup.select('tr, .spieltagsansicht-row, [class*="match"]'):
            text = row.get_text(' ', strip=True)

            # Look for rows with team names and referee
            # Typical format: "Home Team X:X Away Team ... Referee: Name"
            teams = row.select('a[class*="vereins"], a[href*="/verein/"], td[class*="club"]')
            referee_el = row.select_one('a[href*="/schiedsrichter/"], [class*="referee"]')

            if len(teams) >= 2 and referee_el:
                home = teams[0].get_text(strip=True)
                away = teams[1].get_text(strip=True)
                referee = referee_el.get_text(strip=True)

                if home and away and referee:
                    designations.append({
                        'match': f"{home} vs {away}",
                        'home': home,
                        'away': away,
                        'referee': referee,
                    })

        # Alternative parsing: look for referee icons/links anywhere on the page
        if not designations:
            # Some pages have a different structure
            for a in soup.select('a[href*="/schiedsrichter/"]'):
                referee = a.get_text(strip=True)
                if referee and len(referee) > 3:
                    # Find the nearest match context
                    parent = a.parent
                    for _ in range(5):
                        if not parent:
                            break
                        parent_text = parent.get_text(' ', strip=True)
                        # Look for two team names in the parent
                        team_links = parent.select('a[href*="/verein/"]')
                        if len(team_links) >= 2:
                            home = team_links[0].get_text(strip=True)
                            away = team_links[1].get_text(strip=True)
                            if home and away:
                                designations.append({
                                    'match': f"{home} vs {away}",
                                    'home': home,
                                    'away': away,
                                    'referee': referee,
                                })
                                break
                        parent = parent.parent

        return designations if designations else None

    except Exception as e:
        print(f"  Error: {e}")
        return None


# ===================================================================
# Source: RFEF (Spain only) — delegates to existing scrape_referees.py
# ===================================================================

def scrape_designations_rfef(competition):
    """Use existing RFEF scraper for Spanish leagues."""
    try:
        from scrape_referees import scrape_competition
        result = scrape_competition(competition)
        if result and result.get('referees'):
            return [{
                'match': r.get('match', ''),
                'home': r.get('home', ''),
                'away': r.get('away', ''),
                'referee': r.get('referee', ''),
                'var': r.get('var', ''),
            } for r in result['referees'] if r.get('referee') and r['referee'] != 'pendiente']
    except Exception as e:
        print(f"  RFEF error: {e}")
    return None


# ===================================================================
# Main orchestrator
# ===================================================================

def scrape_league_designations(league_key):
    """Scrape designations for a league, trying multiple sources."""
    league = TM_LEAGUES.get(league_key)
    if not league:
        return None

    print(f"\n  === {league['name']} ===")

    designations = None

    # For Spanish leagues, try RFEF first
    if league_key in ('laliga', 'segunda'):
        print(f"  Trying RFEF...")
        designations = scrape_designations_rfef(league_key)

    # Transfermarkt as primary/fallback for all leagues
    if not designations:
        print(f"  Trying Transfermarkt...")
        designations = scrape_designations_transfermarkt(league_key)

    if not designations:
        print(f"  No designations found")
        return None

    print(f"  Found {len(designations)} designations")

    # Cross-reference with stats
    stats_cache = load_referee_stats()
    enriched = []
    for d in designations:
        ref_stats = find_referee_stats(d['referee'], stats_cache)
        verdict = get_verdict(ref_stats['yellow_cards_per_match']) if ref_stats else 'SIN DATOS — buscar manualmente'

        entry = {
            'match': d['match'],
            'home': d.get('home', ''),
            'away': d.get('away', ''),
            'referee': d['referee'],
            'var': d.get('var', ''),
            'stats': ref_stats,
            'verdict': verdict,
        }
        enriched.append(entry)

        ypm = f"{ref_stats['yellow_cards_per_match']:.1f}" if ref_stats else '?.?'
        v = verdict.split(' — ')[0]
        print(f"    {d['match']:40s} | {d['referee']:25s} | {ypm:>5} TA/P | {v}")

    return {
        'competition': league['name'],
        'scraped_at': datetime.now().isoformat(),
        'total_referees': len([e for e in enriched if e['stats']]),
        'referees': enriched,
    }


def save_designations(result, league_key):
    """Save designation data."""
    os.makedirs(REFEREES_DIR, exist_ok=True)
    date_str = datetime.now().strftime('%Y-%m-%d')
    fname = f"{league_key}_designations_{date_str}.json"
    fpath = os.path.join(REFEREES_DIR, fname)

    with open(fpath, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"  Saved: referees/{fname}")
    return fname


def main():
    parser = argparse.ArgumentParser(description='Referee Designation Scraper')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--all', action='store_true')
    group.add_argument('--domestic', action='store_true')
    group.add_argument('--european', action='store_true')
    group.add_argument('--league', '-l', choices=list(TM_LEAGUES.keys()))
    args = parser.parse_args()

    if args.all:
        keys = list(TM_LEAGUES.keys())
    elif args.domestic:
        keys = ['laliga', 'segunda', 'bundesliga', 'serie-a', 'premier-league', 'ligue-1']
    elif args.european:
        keys = ['champions', 'europa-league', 'conference-league']
    elif args.league:
        keys = [args.league]
    else:
        keys = ['laliga', 'segunda']

    print(f"\n{'='*60}")
    print(f"  Referee Designations")
    print(f"{'='*60}")

    for key in keys:
        try:
            result = scrape_league_designations(key)
            if result:
                save_designations(result, key)
            time.sleep(uniform(1.5, 3.0))
        except Exception as e:
            print(f"  ERROR in {key}: {e}")

    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
