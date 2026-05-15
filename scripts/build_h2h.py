#!/usr/bin/env python3
"""
Build per-match H2H (head-to-head) files for the Franken agent.

Reads:
  - odds/manifest.json                    (list of upcoming matches)
  - matches/{league}/{season}.json         (historical match data, last 5 seasons)

Generates:
  - h2h/{league_dir}/{match_id}.json       (last N H2H + aggregates)

Aggregates include: total H2H, W/D/L from current home POV, BTTS%, O/U 2.5%,
average corners and cards per match.

Usage:
  python3 scripts/build_h2h.py
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
MATCHES_DIR = os.path.join(BASE_DIR, "matches")
H2H_DIR = os.path.join(BASE_DIR, "h2h")

# odds league_code -> matches/ subdir to search for H2H
# FA Cup teams are PL teams, so search in epl history.
LEAGUE_CODE_TO_MATCHES_DIR = {
    "ENG1": "epl",
    "ESP1": "laliga",
    "ESP2": "segunda",
    "ITA1": "seriea",
    "ENG_FA": "epl",
    "GER1": "bundesliga",
    "FRA1": "ligue1",
    "POR1": "portugal",
}

MAX_LAST_MATCHES = 10  # store at most this many recent H2H games


def load_all_seasons(matches_subdir):
    """Load every season JSON for a league, return flat list of matches with season tag."""
    pattern = os.path.join(MATCHES_DIR, matches_subdir, "*.json")
    all_matches = []
    for fp in sorted(glob.glob(pattern)):
        # Skip non-season files like league_phase_*.json
        try:
            data = json.load(open(fp))
        except Exception:
            continue
        season = data.get("season") or os.path.basename(fp).replace(".json", "")
        for m in data.get("matches", []):
            m_copy = dict(m)
            m_copy["_season"] = season
            all_matches.append(m_copy)
    return all_matches


def filter_h2h(all_matches, home_norm, away_norm):
    """Return matches where the two teams played each other (in any order)."""
    out = []
    for m in all_matches:
        mh = normalize_team(m.get("home", ""))
        ma = normalize_team(m.get("away", ""))
        if (mh == home_norm and ma == away_norm) or (mh == away_norm and ma == home_norm):
            out.append(m)
    return out


def parse_date(d):
    """Parse 'DD/MM/YYYY' or ISO date. Return sortable string."""
    if not d:
        return ""
    if "/" in d:
        parts = d.split("/")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    return d


def aggregate(h2h_matches, home_norm, away_norm):
    """Compute aggregates from the H2H list, all from current home POV."""
    if not h2h_matches:
        return {
            "total": 0,
            "home_wins": 0, "draws": 0, "away_wins": 0,
            "btts_pct": None, "over_2_5_pct": None,
            "avg_corners": None, "avg_yellow": None, "avg_red": None,
        }

    n = len(h2h_matches)
    home_w = draws = away_w = 0
    btts_count = ou_count = 0
    corners_sum = yellow_sum = red_sum = 0
    corners_n = yellow_n = red_n = 0

    for m in h2h_matches:
        mh = normalize_team(m.get("home", ""))
        fh = m.get("ft_home")
        fa = m.get("ft_away")

        if fh is None or fa is None:
            continue

        # WDL from the current upcoming match's home POV
        if mh == home_norm:
            if fh > fa: home_w += 1
            elif fh < fa: away_w += 1
            else: draws += 1
        else:
            # roles swapped in historic record
            if fa > fh: home_w += 1
            elif fa < fh: away_w += 1
            else: draws += 1

        if fh > 0 and fa > 0:
            btts_count += 1
        if (fh + fa) > 2.5:
            ou_count += 1

        hc, ac = m.get("home_corners"), m.get("away_corners")
        if hc is not None and ac is not None:
            corners_sum += hc + ac
            corners_n += 1

        hy, ay = m.get("home_yellow"), m.get("away_yellow")
        if hy is not None and ay is not None:
            yellow_sum += hy + ay
            yellow_n += 1

        hr, ar = m.get("home_red"), m.get("away_red")
        if hr is not None and ar is not None:
            red_sum += hr + ar
            red_n += 1

    return {
        "total": n,
        "home_wins": home_w,
        "draws": draws,
        "away_wins": away_w,
        "btts_pct": round(100 * btts_count / n, 1),
        "over_2_5_pct": round(100 * ou_count / n, 1),
        "avg_corners": round(corners_sum / corners_n, 2) if corners_n else None,
        "avg_yellow": round(yellow_sum / yellow_n, 2) if yellow_n else None,
        "avg_red": round(red_sum / red_n, 2) if red_n else None,
    }


def trim_match(m):
    """Keep only fields useful for the agent."""
    return {
        "date": parse_date(m.get("date", "")),
        "season": m.get("_season"),
        "home": m.get("home"),
        "away": m.get("away"),
        "ft_home": m.get("ft_home"),
        "ft_away": m.get("ft_away"),
        "ht_home": m.get("ht_home"),
        "ht_away": m.get("ht_away"),
        "home_corners": m.get("home_corners"),
        "away_corners": m.get("away_corners"),
        "home_yellow": m.get("home_yellow"),
        "away_yellow": m.get("away_yellow"),
        "home_red": m.get("home_red"),
        "away_red": m.get("away_red"),
    }


def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def main():
    print("=" * 60)
    print("Build per-match H2H files")
    print("=" * 60)

    manifest_path = os.path.join(ODDS_DIR, "manifest.json")
    manifest = json.load(open(manifest_path))
    upcoming = manifest.get("matches_upcoming", [])

    # Pre-load all seasons per league dir (cache)
    cache = {}

    generated = 0
    empty = 0
    unsupported = 0

    for match in upcoming:
        match_id = match["match_id"]
        league_code = match["league"]
        league_dir = match["urls"]["odds"].split("/odds/")[1].split("/")[0]
        matches_subdir = LEAGUE_CODE_TO_MATCHES_DIR.get(league_code)

        if not matches_subdir:
            print(f"  SKIP {match_id}: no historical matches for league {league_code}")
            unsupported += 1
            continue

        if matches_subdir not in cache:
            cache[matches_subdir] = load_all_seasons(matches_subdir)

        h_norm = normalize_team(match["home"])
        a_norm = normalize_team(match["away"])

        h2h_list = filter_h2h(cache[matches_subdir], h_norm, a_norm)
        h2h_list.sort(key=lambda m: parse_date(m.get("date", "")), reverse=True)
        last_n = h2h_list[:MAX_LAST_MATCHES]

        agg = aggregate(h2h_list, h_norm, a_norm)

        if agg["total"] == 0:
            print(f"  EMPTY {match_id}: no H2H found (norm: {h_norm} vs {a_norm})")
            empty += 1
            # Still write a minimal file so the agent gets a consistent contract
            payload = {
                "match_id": match_id,
                "home": match["home"],
                "away": match["away"],
                "league": league_code,
                "date": match_id[:10],
                "source_seasons": matches_subdir,
                "h2h_count": 0,
                "aggregates": agg,
                "last_matches": [],
                "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        else:
            payload = {
                "match_id": match_id,
                "home": match["home"],
                "away": match["away"],
                "league": league_code,
                "date": match_id[:10],
                "source_seasons": matches_subdir,
                "h2h_count": agg["total"],
                "aggregates": agg,
                "last_matches": [trim_match(m) for m in last_n],
                "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

        out_path = os.path.join(H2H_DIR, league_dir, f"{match_id}.json")
        ensure_dir(out_path)
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        if agg["total"] > 0:
            generated += 1

    print(f"\nResults:")
    print(f"  Files with H2H data: {generated}")
    print(f"  Files empty (no historical match): {empty}")
    print(f"  Unsupported leagues: {unsupported}")
    print(f"  Total processed: {len(upcoming)}")
    print("Done!")


if __name__ == "__main__":
    main()
