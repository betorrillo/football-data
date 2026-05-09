#!/usr/bin/env python3
"""
Build analysis_pack.json and status.json for the Claude agent.

Reads all match data, calculates per-team stats, form, averages,
and pre-packages everything the agent needs for the next 72h of fixtures
into ONE file. The agent reads 1 URL instead of 10+.

Also generates:
- stats/derived/{league}_team_stats_2025-26.json (corners, shots, cards, BTTS, O/U per team)
- stats/derived/segunda_team_stats_2025-26.json
- stats/derived/champions_team_stats_2025-26.json

Usage:
  python3 scripts/build_analysis_pack.py
"""

import json
import os
import re
from collections import defaultdict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCHES_DIR = os.path.join(BASE_DIR, "matches")
STATS_DIR = os.path.join(BASE_DIR, "stats")
FIXTURES_DIR = os.path.join(BASE_DIR, "fixtures")
DERIVED_DIR = os.path.join(STATS_DIR, "derived")

TODAY = datetime.now().strftime("%Y-%m-%d")
CURRENT_SEASON = "2025-26"

LEAGUES = {
    "laliga": "LaLiga",
    "segunda": "Segunda Division",
    "epl": "Premier League",
    "bundesliga": "Bundesliga",
    "seriea": "Serie A",
    "ligue1": "Ligue 1",
    "champions": "Champions League",
}


