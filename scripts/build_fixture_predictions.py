#!/usr/bin/env python3
"""
Build fixture predictions by combining:
- Upcoming fixtures (from football-data.org API)
- Referee stats (from Transfermarkt)
- Team event stats (from ESPN)

Produces a single JSON with enriched fixtures including referee card predictions.

Usage:
  python3 scripts/build_fixture_predictions.py
"""

import glob
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.now().strftime("%Y-%m-%d")


def load_referee_stats():
    """Load referee stats and build lookup by normalized name."""
    refs_files = sorted(glob.glob(os.path.join(BASE_DIR, "referees", "all_referees_*.json")))
    if not refs_files:
        print("  No referee stats found")
        return {}

    data = json.load(open(refs_files[-1]))
    lookup = {}

    for league_key, league_data in data.get("leagues", {}).items():
        for ref in league_data.get("referees", []):
            name = ref["name"].strip()
            name_lower = name.lower()
            lookup[name_lower] = ref
            # Also index by last name for fuzzy matching
            parts = name_lower.split()
            if len(parts) >= 2:
                lookup[parts[-1]] = ref
            # Also index by "First Last" variants
            if len(parts) >= 3:
                # Try "First Last" (skip middle)
                lookup[f"{parts[0]} {parts[-1]}"] = ref

    print(f"  Referee stats loaded: {len(lookup)} lookup entries")
    return lookup


def find_referee(ref_name, lookup):
    """Find referee stats by name with fuzzy matching."""
    if not ref_name:
        return None

    name_lower = ref_name.strip().lower()

    # Exact match
    if name_lower in lookup:
        return lookup[name_lower]

    # Last name match
    parts = name_lower.split()
    if parts:
        last = parts[-1]
        if last in lookup:
            return lookup[last]

    # First + last (skip middle names)
    if len(parts) >= 3:
        first_last = f"{parts[0]} {parts[-1]}"
        if first_last in lookup:
            return lookup[first_last]

    return None


def load_team_event_stats():
    """Load team event stats (goals/cards by time period)."""
    stats = {}
    for f in glob.glob(os.path.join(BASE_DIR, "stats", "events", "team_event_stats_*_2025-26.json")):
        data = json.load(open(f))
        league = data.get("league", "")
        for team_name, team_stats in data.get("teams", {}).items():
            stats[team_name.lower()] = {**team_stats, "league": league}
    print(f"  Team event stats loaded: {len(stats)} teams")
    return stats


def find_team_stats(team_name, stats_lookup):
    """Find team stats with fuzzy matching."""
    if not team_name:
        return None

    name_lower = team_name.strip().lower()

    # Exact
    if name_lower in stats_lookup:
        return stats_lookup[name_lower]

    # Partial match
    for key, val in stats_lookup.items():
        if name_lower in key or key in name_lower:
            return val

    return None


def predict_cards(home_stats, away_stats, ref_stats):
    """
    Predict card probability using λ blend:
    50% team context (avg cards from both teams) + 50% referee TA/match
    """
    components = {}

    # Team-based card average
    team_cards_avg = None
    if home_stats and away_stats:
        home_mp = home_stats.get("mp", 1)
        away_mp = away_stats.get("mp", 1)
        home_cards = (home_stats.get("cards_1h", 0) + home_stats.get("cards_2h", 0)) / max(home_mp, 1)
        away_cards = (away_stats.get("cards_1h", 0) + away_stats.get("cards_2h", 0)) / max(away_mp, 1)
        # Also count cards received by opponents
        home_opp = (home_stats.get("opponent_cards_1h", 0) + home_stats.get("opponent_cards_2h", 0)) / max(home_mp, 1)
        away_opp = (away_stats.get("opponent_cards_1h", 0) + away_stats.get("opponent_cards_2h", 0)) / max(away_mp, 1)
        team_cards_avg = round((home_cards + away_cards + home_opp + away_opp) / 2, 2)
        components["team_cards_avg"] = team_cards_avg

    # Referee card average
    ref_cards_avg = None
    if ref_stats:
        ref_cards_avg = ref_stats.get("career_total_cards_per_match")
        components["ref_cards_per_match"] = ref_cards_avg
        components["ref_verdict"] = ref_stats.get("verdict")
        components["ref_matches"] = ref_stats.get("career_matches")

    # λ blend
    if team_cards_avg is not None and ref_cards_avg is not None:
        blended = round(0.5 * team_cards_avg + 0.5 * ref_cards_avg, 2)
        components["blended_cards_prediction"] = blended
        if blended >= 5.0:
            components["cards_verdict"] = "MUY ALTO"
        elif blended >= 4.5:
            components["cards_verdict"] = "ALTO"
        elif blended >= 3.5:
            components["cards_verdict"] = "MEDIO"
        else:
            components["cards_verdict"] = "BAJO"
    elif ref_cards_avg is not None:
        components["blended_cards_prediction"] = ref_cards_avg
        components["cards_verdict"] = ref_stats.get("verdict", "?")
        components["note"] = "ref-only (no team event data)"
    elif team_cards_avg is not None:
        components["blended_cards_prediction"] = team_cards_avg
        if team_cards_avg >= 5.0:
            components["cards_verdict"] = "MUY ALTO"
        elif team_cards_avg >= 4.5:
            components["cards_verdict"] = "ALTO"
        elif team_cards_avg >= 3.5:
            components["cards_verdict"] = "MEDIO"
        else:
            components["cards_verdict"] = "BAJO"
        components["note"] = "teams-only (no referee assigned)"

    return components


