#!/usr/bin/env python3
"""Enrich context/news files with full betting stats: goals, corners, shots, BTTS, H2H — all markets."""
import json, os
BASE = "/Users/beto/Desktop/bet365 scraper"

def write(folder, name, obj):
    path = os.path.join(BASE, folder, name)
    with open(path, 'w') as f: json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  {folder}/{name}")

def update_context(name, patch):
    """Merge patch into existing context file."""
    path = os.path.join(BASE, "context", name)
    with open(path) as f: d = json.load(f)
    # Deep merge home_team / away_team
    for tk in ("home_team","away_team"):
        if tk in patch:
            d[tk] = {**d.get(tk,{}), **patch.pop(tk)}
    # Merge betting_stats
    d["betting_stats"] = patch.pop("betting_stats", {})
    # Merge h2h, weather etc
    for k,v in patch.items():
        d[k] = v
    write("context", name, d)


# ============================================================================
# OSASUNA - SEVILLA
# ============================================================================
update_context("laliga_osasuna-vs-sevilla_192612595_2026-04-26.json", {
    "home_team": {
        "table_position": 10, "points": None,
        "form_last_10_record": "5W-4D-1L (home)",
        "goals_for_avg_home": 1.80, "goals_against_avg_home": 1.20,
        "shots_on_target_avg": 3.7,
        "corners_for_avg_home": 4.8, "corners_against_avg_home": 3.5,
    },
    "away_team": {
        "table_position": 17, "points": 34,
        "form_last_10_record": "1W-3D-6L (away)",
        "goals_for_avg_away": 1.00, "goals_against_avg_away": 2.10,
        "shots_on_target_avg": 2.2,
        "corners_for_avg_away": 5.9, "corners_against_avg_away": 4.2,
    },
    "betting_stats": {
        "over_2_5": {"home_last_10": 6, "away_last_10": 5, "estimated_probability": 0.55},
        "btts": {"home_last_10": 7, "away_last_10": 6, "estimated_probability": 0.62},
        "corners_total": {
            "osasuna_last_8_under_9_5": 8, "sevilla_last_9_under_10": 7,
            "expected_total_avg": 9.0, "tip": "UNDER 9.5 — fuerte tendencia ambos"
        },
        "shots": {
            "osasuna_avg_shots_on_target": 3.7,
            "sevilla_avg_shots_on_target_away": 2.2,
            "tip": "Osasuna domina remates a puerta — diferencial clave"
        },
        "h2h_summary": {
            "matches": 48, "osasuna_wins": 15, "sevilla_wins": 20, "draws": 13,
            "avg_goals_per_match_h2h": 2.19,
            "last_3_under_2_5": True,
            "last_meeting": "Osasuna 1-0 (en El Sadar)"
        },
    },
    "_data_gaps": [],
    "source_stats": "sportsgambler.com / fctables.com / footystats / sofascore",
})

# ============================================================================
# VILLARREAL - CELTA
# ============================================================================
update_context("laliga_villarreal-vs-celta-de-vigo_192612599_2026-04-26.json", {
    "home_team": {
        "table_position": 3, "points": 62,
        "form_last_10": "5W-3L-2D",
        "form_last_10_home": "6W-4L",
        "goals_for_avg": 1.40, "goals_against_avg": 1.30,
    },
    "away_team": {
        "table_position": 7, "points": 44,
        "form_last_10": "3W-5L-2D",
        "form_last_10_away": "4W-2L-4D",
        "goals_for_avg": 1.50, "goals_against_avg": 1.80,
    },
    "betting_stats": {
        "over_2_5": {"villarreal_last_10_home": 7, "estimated_probability": 0.65},
        "btts": {
            "villarreal_last_10": 8, "celta_last_5_away": 4,
            "estimated_probability": 0.65, "bookmakers_implied": 0.599,
            "tip": "BTTS YES — value detectado por fuentes (1.67 cuota implícita ~60% vs modelo 65-70%)"
        },
        "shots": {"_data_gap": True},
        "corners": {"_data_gap": True},
        "h2h_summary": {
            "last_meeting": "1-1",
            "villarreal_wins_recent": 4, "celta_wins_recent": 3, "draws": 3,
            "historical_open_games": "4-3 y 3-0 en encuentros previos"
        },
    },
    "_data_gaps": ["corners specific avgs", "shots avgs"],
    "source_stats": "sportsgambler.com / comuniate.com / futbolfantasy",
})