def load_matches(league_folder, season=CURRENT_SEASON):
    """Load all matches for a league/season."""
    if league_folder == "champions":
        path = os.path.join(MATCHES_DIR, "champions", f"league_phase_{season}.json")
    else:
        path = os.path.join(MATCHES_DIR, league_folder, f"{season}.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("matches", [])


def safe_int(v):
    if v is None:
        return 0
    try:
        return int(v)
    except:
        return 0


def compute_team_stats(matches, team_name):
    """Compute comprehensive stats for a team from match list."""
    home_matches = [m for m in matches if m.get("home") == team_name and m.get("ft_home") is not None]
    away_matches = [m for m in matches if m.get("away") == team_name and m.get("ft_home") is not None]

    stats = {
        "team": team_name,
        "mp": len(home_matches) + len(away_matches),
        "home_mp": len(home_matches),
        "away_mp": len(away_matches),
        "wins": 0, "draws": 0, "losses": 0,
        "home_wins": 0, "home_draws": 0, "home_losses": 0,
        "away_wins": 0, "away_draws": 0, "away_losses": 0,
        "gf": 0, "ga": 0,
        "home_gf": 0, "home_ga": 0,
        "away_gf": 0, "away_ga": 0,
        "ht_gf": 0, "ht_ga": 0,
        "corners_for": 0, "corners_against": 0,
        "home_corners_for": 0, "home_corners_against": 0,
        "away_corners_for": 0, "away_corners_against": 0,
        "shots_for": 0, "shots_against": 0,
        "shots_target_for": 0, "shots_target_against": 0,
        "fouls_for": 0, "fouls_against": 0,
        "yellows": 0, "reds": 0,
        "opponent_yellows": 0,
        "btts_yes": 0,
        "over_25": 0, "over_15": 0, "over_35": 0,
        "over_25_home": 0, "over_25_away": 0,
        "clean_sheets": 0, "failed_to_score": 0,
        "total_match_corners": 0,
        "total_match_cards": 0,
        # Half-time stats
        "ht_gf_1h": 0, "ht_ga_1h": 0,  # goals scored/conceded in 1st half
        "ht_gf_2h": 0, "ht_ga_2h": 0,  # goals scored/conceded in 2nd half
        "ht_over_05_1h": 0, "ht_over_15_1h": 0,  # match total goals 1st half
        "ht_over_05_2h": 0, "ht_over_15_2h": 0,  # match total goals 2nd half
        "ht_btts_1h": 0, "ht_btts_2h": 0,
        "ht_matches_with_data": 0,  # matches that have HT data
    }

    for m in home_matches:
        gf, ga = safe_int(m.get("ft_home")), safe_int(m.get("ft_away"))
        stats["gf"] += gf
        stats["ga"] += ga
        stats["home_gf"] += gf
        stats["home_ga"] += ga
        stats["ht_gf"] += safe_int(m.get("ht_home"))
        stats["ht_ga"] += safe_int(m.get("ht_away"))

        if gf > ga: stats["wins"] += 1; stats["home_wins"] += 1
        elif gf == ga: stats["draws"] += 1; stats["home_draws"] += 1
        else: stats["losses"] += 1; stats["home_losses"] += 1

        total_goals = gf + ga
        if total_goals > 2.5: stats["over_25"] += 1; stats["over_25_home"] += 1
        if total_goals > 1.5: stats["over_15"] += 1
        if total_goals > 3.5: stats["over_35"] += 1
        if gf > 0 and ga > 0: stats["btts_yes"] += 1
        if ga == 0: stats["clean_sheets"] += 1
        if gf == 0: stats["failed_to_score"] += 1

        # Half-time / 2nd half breakdown
        ht_gf = safe_int(m.get("ht_home"))
        ht_ga = safe_int(m.get("ht_away"))
        if m.get("ht_home") is not None:
            stats["ht_matches_with_data"] += 1
            stats["ht_gf_1h"] += ht_gf
            stats["ht_ga_1h"] += ht_ga
            goals_1h = ht_gf + ht_ga
            if goals_1h > 0.5: stats["ht_over_05_1h"] += 1
            if goals_1h > 1.5: stats["ht_over_15_1h"] += 1
            if ht_gf > 0 and ht_ga > 0: stats["ht_btts_1h"] += 1
            # 2nd half = FT - HT
            gf_2h = gf - ht_gf
            ga_2h = ga - ht_ga
            stats["ht_gf_2h"] += gf_2h
            stats["ht_ga_2h"] += ga_2h
            goals_2h = gf_2h + ga_2h
            if goals_2h > 0.5: stats["ht_over_05_2h"] += 1
            if goals_2h > 1.5: stats["ht_over_15_2h"] += 1
            if gf_2h > 0 and ga_2h > 0: stats["ht_btts_2h"] += 1

        hc = safe_int(m.get("home_corners"))
        ac = safe_int(m.get("away_corners"))
        stats["corners_for"] += hc
        stats["corners_against"] += ac
        stats["home_corners_for"] += hc
        stats["home_corners_against"] += ac
        stats["total_match_corners"] += hc + ac

        stats["shots_for"] += safe_int(m.get("home_shots"))
        stats["shots_against"] += safe_int(m.get("away_shots"))
        stats["shots_target_for"] += safe_int(m.get("home_shots_target"))
        stats["shots_target_against"] += safe_int(m.get("away_shots_target"))
        stats["fouls_for"] += safe_int(m.get("home_fouls"))
        stats["fouls_against"] += safe_int(m.get("away_fouls"))

        hy = safe_int(m.get("home_yellow"))
        ay = safe_int(m.get("away_yellow"))
        stats["yellows"] += hy
        stats["opponent_yellows"] += ay
        stats["reds"] += safe_int(m.get("home_red"))
        stats["total_match_cards"] += hy + ay

    for m in away_matches:
        gf, ga = safe_int(m.get("ft_away")), safe_int(m.get("ft_home"))
        stats["gf"] += gf
        stats["ga"] += ga
        stats["away_gf"] += gf
        stats["away_ga"] += ga
        stats["ht_gf"] += safe_int(m.get("ht_away"))
        stats["ht_ga"] += safe_int(m.get("ht_home"))

        if gf > ga: stats["wins"] += 1; stats["away_wins"] += 1
        elif gf == ga: stats["draws"] += 1; stats["away_draws"] += 1
        else: stats["losses"] += 1; stats["away_losses"] += 1

        total_goals = gf + ga
        if total_goals > 2.5: stats["over_25"] += 1; stats["over_25_away"] += 1
        if total_goals > 1.5: stats["over_15"] += 1
        if total_goals > 3.5: stats["over_35"] += 1
        if gf > 0 and ga > 0: stats["btts_yes"] += 1
        if ga == 0: stats["clean_sheets"] += 1
        if gf == 0: stats["failed_to_score"] += 1

        # Half-time / 2nd half breakdown
        ht_gf = safe_int(m.get("ht_away"))
        ht_ga = safe_int(m.get("ht_home"))
        if m.get("ht_home") is not None:
            stats["ht_matches_with_data"] += 1
            stats["ht_gf_1h"] += ht_gf
            stats["ht_ga_1h"] += ht_ga
            goals_1h = ht_gf + ht_ga
            if goals_1h > 0.5: stats["ht_over_05_1h"] += 1
            if goals_1h > 1.5: stats["ht_over_15_1h"] += 1
            if ht_gf > 0 and ht_ga > 0: stats["ht_btts_1h"] += 1
            gf_2h = gf - ht_gf
            ga_2h = ga - ht_ga
            stats["ht_gf_2h"] += gf_2h
            stats["ht_ga_2h"] += ga_2h
            goals_2h = gf_2h + ga_2h
            if goals_2h > 0.5: stats["ht_over_05_2h"] += 1
            if goals_2h > 1.5: stats["ht_over_15_2h"] += 1
            if gf_2h > 0 and ga_2h > 0: stats["ht_btts_2h"] += 1

        hc = safe_int(m.get("home_corners"))
        ac = safe_int(m.get("away_corners"))
        stats["corners_for"] += ac
        stats["corners_against"] += hc
        stats["away_corners_for"] += ac
        stats["away_corners_against"] += hc
        stats["total_match_corners"] += hc + ac

        stats["shots_for"] += safe_int(m.get("away_shots"))
        stats["shots_against"] += safe_int(m.get("home_shots"))
        stats["shots_target_for"] += safe_int(m.get("away_shots_target"))
        stats["shots_target_against"] += safe_int(m.get("home_shots_target"))
        stats["fouls_for"] += safe_int(m.get("away_fouls"))
        stats["fouls_against"] += safe_int(m.get("home_fouls"))

        hy = safe_int(m.get("away_yellow"))
        ay = safe_int(m.get("home_yellow"))
        stats["yellows"] += hy
        stats["opponent_yellows"] += ay
        stats["reds"] += safe_int(m.get("away_red"))
        stats["total_match_cards"] += hy + ay

    mp = stats["mp"]
    if mp > 0:
        stats["avg"] = {
            "gf": round(stats["gf"] / mp, 2),
            "ga": round(stats["ga"] / mp, 2),
            "corners_for": round(stats["corners_for"] / mp, 2),
            "corners_against": round(stats["corners_against"] / mp, 2),
            "total_corners": round(stats["total_match_corners"] / mp, 2),
            "shots": round(stats["shots_for"] / mp, 2),
            "shots_against": round(stats["shots_against"] / mp, 2),
            "shots_target": round(stats["shots_target_for"] / mp, 2),
            "shots_target_against": round(stats["shots_target_against"] / mp, 2),
            "fouls": round(stats["fouls_for"] / mp, 2),
            "fouls_against": round(stats["fouls_against"] / mp, 2),
            "yellows": round(stats["yellows"] / mp, 2),
            "opponent_yellows": round(stats["opponent_yellows"] / mp, 2),
            "total_match_cards": round(stats["total_match_cards"] / mp, 2),
        }
        stats["pct"] = {
            "over_15": round(stats["over_15"] / mp * 100, 1),
            "over_25": round(stats["over_25"] / mp * 100, 1),
            "over_35": round(stats["over_35"] / mp * 100, 1),
            "btts": round(stats["btts_yes"] / mp * 100, 1),
            "clean_sheet": round(stats["clean_sheets"] / mp * 100, 1),
            "failed_to_score": round(stats["failed_to_score"] / mp * 100, 1),
        }
        # Half-time percentages
        ht_mp = stats["ht_matches_with_data"]
        if ht_mp > 0:
            stats["avg_ht"] = {
                "gf_1h": round(stats["ht_gf_1h"] / ht_mp, 2),
                "ga_1h": round(stats["ht_ga_1h"] / ht_mp, 2),
                "gf_2h": round(stats["ht_gf_2h"] / ht_mp, 2),
                "ga_2h": round(stats["ht_ga_2h"] / ht_mp, 2),
                "total_1h": round((stats["ht_gf_1h"] + stats["ht_ga_1h"]) / ht_mp, 2),
                "total_2h": round((stats["ht_gf_2h"] + stats["ht_ga_2h"]) / ht_mp, 2),
            }
            stats["pct_ht"] = {
                "over_05_1h": round(stats["ht_over_05_1h"] / ht_mp * 100, 1),
                "over_15_1h": round(stats["ht_over_15_1h"] / ht_mp * 100, 1),
                "over_05_2h": round(stats["ht_over_05_2h"] / ht_mp * 100, 1),
                "over_15_2h": round(stats["ht_over_15_2h"] / ht_mp * 100, 1),
                "btts_1h": round(stats["ht_btts_1h"] / ht_mp * 100, 1),
                "btts_2h": round(stats["ht_btts_2h"] / ht_mp * 100, 1),
            }
        # Home averages
        hmp = stats["home_mp"]
        if hmp > 0:
            stats["avg_home"] = {
                "gf": round(stats["home_gf"] / hmp, 2),
                "ga": round(stats["home_ga"] / hmp, 2),
                "corners_for": round(stats["home_corners_for"] / hmp, 2),
                "corners_against": round(stats["home_corners_against"] / hmp, 2),
                "over_25_pct": round(stats["over_25_home"] / hmp * 100, 1),
            }
        # Away averages
        amp = stats["away_mp"]
        if amp > 0:
            stats["avg_away"] = {
                "gf": round(stats["away_gf"] / amp, 2),
                "ga": round(stats["away_ga"] / amp, 2),
                "corners_for": round(stats["away_corners_for"] / amp, 2),
                "corners_against": round(stats["away_corners_against"] / amp, 2),
                "over_25_pct": round(stats["over_25_away"] / amp * 100, 1),
            }
    else:
        stats["avg"] = {}
        stats["pct"] = {}

    return stats


def compute_form(matches, team_name, last_n=5):
    """Get last N matches form for a team."""
    team_matches = []
    for m in matches:
        if m.get("ft_home") is None:
            continue
        if m.get("home") == team_name:
            gf, ga = safe_int(m["ft_home"]), safe_int(m["ft_away"])
            team_matches.append({
                "date": m.get("date", ""),
                "venue": "H",
                "opponent": m["away"],
                "gf": gf, "ga": ga,
                "result": "W" if gf > ga else ("D" if gf == ga else "L"),
                "corners": safe_int(m.get("home_corners")) + safe_int(m.get("away_corners")),
                "team_corners": safe_int(m.get("home_corners")),
                "team_yellows": safe_int(m.get("home_yellow")),
                "total_yellows": safe_int(m.get("home_yellow")) + safe_int(m.get("away_yellow")),
                "team_shots": safe_int(m.get("home_shots")),
                "team_sot": safe_int(m.get("home_shots_target")),
            })
        elif m.get("away") == team_name:
            gf, ga = safe_int(m["ft_away"]), safe_int(m["ft_home"])
            team_matches.append({
                "date": m.get("date", ""),
                "venue": "A",
                "opponent": m["home"],
                "gf": gf, "ga": ga,
                "result": "W" if gf > ga else ("D" if gf == ga else "L"),
                "corners": safe_int(m.get("home_corners")) + safe_int(m.get("away_corners")),
                "team_corners": safe_int(m.get("away_corners")),
                "team_yellows": safe_int(m.get("away_yellow")),
                "total_yellows": safe_int(m.get("home_yellow")) + safe_int(m.get("away_yellow")),
                "team_shots": safe_int(m.get("away_shots")),
                "team_sot": safe_int(m.get("away_shots_target")),
            })

    return team_matches[-last_n:]


def compute_h2h(matches, home_team, away_team, last_n=10):
    """Get H2H between two teams from match data."""
    h2h = []
    for m in matches:
        if m.get("ft_home") is None:
            continue
        if (m.get("home") == home_team and m.get("away") == away_team) or \
           (m.get("home") == away_team and m.get("away") == home_team):
            h2h.append({
                "date": m.get("date", ""),
                "home": m["home"],
                "away": m["away"],
                "ft": f"{safe_int(m['ft_home'])}-{safe_int(m['ft_away'])}",
                "corners": safe_int(m.get("home_corners", 0)) + safe_int(m.get("away_corners", 0)),
                "cards": safe_int(m.get("home_yellow", 0)) + safe_int(m.get("away_yellow", 0)),
            })
    return h2h[-last_n:]


def get_all_teams(matches):
    """Get unique team names from matches."""
    teams = set()
    for m in matches:
        if m.get("home"):
            teams.add(m["home"])
        if m.get("away"):
            teams.add(m["away"])
    return sorted(teams)


def build_derived_stats():
    """Build derived team stats for all leagues including Segunda and Champions."""
    print("=== BUILDING DERIVED TEAM STATS ===")
    os.makedirs(DERIVED_DIR, exist_ok=True)

    for folder, league_name in LEAGUES.items():
        matches = load_matches(folder)
        if not matches:
            continue

        teams = get_all_teams(matches)
        team_stats = []
        for team in teams:
            s = compute_team_stats(matches, team)
            # Keep only averages and percentages for the derived file
            team_stats.append({
                "team": s["team"],
                "mp": s["mp"],
                "w": s["wins"], "d": s["draws"], "l": s["losses"],
                "gf": s["gf"], "ga": s["ga"], "gd": s["gf"] - s["ga"],
                "pts": s["wins"] * 3 + s["draws"],
                "avg": s.get("avg", {}),
                "avg_home": s.get("avg_home", {}),
                "avg_away": s.get("avg_away", {}),
                "pct": s.get("pct", {}),
                "avg_ht": s.get("avg_ht", {}),
                "pct_ht": s.get("pct_ht", {}),
            })

        # Sort by points
        team_stats.sort(key=lambda x: (-x["pts"], -x["gd"], -x["gf"]))

        path = os.path.join(DERIVED_DIR, f"{folder}_team_stats_{CURRENT_SEASON}.json")
        with open(path, "w") as f:
            json.dump({
                "generated": TODAY,
                "league": league_name,
                "season": CURRENT_SEASON,
                "source": "derived from match-by-match data",
                "teams": team_stats,
            }, f, indent=2)
        print(f"  {league_name}: {len(team_stats)} teams")


def load_xg(league_folder):
    """Load xG data for a league if available."""
    path = os.path.join(STATS_DIR, f"xg_{league_folder}_{CURRENT_SEASON}.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    return {t["team"]: t for t in data.get("teams", [])}


def load_cards_stats(league_folder):
    """Load card stats for a league if available."""
    path = os.path.join(STATS_DIR, f"cards_{league_folder}_{CURRENT_SEASON}.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    return {t["team"]: t for t in data.get("teams", [])}


def find_team_fuzzy(team_name, team_dict):
    """Try to match team name with fuzzy matching."""
    if team_name in team_dict:
        return team_dict[team_name]
    # Try common variations
    name_lower = team_name.lower()
    for key in team_dict:
        if key.lower() == name_lower:
            return team_dict[key]
        # Partial match
        if name_lower in key.lower() or key.lower() in name_lower:
            return team_dict[key]
    return None


def load_all_matches_for_league(league_folder):
    """Load all seasons for H2H calculation."""
    all_matches = []
    league_dir = os.path.join(MATCHES_DIR, league_folder)
    if league_folder == "champions":
        path = os.path.join(league_dir, f"league_phase_{CURRENT_SEASON}.json")
        if os.path.exists(path):
            with open(path) as f:
                all_matches.extend(json.load(f).get("matches", []))
        return all_matches

    if not os.path.isdir(league_dir):
        return all_matches
    for fname in sorted(os.listdir(league_dir)):
        if fname.endswith(".json"):
            with open(os.path.join(league_dir, fname)) as f:
                data = json.load(f)
                all_matches.extend(data.get("matches", []))
    return all_matches


def build_analysis_pack():
    """Build the main analysis_pack.json with pre-computed data for upcoming fixtures."""
    print("\n=== BUILDING ANALYSIS PACK ===")

    # Find latest fixtures file
    fixtures_file = None
    for f in sorted(os.listdir(FIXTURES_DIR), reverse=True):
        if f.startswith("next_72h_") and f.endswith(".json"):
            fixtures_file = os.path.join(FIXTURES_DIR, f)
            break

    if not fixtures_file:
        print("  No fixtures file found!")
        return

    with open(fixtures_file) as f:
        fixtures_data = json.load(f)

    # Map fixture league keys to our folder names
    LEAGUE_KEY_MAP = {
        "laliga": "laliga",
        "premier_league": "epl",
        "bundesliga": "bundesliga",
        "serie_a": "seriea",
        "ligue1": "ligue1",
        "ligue_1": "ligue1",
        "segunda": "segunda",
        "champions": "champions",
    }

    pack_matches = []

    for league_key, league_info in fixtures_data.get("leagues", {}).items():
        folder = LEAGUE_KEY_MAP.get(league_key, league_key)
        league_name = LEAGUES.get(folder, league_key)

        # Load current season matches
        matches = load_matches(folder)
        all_matches = load_all_matches_for_league(folder)
        xg_data = load_xg(folder)
        cards_data = load_cards_stats(folder)

        for fixture in league_info.get("matches", []):
            home = fixture["home"]
            away = fixture["away"]

            home_stats = compute_team_stats(matches, home)
            away_stats = compute_team_stats(matches, away)
            home_form = compute_form(matches, home, 5)
            away_form = compute_form(matches, away, 5)
            h2h = compute_h2h(all_matches, home, away)

            home_xg = find_team_fuzzy(home, xg_data)
            away_xg = find_team_fuzzy(away, xg_data)
            home_cards = find_team_fuzzy(home, cards_data)
            away_cards = find_team_fuzzy(away, cards_data)

            match_entry = {
                "match_id": f"{folder}_{fixture['date']}_{slugify(home)}-vs-{slugify(away)}",
                "competition": folder,
                "league_name": league_name if isinstance(league_name, str) else folder,
                "home": home,
                "away": away,
                "date": fixture.get("date", ""),
                "time": fixture.get("time", ""),
                "matchday": league_info.get("matchday", ""),

                "home_season": {
                    "mp": home_stats["mp"],
                    "record": f"{home_stats['wins']}W-{home_stats['draws']}D-{home_stats['losses']}L",
                    "pts": home_stats["wins"] * 3 + home_stats["draws"],
                    "gf": home_stats["gf"], "ga": home_stats["ga"],
                    "avg": home_stats.get("avg", {}),
                    "avg_home": home_stats.get("avg_home", {}),
                    "pct": home_stats.get("pct", {}),
                    "avg_ht": home_stats.get("avg_ht", {}),
                    "pct_ht": home_stats.get("pct_ht", {}),
                },
                "away_season": {
                    "mp": away_stats["mp"],
                    "record": f"{away_stats['wins']}W-{away_stats['draws']}D-{away_stats['losses']}L",
                    "pts": away_stats["wins"] * 3 + away_stats["draws"],
                    "gf": away_stats["gf"], "ga": away_stats["ga"],
                    "avg": away_stats.get("avg", {}),
                    "avg_away": away_stats.get("avg_away", {}),
                    "pct": away_stats.get("pct", {}),
                    "avg_ht": away_stats.get("avg_ht", {}),
                    "pct_ht": away_stats.get("pct_ht", {}),
                },

                "home_form_last5": home_form,
                "away_form_last5": away_form,
                "h2h": h2h,

                "home_xg": home_xg if home_xg else None,
                "away_xg": away_xg if away_xg else None,

                "data_available": {
                    "season_stats": True,
                    "form": len(home_form) > 0 and len(away_form) > 0,
                    "h2h": len(h2h) > 0,
                    "xg": home_xg is not None and away_xg is not None,
                    "referee": False,  # Will be filled by referee scraper
                    "injuries": False,
                    "lineup": False,
                },
                "missing_for_analysis": [],
            }

            # Track what's missing
            missing = []
            if not match_entry["data_available"]["xg"]:
                missing.append("xg")
            if not match_entry["data_available"]["referee"]:
                missing.append("referee")
            if not match_entry["data_available"]["injuries"]:
                missing.append("injuries")
            match_entry["missing_for_analysis"] = missing

            pack_matches.append(match_entry)

    # Sort by date and time
    pack_matches.sort(key=lambda x: (x["date"], x["time"]))

    pack = {
        "generated": TODAY,
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": "1.0",
        "description": "Pre-computed analysis data for upcoming fixtures. Agent reads this ONE file instead of 10+.",
        "total_matches": len(pack_matches),
        "matches": pack_matches,
    }

    path = os.path.join(BASE_DIR, f"analysis_pack_{TODAY}.json")
    with open(path, "w") as f:
        json.dump(pack, f, indent=2)
    print(f"  Analysis pack: {len(pack_matches)} matches saved")

    # Clean old packs
    for old in os.listdir(BASE_DIR):
        if old.startswith("analysis_pack_") and old.endswith(".json") and old != f"analysis_pack_{TODAY}.json":
            os.remove(os.path.join(BASE_DIR, old))

    return pack


def build_status(pack=None):
    """Build status.json — single entry point for the agent."""
    print("\n=== BUILDING STATUS.JSON ===")

    # Find all available data files
    available_files = {}
    for root, dirs, files in os.walk(BASE_DIR):
        if ".git" in root or "scripts" in root:
            continue
        for fname in files:
            if fname.endswith(".json") and fname != "manifest.json":
                rel = os.path.relpath(os.path.join(root, fname), BASE_DIR)
                mtime = os.path.getmtime(os.path.join(root, fname))
                available_files[rel] = {
                    "path": rel,
                    "age_minutes": int((datetime.now().timestamp() - mtime) / 60),
                }

    status = {
        "server_time_utc": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "manifest_version": "4.2",
        "analysis_pack": f"analysis_pack_{TODAY}.json",
        "analysis_pack_url": f"https://raw.githubusercontent.com/betorrillo/football-data/main/analysis_pack_{TODAY}.json",
        "total_data_files": len(available_files),
        "data_directories": {
            "matches": {"files": len([f for f in available_files if f.startswith("matches/")]), "status": "complete"},
            "stats": {"files": len([f for f in available_files if f.startswith("stats/")]), "status": "complete"},
            "stats/derived": {"files": len([f for f in available_files if f.startswith("stats/derived/")]), "status": "complete"},
            "fixtures": {"files": len([f for f in available_files if f.startswith("fixtures/")]), "status": "complete"},
            "referees": {"files": len([f for f in available_files if f.startswith("referees/")]), "status": "pending"},
            "injuries": {"files": len([f for f in available_files if f.startswith("injuries/")]), "status": "pending"},
            "lineups": {"files": len([f for f in available_files if f.startswith("lineups/")]), "status": "pending"},
        },
        "quick_start": "Read analysis_pack_{date}.json for ALL pre-computed data for upcoming fixtures. It contains season stats, form, H2H, xG, and more for every match in the next 72h. You only need this ONE file for analysis.",
    }

    if pack:
        status["fixtures_window"] = {
            "from": pack["matches"][0]["date"] if pack["matches"] else "",
            "to": pack["matches"][-1]["date"] if pack["matches"] else "",
            "total_matches": pack["total_matches"],
        }
        status["matches_summary"] = []
        for m in pack["matches"]:
            status["matches_summary"].append({
                "match_id": m["match_id"],
                "competition": m["competition"],
                "home": m["home"],
                "away": m["away"],
                "date": m["date"],
                "time": m["time"],
                "missing": m["missing_for_analysis"],
            })

    path = os.path.join(BASE_DIR, "status.json")
    with open(path, "w") as f:
        json.dump(status, f, indent=2)
    print(f"  status.json written with {len(available_files)} files tracked")


def slugify(text):
    """Convert team name to URL-safe slug."""
    text = text.lower()
    # Remove accents (basic)
    replacements = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","ü":"u","ö":"o","ä":"a"}
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def main():
    print(f"Analysis Pack Builder — {TODAY}")
    print("=" * 50)

    # Step 1: Build derived stats for all leagues
    build_derived_stats()

    # Step 2: Build analysis pack from fixtures + all data
    pack = build_analysis_pack()

    # Step 3: Build status.json
    build_status(pack)

    print("\n" + "=" * 50)
    print("BUILD COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()
