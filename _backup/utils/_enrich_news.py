#!/usr/bin/env python3
"""Replace news files with all-market betting facts (not just cards)."""
import json, os
BASE = "/Users/beto/Desktop/bet365 scraper"

def write(name, obj):
    path = os.path.join(BASE, "news", name)
    with open(path, 'w') as f: json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  news/{name}")

# ===========================================================================
# OSASUNA - SEVILLA
# ===========================================================================
write("laliga_osasuna-vs-sevilla_192612595_2026-04-26.json", {
    "match": "Osasuna vs Sevilla", "FI": "192612595",
    "summary": "Osasuna (10º) vs Sevilla (17º, 34 pts) en lucha por descenso. Sevilla 4 derrotas en 5. Marcao baja resto temporada. Osasuna recupera Catena+Osambela. H2H 48 partidos: avg 2.19 goles. Últimos 3 H2H bajo 2.5 goles.",
    "headlines": [
        {"date":"2026-04-26","title":"Marcao baja por el resto de la temporada","source":"jornadaperfecta.com","relevance":"high"},
        {"date":"2026-04-26","title":"Osasuna recupera a Catena y Osambela","source":"jornadaperfecta.com","relevance":"medium"},
        {"date":"2026-04-25","title":"Sevilla en zona de descenso a 1 pt","source":"futbolfantasy.com","relevance":"high"},
    ],
    "key_facts_for_betting": {
        "1X2_X2": [
            "Osasuna home 5W-4D-1L últimos 10 → LOCAL_FUERTE en El Sadar",
            "Sevilla away 1W-3D-6L → VISITANTE_DEBIL",
            "Pick claro: Osasuna gana o doble oportunidad 1X"
        ],
        "goles": [
            "Osasuna marca 1.80, recibe 1.20 en casa",
            "Sevilla marca 1.00, recibe 2.10 fuera",
            "H2H avg 2.19 goles | últimos 3 H2H UNDER 2.5",
            "Goles esperados: ~2.6 — line over 2.5 ajustado",
            "BTTS implícito 62% — pick BTTS YES tiene valor sobre cuotas <1.85"
        ],
        "corners": [
            "Osasuna 4.8 a favor / 3.5 contra en casa",
            "Sevilla 5.9 a favor / 4.2 contra fuera",
            "Osasuna últimos 8 todos UNDER 9.5 corners",
            "Sevilla 7 de 9 últimos UNDER 10 corners",
            "Pick claro: UNDER 9.5 CORNERS — alta probabilidad ~75%",
            "Por equipo: Sevilla 5.9 — over 4.5 corners Sevilla viable"
        ],
        "remates": [
            "Osasuna 3.7 a puerta avg",
            "Sevilla 2.2 a puerta avg fuera (bajo)",
            "OVER remates Osasuna favorito vs UNDER remates Sevilla"
        ],
        "tarjetas": [
            "Árbitro Ortiz Arias 4.04 TA/p → MEDIO",
            "Sevilla en lucha descenso → +0.5 tarjetas esperadas (relegation_battle)",
            "Pick tarjetas: cauteloso, line 4.5 puede tener valor"
        ],
        "jugadores": [
            "Akor Adams (Sevilla) titular — 8 goles temporada",
            "Ante Budimir (Osasuna) referencia ataque local — over 1.5 remates plausible"
        ]
    },
    "_data_gaps": []
})