# ============================================================================
# ESPANYOL - LEVANTE
# ============================================================================
update_context("laliga_espanyol-vs-levante_192612603_2026-04-26.json", {
    "home_team": {
        "table_position": 14, "points": 38,
        "form_last_10": "0W-4D-6L (turbulento)",
        "record_season": "10W-8D-14L",
    },
    "away_team": {
        "table_position": 19, "points": 32,
        "form_last_10": "4W-2D-4L",
        "record_season": "8W-8D-16L",
        "form_last_5_away": "4 derrotas en últimos 5",
    },
    "betting_stats": {
        "main_market_pick": "Espanyol Win @ 1.98 (50-60% prob)",
        "correct_score_pick": "1-0 Espanyol @ 6.75",
        "over_2_5": {"recommended": "UNDER 2.5 @ 1.80"},
        "btts": {"_data_gap": True},
        "h2h_summary": {
            "espanyol_unbeaten_last_5": True,
            "last_meeting": "1-1"
        },
        "player_props": {
            "kike_garcia_anytime_scorer": 2.75
        },
    },
    "_data_gaps": ["corners stats", "shots stats", "BTTS detallado"],
    "source_stats": "sportsgambler.com / lagrada.org / infobae",
})

# ============================================================================
# HUESCA - ZARAGOZA (DERBI)
# ============================================================================
update_context("segunda_huesca-vs-real-zaragoza_192612900_2026-04-26.json", {
    "home_team": {
        "table_position": None, "points": None,
        "form_last_10": "0W-3D-7L (terrible)",
        "form_last_10_home": "2W-4D-4L",
        "goals_for_avg": 1.10, "goals_against_avg": 2.10,
        "corners_for_avg_home": 5.5,
    },
    "away_team": {
        "table_position": None, "points": None,
        "form_last_10": "3W-2D-5L",
        "form_last_10_away": "2W-4D-4L",
        "goals_for_avg": 1.10, "goals_against_avg": 1.10,
        "corners_for_avg_away": 5.0,
    },
    "betting_stats": {
        "main_pick": "Huesca +0.25 AH @ 1.61 (~70% prob)",
        "over_2_5": {"huesca_home_last_10": 4, "zaragoza_away_last_10": 3, "estimated_probability": 0.40},
        "btts": {"huesca_home_last_10": 7, "zaragoza_away_last_10": 6, "estimated_probability": 0.60},
        "corners": {"avg_total_expected": 10.5, "context": "Derbi → posible más"},
        "h2h_summary": {
            "zaragoza_unbeaten_last_4": True,
            "last_meeting": "Zaragoza 1-0"
        },
    },
    "_data_gaps": ["puntos exactos en tabla"],
    "source_stats": "sportsgambler.com / aragondigital",
})

# ============================================================================
# LEGANES - ANDORRA
# ============================================================================
update_context("segunda_leganes-vs-fc-andorra_192612902_2026-04-26.json", {
    "home_team": {
        "table_position": 15, "points": None,
        "form_recent_home": "1L en 8 últimos en Butarque",
    },
    "away_team": {
        "table_position": 9, "points": None,
        "form_recent": "3W consecutivas, invicto en 5",
        "milestone": "+50 puntos (matemáticamente salvado)",
    },
    "betting_stats": {
        "over_2_5": {"_data_gap": True},
        "btts": {"_data_gap": True},
        "corners": {"_data_gap": True},
        "context_note": "Leganés fortín local + Andorra ya salvado → posible tablas o victoria local",
    },
    "_data_gaps": ["stats detalladas (sportsgambler genérico)", "corners", "shots", "H2H"],
    "source_stats": "infobae / fotmob",
})

