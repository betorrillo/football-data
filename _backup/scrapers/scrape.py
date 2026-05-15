#!/usr/bin/env python3
"""
Scraper simplificado de bet365.

Uso:
  # Scrape un partido:
  python3 scrape.py "https://www.bet365.com/#/AC/B1/C1/D8/E191744492/F3/I99/"

  # Scrape varios partidos (cada uno en archivo separado):
  python3 scrape.py \
    "https://www.bet365.com/#/AC/B1/C1/D8/E191744492/F3/I99/" \
    "https://www.bet365.com/#/AC/B1/C1/D8/E191852183/F3/I99/" \
    "https://www.bet365.com/#/IP/EV151322823022C1"

  # Desde un archivo de URLs (una por línea):
  python3 scrape.py --file partidos.txt

Los resultados se guardan en la carpeta 'odds/' con un archivo por partido:
  odds/Sevilla_vs_Atletico_de_Madrid_2026-04-11_21-00.json
  odds/Cordoba_vs_Real_Zaragoza_2026-04-11_21-00.json
"""

import sys
import os
import re
import json
import time
from datetime import datetime

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_bet365 import (
    scrape_single_url, get_chrome_tabs, PRIORITY_GROUPS
)
from normalize import normalize_match, make_filename


def sanitize_filename(name):
    """Convert match name to safe filename."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name)
    return name.strip('_')[:80]


def fix_url(url):
    """Auto-fix common URL issues for pre-match pages."""
    url = url.strip()
    if not url:
        return None

    # Ensure /I99/ for pre-match URLs (Crear apuesta tab)
    if '/AC/' in url and '/I99/' not in url:
        # Replace /I{number}/ with /I99/
        url = re.sub(r'/I\d+/', '/I99/', url)

    # Remove trailing whitespace
    url = url.rstrip()

    return url


def main():
    urls = []

    # Parse arguments
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == '--file':
        if len(sys.argv) < 3:
            print("ERROR: --file requires a filename")
            sys.exit(1)
        filepath = sys.argv[2]
        if not os.path.exists(filepath):
            print(f"ERROR: File not found: {filepath}")
            sys.exit(1)
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
    else:
        urls = [u for u in sys.argv[1:] if u.startswith('http')]

    if not urls:
        print("ERROR: No URLs provided")
        sys.exit(1)

    # Fix URLs
    urls = [fix_url(u) for u in urls]
    urls = [u for u in urls if u]

    # Check Chrome connection
    try:
        tabs = get_chrome_tabs()
        bet365 = [t for t in tabs if 'bet365' in t.get('url', '').lower()]
        if not bet365:
            print("ERROR: No bet365 tab open in Chrome")
            print("  1. Close Chrome (Cmd+Q)")
            print("  2. bash launch_chrome.sh")
            print("  3. Open bet365.es and log in")
            sys.exit(1)
    except:
        print("ERROR: Chrome not responding on port 9222")
        print("  1. Close Chrome (Cmd+Q)")
        print("  2. bash launch_chrome.sh")
        sys.exit(1)

    # Create output directory
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'odds')
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  bet365 Scraper - {len(urls)} partido(s)")
    print(f"  Output: {out_dir}/")
    print(f"{'='*60}")

    results = []
    for i, url in enumerate(urls):
        print(f"\n[{i+1}/{len(urls)}] {url[:70]}")

        output = scrape_single_url(url, PRIORITY_GROUPS)
        if not output or output.get('summary', {}).get('total_odds', 0) == 0:
            print(f"  SKIP: No odds extracted")
            results.append({'url': url, 'file': None, 'odds': 0})
            continue

        # Normalize the data
        normalized = normalize_match(output)
        fname = make_filename(output)
        filepath = os.path.join(out_dir, fname)

        # Save normalized JSON
        with open(filepath, 'w') as f:
            json.dump(normalized, f, indent=2, ensure_ascii=False)

        odds_count = output['summary']['total_odds']
        markets_count = len(normalized.get('markets', {}))
        print(f"\n  SAVED: {fname}")
        print(f"  {odds_count} odds | {markets_count} markets")

        results.append({'url': url, 'file': fname, 'odds': odds_count, 'match': normalized.get('match', '')})

    # Summary
    print(f"\n{'='*60}")
    print(f"  RESUMEN")
    print(f"{'='*60}")
    total_odds = 0
    for r in results:
        status = f"{r['odds']} odds" if r['odds'] > 0 else "FAILED"
        match = r.get('match', '')[:40]
        print(f"  {match or r['url'][:40]:40s} | {status}")
        total_odds += r.get('odds', 0)
    print(f"\n  Total: {total_odds} odds en {sum(1 for r in results if r['odds']>0)} partidos")
    print(f"  Archivos en: {out_dir}/")


if __name__ == '__main__':
    main()
