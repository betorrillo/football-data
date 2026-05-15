#!/usr/bin/env python3
"""
Build per-match referee files for the Franken agent.

Strategy:
  1. Primary: look up the assigned referee from football-data.org API output
     (data/api/fixtures_api_*.json). Match by (date, {home_norm, away_norm}).
  2. If the referee is known and exists in referees/all_referees_*.json,
     attach full career stats.
  3. If no assignment is available (LaLiga/Serie A/Segunda are typically not
     covered), emit a `referee_pool` listing the top-N most-active referees
     of that competition with their stats — useful even without exact match.

Generates:
  referee/{league_dir}/{match_id}.json

Each file declares `mode` = "assigned" or "pool" so the agent knows what it got.

Usage:
  python3 scripts/build_referee.py
"""

import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.team_aliases import normalize_team

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ODDS_DIR = os.path.join(BASE_DIR, "odds")
API_DIR = os.path.join(BASE_DIR, "data", "api")
REFEREES_DIR = os.path.join(BASE_DIR, "referees")
REFEREE_OUT_DIR = os.path.join(BASE_DIR, "referee")

# odds league_code -> referees/ file league key (the per-league stats file)
LEAGUE_CODE_TO_REF_KEY = {
    "ENG1": "epl",
    "ESP1": "laliga",
    "ESP2": "segunda",
    "ITA1": "seriea",
    "ENG_FA": "epl",
    "GER1": "bundesliga",
    "FRA1": "ligue1",
    "POR1": "portugal",
}

POOL_SIZE = 5  # how many top referees to include in fallback pool

# Trailing tokens that are pure club-suffix noise on API names
_SUFFIX_TOKENS = re.compile(
    r"(?:\b(?:FC|AFC|CF|BC|SC|SV|VfB|VfL|FSV|RB|AS|AC|SSC|SS|US|GD|UD|CD|SD|GNK|OSC|"
    r"AJ|AC|RC|AC|Calcio|Hellas|Hotspur)\b|\b\d{4}\b)",
    re.IGNORECASE,
)