# ===========================================================================
# VILLARREAL - CELTA
# ===========================================================================
write("laliga_villarreal-vs-celta-de-vigo_192612599_2026-04-26.json", {
    "match": "Villarreal vs Celta de Vigo", "FI": "192612599",
    "summary": "Villarreal (3º, 62 pts, plaza Champions) recibe a Celta (7º, 44 pts) tocado: 4 derrotas seguidas (Barça + Freiburg×2 + Oviedo). Marcelino sin rotaciones. Bajas Celta: Starfelt, Miguel Román.",
    "headlines": [
        {"date":"2026-04-25","title":"Marcelino: 'No habrá rotaciones'","source":"comuniate.com","relevance":"high"},
        {"date":"2026-04-25","title":"Celta acumula 4 derrotas tras Europa","source":"comuniate.com","relevance":"high"},
        {"date":"2026-04-25","title":"Pépé: 13 goles + 14 asistencias","source":"futbolfantasy.com","relevance":"medium"},
    ],
    "key_facts_for_betting": {
        "1X2_X2": [
            "Villarreal 3º, motivación máxima Champions",
            "Villarreal 6W-4L últimos 10 en casa",
            "Celta 4 derrotas consecutivas — momentum negativo",
            "Pick: Villarreal Win o 1X — value alto"
        ],
        "goles": [
            "Villarreal 1.40 a favor / 1.30 en contra",
            "Celta 1.50 a favor / 1.80 en contra",
            "BTTS YES en 8/10 últimos Villarreal — fuerte",
            "Celta away BTTS YES 4 de últimos 5",
            "Over 2.5 hit en 7/10 últimos Villarreal home",
            "Pick fuerte: BTTS YES (modelo 65-70% vs implícita 60% @ 1.67) — VALUE",
            "H2H histórico abierto: 4-3 y 0-3 — over 2.5 plausible"
        ],
        "corners": [
            "Stats específicas no disponibles — DATA_GAP",
            "Villarreal estilo posesión + Celta defensa débil → corners Villarreal alto"
        ],
        "remates": [
            "Pépé generador clave (13G+14A) — over remates jugador top",
            "Celta defensa débil (4 derrotas + 1.80 contra) → over remates Villarreal"
        ],
        "tarjetas": [
            "Árbitro Quintero González — segunda amarilla 0.2/p, expulsiones directas más altas LaLiga",
            "Celta en mal momento + presión → más faltas",
            "Pick tarjetas: line 5.5 puede tener valor"
        ],
        "jugadores": [
            "Pépé (Villarreal) — over remates a puerta y over goles a/asist",
            "Mikautadze (Villarreal) 9 goles — anytime scorer plausible",
            "Borja Iglesias (Celta) gestionado en minutos — risk",
            "Fer López (Celta) capitán fantasy"
        ]
    },
    "_data_gaps": ["corners stats", "shots avgs"]
})

# ===========================================================================
# ESPANYOL - LEVANTE
# ===========================================================================
write("laliga_espanyol-vs-levante_192612603_2026-04-26.json", {
    "match": "Espanyol vs Levante", "FI": "192612603",
    "summary": "Espanyol (14º, 38 pts) cae 0-1 ante Rayo, momento delicado. Levante (19º, 32 pts) llega tras 2-0 a Sevilla. Espanyol pierde a Puado (LCA hasta sept). H2H Espanyol invicto últimos 5.",
    "headlines": [
        {"date":"2026-04-26","title":"Espanyol cae ante Rayo, momento delicado","source":"infobae.com","relevance":"high"},
        {"date":"2026-04-25","title":"Levante venció 2-0 al Sevilla","source":"infobae.com","relevance":"high"},
        {"date":"2026-04-25","title":"Javi Puado fuera por rotura LCA hasta sept","source":"lagrada.org","relevance":"medium"},
    ],
    "key_facts_for_betting": {
        "1X2_X2": [
            "Pick principal: Espanyol Win @ 1.98 (~55-60% prob)",
            "Espanyol H2H invicto últimos 5",
            "Levante 4 derrotas en últimos 5 fuera",
            "Espanyol 6L-4D en últimos 10 (turbulento)"
        ],
        "goles": [
            "Pick recomendado: UNDER 2.5 goles @ 1.80",
            "Correct score pick: 1-0 Espanyol @ 6.75",
            "Espanyol creador Puado baja → ATTACK_LOW",
            "Last meeting 1-1 — partidos cerrados"
        ],
        "corners": [
            "Stats específicas no disponibles — DATA_GAP",
            "Espanyol estilo defensivo + Levante busca permanencia → posible bajo total"
        ],
        "remates": [
            "Sin Puado, remates Espanyol bajan",
            "Levante necesita arriesgar — remates Levante posible alza"
        ],
        "tarjetas": [
            "Árbitro NO confirmado — bloquear picks tarjetas hasta verificar lunes 27"
        ],
        "jugadores": [
            "Kike García (Espanyol) anytime scorer @ 2.75 — pick recomendado",
            "Roger Brugué (Levante) baja"
        ]
    },
    "_data_gaps": ["árbitro", "corners detallados", "BTTS exacto"]
})

