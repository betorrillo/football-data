#!/usr/bin/env python3
"""
Lineup scraper - confirmed starting XIs from LaLiga.com.
Designed to run 45 minutes before each match kickoff.

Usage:
  python3 scrape_lineups.py                        # All today's matches
  python3 scrape_lineups.py --match "Elche vs Valencia"
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

import requests
from cdp_client import CDPClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LINEUPS_DIR = os.path.join(BASE_DIR, 'lineups')
MATCHES_DIR = os.path.join(BASE_DIR, 'matches')
CDP_PORT = 9222

# LaLiga.com match page shows lineups when confirmed
LALIGA_CALENDAR_URLS = {
    'LaLiga': 'https://www.laliga.com/laliga-easports/calendario',
    'LaLiga Hypermotion': 'https://www.laliga.com/laliga-hypermotion/calendario',
}


def load_todays_matches():
    """Load today's matches from matches/ directory."""
    today = datetime.now().strftime('%Y-%m-%d')
    matches = []
    if not os.path.isdir(MATCHES_DIR):
        return matches
    for fname in os.listdir(MATCHES_DIR):
        if not fname.endswith('.json') or today not in fname:
            continue
        with open(os.path.join(MATCHES_DIR, fname)) as f:
            data = json.load(f)
        matches.extend(data.get('matches', []))
    return matches


def scrape_lineup_from_laliga(match_info):
    """Navigate to LaLiga.com and extract confirmed lineups for a match."""
    home = match_info.get('home', '')
    away = match_info.get('away', '')
    comp = match_info.get('competition', 'LaLiga')

    print(f"\n  Scraping lineup: {home} vs {away}")

    try:
        resp = requests.put(f'http://localhost:{CDP_PORT}/json/new?https://www.laliga.com', timeout=10)
        tab = resp.json()
    except:
        print("    Chrome not available")
        return None

    time.sleep(4)
    cdp = CDPClient(tab['webSocketDebuggerUrl'])
    cdp.connect()

    try:
        # Navigate to calendar
        calendar_url = LALIGA_CALENDAR_URLS.get(comp, LALIGA_CALENDAR_URLS['LaLiga'])
        cdp.evaluate(f'window.location.href = "{calendar_url}"')
        time.sleep(6)

        # Find and click the match
        click_result = cdp.evaluate(f'''
        (() => {{
            const links = document.querySelectorAll("a[href]");
            for (const a of links) {{
                const text = a.textContent.toLowerCase();
                if (text.includes("{home.lower()}") && text.includes("{away.lower()}")) {{
                    a.click();
                    return "clicked";
                }}
            }}
            // Try partial match
            for (const a of links) {{
                const text = a.textContent.toLowerCase();
                if (text.includes("{home.lower()[:6]}") && text.includes("{away.lower()[:6]}")) {{
                    a.click();
                    return "clicked_partial";
                }}
            }}
            return "not_found";
        }})()
        ''')

        if click_result == 'not_found':
            print(f"    Match not found on LaLiga.com")
            return None

        time.sleep(5)

        # Check for confirmed lineups ("TITULARES")
        lineup_data = cdp.evaluate('''
        (() => {
            const text = document.body.textContent;

            // Check if lineups are confirmed
            const hasLineups = text.includes("TITULARES") || text.includes("Titulares");
            if (!hasLineups) {
                return JSON.stringify({ confirmed: false, reason: "No confirmed lineups yet" });
            }

            // Extract lineup info
            const result = { confirmed: true, home: {}, away: {} };

            // Look for formation patterns (e.g., "4-4-2", "4-3-3")
            const formations = text.match(/\\d-\\d-\\d(-\\d)?/g);
            if (formations && formations.length >= 2) {
                result.home.formation = formations[0];
                result.away.formation = formations[1];
            }

            // Extract player names from lineup sections
            // LaLiga.com typically lists players in order
            const playerEls = document.querySelectorAll(
                '[class*="lineup"] [class*="player"], ' +
                '[class*="Lineup"] [class*="Player"], ' +
                '[class*="squad"] [class*="name"]'
            );

            const players = [];
            playerEls.forEach(el => {
                const name = el.textContent.trim();
                if (name && name.length > 2 && name.length < 40) {
                    players.push(name);
                }
            });

            result._players = players.slice(0, 40);
            result._bodyPreview = text.substring(
                Math.max(0, text.indexOf("TITULARES") - 100),
                text.indexOf("TITULARES") + 2000
            );

            return JSON.stringify(result);
        })()
        ''')

        if lineup_data:
            data = json.loads(lineup_data)
            if data.get('confirmed'):
                print(f"    Lineups CONFIRMED")
                return _parse_lineup_data(data, home, away, comp)
            else:
                print(f"    {data.get('reason', 'Not confirmed yet')}")
                return None

    except Exception as e:
        print(f"    Error: {e}")
        return None

    finally:
        cdp.disconnect()
        requests.put(f'http://localhost:{CDP_PORT}/json/close/{tab["id"]}', timeout=5)


def _parse_lineup_data(data, home, away, competition):
    """Parse raw lineup data into structured format."""
    output = {
        'match': f"{home} vs {away}",
        'competition': competition,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'scraped_at': datetime.now().isoformat(),
        'confirmed': True,
        'home': {
            'team': home,
            'formation': data.get('home', {}).get('formation', ''),
            'coach': '',
            'starting_xi': [],
            'substitutes': [],
            'unavailable': [],
        },
        'away': {
            'team': away,
            'formation': data.get('away', {}).get('formation', ''),
            'coach': '',
            'starting_xi': [],
            'substitutes': [],
            'unavailable': [],
        },
    }

    # Split players between home and away
    players = data.get('_players', [])
    if len(players) >= 22:
        output['home']['starting_xi'] = players[:11]
        output['away']['starting_xi'] = players[11:22]
        if len(players) > 22:
            mid = 22 + (len(players) - 22) // 2
            output['home']['substitutes'] = players[22:mid]
            output['away']['substitutes'] = players[mid:]

    return output


def save_lineup(lineup):
    """Save lineup to lineups/ directory."""
    os.makedirs(LINEUPS_DIR, exist_ok=True)
    date_str = datetime.now().strftime('%Y-%m-%d')
    home = re.sub(r'[^a-zA-ZÀ-ÿ0-9]', '-', lineup['home']['team']).lower().strip('-')
    away = re.sub(r'[^a-zA-ZÀ-ÿ0-9]', '-', lineup['away']['team']).lower().strip('-')
    comp = lineup['competition'].lower().replace(' ', '-')
    fname = f"{comp}_{home}-vs-{away}_{date_str}.json"
    fpath = os.path.join(LINEUPS_DIR, fname)

    with open(fpath, 'w') as f:
        json.dump(lineup, f, indent=2, ensure_ascii=False)

    print(f"    Saved: lineups/{fname}")
    return fname


def main():
    parser = argparse.ArgumentParser(description='Lineup Scraper')
    parser.add_argument('--match', help='Specific match (e.g., "Elche vs Valencia")')
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Lineup Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    matches = load_todays_matches()
    if args.match:
        matches = [m for m in matches if args.match.lower() in m.get('match', '').lower()]

    if not matches:
        print("  No matches found. Run scrape_matches.py first.")
        return

    saved = 0
    for match in matches:
        lineup = scrape_lineup_from_laliga(match)
        if lineup:
            save_lineup(lineup)
            saved += 1

    print(f"\n  Done! {saved}/{len(matches)} lineups saved")


if __name__ == '__main__':
    main()
