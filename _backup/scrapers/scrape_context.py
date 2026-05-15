#!/usr/bin/env python3
"""
Match context scraper - classification, form, motivation, rotation risk.
Sources: Flashscore (primary), LaLiga.com (backup).

Usage:
  python3 scrape_context.py                      # Today's matches
  python3 scrape_context.py --match "Elche vs Valencia"
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTEXT_DIR = os.path.join(BASE_DIR, 'context')
MATCHES_DIR = os.path.join(BASE_DIR, 'matches')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9',
}

# Relegation/promotion zones by competition
ZONES = {
    'LaLiga': {
        'relegation': range(18, 21),  # 18-20
        'champions': range(1, 5),     # 1-4
        'europa': range(5, 8),        # 5-7
        'total_teams': 20,
    },
    'LaLiga Hypermotion': {
        'relegation': range(19, 23),  # 19-22
        'promotion_direct': range(1, 3),  # 1-2
        'promotion_playoff': range(3, 7),  # 3-6
        'total_teams': 22,
    },
}


def load_todays_matches():
    """Load matches from the matches/ directory for today."""
    today = datetime.now().strftime('%Y-%m-%d')
    matches = []

    if not os.path.isdir(MATCHES_DIR):
        return matches

    for fname in os.listdir(MATCHES_DIR):
        if not fname.endswith('.json') or today not in fname:
            continue
        with open(os.path.join(MATCHES_DIR, fname)) as f:
            data = json.load(f)
        for m in data.get('matches', []):
            matches.append(m)

    return matches


def fetch_flashscore_standings(competition='laliga'):
    """Fetch league standings from Flashscore."""
    urls = {
        'laliga': 'https://www.flashscore.com/football/spain/laliga/standings/',
        'segunda': 'https://www.flashscore.com/football/spain/laliga2/standings/',
    }
    url = urls.get(competition)
    if not url:
        return {}

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [flashscore] HTTP {resp.status_code}")
            return {}

        soup = BeautifulSoup(resp.text, 'lxml')
        standings = {}

        # Parse standings table
        rows = soup.select('.ui-table__row, tr[class*="table__row"]')
        for row in rows:
            cells = row.select('td, .table__cell')
            if len(cells) < 8:
                continue

            try:
                pos_text = cells[0].get_text(strip=True)
                pos = int(re.search(r'\d+', pos_text).group()) if re.search(r'\d+', pos_text) else 0
                team = cells[1].get_text(strip=True)
                played = int(cells[2].get_text(strip=True) or '0')
                wins = int(cells[3].get_text(strip=True) or '0')
                draws = int(cells[4].get_text(strip=True) or '0')
                losses = int(cells[5].get_text(strip=True) or '0')
                gf_ga = cells[6].get_text(strip=True)
                points = int(cells[7].get_text(strip=True) or '0')

                gf, ga = 0, 0
                gm = re.match(r'(\d+):(\d+)', gf_ga)
                if gm:
                    gf, ga = int(gm.group(1)), int(gm.group(2))

                standings[_normalize_team(team)] = {
                    'position': pos,
                    'played': played,
                    'wins': wins,
                    'draws': draws,
                    'losses': losses,
                    'goals_scored': gf,
                    'goals_conceded': ga,
                    'points': points,
                    'goals_per_match': round(gf / played, 2) if played > 0 else 0,
                    'conceded_per_match': round(ga / played, 2) if played > 0 else 0,
                }
            except (ValueError, AttributeError):
                continue

        print(f"  [flashscore] Loaded standings: {len(standings)} teams")
        return standings

    except Exception as e:
        print(f"  [flashscore] Error: {e}")
        return {}


def fetch_team_form(team_name, competition='laliga'):
    """Fetch recent form and schedule for a team from Flashscore."""
    # This would require team-specific pages - simplified version using standings
    # For a full implementation, we'd navigate to the team page
    return {
        'form_last_5': [],
        'home_record': {},
        'away_record': {},
    }


def calculate_motivation(team_data, competition_name):
    """Calculate motivation level based on standings."""
    pos = team_data.get('position', 10)
    pts = team_data.get('points', 0)
    zones = ZONES.get(competition_name, ZONES['LaLiga'])

    # Get zone boundaries from standings
    # (simplified: use position directly)
    if pos in zones.get('relegation', []):
        return 'relegation_battle'

    if competition_name == 'LaLiga Hypermotion':
        if pos in zones.get('promotion_direct', []):
            return 'title_race'
        if pos in zones.get('promotion_playoff', []):
            return 'promotion_fight'

    if pos in zones.get('champions', range(1, 5)):
        if pos <= 2:
            return 'title_race'
        return 'champions_qualification'

    if pos in zones.get('europa', range(5, 8)):
        return 'europa_qualification'

    # Check proximity to zones
    total = zones.get('total_teams', 20)
    rel_start = min(zones.get('relegation', [18])) if zones.get('relegation') else 18

    if pos >= rel_start - 3:  # Close to relegation
        return 'relegation_battle'

    europa_end = max(zones.get('europa', [7])) if zones.get('europa') else 7
    if pos <= europa_end + 3:
        return 'europa_qualification'

    return 'nothing_to_play_for' if pos > 10 else 'mid_table'


def build_team_context(team_name, standings, competition_name, next_match_info=None):
    """Build full context for a team."""
    normalized = _normalize_team(team_name)

    # Find team in standings (fuzzy match)
    team_data = standings.get(normalized)
    if not team_data:
        # Try partial match
        for key, val in standings.items():
            if normalized in key or key in normalized:
                team_data = val
                break

    if not team_data:
        return {'team': team_name, 'error': 'not_found_in_standings'}

    motivation = calculate_motivation(team_data, competition_name)

    # Check European rotation risk
    rotation_risk = False
    if next_match_info:
        next_comp = next_match_info.get('competition', '').lower()
        days_until = next_match_info.get('days_until', 99)
        if days_until <= 5 and any(k in next_comp for k in ['champions', 'europa', 'copa del rey']):
            rotation_risk = True

    return {
        'team': team_name,
        'position': team_data.get('position', 0),
        'points': team_data.get('points', 0),
        'played': team_data.get('played', 0),
        'wins': team_data.get('wins', 0),
        'draws': team_data.get('draws', 0),
        'losses': team_data.get('losses', 0),
        'goals_scored': team_data.get('goals_scored', 0),
        'goals_conceded': team_data.get('goals_conceded', 0),
        'goals_per_match': team_data.get('goals_per_match', 0),
        'conceded_per_match': team_data.get('conceded_per_match', 0),
        'form_last_5': [],  # Would need team page scraping
        'motivation': motivation,
        'european_rotation_risk': rotation_risk,
        'days_since_last_match': None,  # Would need schedule scraping
        'next_match_after_this': next_match_info,
    }


def scrape_all_context():
    """Scrape context for all today's matches."""
    matches = load_todays_matches()
    if not matches:
        print("  No matches found for today. Run scrape_matches.py first.")
        return []

    print(f"  Found {len(matches)} matches for today")

    # Fetch standings
    standings_laliga = fetch_flashscore_standings('laliga')
    standings_segunda = fetch_flashscore_standings('segunda')

    results = []
    for match in matches:
        home = match.get('home', '')
        away = match.get('away', '')
        comp = match.get('competition', 'LaLiga')

        standings = standings_laliga if 'Hypermotion' not in comp else standings_segunda

        print(f"\n  {home} vs {away}")

        home_ctx = build_team_context(home, standings, comp)
        away_ctx = build_team_context(away, standings, comp)

        output = {
            'match': f"{home} vs {away}",
            'competition': comp,
            'date': match.get('date', ''),
            'kickoff': match.get('time', ''),
            'scraped_at': datetime.now().isoformat(),
            'home': home_ctx,
            'away': away_ctx,
            'h2h_last_5': [],  # Would need H2H scraping
        }

        results.append(output)

        # Print summary
        hm = home_ctx.get('motivation', '?')
        am = away_ctx.get('motivation', '?')
        print(f"    {home}: #{home_ctx.get('position','?')} {home_ctx.get('points','?')}pts [{hm}]")
        print(f"    {away}: #{away_ctx.get('position','?')} {away_ctx.get('points','?')}pts [{am}]")

    return results