# ===========================================================================
# HUESCA - ZARAGOZA
# ===========================================================================
write("segunda_huesca-vs-real-zaragoza_192612900_2026-04-26.json", {
    "match": "Huesca vs Real Zaragoza", "FI": "192612900",
    "summary": "Derbi aragonés agónico — ambos zona descenso a Primera RFEF. Huesca 7L-3D en 10. Zaragoza invicto vs Huesca últimos 4. Árbitro Arcediano (5.33 TA/p — ALTO).",
    "headlines": [
        {"date":"2026-04-25","title":"El derbi aragonés más agónico de la historia","source":"sportaragon.com","relevance":"high"},
        {"date":"2026-04-26","title":"Arcediano arbitrará el derbi","source":"sportaragon.com","relevance":"high"},
    ],
    "key_facts_for_betting": {
        "1X2_X2": [
            "Pick value: Huesca +0.25 AH @ 1.61 (~70% prob)",
            "Zaragoza invicto vs Huesca últimos 4 — H2H favorable",
            "Ambos en idéntico récord home/away (2W-4D-4L) — partido equilibrado",
        ],
        "goles": [
            "Huesca 1.10 favor / 2.10 contra — defensa débil local",
            "Zaragoza 1.10 favor / 1.10 contra — equilibrado",
            "Over 2.5: solo 4/10 Huesca home, 3/10 Zaragoza away — UNDER 2.5 favorito",
            "BTTS YES: 7/10 Huesca, 6/10 Zaragoza — viable BTTS YES + UNDER 2.5 combo",
            "Last meeting: Zaragoza 1-0"
        ],
        "corners": [
            "Huesca 5.5 corners home avg",
            "Zaragoza 5.0 corners away avg",
            "Total esperado ~10.5 — line 9.5 over plausible (derbi → más)"
        ],
        "remates": [
            "Datos específicos no disponibles — DATA_GAP",
            "Derbi → más intensidad → over remates plausible"
        ],
        "tarjetas": [
            "✓ PICK FUERTE: Árbitro Arcediano 5.33 TA/p → ALTO",
            "Derbi aragonés → +0.5 a +1 tarjeta extra esperada",
            "Tarjetas total: line 5.5 over con value (modelo ~6-7 esperadas)",
            "Tarjetas por equipo: ambos line 2.5 over plausible"
        ]
    },
    "_data_gaps": ["shots avgs"]
})

# ===========================================================================
# LEGANES - ANDORRA
# ===========================================================================
write("segunda_leganes-vs-fc-andorra_192612902_2026-04-26.json", {
    "match": "Leganés vs FC Andorra", "FI": "192612902",
    "summary": "Leganés (15º) busca permanencia. Fortín en Butarque (1L en 8 últimos). Andorra (9º) en racha 3W consecutivas, +50 pts (salvado). Posible relajación visitante.",
    "headlines": [
        {"date":"2026-04-25","title":"Andorra ilusiona: 3 victorias seguidas","source":"infobae.com","relevance":"high"},
    ],
    "key_facts_for_betting": {
        "1X2_X2": [
            "Leganés home 1L en 8 → fortín local",
            "Andorra ya salvado (50+ pts) → posible relajación motivacional",
            "Pick: Leganés Win o 1X plausible (motivación + casa)"
        ],
        "goles": [
            "DATA_GAP — pero contexto: Leganés sólido en casa, Andorra en racha → partido cerrado",
            "Posible UNDER 2.5 por defensa Leganés home"
        ],
        "corners": ["Sin datos específicos"],
        "remates": ["Sin datos específicos"],
        "tarjetas": [
            "Árbitro NO confirmado — BLOQUEAR picks tarjetas",
            "Re-verificar el día del partido"
        ],
        "jugadores": ["Sin datos específicos"]
    },
    "_data_gaps": ["árbitro","goles avgs","corners","remates","H2H"]
})

# ===========================================================================
# CEUTA - RACING
# ===========================================================================
write("segunda_ad-ceuta-vs-racing-santander_192612905_2026-04-26.json", {
    "match": "AD Ceuta vs Racing Santander", "FI": "192612905",
    "summary": "Ceuta (50 pts) recibe al líder Racing con defensa diezmada — solo 1 central disponible. Murube fortín, pero contexto desfavorable. Árbitro Mallo (4.86 TA/p — ALTO).",
    "headlines": [
        {"date":"2026-04-24","title":"Ceuta solo tiene un central disponible","source":"ceutatv.com","relevance":"high"},
        {"date":"2026-04-25","title":"Eder Mallo arbitrará el partido","source":"ceutatv.com","relevance":"high"},
    ],
    "key_facts_for_betting": {
        "1X2_X2": [
            "Racing líder Segunda — favorito",
            "Ceuta defensa weak (1 central) — desventaja estructural",
            "Pero Ceuta motivación playoff (50 pts) + fortín Murube",
            "Pick: Racing Win pero con cuidado"
        ],
        "goles": [
            "Sin avgs exactos pero defensa Ceuta diezmada → over goles Racing",
            "BTTS YES probable (Ceuta marca en casa, Racing como líder marca casi siempre)"
        ],
        "corners": [
            "Sin datos específicos",
            "Racing como dominador → corners Racing favorito"
        ],
        "remates": [
            "Racing líder → ATTACK_HIGH → over remates Racing fuerte pick",
            "Sobre remates a puerta Racing también"
        ],
        "tarjetas": [
            "✓ Árbitro Mallo 4.86 TA/p → ALTO",
            "Pick tarjetas total line 4.5+ over plausible",
            "Bajas Ceuta defensa → más faltas locales → over tarjetas Ceuta"
        ]
    },
    "_data_gaps": ["goles avgs específicos","corners","H2H"]
})

