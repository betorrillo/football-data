#!/usr/bin/env python3
"""
Split bulk data files into per-match JSON files for the Franken agent.

Reads:
  - odds/{league}/*.json          (match list + team names)
  - stats/derived/*_team_stats.json (team form, corners, cards, BTTS, O/U)
  - stats/xg_*.json               (xG per team)
  - stats/cards_*.json             (card totals per team)
  - lineups/probable_*.json        (team profiles, injuries)
  - referees/all_referees_*.json   (referee career stats)
  - predictions/fixture_predictions_*.json (match predictions)
  - injuries/all_injuries_*.json   (current injuries)

Generates:
  - context/{league}/{match_id}.json  (team stats for both teams)
  - lineups/{league}/{match_id}.json  (profiles + injuries for both teams)
  - referee/{league}/{match_id}.json  (assigned referee stats, if known)

Also updates odds/manifest.json with correct 'available' per match.

Usage:
  python3 scripts/split_bulk_to_matches.py
"""

import glob
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.team_aliases import normalize_team

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ODDS_DIR = os.path.join(BASE_DIR, "odds")
STATS_DIR = os.path.join(BASE_DIR, "stats")
LINEUPS_DIR = os.path.join(BASE_DIR, "lineups")
REFEREES_DIR = os.path.join(BASE_DIR, "referees")
PREDICTIONS_DIR = os.path.join(BASE_DIR, "predictions")
INJURIES_DIR = os.path.join(BASE_DIR, "injuries")

# Map from odds league_code to stats file keys
LEAGUE_CODE_TO_STATS = {
    "ENG1": "epl",
    "ESP1": "laliga",
    "ESP2": "segunda",
    "ITA1": "seriea",
    "ENG_FA": "epl",  # FA Cup teams are PL teams, use PL stats
    "GER1": "bundesliga",
    "FRA1": "ligue1",
    "POR1": "portugal",
}

# Map from lineups competition field to odds league dirs
LINEUP_COMP_TO_DIR = {
    "laliga": "laliga",
    "segunda": "segunda",
    "epl": "premier",
    "premier_league": "premier",
    "seriea": "serie-a",
    "serie_a": "serie-a",
    "bundesliga": "bundesliga",
    "ligue1": "ligue1",
    "fa_cup": "fa-cup",
    "champions": "champions",
    "portugal": "portugal",
}


def load_latest(directory, pattern):
    """Load most recent file matching glob pattern."""
    files = sorted(glob.glob(os.path.join(directory, pattern)))
    if not files:
        return None
    with open(files[-1]) as f:
        return json.load(f)


def build_team_lookup(stats_key):
    """Build normalized team name -> stats dict from derived stats."""
    path = os.path.join(STATS_DIR, "derived", f"{stats_key}_team_stats_2025-26.json")
    if not os.path.exists(path):
        return {}
    data = json.load(open(path))
    lookup = {}
    for team in data.get("teams", []):
        norm = normalize_team(team["team"])
        lookup[norm] = team
    return lookup


def build_xg_lookup(stats_key):
    """Build normalized team name -> xG dict."""
    path = os.path.join(STATS_DIR, f"xg_{stats_key}_2025-26.json")
    if not os.path.exists(path):
        return {}
    data = json.load(open(path))
    lookup = {}
    for team in data.get("teams", []):
        norm = normalize_team(team["team"])
        lookup[norm] = team
    return lookup


def build_cards_lookup(stats_key):
    """Build normalized team name -> cards dict."""
    path = os.path.join(STATS_DIR, f"cards_{stats_key}_2025-26.json")
    if not os.path.exists(path):
        return {}
    data = json.load(open(path))
    lookup = {}
    for team in data.get("teams", []):
        norm = normalize_team(team["team"])
        lookup[norm] = team
    return lookup


def build_injuries_lookup():
    """Build normalized team name -> injuries list."""
    data = load_latest(INJURIES_DIR, "all_injuries_*.json")
    if not data:
        return {}
    lookup = {}
    for league_key, league_data in data.get("leagues", {}).items():
        for team_name, injuries in league_data.get("teams", {}).items():
            norm = normalize_team(team_name)
            lookup[norm] = injuries
    return lookup


def build_referee_lookup():
    """Build normalized referee name -> stats dict."""
    data = load_latest(REFEREES_DIR, "all_referees_*.json")
    if not data:
        return {}
    lookup = {}
    for league_key, league_data in data.get("leagues", {}).items():
        for ref in league_data.get("referees", []):
            name = ref["name"].strip().lower()
            lookup[name] = ref
            parts = name.split()
            if len(parts) >= 2:
                lookup[parts[-1]] = ref
    return lookup


