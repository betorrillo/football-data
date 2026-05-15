#!/usr/bin/env python3
"""Generate referees/context/lineups/news JSON files from gathered web research."""
import json, os, datetime
BASE = "/Users/beto/Desktop/bet365 scraper"
TODAY = "2026-04-26"

def write(folder, name, obj):
    path = os.path.join(BASE, folder, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path

def verdict(yc):
    if yc is None: return None, "stats no disponibles"
    if yc >= 4.5: return "ALTO", f"{yc} TA/p ≥ 4.5 → ALTO"
    if yc >= 3.5: return "MEDIO", f"{yc} TA/p en 3.5-4.5 → MEDIO"
    return "BAJO", f"{yc} TA/p < 3.5 → BAJO"


# ============================================================================
# REFEREES
# ============================================================================
refs = [
    # LaLiga
    {
        "fname": "laliga_osasuna-vs-sevilla_192612595_2026-04-26.json",
        "match": "Osasuna vs Sevilla", "FI": "192612595", "competition": "LaLiga", "kickoff": "2026-04-26T18:30:00",
        "referee": "Miguel Ángel Ortiz Arias",
        "verified_date": "2026-04-26", "is_same_day": True,
        "source": "estadisticaslaliga.es / valuestats.com / dazn.com",
        "stats": {"yellow_cards_per_match": 4.04, "red_cards_per_match": 0.23, "fouls_per_match": None,
                  "matches_total_career": 71, "yellows_total_career": 295, "reds_total_career": 18, "season": "2025-26"},
        "_data_gaps": ["fouls_per_match"],
    },
    {
        "fname": "laliga_villarreal-vs-celta-de-vigo_192612599_2026-04-26.json",
        "match": "Villarreal vs Celta de Vigo", "FI": "192612599", "competition": "LaLiga", "kickoff": "2026-04-26T21:00:00",
        "referee": "Alejandro Quintero González",
        "verified_date": "2026-04-26", "is_same_day": True,
        "source": "valuestats.com / es.whoscored.com",
        "stats": {"yellow_cards_per_match": None, "red_cards_per_match": 0.5, "second_yellow_per_match": 0.2,
                  "matches_total_career": None, "season": "2025-26",
                  "note": "Tasa más alta de expulsiones directas en LaLiga 2025-26"},
        "_data_gaps": ["yellow_cards_per_match (no encontrado en fuentes públicas)"],
    },
    {
        "fname": "laliga_espanyol-vs-levante_192612603_2026-04-26.json",
        "match": "Espanyol vs Levante", "FI": "192612603", "competition": "LaLiga", "kickoff": "2026-04-27T21:00:00",
        "referee": None,
        "verified_date": "2026-04-26", "is_same_day": False,
        "source": None,
        "stats": None,
        "_data_gaps": ["referee (designación no encontrada en RFEF/LaLiga sources al momento del scrape)",
                       "Re-verificar el lunes 27 antes del kickoff"],
    },
    # Segunda
    {
        "fname": "segunda_huesca-vs-real-zaragoza_192612900_2026-04-26.json",
        "match": "Huesca vs Real Zaragoza", "FI": "192612900", "competition": "Segunda División", "kickoff": "2026-04-26T18:30:00",
        "referee": "Dámaso Arcediano Monescillo",
        "verified_date": "2026-04-26", "is_same_day": True,
        "source": "valuestats.com / sportaragon.com",
        "stats": {"yellow_cards_per_match": 5.33, "red_cards_per_match": 0.22, "matches_this_season": 9,
                  "matches_career_segunda": 19, "experience_years": 14, "season": "2025-26"},
        "_data_gaps": [],
    },
    {
        "fname": "segunda_leganes-vs-fc-andorra_192612902_2026-04-26.json",
        "match": "Leganés vs FC Andorra", "FI": "192612902", "competition": "Segunda División", "kickoff": "2026-04-26T16:30:00",
        "referee": None,
        "verified_date": "2026-04-26", "is_same_day": False,
        "source": None, "stats": None,
        "_data_gaps": ["referee (no asignado/no encontrado al momento del scrape)"],
    },
    {
        "fname": "segunda_ad-ceuta-vs-racing-santander_192612905_2026-04-26.json",
        "match": "AD Ceuta vs Racing Santander", "FI": "192612905", "competition": "Segunda División", "kickoff": "2026-04-26T21:00:00",
        "referee": "Eder Mallo Fernández",
        "verified_date": "2026-04-26", "is_same_day": True,
        "source": "ceutatv.com / besoccer.com / transfermarkt",
        "stats": {"yellow_cards_per_match": 4.86, "red_cards_per_match": 0.10, "matches_this_season_segunda": 14,
                  "season": "2025-26", "yellows_per_season_total": 102, "matches_per_season": 21,
                  "note": "Primera temporada en Segunda División, debutó 2024-25"},
        "_data_gaps": [],
    },
    {
        "fname": "segunda_cadiz-vs-las-palmas_192612907_2026-04-26.json",
        "match": "Cádiz vs Las Palmas", "FI": "192612907", "competition": "Segunda División", "kickoff": "2026-04-27T19:30:00",
        "referee": None,
        "verified_date": "2026-04-26", "is_same_day": False,
        "source": None, "stats": None,
        "_data_gaps": ["referee no encontrado para fecha 27/04 (el resultado de cadizcf.com era de jornada 33, no 37)",
                       "Re-verificar lunes 27"],
    },
    # Serie A
    {
        "fname": "serie-a_ac-milan-vs-juventus_192613460_2026-04-26.json",
        "match": "AC Milan vs Juventus", "FI": "192613460", "competition": "Serie A", "kickoff": "2026-04-26T20:45:00",
        "referee": "Simone Sozza",
        "verified_date": "2026-04-26", "is_same_day": True,
        "source": "sport.sky.it / corrieredellosport / valuestats.com",
        "stats": {"yellow_cards_per_match": 4.64, "red_cards_per_match": 0.12,
                  "matches_2024_25": 21, "yellows_2024_25": 100, "reds_2024_25": 2, "penalties_2024_25": 10,
                  "season": "2025-26",
                  "var": "Abisso", "avar": "Maresca", "fourth_official": "Zufferli", "assistants": ["Perrotti", "M. Rossi"]},
        "_data_gaps": ["yellow_cards_per_match es promedio histórico, no específico 2025-26"],
    },
]

for r in refs:
    name = r.pop("fname")
    yc = (r.get("stats") or {}).get("yellow_cards_per_match")
    v, reason = verdict(yc)
    r["match_date"] = TODAY
    r["verdict"] = v
    r["verdict_reason"] = reason
    write("referees", name, r)
    print(f"  referees/{name}")


# ============================================================================
# CONTEXT
# ============================================================================
ctx = [
    {
        "fname": "laliga_osasuna-vs-sevilla_192612595_2026-04-26.json",
        "match": "Osasuna vs Sevilla", "FI": "192612595", "competition": "LaLiga", "kickoff": "2026-04-26T18:30:00",
        "stadium": "El Sadar (Pamplona)",
        "home_team": {"name":"Osasuna","table_position":10,"points":None,"form_last_5":["D","D","L","L","W"],
                      "motivation":"midtable","european_rotation_risk":False,
                      "key_injuries":["Iker Benito (lesión larga duración)"], "key_suspensions":[],
                      "_recovered": ["Alejandro Catena","Asier Osambela"]},
        "away_team": {"name":"Sevilla","table_position":17,"points":34,"form_last_5":["L","L","L","L","W"],
                      "motivation":"relegation_battle","european_rotation_risk":False,
                      "key_injuries":["Marcao (resto temporada)"], "key_suspensions":[],
                      "_doubtful":["César Azpilicueta"]},
        "h2h_last_5": [], "weather": {"city":"Pamplona","temp_celsius":24,"wind_kmh":16,"conditions":None,"rain_probability":None},
        "_data_gaps": ["puntos exactos Osasuna","H2H","rain_probability","conditions"],
        "source":"futbolfantasy.com / jornadaperfecta.com / Marca",
    },
    {
        "fname": "laliga_villarreal-vs-celta-de-vigo_192612599_2026-04-26.json",
        "match": "Villarreal vs Celta de Vigo", "FI": "192612599", "competition": "LaLiga", "kickoff": "2026-04-26T21:00:00",
        "stadium": "Estadio de la Cerámica (Villarreal)",
        "home_team": {"name":"Villarreal","table_position":3,"points":None,"form_last_5":["D"],
                      "motivation":"champions_league_qualification","european_rotation_risk":False,
                      "key_injuries":["Foyth","Pau Cabanes","Logan Costa"], "key_doubts":["Mouriño"], "key_suspensions":[],
                      "manager_note":"Marcelino dijo que no habrá rotaciones"},
        "away_team": {"name":"Celta de Vigo","table_position":None,"points":None,"form_last_5":["L","L","L","L"],
                      "motivation":"midtable","european_rotation_risk":True,
                      "key_injuries":["Carl Starfelt (lumbalgia)","Miguel Román (fractura pie ~3 meses)"],
                      "key_suspensions":[], "key_doubts":["Borja Iglesias","Marcos Alonso","Ilaix Moriba (gestión minutos)"],
                      "european_context": "Eliminados Europa League ante Freiburg"},
        "h2h_last_5": ["Villarreal 4-3 Celta (temp pasada)","Celta 3-0 Villarreal (temp pasada)"],
        "weather":{"city":"Villarreal","temp_celsius":None,"wind_kmh":None,"conditions":None,"rain_probability":None},
        "_data_gaps":["puntos exactos","posición Celta","weather completo"],
        "source":"comuniate.com / futbolfantasy.com",
    },
    {
        "fname": "laliga_espanyol-vs-levante_192612603_2026-04-26.json",
        "match": "Espanyol vs Levante", "FI": "192612603", "competition": "LaLiga", "kickoff": "2026-04-27T21:00:00",
        "stadium": "RCDE Stadium (Cornellà-El Prat)",
        "home_team": {"name":"Espanyol","table_position":12,"points":38,"record":"10W-8D-14L",
                      "motivation":"midtable","european_rotation_risk":False,
                      "key_injuries":["Javi Puado (rotura LCA, hasta septiembre)"],
                      "key_suspensions":[], "_recovered":["Urko González (cumplió sanción)"],
                      "form_last_5":["L"], "last_match":"0-1 vs Rayo Vallecano (derrota)"},
        "away_team": {"name":"Levante","table_position":19,"points":32,"record":"8W-8D-16L",
                      "motivation":"relegation_battle","european_rotation_risk":False,
                      "key_injuries":["Roger Brugué (hasta mayo)"], "key_doubts":["Unai Elgezabal"],
                      "key_suspensions":[],
                      "form_last_5":["W"], "last_match":"2-0 vs Sevilla (victoria)"},
        "h2h_last_5":[],
        "weather":{"city":"Barcelona","temp_celsius":None,"wind_kmh":None,"conditions":None,"rain_probability":None},
        "_data_gaps":["forma_last_5 completo (solo último resultado)","H2H","weather"],
        "source":"infobae.com / lagrada.org / eldesmarque",
    },
    {
        "fname": "segunda_huesca-vs-real-zaragoza_192612900_2026-04-26.json",
        "match": "Huesca vs Real Zaragoza", "FI": "192612900", "competition": "Segunda División", "kickoff": "2026-04-26T18:30:00",
        "stadium": "El Alcoraz (Huesca)",
        "home_team": {"name":"SD Huesca","table_position":None,"points":None,
                      "motivation":"relegation_battle","european_rotation_risk":False,
                      "_note":"Posición relegación a Primera RFEF","manager":"José Luis Oltra (primer derbi aragonés)"},
        "away_team": {"name":"Real Zaragoza","table_position":None,"points":None,
                      "motivation":"relegation_battle","european_rotation_risk":False,
                      "_note":"Posición relegación a Primera RFEF","manager":"David Navarro"},
        "h2h_last_5":[],
        "weather":{"city":"Huesca","temp_celsius":None,"wind_kmh":None,"conditions":None,"rain_probability":None},
        "_data_gaps":["posiciones tabla","puntos exactos","H2H","weather"],
        "source":"sportaragon.com / aragondigital.es",
        "context_note":"Derbi aragonés con ambos equipos en zona de descenso a Primera RFEF (categoría no profesional). Máxima motivación."
    },
    {
        "fname": "segunda_leganes-vs-fc-andorra_192612902_2026-04-26.json",
        "match": "Leganés vs FC Andorra", "FI": "192612902", "competition": "Segunda División", "kickoff": "2026-04-26T16:30:00",
        "stadium": "Butarque (Leganés)",
        "home_team": {"name":"CD Leganés","table_position":15,"points":None,
                      "motivation":"midtable","european_rotation_risk":False,
                      "_note":"Necesita llegar a 50 puntos, mejorando en casa: solo 1 derrota en últimos 8 partidos en Butarque",
                      "form_recent":"buena en casa"},
        "away_team": {"name":"FC Andorra","table_position":9,"points":None,
                      "motivation":"playoff_push","european_rotation_risk":False,
                      "form_last_5":["W","W","W"], "_note":"3 victorias consecutivas, invicto en últimos 5, supera 50 puntos (matemáticamente salvado)"},
        "h2h_last_5":[],
        "weather":{"city":"Leganés","temp_celsius":None,"wind_kmh":None,"conditions":None,"rain_probability":None},
        "_data_gaps":["puntos exactos","H2H","weather","XI confirmado pendiente"],
        "source":"jornadaperfecta.com / fotmob.com / infobae",
    },
    {
        "fname": "segunda_ad-ceuta-vs-racing-santander_192612905_2026-04-26.json",
        "match": "AD Ceuta vs Racing Santander", "FI": "192612905", "competition": "Segunda División", "kickoff": "2026-04-26T21:00:00",
        "stadium": "Alfonso Murube (Ceuta)",
        "home_team": {"name":"AD Ceuta","table_position":None,"points":50,
                      "motivation":"playoff_push","european_rotation_risk":False,
                      "_note":"Recién celebró 50 puntos (J36). 'Murube' fortín. Solo un central disponible.",
                      "key_injuries":["Bajas en defensa central"]},
        "away_team": {"name":"Racing Santander","table_position":1,"points":None,
                      "motivation":"promotion_race","european_rotation_risk":False,
                      "_note":"Líder Segunda División"},
        "h2h_last_5":[],
        "weather":{"city":"Ceuta","temp_celsius":None,"wind_kmh":None,"conditions":None,"rain_probability":None},
        "_data_gaps":["puntos Racing","H2H","weather","XI confirmado pendiente"],
        "source":"elfarodeceuta.es / ceutatv.com / racinguismo.com",
    },
    {
        "fname": "segunda_cadiz-vs-las-palmas_192612907_2026-04-26.json",
        "match": "Cádiz vs Las Palmas", "FI": "192612907", "competition": "Segunda División", "kickoff": "2026-04-27T19:30:00",
        "stadium": "Nuevo Mirandilla (Cádiz)",
        "home_team": {"name":"Cádiz CF","table_position":None,"points":None,
                      "motivation":"midtable","european_rotation_risk":False},
        "away_team": {"name":"UD Las Palmas","table_position":None,"points":None,
                      "motivation":"playoff_push","european_rotation_risk":False},
        "h2h_last_5":[],
        "weather":{"city":"Cádiz","temp_celsius":None,"wind_kmh":None,"conditions":None,"rain_probability":None},
        "_data_gaps":["posiciones y puntos","forma reciente","H2H","weather","alineaciones","árbitro pendiente"],
        "source":"laliga.com (limitado)",
    },
    {
        "fname": "serie-a_ac-milan-vs-juventus_192613460_2026-04-26.json",
        "match": "AC Milan vs Juventus", "FI": "192613460", "competition": "Serie A", "kickoff": "2026-04-26T20:45:00",
        "stadium": "San Siro / Giuseppe Meazza (Milán)",
        "home_team": {"name":"AC Milan","table_position":None,"points":None,
                      "motivation":"european_qualification","european_rotation_risk":True},
        "away_team": {"name":"Juventus","table_position":None,"points":None,
                      "motivation":"champions_league_qualification","european_rotation_risk":True},
        "h2h_last_5":[],
        "weather":{"city":"Milán","temp_celsius":None,"wind_kmh":None,"conditions":None,"rain_probability":None},
        "_data_gaps":["posiciones tabla Serie A","puntos","forma últimos 5","H2H","weather","alineaciones probables"],
        "source":"corrieredellosport / sport.sky.it (parcial)",
        "context_note":"Big match jornada 34 Serie A. Designación arbitral alta (Sozza), promedio 4.64 TA/p → ALTO."
    },
]
for c in ctx:
    name = c.pop("fname")
    write("context", name, c)
    print(f"  context/{name}")


# ============================================================================
# LINEUPS
# ============================================================================
lineups = [
    {
        "fname":"laliga_osasuna-vs-sevilla_192612595_2026-04-26.json",
        "match":"Osasuna vs Sevilla","FI":"192612595","kickoff":"2026-04-26T18:30:00",
        "confirmed":True,
        "home_xi_confirmed":["Sergio Herrera","Valentín Rosier","Alejandro Catena","Iker Muñoz","Javi Galán",
                              "Jon Moncayola","Boyomo","Rubén García","Aimar Oroz","Víctor Muñoz","Ante Budimir"],
        "away_xi_confirmed":["Odysseas Vlachodimos","José Ángel Carmona","Kike Salas","Gabriel Suazo","Andrés Castrín",
                              "Lucien Agoume","Djibril Sow","Rubén Vargas","Isaac Romero","Joaquín Oso","Neal Maupay"],
        "home_xi_probable":None,"away_xi_probable":None,
        "key_absences":{"home":["Iker Benito (lesión)"],"away":["Marcao (lesión, resto temp)","César Azpilicueta (duda)"]},
        "_data_gaps":["banquillo","key_absences detalladas"],
        "source":"futbolfantasy.com (live match data)"
    },
    {
        "fname":"laliga_villarreal-vs-celta-de-vigo_192612599_2026-04-26.json",
        "match":"Villarreal vs Celta de Vigo","FI":"192612599","kickoff":"2026-04-26T21:00:00",
        "confirmed":False,
        "home_xi_probable":["Arnau Tenas","Pedraza","Rafa Marín","Pau Navarro","Freeman",
                             "Comesaña","Pape Gueye","Moleiro","Pépé","Mikautadze","Gerard Moreno"],
        "away_xi_probable":["Radu","Yoel Lago","Javi Rodríguez","Álvaro Núñez","Marcos Alonso",
                             "Hugo Sotelo","Ilaix Moriba","Mingueza","Fer López","Borja Iglesias","Ferran Jutglà"],
        "home_xi_confirmed":None,"away_xi_confirmed":None,
        "key_absences":{"home":["Foyth (lesión)","Pau Cabanes (lesión)","Logan Costa (lesión)","Mouriño (duda)"],
                        "away":["Carl Starfelt (lumbalgia)","Miguel Román (fractura pie)"]},
        "_data_gaps":["XI confirmado (publicación ~45 min antes kickoff)"],
        "source":"comuniate.com / futbolfantasy.com (probables)"
    },
    {
        "fname":"laliga_espanyol-vs-levante_192612603_2026-04-26.json",
        "match":"Espanyol vs Levante","FI":"192612603","kickoff":"2026-04-27T21:00:00",
        "confirmed":False,
        "home_xi_probable":None,"away_xi_probable":None,
        "home_xi_confirmed":None,"away_xi_confirmed":None,
        "key_absences":{"home":["Javi Puado (rotura LCA hasta septiembre)"],
                        "away":["Roger Brugué (hasta mayo)","Unai Elgezabal (duda)"]},
        "_data_gaps":["XI completo no publicado al momento del scrape (faltan +24h al kickoff)"],
        "source":"infobae.com / lagrada.org"
    },
    {
        "fname":"segunda_huesca-vs-real-zaragoza_192612900_2026-04-26.json",
        "match":"Huesca vs Real Zaragoza","FI":"192612900","kickoff":"2026-04-26T18:30:00",
        "confirmed":True,
        "_note":"Alineaciones publicadas en sportaragon.com — re-verificar URL para detalles completos",
        "home_xi_probable":None,"away_xi_probable":None,
        "home_xi_confirmed":None,"away_xi_confirmed":None,
        "away_xi_partial":["Cuenca (extremo izq)","Rober González (mediapunta)","Dani Gómez (delantero)"],
        "key_absences":{"home":[],"away":[]},
        "_data_gaps":["XI confirmado completo (la fuente lo tiene publicado)"],
        "source":"sportaragon.com"
    },
    {
        "fname":"segunda_leganes-vs-fc-andorra_192612902_2026-04-26.json",
        "match":"Leganés vs FC Andorra","FI":"192612902","kickoff":"2026-04-26T16:30:00",
        "confirmed":False,
        "home_xi_probable":None,"away_xi_probable":None,
        "home_xi_confirmed":None,"away_xi_confirmed":None,
        "key_absences":{"home":[],"away":[]},
        "_data_gaps":["XI no consultado en detalle"],
        "source":"jornadaperfecta.com / fotmob.com (URLs identificadas, no fetched)"
    },
    {
        "fname":"segunda_ad-ceuta-vs-racing-santander_192612905_2026-04-26.json",
        "match":"AD Ceuta vs Racing Santander","FI":"192612905","kickoff":"2026-04-26T21:00:00",
        "confirmed":False,
        "home_xi_probable":None,"away_xi_probable":None,
        "home_xi_confirmed":None,"away_xi_confirmed":None,
        "key_absences":{"home":["Solo un central disponible — bajas en defensa central"],"away":[]},
        "_data_gaps":["XI completo no consultado"],
        "source":"ceutatv.com"
    },
    {
        "fname":"segunda_cadiz-vs-las-palmas_192612907_2026-04-26.json",
        "match":"Cádiz vs Las Palmas","FI":"192612907","kickoff":"2026-04-27T19:30:00",
        "confirmed":False,
        "home_xi_probable":None,"away_xi_probable":None,
        "home_xi_confirmed":None,"away_xi_confirmed":None,
        "key_absences":{"home":[],"away":[]},
        "_data_gaps":["XI no consultado al momento del scrape"],
        "source":None
    },
    {
        "fname":"serie-a_ac-milan-vs-juventus_192613460_2026-04-26.json",
        "match":"AC Milan vs Juventus","FI":"192613460","kickoff":"2026-04-26T20:45:00",
        "confirmed":False,
        "home_xi_probable":None,"away_xi_probable":None,
        "home_xi_confirmed":None,"away_xi_confirmed":None,
        "key_absences":{"home":[],"away":[]},
        "_data_gaps":["XI Milan-Juve no consultado en detalle (gazzetta.it pendiente)"],
        "source":None
    },
]
for l in lineups:
    name = l.pop("fname")
    write("lineups", name, l)
    print(f"  lineups/{name}")


# ============================================================================
# NEWS
# ============================================================================
news = [
    {
        "fname":"laliga_osasuna-vs-sevilla_192612595_2026-04-26.json",
        "match":"Osasuna vs Sevilla","FI":"192612595",
        "summary":"Osasuna (10º) recibe a un Sevilla (17º) en plena lucha por descenso, a 1 punto de la zona roja. Sevilla viene de 4 derrotas en 5 partidos. Los locales recuperan a Catena y Osambela tras sanción.",
        "headlines":[
            {"date":"2026-04-25","title":"Sevilla en crisis: 4 derrotas y 1 victoria en últimos 5","source":"jornadaperfecta.com","relevance":"high","url":"https://www.jornadaperfecta.com/blog/alineaciones-osasuna-sevilla-j32-25-26/"},
            {"date":"2026-04-26","title":"Marcao baja por el resto de la temporada","source":"jornadaperfecta.com","relevance":"high","url":"https://www.jornadaperfecta.com/blog/alineaciones-osasuna-sevilla-j32-25-26/"},
            {"date":"2026-04-26","title":"Osasuna recupera a Catena y Osambela","source":"jornadaperfecta.com","relevance":"medium"},
        ],
        "key_facts_for_betting":[
            "Sevilla forma D-D-L-L-W → ATTACK_LOW + DEFENSE_VULNERABLE",
            "Sevilla en lucha por descenso (motivación alta) — más intensidad y faltas posible",
            "Árbitro Ortiz Arias 4.04 TA/p → TARJETAS_MEDIO",
            "Osasuna refuerzo defensa (Catena vuelve) — under goles plausible",
            "Akor Adams (Sevilla) titular probable, 8 goles esta temporada"
        ],
        "_data_gaps":[]
    },
    {
        "fname":"laliga_villarreal-vs-celta-de-vigo_192612599_2026-04-26.json",
        "match":"Villarreal vs Celta de Vigo","FI":"192612599",
        "summary":"Villarreal (3º, plaza Champions) recibe a un Celta tocado: 4 derrotas consecutivas (Barcelona y Freiburg ×2 incluidas) y baja de su pivote Starfelt. Marcelino mantiene equipo sin rotaciones.",
        "headlines":[
            {"date":"2026-04-25","title":"Marcelino: 'No habrá rotaciones, es un partido clave para el 3º puesto'","source":"comuniate.com","relevance":"high"},
            {"date":"2026-04-25","title":"Celta acumula 4 derrotas seguidas tras eliminación europea","source":"comuniate.com","relevance":"high"},
            {"date":"2026-04-25","title":"Pépé: 13 goles + 14 asistencias temporada","source":"futbolfantasy.com","relevance":"medium"},
        ],
        "key_facts_for_betting":[
            "Villarreal motivación máxima (clasif Champions)",
            "Celta european_rotation_risk + 4 derrotas → ATTACK_LOW",
            "Borja Iglesias gestionado en minutos (entró tarde vs Barça) — under remates jugador propable",
            "Celta defensa débil reciente: 4 derrotas con goles encajados",
            "H2H histórico: 4-3 y 0-3 — partidos abiertos de muchos goles",
        ],
        "_data_gaps":[]
    },
    {
        "fname":"laliga_espanyol-vs-levante_192612603_2026-04-26.json",
        "match":"Espanyol vs Levante","FI":"192612603",
        "summary":"Crisis del Espanyol (12º, 38 pts) tras caer 0-1 ante Rayo. Levante (19º, 32 pts) llega motivado tras vencer 2-0 al Sevilla. Cierre de jornada lunes 27.",
        "headlines":[
            {"date":"2026-04-26","title":"Espanyol cae ante Rayo, momento delicado","source":"infobae.com","relevance":"high"},
            {"date":"2026-04-25","title":"Levante venció 2-0 al Sevilla y busca permanencia","source":"infobae.com","relevance":"high"},
            {"date":"2026-04-25","title":"Javi Puado fuera por rotura LCA hasta septiembre","source":"lagrada.org","relevance":"medium"},
        ],
        "key_facts_for_betting":[
            "Levante motivación alta (descenso, 2-0 a Sevilla en últ jornada)",
            "Espanyol pierde a Puado (creador) — ATTACK_LOW",
            "Espanyol recupera a Urko González",
            "Partido de cierre de jornada — presión psicológica añadida",
            "Árbitro pendiente — re-verificar el lunes 27 antes del kickoff"
        ],
        "_data_gaps":["árbitro"]
    },
    {
        "fname":"segunda_huesca-vs-real-zaragoza_192612900_2026-04-26.json",
        "match":"Huesca vs Real Zaragoza","FI":"192612900",
        "summary":"Derbi aragonés agónico: ambos en zona de descenso a Primera RFEF. Primer derbi de Oltra al frente del Huesca. Arcediano Monescillo, árbitro de tarjeta fácil (5.33 TA/p).",
        "headlines":[
            {"date":"2026-04-25","title":"El derbi aragonés más agónico de la historia","source":"sportaragon.com","relevance":"high","url":"https://www.sportaragon.com/articulo/futbol-aragon/sd-huesca-real-zaragoza-derbi-mas-agonico-historia/20260425101142151717.html"},
            {"date":"2026-04-26","title":"Arcediano Monescillo arbitrará el derbi","source":"sportaragon.com","relevance":"high","url":"https://www.sportaragon.com/articulo/real-zaragoza/quien-es-damaso-arcediano-arbitro-sd-huesca-real-zaragoza/20260426174655151763.html"},
        ],
        "key_facts_for_betting":[
            "MOTIVACIÓN MÁXIMA: ambos descenso a categoría no profesional",
            "Árbitro Arcediano 5.33 TA/p → TARJETAS_ALTO ✓ pick viable",
            "Derbi histórico → más faltas y tarjetas esperadas",
            "Real Zaragoza alineación: Cuenca-Rober González-Dani Gómez referencia"
        ],
        "_data_gaps":[]
    },
    {
        "fname":"segunda_leganes-vs-fc-andorra_192612902_2026-04-26.json",
        "match":"Leganés vs FC Andorra","FI":"192612902",
        "summary":"Leganés (15º) busca asegurar permanencia en casa (1 derrota en 8 últimos partidos en Butarque). Andorra (9º) llega lanzado: 3 victorias seguidas, invicto en 5, ya supera 50 puntos.",
        "headlines":[
            {"date":"2026-04-25","title":"Andorra ilusiona: 3 victorias seguidas y permanencia matemática","source":"infobae.com","relevance":"high"},
        ],
        "key_facts_for_betting":[
            "Andorra forma W-W-W → ATTACK_HIGH",
            "Leganés fortín en Butarque (1L en 8) → defensa local sólida",
            "Andorra ya está salvado (50+ pts) → posible relajación motivacional",
            "Leganés necesita 50 pts: motivación media-alta",
            "Árbitro pendiente — bloquear picks de tarjetas por ahora"
        ],
        "_data_gaps":["árbitro"]
    },
    {
        "fname":"segunda_ad-ceuta-vs-racing-santander_192612905_2026-04-26.json",
        "match":"AD Ceuta vs Racing Santander","FI":"192612905",
        "summary":"AD Ceuta (50 pts, J36) recibe al líder Racing Santander con su defensa diezmada — solo un central disponible. Eder Mallo (4.86 TA/p) es el árbitro.",
        "headlines":[
            {"date":"2026-04-24","title":"Ceuta solo tiene un central disponible para recibir al Racing","source":"ceutatv.com","relevance":"high","url":"https://www.ceutatv.com/articulo/ad-ceuta-fc/ad-ceuta-fc-recibira-racing-santander-tan-solo-central-disponible/20260424111458241749.html"},
            {"date":"2026-04-25","title":"Designación: Eder Mallo arbitrará el partido","source":"ceutatv.com","relevance":"high"},
        ],
        "key_facts_for_betting":[
            "Ceuta DEFENSE_WEAK (1 central) → over goles + over remates Racing",
            "Racing líder Segunda → ATTACK_HIGH visitante",
            "Árbitro Mallo 4.86 TA/p → TARJETAS_ALTO ✓",
            "Ceuta en pelea por playoff (50 pts) → motivación máxima local",
            "Racing busca consolidar liderato"
        ],
        "_data_gaps":[]
    },
    {
        "fname":"segunda_cadiz-vs-las-palmas_192612907_2026-04-26.json",
        "match":"Cádiz vs Las Palmas","FI":"192612907",
        "summary":"Partido a disputarse el lunes 27 abril 19:30 cerrando jornada. Información limitada al momento del scrape.",
        "headlines":[],
        "key_facts_for_betting":[
            "Datos contextuales escasos al momento del scrape",
            "Re-verificar previas/árbitro lunes 27 antes del kickoff"
        ],
        "_data_gaps":["contexto reciente","árbitro","forma","alineaciones"]
    },
    {
        "fname":"serie-a_ac-milan-vs-juventus_192613460_2026-04-26.json",
        "match":"AC Milan vs Juventus","FI":"192613460",
        "summary":"Big match jornada 34 Serie A. Sozza (4.64 TA/p) dirige uno de los clásicos italianos. Designación arbitral de alto nivel.",
        "headlines":[
            {"date":"2026-04-23","title":"Sozza designato per Milan-Juve","source":"sport.sky.it","relevance":"high","url":"https://sport.sky.it/calcio/serie-a/2026/04/23/arbitri-serie-a-designazioni-giornata-34"},
            {"date":"2026-04-23","title":"VAR Abisso, AVAR Maresca","source":"corrieredellosport.it","relevance":"medium"},
        ],
        "key_facts_for_betting":[
            "Árbitro Sozza 4.64 TA/p → TARJETAS_ALTO ✓ (clásico = más tarjetas)",
            "Big match histórico — intensidad alta esperada",
            "Sozza histórico: 4.76 promedio en clásicos según prensa",
            "Designación VAR pesada (Abisso) — más revisiones probables",
            "Faltan datos forma/clasificación recientes Serie A"
        ],
        "_data_gaps":["forma últimos 5","posiciones tabla Serie A","alineaciones"]
    },
]
for n in news:
    name = n.pop("fname")
    write("news", name, n)
    print(f"  news/{name}")

print(f"\n✅ {len(refs)} referees + {len(ctx)} context + {len(lineups)} lineups + {len(news)} news = {len(refs)+len(ctx)+len(lineups)+len(news)} archivos")