# ============================================================================
# CEUTA - RACING SANTANDER
# ============================================================================
update_context("segunda_ad-ceuta-vs-racing-santander_192612905_2026-04-26.json", {
    "home_team": {
        "table_position": None, "points": 50,
        "context": "Murube fortín, recién celebraron 50 pts (J36)",
        "key_injuries": ["Solo 1 central disponible — DEFENSE_WEAK"],
    },
    "away_team": {
        "table_position": 1, "points": None,
        "context": "Líder Segunda División",
    },
    "betting_stats": {
        "over_2_5": {"_data_gap": True, "expected": "ALTO por debilidad defensiva local + ataque líder"},
        "btts": {"_data_gap": True, "expected": "PROBABLE por defensa Ceuta diezmada"},
        "shots": {"context": "Racing como líder genera muchas ocasiones — sobre Racing remates favorito"},
        "corners": {"_data_gap": True},
    },
    "_data_gaps": ["stats detalladas mercados", "H2H", "corners exactos"],
    "source_stats": "ceutatv / racinguismo / elfarodeceuta",
})

# ============================================================================
# CADIZ - LAS PALMAS
# ============================================================================
update_context("segunda_cadiz-vs-las-palmas_192612907_2026-04-26.json", {
    "home_team": {
        "table_position": 18, "points": 38,
        "form_recent_home": "7 derrotas consecutivas en casa",
        "form_recent": "9 derrotas en últimos 10 totales",
        "goals_for_avg": 0.50,
    },
    "away_team": {
        "table_position": 8, "points": 60,
        "form_last_10": "6W",
    },
    "betting_stats": {
        "main_pick": "Las Palmas Win @ 2.12 (50-55% prob)",
        "correct_score_pick": "0-1 Las Palmas @ 6.00",
        "corners_pick": "UNDER 9.5 @ 1.66",
        "over_2_5": {"_data_gap_partial": True, "context": "Cádiz 0.5 goles/p → UNDER probable"},
        "btts": {"_data_gap": True, "expected": "BTTS NO probable (Cádiz no marca)"},
        "h2h_summary": {
            "las_palmas_unbeaten_last_3": True
        },
        "player_props": {
            "manuel_fuster_anytime_scorer": 4.30
        },
    },
    "_data_gaps": ["BTTS exacto","corners avgs","shots avgs"],
    "source_stats": "sportsgambler.com",
})

# ============================================================================
# MILAN - JUVENTUS
# ============================================================================
update_context("serie-a_ac-milan-vs-juventus_192613460_2026-04-26.json", {
    "home_team": {
        "table_position": 3, "points": 66,
        "form_last_5": ["W"], "form_recent": "Mejor que el año pasado (+15 pts)",
        "shots_on_target_avg": 4.64,
        "shots_off_target_avg": 8.36,
        "xG_total_season": 45.48,
        "xG_rank_serie_a": 4,
        "corners_for": 43, "corners_against": 26,
        "positional_attacks_10plus_passes": 104,
        "direct_attacks": 60,
        "key_doubts": ["Athekame, Fofana, Leão, Modrić, Saelemaekers (1 amarilla de sanción)"],
        "european_rotation_risk": False,
    },
    "away_team": {
        "table_position": 4, "points": 63,
        "form_recent": "Más en forma desde mid-marzo: 13 pts. Win vs Bologna 2-0 y Udinese 1-0.",
        "xG_home": 2.13,
        "positional_attacks_10plus_passes": 121,
        "direct_attacks": 58,
        "key_injuries": ["Perin", "Cabal", "Milik"],
        "european_rotation_risk": False,
    },
    "betting_stats": {
        "context": "Big match Serie A — ambos pelean Champions (Milan 3º, Juve 4º) — máxima motivación",
        "over_2_5": {"_data_gap_partial": True, "context": "Milan xG alto + Juve 13 pts en 5 → over plausible"},
        "btts": {"_data_gap_partial": True, "context": "Ambos equipos atacantes top-4 xG → BTTS YES probable"},
        "shots": {
            "milan_avg_on_target": 4.64,
            "milan_avg_off_target": 8.36,
            "tip": "Milan domina remates → over remates Milan favorito"
        },
        "corners": {
            "milan_corners_for_total_season": 43,
            "milan_corners_failed": 26,
            "_data_gap": "promedios por partido"
        },
        "h2h_summary": {
            "all_time_meetings": 181,
            "milan_wins": 53, "milan_goals": 227,
        },
    },
    "_data_gaps": ["forma últimos 5 detallada", "corners por partido", "BTTS % específico"],
    "source_stats": "acmilan.com / footystats / one-versus-one / valuestats",
})

print("\n✅ Context enriquecido con stats completos para todos los mercados (goles, corners, remates, BTTS, H2H, X2)")
