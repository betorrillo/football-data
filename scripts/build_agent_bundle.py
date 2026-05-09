#!/usr/bin/env python3
"""
Build agent_bundle.json — a SINGLE file containing ALL data the Claude agent needs.

This solves the web_fetch restriction: instead of needing to fetch 5+ URLs,
the user uploads this ONE file as Project Knowledge in Claude.ai Projects.
The agent has instant access to everything without any web requests.

Also builds agent_bundle_compact.json with minimal whitespace for smaller size.

Usage:
  python3 scripts/build_agent_bundle.py
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.now().strftime("%Y-%m-%d")


def load_json(path):
    """Load a JSON file, return empty dict if not found."""
    full = os.path.join(BASE_DIR, path)
    if not os.path.exists(full):
        return {}
    with open(full) as f:
        return json.load(f)


def find_latest(directory, prefix):
    """Find latest file matching prefix in directory."""
    dir_path = os.path.join(BASE_DIR, directory)
    if not os.path.isdir(dir_path):
        return None
    files = sorted([f for f in os.listdir(dir_path)
                   if f.startswith(prefix) and f.endswith(".json")], reverse=True)
    return f"{directory}/{files[0]}" if files else None


def main():
    print(f"Agent Bundle Builder — {TODAY}")
    print("=" * 50)

    # Load analysis pack
    pack_path = f"analysis_pack_{TODAY}.json"
    if not os.path.exists(os.path.join(BASE_DIR, pack_path)):
        # Find latest
        packs = sorted([f for f in os.listdir(BASE_DIR)
                       if f.startswith("analysis_pack_") and f.endswith(".json")], reverse=True)
        pack_path = packs[0] if packs else None

    pack = load_json(pack_path) if pack_path else {}
    print(f"  Analysis pack: {pack.get('total_matches', 0)} matches")

    # Load referees
    ref_path = find_latest("referees", "all_referees_")
    referees = load_json(ref_path) if ref_path else {}
    print(f"  Referees: {referees.get('grand_total', 0)}")

    # Load injuries (all leagues)
    all_injuries = {}
    leagues = ["laliga", "segunda", "epl", "bundesliga", "seriea", "ligue1"]
    total_injured = 0
    for league in leagues:
        inj_path = find_latest("injuries", f"{league}_")
        if inj_path:
            data = load_json(inj_path)
            all_injuries[league] = data.get("teams", {})
            total_injured += data.get("total_injured", 0)
    print(f"  Injuries: {total_injured} total")

    # Load lineups
    lineup_path = find_latest("lineups", "probable_")
    lineups = load_json(lineup_path) if lineup_path else {}
    print(f"  Lineups: {lineups.get('total_matches', 0)} matches")

    # Build the bundle
    bundle = {
        "_meta": {
            "description": "Complete football analysis data for Claude AI agent. This ONE file replaces all web fetches.",
            "generated": TODAY,
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "version": "1.0",
            "usage": "Upload this file as Project Knowledge in Claude.ai Projects. The agent reads it directly — no web_fetch needed.",
            "github_repo": "https://github.com/betorrillo/football-data",
            "auto_updated": "Tue+Fri via GitHub Actions",
        },

        "matches": pack.get("matches", []),

        "referees": referees.get("leagues", {}),

        "injuries": all_injuries,

        "lineups": lineups.get("matches", []),
    }

    # Save readable version
    readable_path = os.path.join(BASE_DIR, "agent_bundle.json")
    with open(readable_path, "w") as f:
        json.dump(bundle, f, indent=1)
    readable_size = os.path.getsize(readable_path)
    print(f"\n  agent_bundle.json: {readable_size:,} bytes ({readable_size/1024:.0f} KB)")

    # Save compact version
    compact_path = os.path.join(BASE_DIR, "agent_bundle_compact.json")
    with open(compact_path, "w") as f:
        json.dump(bundle, f, separators=(",", ":"))
    compact_size = os.path.getsize(compact_path)
    print(f"  agent_bundle_compact.json: {compact_size:,} bytes ({compact_size/1024:.0f} KB)")

    # Estimate tokens (~4 chars per token for JSON)
    est_tokens = compact_size / 4
    print(f"  Estimated tokens: ~{est_tokens:,.0f}")

    if est_tokens > 150000:
        print("\n  ⚠️  WARNING: Bundle may be too large for Project Knowledge.")
        print("  Consider using agent_bundle_compact.json or splitting by league.")
    else:
        print("\n  ✅ Bundle fits in Claude.ai Project Knowledge!")

    print(f"\n{'='*50}")
    print("BUNDLE BUILD COMPLETE")
    print(f"\nNext step: Upload agent_bundle.json to your Claude.ai Project Knowledge")


if __name__ == "__main__":
    main()
