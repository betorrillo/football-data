#!/usr/bin/env python3
"""
Weekend Scraper - Runs referee + odds scraping with one command.

Usage:
  python3 scrape_all_weekend.py --matchday 31
  python3 scrape_all_weekend.py --matchday 31 --odds-file partidos.txt
  python3 scrape_all_weekend.py --matchday 31 --odds-urls URL1 URL2
  python3 scrape_all_weekend.py --matchday 31 --skip-odds
  python3 scrape_all_weekend.py --matchday 31 --skip-referees
"""

import argparse
import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run(cmd, label):
    """Run a command and print its output."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}\n")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description='Weekend Scraper')
    parser.add_argument('--matchday', '-m', type=int, required=True, help='Matchday number')
    parser.add_argument('--skip-referees', action='store_true', help='Skip referee scraping')
    parser.add_argument('--skip-odds', action='store_true', help='Skip odds scraping')
    parser.add_argument('--odds-file', help='File with bet365 URLs for odds scraping')
    parser.add_argument('--odds-urls', nargs='+', help='bet365 URLs for odds scraping')
    parser.add_argument('--segunda-matchday', type=int, help='Segunda matchday (if different)')
    args = parser.parse_args()

    results = []

    # --- Referees ---
    if not args.skip_referees:
        # LaLiga
        ok = run(
            [sys.executable, 'scrape_referees.py', '-c', 'laliga', '-m', str(args.matchday)],
            f"ÁRBITROS LaLiga - Jornada {args.matchday}"
        )
        results.append(('Árbitros LaLiga', ok))

        # Segunda
        segunda_md = args.segunda_matchday or args.matchday
        ok = run(
            [sys.executable, 'scrape_referees.py', '-c', 'segunda', '-m', str(segunda_md)],
            f"ÁRBITROS Segunda - Jornada {segunda_md}"
        )
        results.append(('Árbitros Segunda', ok))

    # --- Odds ---
    if not args.skip_odds:
        if args.odds_file:
            ok = run(
                [sys.executable, 'scrape.py', '--file', args.odds_file],
                "CUOTAS bet365"
            )
            results.append(('Cuotas bet365', ok))
        elif args.odds_urls:
            ok = run(
                [sys.executable, 'scrape.py'] + args.odds_urls,
                "CUOTAS bet365"
            )
            results.append(('Cuotas bet365', ok))
        else:
            print("\n  [SKIP] Odds scraping: no URLs provided")
            print("  Use --odds-file or --odds-urls to scrape odds")

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"  RESUMEN FINAL")
    print(f"{'='*60}")
    for label, ok in results:
        status = "OK" if ok else "ERROR"
        print(f"  {label:30s} [{status}]")

    print(f"\n  Archivos:")
    print(f"    Árbitros: {BASE_DIR}/referees/")
    print(f"    Cuotas:   {BASE_DIR}/odds/")
    print(f"\n  Servidor: python3 server.py")
    print(f"    http://localhost:8080/odds/")
    print(f"    http://localhost:8080/referees/")


if __name__ == '__main__':
    main()