# ===========================================================================
# CADIZ - LAS PALMAS
# ===========================================================================
write("segunda_cadiz-vs-las-palmas_192612907_2026-04-26.json", {
    "match": "Cádiz vs Las Palmas", "FI": "192612907",
    "summary": "Cádiz (18º, 38 pts) en CRISIS: 7 derrotas seguidas en casa, 9 derrotas en últimos 10. Solo 0.5 goles/p. Las Palmas (8º, 60 pts) viene de 6 victorias en 10. H2H Las Palmas invicto últimos 3.",
    "headlines": [],
    "key_facts_for_betting": {
        "1X2_X2": [
            "✓ PICK FUERTE: Las Palmas Win @ 2.12 (~50-55% prob — VALUE vs implícita 47%)",
            "Cádiz 9 derrotas en 10 — ATTACK_NULO + DEFENSE_VULNERABLE",
            "Las Palmas momentum (6W en 10)",
            "Doble oportunidad X2 también muy sólida"
        ],
        "goles": [
            "Cádiz 0.5 goles/p — UNDER 2.5 favorito",
            "Correct score pick: 0-1 Las Palmas @ 6.00",
            "BTTS NO probable (Cádiz no marca)"
        ],
        "corners": [
            "✓ PICK: UNDER 9.5 CORNERS @ 1.66 (recomendación analistas)"
        ],
        "remates": [
            "Cádiz remates muy bajos (0.5 G/p) — UNDER remates Cádiz fuerte"
        ],
        "tarjetas": [
            "Árbitro NO confirmado — BLOQUEAR picks tarjetas hasta verificar"
        ],
        "jugadores": [
            "✓ Manuel Fuster (Las Palmas) anytime scorer @ 4.30 — pick value"
        ]
    },
    "_data_gaps": ["árbitro","forma últimos 5 detallada","H2H estats completos"]
})

# ===========================================================================
# MILAN - JUVENTUS
# ===========================================================================
write("serie-a_ac-milan-vs-juventus_192613460_2026-04-26.json", {
    "match": "AC Milan vs Juventus", "FI": "192613460",
    "summary": "Big match: Milan (3º, 66 pts) vs Juve (4º, 63 pts). Ambos pelean Champions. Juve mejor en forma (13 pts en 5). Milan +15 pts vs misma posición temp pasada. Sozza (4.64 TA/p ALTO) arbitra. H2H 181 partidos: 53W Milan.",
    "headlines": [
        {"date":"2026-04-23","title":"Sozza designato per Milan-Juve","source":"sport.sky.it","relevance":"high"},
        {"date":"2026-04-25","title":"Juve ha collezionato 13 punti dalla mid-marzo","source":"acmilan.com","relevance":"high"},
        {"date":"2026-04-25","title":"Milan a piena rosa — Juve senza Perin/Cabal/Milik","source":"acmilan.com","relevance":"medium"},
    ],
    "key_facts_for_betting": {
        "1X2_X2": [
            "Big match — partido equilibrado por puntos (3 de diferencia)",
            "Milan en casa San Siro + plantilla completa",
            "Juve mejor momento reciente",
            "Pick conservador: Doble oportunidad 1X o BTTS"
        ],
        "goles": [
            "Milan top 4 xG (45.48 total)",
            "Juve xG home 2.13",
            "Ambos atacantes top → BTTS YES probable",
            "Over 2.5 plausible (ambos generan ocasiones)"
        ],
        "corners": [
            "Milan 43 corners a favor / 26 fallidos",
            "Datos avg por partido no disponibles",
            "Ambos estilo posesión → corners totales medio-alto"
        ],
        "remates": [
            "✓ Milan 4.64 a puerta + 8.36 fuera = 13 remates totales avg",
            "Pick: over remates totales Milan favorito",
            "Over remates a puerta totales del partido también plausible (>9)"
        ],
        "tarjetas": [
            "✓ PICK FUERTE: Sozza 4.64 TA/p → ALTO",
            "Big match histórico con tensión → +0.5 tarjetas extra",
            "Pick total tarjetas line 5.5 over con value",
            "VAR Abisso (más revisiones esperables)"
        ],
        "jugadores": [
            "Milan: Athekame/Fofana/Leão/Modrić/Saelemaekers a 1 amarilla de sanción → más cuidado o más tarjetas",
            "Juve: ataque Yildiz/Vlahovic — anytime scorer plausible"
        ]
    },
    "_data_gaps": ["forma últimos 5 detallada","corners avg por partido","BTTS % específico"]
})

print("\n✅ Todos los news enriquecidos con key_facts_for_betting por mercado: 1X2/X2, goles, corners, remates, tarjetas, jugadores")
