#!/usr/bin/env python3
"""
Automated scheduler for bet365 scraping ecosystem.
Runs scrapers at configured times and schedules lineups before kickoff.

Usage:
  python3 scheduler.py              # Start daemon
  python3 scheduler.py --run-now    # Run morning scrape immediately
  python3 scheduler.py --dry-run    # Show schedule without executing
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

import schedule

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MATCHES_DIR = os.path.join(BASE_DIR, 'matches')
LOG_FILE = os.path.join(BASE_DIR, 'scheduler.log')


def log(msg):
    """Log to console and file."""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')


def run_script(script, args=None, label=None):
    """Run a Python script and log result."""
    cmd = [sys.executable, os.path.join(BASE_DIR, script)]
    if args:
        cmd.extend(args)
    label = label or script
    log(f"Starting: {label}")
    try:
        result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            log(f"  OK: {label}")
        else:
            log(f"  ERROR: {label} (exit {result.returncode})")
            if result.stderr:
                log(f"  stderr: {result.stderr[:200]}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT: {label}")
        return False
    except Exception as e:
        log(f"  EXCEPTION: {label}: {e}")
        return False


def check_chrome():
    """Check if Chrome with CDP is running."""
    import requests as req
    try:
        resp = req.get(f'http://localhost:9222/json/version', timeout=3)
        return resp.status_code == 200
    except:
        return False


def morning_scrape():
    """Morning routine: discover matches, scrape odds, referees, context."""
    log("=" * 50)
    log("MORNING SCRAPE STARTING")
    log("=" * 50)

    if not check_chrome():
        log("ERROR: Chrome not running on port 9222. Run: bash launch_chrome.sh")
        return

    # Determine if it's a European day (Tue/Wed) or domestic day
    weekday = datetime.now().weekday()
    is_european_day = weekday in (1, 2)  # Tuesday, Wednesday

    # 1. Referee stats (weekly refresh)
    log("\n--- Phase 1: Referee Stats ---")
    if is_european_day:
        run_script('scrape_referees_international.py', ['--european'], label='Referee Stats (European)')
    else:
        run_script('scrape_referees_international.py', ['--all'], label='Referee Stats (All Leagues)')

    # 2. Designations (which referee pitches which match)
    log("\n--- Phase 2: Designations ---")
    if is_european_day:
        run_script('scrape_designations.py', ['--european'], label='Designations (European)')
    else:
        run_script('scrape_designations.py', ['--domestic'], label='Designations (Domestic)')

    # 3. Discover matches
    log("\n--- Phase 3: Match Discovery ---")
    if is_european_day:
        run_script('scrape_matches.py', ['--european'], label='Match Discovery (European)')
    else:
        run_script('scrape_matches.py', ['--domestic'], label='Match Discovery (Domestic)')

    # 4. Scrape odds
    log("\n--- Phase 4: Odds ---")
    urls_file = os.path.join(MATCHES_DIR, 'today_urls.txt')
    if os.path.exists(urls_file):
        run_script('scrape.py', ['--file', urls_file], label='Odds Scraping')
    else:
        log("  No match URLs found, skipping odds")

    # 5. Context (Spanish leagues only for now)
    log("\n--- Phase 5: Context ---")
    run_script('scrape_context.py', label='Match Context')

    # 5. Schedule lineup scrapes for each match
    schedule_lineup_scrapes()

    log("\nMORNING SCRAPE COMPLETE")


def schedule_lineup_scrapes():
    """Read match kickoff times and schedule lineup scrapes at kickoff - 45min."""
    today = datetime.now().strftime('%Y-%m-%d')
    matches = []

    if not os.path.isdir(MATCHES_DIR):
        return

    for fname in os.listdir(MATCHES_DIR):
        if not fname.endswith('.json') or today not in fname:
            continue
        try:
            with open(os.path.join(MATCHES_DIR, fname)) as f:
                data = json.load(f)
            matches.extend(data.get('matches', []))
        except:
            continue

    if not matches:
        log("  No matches to schedule lineups for")
        return

    now = datetime.now()
    scheduled = 0

    for match in matches:
        kickoff_str = match.get('time', '')
        match_name = match.get('match', '?')

        if not kickoff_str or ':' not in kickoff_str:
            continue

        try:
            h, m = map(int, kickoff_str.split(':'))
            kickoff = now.replace(hour=h, minute=m, second=0, microsecond=0)

            # Schedule lineup scrape 45 min before
            lineup_time = kickoff - timedelta(minutes=45)
            # Schedule odds update 30 min before
            odds_time = kickoff - timedelta(minutes=30)

            if lineup_time > now:
                time_str = lineup_time.strftime('%H:%M')
                schedule.every().day.at(time_str).do(
                    run_pre_match, match_name=match_name, match_url=match.get('url', '')
                ).tag('lineup', match_name)
                log(f"  Scheduled: {match_name} — lineups at {time_str}, odds at {odds_time.strftime('%H:%M')}")
                scheduled += 1
            else:
                log(f"  Skipped: {match_name} at {kickoff_str} (already past)")

        except (ValueError, AttributeError):
            continue

    log(f"  {scheduled} pre-match scrapes scheduled")


def run_pre_match(match_name, match_url=''):
    """Run pre-match scrapes (lineups + odds update) for a specific match."""
    log(f"\nPRE-MATCH: {match_name}")

    # Lineups
    run_script('scrape_lineups.py', ['--match', match_name], label=f'Lineups: {match_name}')

    # Updated odds
    if match_url:
        run_script('scrape.py', [match_url], label=f'Odds update: {match_name}')

    # Clear this job after execution (one-shot)
    return schedule.CancelJob


def main():
    parser = argparse.ArgumentParser(description='Scraping Scheduler')
    parser.add_argument('--run-now', action='store_true', help='Run morning scrape immediately')
    parser.add_argument('--dry-run', action='store_true', help='Show schedule without executing')
    args = parser.parse_args()

    log(f"\n{'='*50}")
    log(f"SCHEDULER STARTED")
    log(f"{'='*50}")

    if args.run_now:
        morning_scrape()
        return

    if args.dry_run:
        log("DRY RUN — Schedule configuration:")
        log("  Morning scrape: Fri/Sat/Sun/Tue/Wed at 09:00")
        log("  Pre-match lineups: 45 min before each kickoff (dynamic)")
        log("  Pre-match odds: 30 min before each kickoff (dynamic)")
        return

    # Schedule morning scrape on match days
    for day in ['friday', 'saturday', 'sunday', 'tuesday', 'wednesday']:
        getattr(schedule.every(), day).at('09:00').do(morning_scrape).tag('morning')

    log("Schedule configured:")
    log("  Morning scrape: Fri/Sat/Sun/Tue/Wed at 09:00")
    log("  Pre-match scrapes: scheduled dynamically after match discovery")
    log(f"\nWaiting for next scheduled task...")

    # Main loop
    while True:
        try:
            schedule.run_pending()
            time.sleep(30)
        except KeyboardInterrupt:
            log("\nScheduler stopped by user")
            break
        except Exception as e:
            log(f"ERROR in scheduler loop: {e}")
            time.sleep(60)


if __name__ == '__main__':
    main()
