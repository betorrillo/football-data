#!/usr/bin/env python3
"""
Build per-match referee files for the Franken agent.

Strategy (in order of preference):
  1. **Official source per league** (referee_sources/*): scrape the
     federation/league site for that matchweek's designations. Match by
     ordered (home_norm, away_norm). Highest confidence.
       - Serie A:    AIA-FIGC (aia-figc.it)
       - (more leagues to be added: DFB, LFP, PGMOL, RFEF, FPF)
  2. **football-data.org API** fallback: cross-source confirmation. Match
     by (date, frozenset({home, away})) using relaxed_normalize.
  3. **Pool**: top-N most-active referees of the competition with full
     career stats — useful even without exact assignment.

Output `mode` is one of:
  - "assigned_official"  -> from a federation source, order-confirmed
  - "assigned_official_order_swapped" -> federation confirms a fixture
       with reversed home/away vs the manifest (flag: bet365 scraper may
       have swapped them — agent should treat home/away cautiously)
  - "assigned"           -> from the API fallback
  - "pool"               -> top-5 league candidates

Generates:
  referee/{league_dir}/{match_id}.json

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

# Map odds league_code -> module name in referee_sources/.
# If a league isn't here, we skip the official-source step for it.
OFFICIAL_SOURCES = {
    "ITA1": "seriea_aia",
    "GER1": "bundesliga_dfb",
    "ENG1": "premier_pgmol",
    "ENG_FA": "premier_pgmol",  # FA Cup officials come from the PGMOL pool too
    "POR1": "primeira_record",
    "ESP1": "rfef_playwright",
    "ESP2": "rfef_playwright",
    # "FRA1": "ligue1_lfp",          # API already covers L1; skip
}


def load_official_sources():
    """Pre-fetch every official source once and build ordered lookups."""
    out = {}
    for league_code, mod_name in OFFICIAL_SOURCES.items():
        try:
            mod = __import__(
                f"referee_sources.{mod_name}",
                fromlist=["fetch_designations"],
            )
            designations = mod.fetch_designations()
            ordered = {
                (normalize_team(d["home"]), normalize_team(d["away"])): d
                for d in designations
            }
            out[league_code] = ordered
            print(f"  Official [{league_code}] {mod_name}: {len(designations)} designations")
        except Exception as e:
            print(f"  Official [{league_code}] {mod_name} FAILED: {e}")
            out[league_code] = {}
    return out


def find_official(home_raw, away_raw, manifest_date, league_code, official_lookup):
    """Look up an official designation; return (designation, confidence, flags).

    confidence:
      - "high"          : ordered match
      - "order_swapped" : same pair but home/away inverted in the manifest
      - None            : no match

    flags: list of strings, may include:
      - "date_drift"    : the official source publishes a different date
                          for this fixture than the manifest
    """
    pool = official_lookup.get(league_code) or {}
    if not pool:
        return None, None, []
    h = normalize_team(home_raw)
    a = normalize_team(away_raw)
    flags = []
    entry = None
    confidence = None
    if (h, a) in pool:
        entry = pool[(h, a)]
        confidence = "high"
    elif (a, h) in pool:
        entry = pool[(a, h)]
        confidence = "order_swapped"
    if entry:
        src_date = entry.get("date")
        if src_date and manifest_date and src_date != manifest_date:
            flags.append("date_drift")
    return entry, confidence, flags

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

    print("\nLoading official sources...")
    official_lookup = load_official_sources()

    api_lookup = build_api_referee_lookup()
    print(f"\n  API assignments loaded: {len(api_lookup) // 2 if api_lookup else 0} unique (indexed twice)")

    stats_by_name, refs_by_league = build_referee_stats_lookup()
    print(f"  Referee stats: {len(stats_by_name)} name keys, {len(refs_by_league)} leagues")

    manifest = json.load(open(os.path.join(ODDS_DIR, "manifest.json")))
    upcoming = manifest.get("matches_upcoming", [])

    official_count = 0
    swapped_count = 0
    api_count = 0
    pool_count = 0

    for m in upcoming:
        match_id = m["match_id"]
        date = match_id[:10]
        league_code = m["league"]
        league_dir = m["urls"]["odds"].split("/odds/")[1].split("/")[0]
        ref_key = LEAGUE_CODE_TO_REF_KEY.get(league_code)

        payload = None

        # 1) Official source (highest priority)
        official, conf, flags = find_official(
            m["home"], m["away"], date, league_code, official_lookup
        )
        if official:
            # The federation publishes the referee name (often surname-only,
            # ALL CAPS). Stats lookup uses full names; we still try the surname.
            ref_name = official.get("referee", "")
            stub = {"name": ref_name, "nationality": None}
            assigned = attach_stats(stub, stats_by_name)
            mode = "assigned_official" if conf == "high" else "assigned_official_order_swapped"
            payload = {
                "match_id": match_id,
                "home": m["home"],
                "away": m["away"],
                "league": league_code,
                "date": date,
                "mode": mode,
                "referee": assigned,
                "var": official.get("var"),
                "official_source": {
                    "url": official.get("source_url"),
                    "home_as_published": official.get("home"),
                    "away_as_published": official.get("away"),
                    "kickoff_time": official.get("kickoff_time"),
                    "date_as_published": official.get("date"),
                },
                "flags": flags,
                "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            warnings = []
            if conf == "order_swapped":
                warnings.append(
                    "Official federation source has home/away REVERSED versus this manifest. "
                    "The bet365 odds scraper may have swapped them. Trust the order in "
                    "official_source.home_as_published / away_as_published."
                )
                swapped_count += 1
            else:
                official_count += 1
            if "date_drift" in flags:
                warnings.append(
                    f"Date mismatch: manifest says {date}, "
                    f"official source publishes {official.get('date')}. "
                    "Same fixture (same ordered teams), different scheduled date — "
                    "could be a manifest scraping artifact or a fixture postponement."
                )
            if warnings:
                payload["warning"] = " ".join(warnings)

        # 2) API fallback
        if payload is None:
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
                api_count += 1

        # 3) Pool fallback
        if payload is None:
            pool = build_pool(refs_by_league.get(ref_key, []), POOL_SIZE) if ref_key else []
            if not pool:
                continue
            payload = {
                "match_id": match_id,
                "home": m["home"],
                "away": m["away"],
                "league": league_code,
                "date": date,
                "mode": "pool",
                "note": (
                    "No per-match referee assignment from official or API source. "
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
    print(f"  Official source (high confidence): {official_count}")
    print(f"  Official source (ORDER SWAPPED ⚠): {swapped_count}")
    print(f"  API fallback:                      {api_count}")
    print(f"  Pool fallback:                     {pool_count}")
    print(f"  Total written: {official_count + swapped_count + api_count + pool_count} / {len(upcoming)}")
    print("Done!")


if __name__ == "__main__":
    main()