def save_context(results):
    """Save context data."""
    os.makedirs(CONTEXT_DIR, exist_ok=True)
    date_str = datetime.now().strftime('%Y-%m-%d')

    saved = []
    for ctx in results:
        home = re.sub(r'[^a-zA-ZÀ-ÿ0-9]', '-', ctx.get('home', {}).get('team', 'unknown')).lower().strip('-')
        away = re.sub(r'[^a-zA-ZÀ-ÿ0-9]', '-', ctx.get('away', {}).get('team', 'unknown')).lower().strip('-')
        comp = ctx.get('competition', 'unknown').lower().replace(' ', '-')
        fname = f"{comp}_{home}-vs-{away}_{date_str}.json"
        fpath = os.path.join(CONTEXT_DIR, fname)

        with open(fpath, 'w') as f:
            json.dump(ctx, f, indent=2, ensure_ascii=False)
        saved.append(fname)

    print(f"\n  Saved {len(saved)} context files to context/")
    return saved


def _normalize_team(name):
    """Normalize team name for matching."""
    name = name.lower().strip()
    # Common variations
    replacements = {
        'atlético de madrid': 'atletico',
        'atlético': 'atletico',
        'athletic club': 'athletic',
        'real sociedad': 'r. sociedad',
        'real betis': 'betis',
        'real madrid': 'r. madrid',
        'real valladolid': 'valladolid',
        'rayo vallecano': 'rayo',
        'celta de vigo': 'celta',
        'deportivo alavés': 'alaves',
        'rcd mallorca': 'mallorca',
        'rcd espanyol': 'espanyol',
        'fc barcelona': 'barcelona',
        'ud las palmas': 'las palmas',
        'ca osasuna': 'osasuna',
        'cd leganés': 'leganes',
    }
    for full, short in replacements.items():
        if full in name:
            return short
    return name


def main():
    parser = argparse.ArgumentParser(description='Match Context Scraper')
    parser.add_argument('--match', help='Specific match to scrape')
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Match Context Scraper")
    print(f"{'='*60}")

    results = scrape_all_context()

    if results:
        save_context(results)

    print(f"\n{'='*60}")
    print(f"  Done! {len(results)} matches processed")


if __name__ == '__main__':
    main()
