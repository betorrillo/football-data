#!/usr/bin/env python3
"""Scrape all bet365 CL match tabs with full dropdown iteration."""
import sys, json, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from cdp_client import CDPClient
from scrape_bet365 import *
import requests

tabs = requests.get('http://localhost:9222/json', timeout=5).json()
bet_tabs = [t for t in tabs if 'bet365' in t.get('url', '').lower() and '/AC/B1/' in t.get('url', '')]
print(f"Found {len(bet_tabs)} bet365 match tabs")

os.makedirs('odds', exist_ok=True)

for i, t in enumerate(bet_tabs):
    url = t.get('url', '')
    print(f"\n{'='*60}")
    print(f"Tab {i}: {url[:80]}")
    print(f"{'='*60}")

    cdp = CDPClient(t['webSocketDebuggerUrl'])
    if not cdp.connect():
        print("  FAILED to connect")
        continue

    try:
        match_info, results = scrape_match_on_tab(cdp, only_groups=None)
        output = build_output(match_info, results)

        # Build filename from match name
        match_name = output.get('match', '').lower()
        home = output.get('home', '').lower().replace(' ', '-')
        away = output.get('away', '').lower().replace(' ', '-')
        comp = 'uefa-champions-league'
        date = '2026-04-15'
        if 'liverpool' in match_name: date = '2026-04-14'

        if home and away:
            fname = f"odds/{comp}_{home}-vs-{away}_{date}.json"
        else:
            fname = f"odds/{comp}_match-{i}_{date}.json"

        with open(fname, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\nDONE: {output['match']}")
        print(f"Cuotas: {output['summary']['total_odds']}")
        print(f"Mercados: {output['summary']['total_markets']}")
        print(f"Archivo: {fname}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
    finally:
        cdp.disconnect()
        time.sleep(2)

print(f"\n{'='*60}")
print("TODOS LOS SCRAPES COMPLETADOS")
print(f"{'='*60}")