def relaxed_normalize(name):
    """Normalize aggressively for matching: strip common club-suffix tokens."""
    if not name:
        return ""
    cleaned = _SUFFIX_TOKENS.sub("", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return normalize_team(cleaned)


def load_latest(directory, pattern):
    files = sorted(glob.glob(os.path.join(directory, pattern)))
    if not files:
        return None
    return json.load(open(files[-1]))


def build_api_referee_lookup():
    """Return {(date, frozenset({home_norm, away_norm})): referee_dict}."""
    data = load_latest(API_DIR, "fixtures_api_*.json")
    if not data:
        return {}
    lookup = {}
    for code, lv in data.items():
        if not isinstance(lv, dict):
            continue
        for f in lv.get("fixtures", []):
            refs = f.get("referees", [])
            if not refs:
                continue
            date = f.get("date", "")
            home_raw = f.get("home_team", "")
            away_raw = f.get("away_team", "")
            if not (date and home_raw and away_raw):
                continue
            # Index under both strict and relaxed normalizations
            for h_func, a_func in ((normalize_team, normalize_team), (relaxed_normalize, relaxed_normalize)):
                h, a = h_func(home_raw), a_func(away_raw)
                if h and a:
                    lookup[(date, frozenset({h, a}))] = refs[0]
    return lookup


def build_referee_stats_lookup():
    """Return {ref_name_lower: stats_dict, ref_league: league_key}."""
    data = load_latest(REFEREES_DIR, "all_referees_*.json")
    if not data:
        return {}, {}
    by_name = {}
    by_league = {}
    for league_key, ld in data.get("leagues", {}).items():
        by_league[league_key] = ld.get("referees", [])
        for ref in ld.get("referees", []):
            name = ref.get("name", "").strip()
            if name:
                by_name[name.lower()] = ref
                # also index by last token (e.g. "Kavanagh")
                tokens = name.split()
                if len(tokens) >= 2:
                    by_name.setdefault(tokens[-1].lower(), ref)
    return by_name, by_league


def attach_stats(ref_entry, stats_by_name):
    """Augment an API referee entry with career stats if available."""
    name = ref_entry.get("name", "")
    if not name:
        return ref_entry
    s = stats_by_name.get(name.lower())
    if not s:
        # try last name
        last = name.split()[-1].lower() if name.split() else ""
        s = stats_by_name.get(last)
    if s:
        return {
            "name": name,
            "nationality": ref_entry.get("nationality"),
            "matched": True,
            "career_matches": s.get("career_matches"),
            "career_yc": s.get("career_yc"),
            "career_rc": s.get("career_rc"),
            "career_pk": s.get("career_pk"),
            "career_yc_per_match": s.get("career_yc_per_match"),
            "career_rc_per_match": s.get("career_rc_per_match"),
            "career_pk_per_match": s.get("career_pk_per_match"),
            "career_total_cards_per_match": s.get("career_total_cards_per_match"),
            "verdict": s.get("verdict"),
        }
    return {
        "name": name,
        "nationality": ref_entry.get("nationality"),
        "matched": False,
    }


def build_pool(league_refs, n=POOL_SIZE):
    """Return top-N most-active referees in the league as fallback pool."""
    if not league_refs:
        return []
    ranked = sorted(
        [r for r in league_refs if r.get("career_matches")],
        key=lambda r: r.get("career_matches", 0),
        reverse=True,
    )
    out = []
    for r in ranked[:n]:
        out.append({
            "name": r.get("name"),
            "career_matches": r.get("career_matches"),
            "career_yc": r.get("career_yc"),
            "career_rc": r.get("career_rc"),
            "career_pk": r.get("career_pk"),
            "career_yc_per_match": r.get("career_yc_per_match"),
            "career_rc_per_match": r.get("career_rc_per_match"),
            "career_total_cards_per_match": r.get("career_total_cards_per_match"),
            "verdict": r.get("verdict"),
        })
    return out


def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def main():
    print("=" * 60)
    print("Build per-match referee files")
    print("=" * 60)

    api_lookup = build_api_referee_lookup()
    print(f"  API assignments loaded: {len(api_lookup) // 2 if api_lookup else 0} unique (indexed twice)")

    stats_by_name, refs_by_league = build_referee_stats_lookup()
    print(f"  Referee stats: {len(stats_by_name)} name keys, {len(refs_by_league)} leagues")

    manifest = json.load(open(os.path.join(ODDS_DIR, "manifest.json")))
    upcoming = manifest.get("matches_upcoming", [])

    assigned_count = 0
    pool_count = 0

    for m in upcoming:
        match_id = m["match_id"]
        date = match_id[:10]
        league_code = m["league"]
        league_dir = m["urls"]["odds"].split("/odds/")[1].split("/")[0]
        ref_key = LEAGUE_CODE_TO_REF_KEY.get(league_code)

        h = normalize_team(m["home"])
        a = normalize_team(m["away"])
        hr = relaxed_normalize(m["home"])
        ar = relaxed_normalize(m["away"])

        ref_entry = (
            api_lookup.get((date, frozenset({h, a})))
            or api_lookup.get((date, frozenset({hr, ar})))
        )

        if ref_entry:
            assigned = attach_stats(ref_entry, stats_by_name)
            payload = {
                "match_id": match_id,
                "home": m["home"],
                "away": m["away"],
                "league": league_code,
                "date": date,
                "mode": "assigned",
                "referee": assigned,
                "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            assigned_count += 1
        else:
            pool = build_pool(refs_by_league.get(ref_key, []), POOL_SIZE) if ref_key else []
            if not pool:
                # nothing to write
                continue
            payload = {
                "match_id": match_id,
                "home": m["home"],
                "away": m["away"],
                "league": league_code,
                "date": date,
                "mode": "pool",
                "note": (
                    "No per-match referee assignment available from API source. "
                    f"Listing the top-{POOL_SIZE} most-active referees of the competition."
                ),
                "referee_pool": pool,
                "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            pool_count += 1

        out_path = os.path.join(REFEREE_OUT_DIR, league_dir, f"{match_id}.json")
        ensure_dir(out_path)
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\nResults:")
    print(f"  Assigned referee: {assigned_count}")
    print(f"  Pool fallback:    {pool_count}")
    print(f"  Total written:    {assigned_count + pool_count} / {len(upcoming)}")
    print("Done!")


if __name__ == "__main__":
    main()