def main():
    print(f"Fixture Predictions Builder — {TODAY}")
    print("=" * 50)

    ref_lookup = load_referee_stats()
    team_stats = load_team_event_stats()

    # Load fixtures
    fixtures_files = sorted(glob.glob(os.path.join(BASE_DIR, "data", "api", "fixtures_api_*.json")))
    if not fixtures_files:
        print("  No fixtures found!")
        return

    fixtures_data = json.load(open(fixtures_files[-1]))

    all_predictions = {}
    total_fixtures = 0
    total_with_ref = 0

    for comp_code, comp_data in fixtures_data.items():
        comp_name = comp_data.get("competition", comp_code)
        fixtures = comp_data.get("fixtures", [])

        enriched = []
        for fix in fixtures:
            home = fix.get("home_team", "")
            away = fix.get("away_team", "")
            date = fix.get("date", "")
            time_ = fix.get("time", "")
            refs = fix.get("referees", [])
            ref_name = refs[0].get("name") if refs else None

            # Find data
            ref_stats = find_referee(ref_name, ref_lookup) if ref_name else None
            home_stats = find_team_stats(home, team_stats)
            away_stats = find_team_stats(away, team_stats)

            # Build prediction
            cards_pred = predict_cards(home_stats, away_stats, ref_stats)

            entry = {
                "date": date,
                "time": time_,
                "home": fix.get("home_short", home),
                "away": fix.get("away_short", away),
                "matchday": fix.get("matchday"),
            }

            if ref_name:
                entry["referee"] = ref_name
                total_with_ref += 1

            if cards_pred:
                entry["cards_analysis"] = cards_pred

            # Add team goal timing if available
            if home_stats:
                entry["home_goals_1h_avg"] = round(home_stats.get("goals_scored_1h", 0) / max(home_stats.get("mp", 1), 1), 2)
                entry["home_goals_2h_avg"] = round(home_stats.get("goals_scored_2h", 0) / max(home_stats.get("mp", 1), 1), 2)
            if away_stats:
                entry["away_goals_1h_avg"] = round(away_stats.get("goals_scored_1h", 0) / max(away_stats.get("mp", 1), 1), 2)
                entry["away_goals_2h_avg"] = round(away_stats.get("goals_scored_2h", 0) / max(away_stats.get("mp", 1), 1), 2)

            enriched.append(entry)
            total_fixtures += 1

        all_predictions[comp_code] = {
            "competition": comp_name,
            "fixtures": enriched,
            "total": len(enriched),
        }

        # Print sample
        with_ref = [e for e in enriched if "referee" in e]
        print(f"\n  {comp_name}: {len(enriched)} fixtures, {len(with_ref)} with referee")
        for e in with_ref[:2]:
            verdict = e.get("cards_analysis", {}).get("cards_verdict", "?")
            blended = e.get("cards_analysis", {}).get("blended_cards_prediction", "?")
            print(f"    {e['home']} vs {e['away']} | {e.get('referee','?')} | cards: {blended} ({verdict})")

    # Save
    output = {
        "generated": TODAY,
        "total_fixtures": total_fixtures,
        "fixtures_with_referee": total_with_ref,
        "predictions": all_predictions,
    }

    path = os.path.join(BASE_DIR, "predictions", f"fixture_predictions_{TODAY}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Also save as latest (fixed name for Drive)
    latest_path = os.path.join(BASE_DIR, "predictions", "fixture_predictions_latest.json")
    with open(latest_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"COMPLETE — {total_fixtures} fixtures, {total_with_ref} with referee analysis")
    print(f"Saved: {path}")


if __name__ == "__main__":
    main()
