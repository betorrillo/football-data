#!/usr/bin/env python3
"""
Generate probable lineups based on:
- Who has started most frequently this season (from match-by-match data)
- Known injuries/suspensions (from injuries/ directory)
- Card suspensions (5 yellows = 1 match ban in most leagues)

This doesn't use external data for starters — it uses our OWN match data
to determine who the regular starters are, then cross-references injuries.

Since our match data doesn't have individual player names per match (only team stats),
we generate a "team profile" approach: likely formation, key stats, and flag
which positions are weakened by injuries.

For actual player-level lineups we need the injuries data which has player names.

Usage:
  python3 scripts/build_probable_lineups.py
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCHES_DIR = os.path.join(BASE_DIR, "matches")
INJURIES_DIR = os.path.join(BASE_DIR, "injuries")
LINEUPS_DIR = os.path.join(BASE_DIR, "lineups")
FIXTURES_DIR = os.path.join(BASE_DIR, "fixtures")

TODAY = datetime.now().strftime("%Y-%m-%d")
CURRENT_SEASON = "2025-26"

LEAGUES = {
    "laliga": "LaLiga",
    "segunda": "Segunda Division",
    "epl": "Premier League",
    "bundesliga": "Bundesliga",
    "seriea": "Serie A",
    "ligue1": "Ligue 1",
}

LEAGUE_KEY_MAP = {
    "laliga": "laliga",
    "premier_league": "epl",
    "bundesliga": "bundesliga",
    "serie_a": "seriea",
    "ligue1": "ligue1",
    "ligue_1": "ligue1",
    "segunda": "segunda",
}


def safe_int(v):
    try:
        return int(v) if v is not None else 0
    except:
        return 0


def load_matches(league_folder):
    """Load current season matches."""
    path = os.path.join(MATCHES_DIR, league_folder, f"{CURRENT_SEASON}.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f).get("matches", [])


def load_injuries(league_key):
    """Load latest injury data for a league."""
    if not os.path.isdir(INJURIES_DIR):
        return {}
    files = sorted([f for f in os.listdir(INJURIES_DIR)
                   if f.startswith(f"{league_key}_") and f.endswith(".json")], reverse=True)
    if not files:
        return {}
    with open(os.path.join(INJURIES_DIR, files[0])) as f:
        data = json.load(f)
    return data.get("teams", {})


def analyze_team_profile(matches, team_name):
    """
    Build a team profile from match data:
    - Typical goal output, clean sheet rate
    - Consistency patterns (variance in goals, corners, cards)
    - Home vs away tendencies
    - Recent trajectory (improving/declining)
    """
    home_matches = [m for m in matches if m.get("home") == team_name and m.get("ft_home") is not None]
    away_matches = [m for m in matches if m.get("away") == team_name and m.get("ft_home") is not None]

    # Get last 10 matches for recent form analysis
    all_team = []
    for m in matches:
        if m.get("ft_home") is None:
            continue
        if m.get("home") == team_name:
            all_team.append({
                "venue": "H",
                "gf": safe_int(m["ft_home"]), "ga": safe_int(m["ft_away"]),
                "shots": safe_int(m.get("home_shots")),
                "sot": safe_int(m.get("home_shots_target")),
                "corners": safe_int(m.get("home_corners")),
                "yellows": safe_int(m.get("home_yellow")),
            })
        elif m.get("away") == team_name:
            all_team.append({
                "venue": "A",
                "gf": safe_int(m["ft_away"]), "ga": safe_int(m["ft_home"]),
                "shots": safe_int(m.get("away_shots")),
                "sot": safe_int(m.get("away_shots_target")),
                "corners": safe_int(m.get("away_corners")),
                "yellows": safe_int(m.get("away_yellow")),
            })

    if not all_team:
        return None

    last10 = all_team[-10:]
    last5 = all_team[-5:]

    profile = {
        "total_matches": len(all_team),
        "last5_goals_scored": sum(m["gf"] for m in last5),
        "last5_goals_conceded": sum(m["ga"] for m in last5),
        "last5_results": "".join("W" if m["gf"]>m["ga"] else ("D" if m["gf"]==m["ga"] else "L") for m in last5),
        "last5_avg_shots": round(sum(m["shots"] for m in last5) / len(last5), 1),
        "last5_avg_sot": round(sum(m["sot"] for m in last5) / len(last5), 1),
        "last5_avg_corners": round(sum(m["corners"] for m in last5) / len(last5), 1),
        "last5_avg_yellows": round(sum(m["yellows"] for m in last5) / len(last5), 1),
        "last10_goals_scored": sum(m["gf"] for m in last10),
        "last10_goals_conceded": sum(m["ga"] for m in last10),
        "trajectory": "improving" if sum(m["gf"] for m in last5) > sum(m["gf"] for m in last10[:5]) else "declining" if sum(m["gf"] for m in last5) < sum(m["gf"] for m in last10[:5]) else "stable",
    }

    # Consistency: standard deviation of goals scored
    goals = [m["gf"] for m in last10]
    if len(goals) > 1:
        mean = sum(goals) / len(goals)
        variance = sum((g - mean)**2 for g in goals) / len(goals)
        profile["scoring_consistency"] = "consistent" if variance < 1.0 else "variable" if variance < 2.5 else "unpredictable"

    return profile


def build_match_context(home, away, league_key, matches, injuries_data):
    """Build lineup/context for a specific match."""
    home_profile = analyze_team_profile(matches, home)
    away_profile = analyze_team_profile(matches, away)

    home_injuries = injuries_data.get(home, [])
    away_injuries = injuries_data.get(away, [])

    # Try fuzzy match for injury data
    if not home_injuries:
        for team_name, inj_list in injuries_data.items():
            if home.lower() in team_name.lower() or team_name.lower() in home.lower():
                home_injuries = inj_list
                break
    if not away_injuries:
        for team_name, inj_list in injuries_data.items():
            if away.lower() in team_name.lower() or team_name.lower() in away.lower():
                away_injuries = inj_list
                break

    context = {
        "home": home,
        "away": away,
        "home_profile": home_profile,
        "away_profile": away_profile,
        "home_injuries": home_injuries if home_injuries else [],
        "away_injuries": away_injuries if away_injuries else [],
        "home_injury_count": len(home_injuries) if home_injuries else 0,
        "away_injury_count": len(away_injuries) if away_injuries else 0,
        "confirmed": False,
        "type": "probable",
        "note": "Based on season match data patterns and known injuries. Confirm with official lineups 45min before kickoff.",
    }

    return context


def main():
    print(f"Probable Lineup Builder — {TODAY}")
    print("=" * 50)
    os.makedirs(LINEUPS_DIR, exist_ok=True)

    # Load fixtures
    fixtures_file = None
    for f in sorted(os.listdir(FIXTURES_DIR), reverse=True):
        if f.startswith("next_72h_") and f.endswith(".json"):
            fixtures_file = os.path.join(FIXTURES_DIR, f)
            break

    if not fixtures_file:
        print("No fixtures file found!")
        return

    with open(fixtures_file) as f:
        fixtures_data = json.load(f)

    all_lineups = []

    for league_key, league_info in fixtures_data.get("leagues", {}).items():
        folder = LEAGUE_KEY_MAP.get(league_key, league_key)
        if folder not in LEAGUES:
            continue

        matches = load_matches(folder)
        injuries = load_injuries(folder)

        print(f"\n{LEAGUES.get(folder, folder)}:")

        for fixture in league_info.get("matches", []):
            home = fixture["home"]
            away = fixture["away"]

            context = build_match_context(home, away, folder, matches, injuries)
            context["date"] = fixture.get("date", "")
            context["time"] = fixture.get("time", "")
            context["competition"] = folder

            all_lineups.append(context)
            injury_info = f" (injuries: {context['home_injury_count']}H/{context['away_injury_count']}A)" if context['home_injury_count'] or context['away_injury_count'] else ""
            print(f"  {home} vs {away}{injury_info}")

    # Save combined file
    output = {
        "generated": TODAY,
        "type": "probable_lineups",
        "description": "Team profiles and injury cross-reference for upcoming matches. Based on season patterns, NOT confirmed lineups.",
        "total_matches": len(all_lineups),
        "matches": all_lineups,
    }

    path = os.path.join(LINEUPS_DIR, f"probable_{TODAY}.json")
    with open(path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved {len(all_lineups)} match contexts")

    # Clean old files
    for old in os.listdir(LINEUPS_DIR):
        if old.startswith("probable_") and old.endswith(".json") and old != f"probable_{TODAY}.json":
            try:
                os.remove(os.path.join(LINEUPS_DIR, old))
            except:
                pass

    print(f"\n{'='*50}")
    print("LINEUP BUILD COMPLETE")


if __name__ == "__main__":
    main()