def build_lineup_lookup():
    """Build (norm_home, norm_away) -> lineup entry."""
    data = load_latest(LINEUPS_DIR, "probable_*.json")
    if not data:
        return {}
    lookup = {}
    for match in data.get("matches", []):
        h = normalize_team(match.get("home", ""))
        a = normalize_team(match.get("away", ""))
        if h and a:
            lookup[(h, a)] = match
    return lookup


def find_team_stats(team_name, stats_lookup, xg_lookup, cards_lookup):
    """Find and merge all stats for a team."""
    norm = normalize_team(team_name)
    base = stats_lookup.get(norm)
    if not base:
        return None

    result = dict(base)  # copy

    # Merge xG
    xg = xg_lookup.get(norm)
    if xg:
        result["xg"] = xg.get("xg")
        result["xga"] = xg.get("xga")
        result["xg_diff"] = xg.get("xg_diff")
        result["xga_diff"] = xg.get("xga_diff")

    # Merge cards totals
    cards = cards_lookup.get(norm)
    if cards:
        result["yellow_cards_total"] = cards.get("yellow_cards")
        result["red_cards_total"] = cards.get("red_cards")
        result["yc_per_match"] = cards.get("yc_per_match")

    return result


def generate_context(match_meta, stats_key):
    """Generate context JSON for a match."""
    stats_lookup = build_team_lookup(stats_key)
    xg_lookup = build_xg_lookup(stats_key)
    cards_lookup = build_cards_lookup(stats_key)

    home = match_meta["home_team"]
    away = match_meta["away_team"]

    home_stats = find_team_stats(home, stats_lookup, xg_lookup, cards_lookup)
    away_stats = find_team_stats(away, stats_lookup, xg_lookup, cards_lookup)

    if not home_stats and not away_stats:
        return None

    return {
        "match_id": match_meta["match_id"],
        "home": home,
        "away": away,
        "league": match_meta["league_code"],
        "date": match_meta["date"],
        "home_stats": home_stats,
        "away_stats": away_stats,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def generate_lineup(match_meta, lineup_lookup, injuries_lookup):
    """Generate lineup JSON for a match."""
    h_norm = normalize_team(match_meta["home_team"])
    a_norm = normalize_team(match_meta["away_team"])

    lineup = lineup_lookup.get((h_norm, a_norm))

    # Build result even without lineup match (still useful for injuries)
    home_injuries = injuries_lookup.get(h_norm, [])
    away_injuries = injuries_lookup.get(a_norm, [])

    result = {
        "match_id": match_meta["match_id"],
        "home": match_meta["home_team"],
        "away": match_meta["away_team"],
        "league": match_meta["league_code"],
        "date": match_meta["date"],
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if lineup:
        result["home_profile"] = lineup.get("home_profile")
        result["away_profile"] = lineup.get("away_profile")
        result["confirmed"] = lineup.get("confirmed", False)
        result["type"] = lineup.get("type", "probable")
        # Use lineup injuries if available, fallback to injuries dir
        result["home_injuries"] = lineup.get("home_injuries") or home_injuries
        result["away_injuries"] = lineup.get("away_injuries") or away_injuries
    else:
        result["home_profile"] = None
        result["away_profile"] = None
        result["confirmed"] = False
        result["type"] = "unavailable"
        result["home_injuries"] = home_injuries
        result["away_injuries"] = away_injuries

    # Only generate if we have SOMETHING useful
    has_data = (
        result.get("home_profile")
        or result.get("away_profile")
        or result["home_injuries"]
        or result["away_injuries"]
    )
    return result if has_data else None


def generate_referee(match_meta, referee_lookup):
    """Generate referee JSON for a match. Returns None if no referee data."""
    # For now, we don't have per-match referee assignments in predictions
    # But we can still provide the league's referee pool stats
    # Future: cross-reference with official assignment data
    return None  # Will be enhanced when assignment data is available


def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def main():
    print("=" * 60)
    print("Split bulk data -> per-match files")
    print("=" * 60)

    # Load all bulk data
    print("\nLoading bulk data...")
    lineup_lookup = build_lineup_lookup()
    print(f"  Lineups: {len(lineup_lookup)} matches")

    injuries_lookup = build_injuries_lookup()
    print(f"  Injuries: {len(injuries_lookup)} teams")

    referee_lookup = build_referee_lookup()
    print(f"  Referees: {len(referee_lookup)} entries")

    # Cache stats lookups per league (avoid reloading)
    stats_cache = {}
    xg_cache = {}
    cards_cache = {}

    # Scan all odds files to get match list
    manifest_path = os.path.join(ODDS_DIR, "manifest.json")
    manifest = json.load(open(manifest_path))
    matches = manifest.get("matches_upcoming", [])

    print(f"\nProcessing {len(matches)} matches...")

    context_count = 0
    lineup_count = 0
    referee_count = 0

    for match in matches:
        match_id = match["match_id"]
        league_code = match["league"]
        league_dir = match["urls"]["odds"].split("/odds/")[1].split("/")[0]  # premier, laliga, etc.
        stats_key = LEAGUE_CODE_TO_STATS.get(league_code)

        # Read odds file for full meta
        odds_path = os.path.join(ODDS_DIR, league_dir, f"{match_id}.json")
        if not os.path.exists(odds_path):
            print(f"  SKIP {match_id}: odds file missing")
            continue

        odds_data = json.load(open(odds_path))
        meta = odds_data.get("meta", {})
        meta["match_id"] = match_id
        meta["date"] = match_id[:10]

        available = ["odds"]

        # --- CONTEXT ---
        if stats_key:
            if stats_key not in stats_cache:
                stats_cache[stats_key] = build_team_lookup(stats_key)
                xg_cache[stats_key] = build_xg_lookup(stats_key)
                cards_cache[stats_key] = build_cards_lookup(stats_key)

            # Temporarily swap in cached lookups
            context = generate_context_with_cache(
                meta, stats_cache[stats_key], xg_cache[stats_key], cards_cache[stats_key]
            )
            if context:
                out_path = os.path.join(BASE_DIR, "context", league_dir, f"{match_id}.json")
                ensure_dir(out_path)
                with open(out_path, "w") as f:
                    json.dump(context, f, indent=2, ensure_ascii=False)
                context_count += 1
                available.append("context")

        # --- LINEUPS ---
        lineup = generate_lineup(meta, lineup_lookup, injuries_lookup)
        if lineup:
            out_path = os.path.join(BASE_DIR, "lineups", league_dir, f"{match_id}.json")
            ensure_dir(out_path)
            with open(out_path, "w") as f:
                json.dump(lineup, f, indent=2, ensure_ascii=False)
            lineup_count += 1
            available.append("lineups")

        # --- REFEREE ---
        ref_data = generate_referee(meta, referee_lookup)
        if ref_data:
            out_path = os.path.join(BASE_DIR, "referee", league_dir, f"{match_id}.json")
            ensure_dir(out_path)
            with open(out_path, "w") as f:
                json.dump(ref_data, f, indent=2, ensure_ascii=False)
            referee_count += 1
            available.append("referee")

        # --- H2H (generated separately by build_h2h.py; just detect presence) ---
        h2h_path = os.path.join(BASE_DIR, "h2h", league_dir, f"{match_id}.json")
        if os.path.exists(h2h_path):
            try:
                h2h_data = json.load(open(h2h_path))
                if h2h_data.get("h2h_count", 0) > 0:
                    available.append("h2h")
            except Exception:
                pass

        # Update manifest entry
        match["available"] = available

    # --- UPDATE MANIFEST ---
    manifest["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nResults:")
    print(f"  Context files: {context_count}/{len(matches)}")
    print(f"  Lineup files:  {lineup_count}/{len(matches)}")
    print(f"  Referee files: {referee_count}/{len(matches)}")
    print(f"  Manifest updated: {manifest_path}")
    print("Done!")


def generate_context_with_cache(match_meta, stats_lookup, xg_lookup, cards_lookup):
    """Generate context JSON using pre-loaded lookups."""
    home = match_meta.get("home_team", "")
    away = match_meta.get("away_team", "")

    home_stats = find_team_stats(home, stats_lookup, xg_lookup, cards_lookup)
    away_stats = find_team_stats(away, stats_lookup, xg_lookup, cards_lookup)

    if not home_stats and not away_stats:
        return None

    return {
        "match_id": match_meta["match_id"],
        "home": home,
        "away": away,
        "league": match_meta.get("league_code", ""),
        "date": match_meta.get("date", ""),
        "home_stats": home_stats,
        "away_stats": away_stats,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


if __name__ == "__main__":
    main()
