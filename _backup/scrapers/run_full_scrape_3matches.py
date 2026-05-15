#!/usr/bin/env python3
"""Full scrape of 3 CL matches with dropdown iteration."""
import sys, json, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from cdp_client import CDPClient
from scrape_bet365 import *
import requests
from datetime import datetime

tabs = requests.get('http://localhost:9222/json', timeout=5).json()
bet_tabs = [t for t in tabs if 'bet365' in t.get('url', '').lower()]
print(f"Found {len(bet_tabs)} bet365 tabs")

MATCHES = [
    (0, 'odds/uefa-champions-league_arsenal-vs-sporting_2026-04-15.json'),
    (1, 'odds/uefa-champions-league_liverpool-vs-psg_2026-04-14.json'),
    (2, 'odds/uefa-champions-league_bayern-de-múnich-vs-real-madrid_2026-04-15.json'),
]

for tab_idx, fname in MATCHES:
    if tab_idx >= len(bet_tabs):
        print(f"\nSKIP: tab {tab_idx} not available")
        continue

    t = bet_tabs[tab_idx]
    print(f"\n{'='*60}")
    print(f"SCRAPING TAB {tab_idx}: {t.get('url', '')[:80]}")
    print(f"{'='*60}")

    cdp = CDPClient(t['webSocketDebuggerUrl'])
    if not cdp.connect():
        print(f"  FAILED to connect")
        continue

    try:
        match_info, results = scrape_match_on_tab(cdp, only_groups=None)
        output = build_output(match_info, results)

        os.makedirs('odds', exist_ok=True)
        with open(fname, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*60}")
        print(f"DONE: {output['match']}")
        print(f"Total odds: {output['summary']['total_odds']}")
        print(f"Total markets: {output['summary']['total_markets']}")
        print(f"Saved to: {fname}")
        print(f"{'='*60}")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        cdp.disconnect()
        time.sleep(2)

print(f"\n{'='*60}")
print(f"ALL DONE!")
print(f"{'='*60}")
