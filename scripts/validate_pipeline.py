#!/usr/bin/env python3
"""
Smoke-test the pipeline output.

For each match_id listed in odds/manifest.json, verify that every expected
per-match file exists, parses as JSON, and declares a match_id matching
its directory entry. Print a health summary and exit non-zero if any
critical invariant breaks (use --strict to also fail on missing optional
data like lineups or referee assignments).

Usage:
  python3 scripts/validate_pipeline.py            # health report, exit 0
  python3 scripts/validate_pipeline.py --strict   # exit 1 on any gap
"""

import json
import os
import sys
from collections import Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ODDS_DIR = os.path.join(BASE_DIR, "odds")

# (kind, required?). Lineups + referee are advisory (we always try to fill
# them but some matches have no source data).
KINDS = [
    ("odds", True),
    ("context", True),
    ("h2h", True),
    ("lineups", False),
    ("referee", False),
]


def check_file(kind, league_dir, match_id):
    """Return (status, info) for a per-match file.

    Status is one of: "ok", "missing", "bad_json", "match_id_mismatch"
    """
    path = os.path.join(BASE_DIR, kind, league_dir, f"{match_id}.json")
    if not os.path.exists(path):
        return "missing", None
    try:
        data = json.load(open(path))
    except Exception as e:
        return "bad_json", str(e)
    declared = data.get("match_id")
    if declared and declared != match_id:
        return "match_id_mismatch", declared
    return "ok", data


def main():
    strict = "--strict" in sys.argv

    manifest_path = os.path.join(ODDS_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        print("FAIL: odds/manifest.json missing")
        sys.exit(1)

    manifest = json.load(open(manifest_path))
    upcoming = manifest.get("matches_upcoming", [])
    print(f"Validating {len(upcoming)} fixtures from manifest…\n")

    coverage = {kind: Counter() for kind, _ in KINDS}
    referee_modes = Counter()
    referee_flags = Counter()
    issues = []

    for m in upcoming:
        match_id = m["match_id"]
        league_dir = m["urls"]["odds"].split("/odds/")[1].split("/")[0]
        for kind, required in KINDS:
            status, info = check_file(kind, league_dir, match_id)
            coverage[kind][status] += 1
            if kind == "referee" and status == "ok":
                referee_modes[info.get("mode", "?")] += 1
                for f in info.get("flags", []) or []:
                    referee_flags[f] += 1
            if status != "ok":
                severity = "FAIL" if required else "WARN"
                issues.append(f"  [{severity}] {kind}/{league_dir}/{match_id}.json — {status}"
                              + (f" ({info})" if info else ""))

    # --- Print summary table ---
    print(f"{'kind':10} {'ok':>4} {'missing':>8} {'bad_json':>9} {'mid_mismatch':>13}")
    for kind, _ in KINDS:
        c = coverage[kind]
        print(
            f"{kind:10} {c['ok']:>4} {c['missing']:>8} {c['bad_json']:>9} "
            f"{c['match_id_mismatch']:>13}"
        )

    print(f"\nReferee modes:")
    for mode, n in referee_modes.most_common():
        print(f"  {mode:40} {n}")
    if referee_flags:
        print(f"\nReferee flags (cross-source signal):")
        for flag, n in referee_flags.most_common():
            print(f"  {flag:40} {n}")

    # --- Coverage by data_type (relative to manifest 'available' field) ---
    declared_available = Counter()
    for m in upcoming:
        for a in m.get("available", []):
            declared_available[a] += 1
    print(f"\nManifest 'available' counts:")
    for k, n in sorted(declared_available.items(), key=lambda x: -x[1]):
        print(f"  {k:25} {n}/{len(upcoming)}")

    # --- Issues ---
    critical = [i for i in issues if i.startswith("  [FAIL")]
    warn = [i for i in issues if i.startswith("  [WARN")]

    if issues:
        print(f"\nIssues ({len(critical)} fail, {len(warn)} warn):")
        for line in issues[:25]:
            print(line)
        if len(issues) > 25:
            print(f"  …and {len(issues) - 25} more")
    else:
        print("\nNo issues.")

    print(
        f"\nResult: {len(critical)} critical, {len(warn)} optional gaps "
        f"across {len(upcoming)} fixtures."
    )

    if critical or (strict and warn):
        sys.exit(1)


if __name__ == "__main__":
    main()
