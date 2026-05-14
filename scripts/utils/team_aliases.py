#!/usr/bin/env python3
"""
Team name normalization — maps variant spellings to canonical names.

Sources use different names for the same team:
  - football-data.co.uk: "Ath Bilbao"
  - ESPN: "Athletic Club"
  - Transfermarkt: "Athletic Bilbao"
  - FotMob: "Athletic Club"
  - bet365: "Athletic Bilbao"

This module normalizes all variants to the football-data.co.uk name
(since that's our primary match data source).
"""

# Canonical name (football-data.co.uk) -> list of known aliases
ALIASES = {
    # === LaLiga ===
    "Ath Bilbao": ["Athletic Bilbao", "Athletic Club", "Athletic"],
    "Ath Madrid": ["Atletico Madrid", "Atlético Madrid", "Atlético de Madrid", "Atletico de Madrid", "Atleti"],
    "Betis": ["Real Betis", "Real Betis Balompié"],
    "Celta": ["Celta Vigo", "Celta de Vigo", "RC Celta"],
    "Espanol": ["Espanyol", "RCD Espanyol"],
    "La Coruna": ["Deportivo La Coruña", "Deportivo", "RC Deportivo"],
    "Mallorca": ["RCD Mallorca", "Real Mallorca"],
    "Sociedad": ["Real Sociedad"],
    "Vallecano": ["Rayo Vallecano", "Rayo"],

    # === Segunda Division ===
    "Almeria": ["UD Almería", "Almería"],
    "Burgos": ["Burgos CF"],
    "Cadiz": ["Cádiz CF", "Cádiz"],
    "Cartagena": ["FC Cartagena"],
    "Castellon": ["CD Castellón", "Castellón"],
    "Eibar": ["SD Eibar"],
    "Elche": ["Elche CF"],
    "Ferrol": ["Racing de Ferrol", "Racing Ferrol"],
    "Huesca": ["SD Huesca"],
    "Mirandes": ["CD Mirandés", "Mirandés"],
    "Oviedo": ["Real Oviedo"],
    "Sp Gijon": ["Sporting Gijón", "Sporting de Gijón", "Real Sporting"],
    "Tenerife": ["CD Tenerife"],
    "Zaragoza": ["Real Zaragoza"],

    # === Premier League ===
    "Man City": ["Manchester City", "Manchester City FC"],
    "Man United": ["Manchester United", "Manchester Utd", "Manchester United FC"],
    "Newcastle": ["Newcastle United", "Newcastle Utd"],
    "Nott'm Forest": ["Nottingham Forest", "Nottingham", "Nott Forest"],
    "Sheffield United": ["Sheffield Utd"],
    "Spurs": ["Tottenham", "Tottenham Hotspur"],
    "West Ham": ["West Ham United", "West Ham Utd"],
    "Wolves": ["Wolverhampton", "Wolverhampton Wanderers"],
    "Brighton": ["Brighton & Hove Albion", "Brighton and Hove Albion"],
    "Leicester": ["Leicester City"],
    "Ipswich": ["Ipswich Town"],

    # === Bundesliga ===
    "Dortmund": ["Borussia Dortmund", "BVB"],
    "Ein Frankfurt": ["Eintracht Frankfurt"],
    "FC Koln": ["1. FC Köln", "FC Köln", "Köln"],
    "Leverkusen": ["Bayer Leverkusen", "Bayer 04 Leverkusen"],
    "M'gladbach": ["Borussia Mönchengladbach", "Mönchengladbach", "Gladbach", "Borussia M'gladbach"],
    "Mainz": ["Mainz 05", "1. FSV Mainz 05"],
    "RB Leipzig": ["Leipzig", "RasenBallsport Leipzig"],
    "Wolfsburg": ["VfL Wolfsburg"],
    "Stuttgart": ["VfB Stuttgart"],
    "Freiburg": ["SC Freiburg"],
    "Augsburg": ["FC Augsburg"],
    "Hoffenheim": ["TSG Hoffenheim", "TSG 1899 Hoffenheim"],
    "Heidenheim": ["1. FC Heidenheim"],
    "St Pauli": ["FC St. Pauli", "St. Pauli"],
    "Holstein Kiel": ["Holstein", "KSV Holstein"],

    # === Serie A ===
    "AC Milan": ["Milan"],
    "Inter": ["Inter Milan", "Internazionale", "FC Internazionale"],
    "Napoli": ["SSC Napoli"],
    "Roma": ["AS Roma"],
    "Lazio": ["SS Lazio"],
    "Juventus": ["Juve"],
    "Parma": ["Parma Calcio", "Parma Calcio 1913"],
    "Verona": ["Hellas Verona"],

    # === Ligue 1 ===
    "Paris SG": ["Paris Saint-Germain", "Paris Saint Germain", "PSG"],
    "Marseille": ["Olympique Marseille", "Olympique de Marseille", "OM"],
    "Lyon": ["Olympique Lyon", "Olympique Lyonnais", "OL"],
    "Monaco": ["AS Monaco"],
    "St Etienne": ["Saint-Étienne", "AS Saint-Étienne", "St Étienne"],
    "Rennes": ["Stade Rennais"],

    # === Primeira Liga ===
    "Sp Lisbon": ["Sporting CP", "Sporting Lisbon", "Sporting Clube de Portugal", "Sporting"],
    "Porto": ["FC Porto"],
    "Benfica": ["SL Benfica"],
    "Sp Braga": ["Braga", "SC Braga", "Sporting Braga", "Sporting Clube de Braga"],
    "Guimaraes": ["Vitória de Guimarães", "Vitória SC", "Vitória Guimarães"],
    "Famalicao": ["FC Famalicão", "Famalicão"],
    "Gil Vicente": ["Gil Vicente FC"],
    "Santa Clara": ["CD Santa Clara"],
    "Casa Pia": ["Casa Pia AC"],
    "Moreirense": ["Moreirense FC"],
    "Arouca": ["FC Arouca"],
    "Estoril": ["Estoril Praia", "GD Estoril Praia"],
    "Rio Ave": ["Rio Ave FC"],
    "Vizela": ["FC Vizela"],
    "Estrela": ["Estrela Amadora", "CF Estrela da Amadora", "Amadora"],
    "Nacional": ["CD Nacional"],
    "Boavista": ["Boavista FC"],
    "AVS": ["AVS Futebol SAD"],
}

# Build reverse lookup: alias -> canonical name
_ALIAS_MAP = {}
for canonical, variants in ALIASES.items():
    _ALIAS_MAP[canonical.lower()] = canonical
    for v in variants:
        _ALIAS_MAP[v.lower()] = canonical


def normalize_team(name):
    """Return canonical team name, or the original if no alias is found."""
    if not name:
        return name
    return _ALIAS_MAP.get(name.lower().strip(), name)


def teams_match(name_a, name_b):
    """Check if two team names refer to the same team."""
    if not name_a or not name_b:
        return False
    return normalize_team(name_a) == normalize_team(name_b)
