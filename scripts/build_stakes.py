#!/usr/bin/env python3
"""
Build stakes.json — what's at play in the upcoming matchday.

Generates per-league context:
- Standings with zones (champion, UCL, UEL, relegation)
- What each team is playing for
- Pichichi race (top scorers)
- Zamora race (least goals conceded per match = best GK)
- Key battles (6-pointers, title deciders, relegation finals)

Usage:
  python3 scripts/build_stakes.py
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.team_aliases import normalize_team

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEAGUE_CONFIG = {
    "epl": {
        "name": "Premier League",
        "code": "ENG1",
        "ucl_spots": 4,
        "uel_spots": 2,  # 5th-6th
        "relegation": 3,
        "total_matchdays": 38,
        "zamora_name": "Golden Glove",
    },
    "laliga": {
        "name": "La Liga",
        "code": "ESP1",
        "ucl_spots": 4,
        "uel_spots": 2,
        "relegation": 3,
        "total_matchdays": 38,
        "zamora_name": "Trofeo Zamora",
    },
    "segunda": {
        "name": "Segunda División",
        "code": "ESP2",
        "ucl_spots": 0,
        "uel_spots": 0,
        "promotion_direct": 2,
        "promotion_playoff": 4,  # 3rd-6th
        "relegation": 3,
        "total_matchdays": 42,
    },
    "seriea": {
        "name": "Serie A",
        "code": "ITA1",
        "ucl_spots": 4,
        "uel_spots": 2,
        "relegation": 3,
        "total_matchdays": 38,
        "zamora_name": "Best GK",
    },
}


def load_standings(league_key):
    path = os.path.join(BASE_DIR, "stats", "derived", f"{league_key}_team_stats_2025-26.json")
    if not os.path.exists(path):
        return []
    data = json.load(open(path))
    teams = sorted(data["teams"], key=lambda t: (-t["pts"], -t["gd"], -t["gf"]))
    return teams


def load_scorers(league_key):
    path = os.path.join(BASE_DIR, "stats", "players", f"scorers_{league_key}_2025-26.json")
    if not os.path.exists(path):
        return []
    data = json.load(open(path))
    return data.get("top_scorers", [])


def load_player_stats(league_key):
    path = os.path.join(BASE_DIR, "stats", "players", f"player_stats_{league_key}_2025-26.json")
    if not os.path.exists(path):
        return []
    data = json.load(open(path))
    return data.get("players", [])


def classify_team(pos, total, config):
    """Classify what a team is playing for based on position."""
    if config.get("promotion_direct"):
        # Segunda/promotion league
        if pos <= config["promotion_direct"]:
            return "promotion_direct"
        elif pos <= config["promotion_direct"] + config.get("promotion_playoff", 0):
            return "promotion_playoff"
        elif pos > total - config["relegation"]:
            return "relegation"
        else:
            return "mid_table"
    else:
        if pos == 1:
            return "champion"
        elif pos <= config["ucl_spots"]:
            return "ucl"
        elif pos <= config["ucl_spots"] + config["uel_spots"]:
            return "uel"
        elif pos > total - config["relegation"]:
            return "relegation"
        else:
            return "mid_table"


def describe_stake(team, pos, total, config, standings):
    """Generate human-readable stake description."""
    zone = classify_team(pos, total, config)
    pts = team["pts"]
    mp = team["mp"]
    remaining = config.get("total_matchdays", 38) - mp

    descriptions = []

    if zone == "champion":
        gap = pts - standings[1]["pts"] if len(standings) > 1 else 0
        if gap > remaining * 3:
            descriptions.append(f"Champion confirmed (lead: {gap} pts)")
        elif gap > 0:
            descriptions.append(f"Leader, {gap} pts ahead of {standings[1]['team']}")
        else:
            descriptions.append("Joint leader on GD")

    elif zone == "ucl":
        gap_above = pts - standings[pos - 2]["pts"] if pos > 1 else 0
        gap_below = pts - standings[pos]["pts"] if pos < total else 0
        descriptions.append(f"UCL zone (pos {pos})")
        if gap_below <= 3:
            descriptions.append(f"Only {gap_below} pts above {standings[pos]['team']}")

    elif zone == "uel":
        descriptions.append(f"Europa zone (pos {pos})")

    elif zone == "promotion_direct":
        descriptions.append(f"Direct promotion (pos {pos})")

    elif zone == "promotion_playoff":
        descriptions.append(f"Promotion playoff (pos {pos})")

    elif zone == "relegation":
        gap = standings[total - config["relegation"] - 1]["pts"] - pts
        safety_team = standings[total - config["relegation"] - 1]["team"]
        descriptions.append(f"RELEGATION ZONE (pos {pos})")
        descriptions.append(f"{gap} pts from safety ({safety_team})")
        if gap > remaining * 3:
            descriptions.append("Mathematically relegated")

    else:
        # Check if close to any zone
        ucl_cutoff = config.get("ucl_spots", 0)
        rel_cutoff = total - config.get("relegation", 3)
        if ucl_cutoff > 0:
            gap_to_ucl = standings[ucl_cutoff - 1]["pts"] - pts
            if gap_to_ucl <= 6:
                descriptions.append(f"{gap_to_ucl} pts from UCL ({standings[ucl_cutoff-1]['team']})")
        gap_to_rel = pts - standings[rel_cutoff]["pts"]
        if gap_to_rel <= 6:
            descriptions.append(f"Only {gap_to_rel} pts above relegation")

    if not descriptions:
        descriptions.append("Nothing at stake (mid-table)")

    return {"zone": zone, "descriptions": descriptions}


def build_pichichi(scorers, league_name):
    """Build Pichichi/top scorer race."""
    if not scorers:
        return None
    leader = scorers[0]
    contenders = [s for s in scorers[1:6] if s["goals"] >= leader["goals"] - 4]
    contender_list = [
        {
            "name": s["name"],
            "team": s["team"],
            "goals": s["goals"],
            "gap": leader["goals"] - s["goals"],
        }
        for s in contenders
    ]

    return {
        "title": f"Pichichi / Top Scorer — {league_name}",
        "leader": {
            "name": leader["name"],
            "team": leader["team"],
            "goals": leader["goals"],
        },
        "contenders": contender_list,
        "race_alive": len(contender_list) > 0 and contender_list[0]["gap"] <= 3,
    }


def build_zamora(standings, league_name, zamora_name):
    """Build Zamora/Golden Glove race (least goals per match)."""
    candidates = []
    for t in standings:
        if t["mp"] >= 20:  # minimum matches
            ga_per_match = round(t["ga"] / t["mp"], 3)
            candidates.append({
                "team": t["team"],
                "ga": t["ga"],
                "mp": t["mp"],
                "ga_per_match": ga_per_match,
            })
    candidates.sort(key=lambda x: x["ga_per_match"])

    if not candidates:
        return None

    return {
        "title": f"{zamora_name} — {league_name}",
        "note": "Least goals conceded per match (team-level, GK-specific data not available)",
        "leader": candidates[0],
        "contenders": candidates[1:4],
        "race_alive": len(candidates) > 1 and (candidates[1]["ga_per_match"] - candidates[0]["ga_per_match"]) < 0.15,
    }


def find_key_matches(standings, config, odds_teams):
    """Identify 6-pointers and key matches."""
    total = len(standings)
    key_matches = []
    team_zones = {}

    for i, t in enumerate(standings):
        zone = classify_team(i + 1, total, config)
        team_zones[normalize_team(t["team"])] = {
            "pos": i + 1,
            "zone": zone,
            "team": t["team"],
            "pts": t["pts"],
        }

    # Check which odds matches involve teams in interesting positions
    for home_norm, away_norm in odds_teams:
        h = team_zones.get(home_norm)
        a = team_zones.get(away_norm)
        if not h or not a:
            continue

        interest = []
        if h["zone"] == "relegation" and a["zone"] == "relegation":
            interest.append("RELEGATION 6-POINTER")
        elif h["zone"] == "relegation" or a["zone"] == "relegation":
            interest.append("Relegation battle")
        if h["zone"] in ("champion", "ucl") and a["zone"] in ("champion", "ucl"):
            interest.append("TOP-4 CLASH")
        if h["zone"] == "champion" or a["zone"] == "champion":
            interest.append("Title race")
        if abs(h["pts"] - a["pts"]) <= 3 and h["zone"] == a["zone"]:
            interest.append("Direct rivals (same zone, ≤3 pts apart)")

        if interest:
            key_matches.append({
                "home": h["team"],
                "away": a["team"],
                "home_pos": h["pos"],
                "away_pos": a["pos"],
                "pts_gap": abs(h["pts"] - a["pts"]),
                "interest": interest,
            })

    return key_matches


def main():
    print("Building stakes.json...")

    # Get odds teams to know which matches are upcoming
    import glob

    odds_teams_by_league = {}
    for f in glob.glob(os.path.join(BASE_DIR, "odds", "**", "2026-05-17*.json"), recursive=True):
        if "manifest" in f:
            continue
        data = json.load(open(f))
        meta = data.get("meta", {})
        league_code = meta.get("league_code", "")
        h = normalize_team(meta.get("home_team", ""))
        a = normalize_team(meta.get("away_team", ""))
        if h and a:
            odds_teams_by_league.setdefault(league_code, []).append((h, a))

    stakes = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "matchday_date": "2026-05-17",
        "leagues": {},
    }

    code_to_key = {"ENG1": "epl", "ESP1": "laliga", "ESP2": "segunda", "ITA1": "seriea"}

    for league_key, config in LEAGUE_CONFIG.items():
        code = config["code"]
        standings = load_standings(league_key)
        if not standings:
            continue

        total = len(standings)
        mp = standings[0]["mp"]
        remaining = config.get("total_matchdays", 38) - mp

        # Build standings with stakes
        classified = []
        for i, t in enumerate(standings):
            stake = describe_stake(t, i + 1, total, config, standings)
            classified.append({
                "pos": i + 1,
                "team": t["team"],
                "pts": t["pts"],
                "w": t["w"], "d": t["d"], "l": t["l"],
                "gf": t["gf"], "ga": t["ga"], "gd": t["gd"],
                "zone": stake["zone"],
                "stake": stake["descriptions"],
            })

        # Pichichi
        scorers = load_scorers(league_key)
        pichichi = build_pichichi(scorers, config["name"])

        # Zamora
        zamora = build_zamora(standings, config["name"], config.get("zamora_name", "Zamora"))

        # Key matches
        odds_teams = odds_teams_by_league.get(code, [])
        key_matches = find_key_matches(standings, config, odds_teams)

        league_data = {
            "name": config["name"],
            "matchday": mp + 1,
            "remaining_after_this": remaining - 1,
            "is_last_matchday": remaining <= 1,
            "standings": classified,
            "pichichi": pichichi,
            "zamora": zamora,
            "key_matches": key_matches,
        }

        stakes["leagues"][code] = league_data
        print(f"  {config['name']}: {len(classified)} teams, {len(key_matches)} key matches, pichichi={'yes' if pichichi else 'no'}")

    # Save
    out_path = os.path.join(BASE_DIR, "stakes.json")
    with open(out_path, "w") as f:
        json.dump(stakes, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out_path} ({os.path.getsize(out_path) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
