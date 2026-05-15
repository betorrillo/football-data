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
    "Espanol": ["Espanyol", "RCD Espanyol", "RCD Espanyol Barcelona"],
    "La Coruna": ["Deportivo La Coruña", "Deportivo", "RC Deportivo"],
    "Mallorca": ["RCD Mallorca", "Real Mallorca"],
    "Sociedad": ["Real Sociedad"],
    "Vallecano": ["Rayo Vallecano", "Rayo"],
    "Villarreal": ["Villarreal CF"],
    "Las Palmas": ["UD Las Palmas"],
    "Granada": ["Granada CF"],

    # === Segunda Division ===
    "Alaves": ["Alavés", "Deportivo Alavés"],
    "Albacete": ["Albacete Balompié", "Albacete BP"],
    "Almeria": ["UD Almería", "Almería"],
    "Andorra": ["FC Andorra"],
    "Leganes": ["Leganés", "CD Leganés"],
    "Burgos": ["Burgos CF"],
    "Cadiz": ["Cádiz CF", "Cádiz"],
    "Cartagena": ["FC Cartagena"],
    "Castellon": ["CD Castellón", "Castellón"],
    "Ceuta": ["AD Ceuta"],
    "Cordoba": ["Córdoba", "Córdoba CF"],
    "Cultural Leonesa": ["Cultural y Deportiva Leonesa", "Cultural"],
    "Eibar": ["SD Eibar"],
    "Elche": ["Elche CF"],
    "Ferrol": ["Racing de Ferrol", "Racing Ferrol"],
    "Huesca": ["SD Huesca"],
    "La Coruna": ["Deportivo La Coruña", "Deportivo", "RC Deportivo", "Deportivo de La Coruña"],
    "Malaga": ["Málaga", "Málaga CF", "Málaga C.F."],
    "Mirandes": ["CD Mirandés", "Mirandés"],
    "Oviedo": ["Real Oviedo"],
    "Santander": ["Racing Santander", "Racing de Santander"],
    "Sociedad B": ["Real Sociedad B", "Real Sociedad II"],
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
    "Leeds": ["Leeds United", "Leeds Utd"],
    "Sunderland": ["Sunderland AFC"],
    "Burnley": ["Burnley FC"],

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
    "Milan": ["AC Milan", "AC Milán"],
    "Inter": ["Inter Milan", "Internazionale", "FC Internazionale", "Inter de Milán", "Inter de Milan"],
    "Napoli": ["SSC Napoli", "Nápoles"],
    "Roma": ["AS Roma"],
    "Lazio": ["SS Lazio"],
    "Juventus": ["Juve", "Juventus FC"],
    "Bologna": ["Bolonia", "Bologna FC 1909"],
    "Parma": ["Parma Calcio", "Parma Calcio 1913"],
    "Verona": ["Hellas Verona", "H. Verona", "H Verona"],
    "Atalanta": ["Atalanta BC"],
    "Cagliari": ["Cagliari Calcio"],
    "Torino": ["Torino FC"],
    "Sassuolo": ["US Sassuolo"],
    "Lecce": ["US Lecce"],
    "Udinese": ["Udinese Calcio"],
    "Cremonese": ["US Cremonese"],

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
    "Guimaraes": ["Vitória de Guimarães", "Vitória SC", "Vitória Guimarães", "Vitória de Guimaraes"],
    "Famalicao": ["FC Famalicão", "Famalicão", "FC Famalicao"],
    "Gil Vicente": ["Gil Vicente FC"],
    "Santa Clara": ["CD Santa Clara"],
    "Casa Pia": ["Casa Pia AC"],
    "Moreirense": ["Moreirense FC"],
    "Arouca": ["FC Arouca"],
    "Estoril": ["Estoril Praia", "GD Estoril Praia"],
    "Rio Ave": ["Rio Ave FC"],
    "Vizela": ["FC Vizela"],
    "Estrela": ["Estrela Amadora", "CF Estrela da Amadora", "Amadora"],
    "Nacional": ["CD Nacional", "C.D. Nacional"],
    "Boavista": ["Boavista FC"],
    "AVS": ["AVS Futebol SAD"],
}

import re
import unicodedata

# Build reverse lookup: alias -> canonical name (key is lowercased + diacritics-stripped)
_ALIAS_MAP = {}


def _strip_diacritics(s):
    """Remove combining marks (turn 'Alavés' -> 'Alaves', 'Köln' -> 'Koln')."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def _key(s):
    """Lookup key: lowercase, diacritics-stripped, whitespace-collapsed."""
    s = _strip_diacritics(s).lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


for canonical, variants in ALIASES.items():
    _ALIAS_MAP[_key(canonical)] = canonical
    for v in variants:
        _ALIAS_MAP[_key(v)] = canonical

# Tokens to strip when the direct lookup fails. Pure noise on club names
# from various data sources: legal forms, founding years, club abbreviations.
# Order matters: longer multi-word forms first.
_SUFFIX_TOKENS = [
    # Multi-word + dotted
    r"\bC\.\s*D\.",  # "C.D." (with internal dot)
    r"\bF\.\s*C\.",
    r"\bA\.\s*S\.",
    r"\bU\.\s*S\.",
    # Four-digit founding years (e.g. "FC St. Pauli 1910", "Bologna FC 1909")
    r"\b(?:18|19|20)\d{2}\b",
    # Compact club-form abbreviations (anywhere)
    r"\b(?:FC|AFC|CF|BC|SC|SV|VfB|VfL|FSV|RB|AS|AC|SSC|SS|US|GD|UD|CD|SD|GNK|OSC|"
    r"AJ|RC|TSG|SG|FK|KSV|FCV|AFC|RCD|GFC|CFC|EC|EFC|ACF|SD|CP)\b",
    # Italian/Spanish/Portuguese descriptors
    r"\b(?:Calcio|Sporting Club(?:e)?|Sporting Clube de|Hellas|Real Sporting de?|"
    r"Futebol Clube|Clube de Futebol)\b",
    # Common English-noise suffixes that survive league prefixes
    r"\b(?:Hotspur|United|Wanderers|Albion|Town|City|Athletic|FC|Football Club)\b",
]
_SUFFIX_RE = re.compile("|".join(_SUFFIX_TOKENS), re.IGNORECASE)
# Leading numeric prefixes like "1. FC Köln" or "1899 Hoffenheim"
_LEADING_NUM_PREFIX_RE = re.compile(r"^(?:\d+\.\s*|\d{4}\s+)")


def _aggressive_clean(name):
    """Strip founding years, legal forms, club-tag tokens. Used only as fallback."""
    s = _LEADING_NUM_PREFIX_RE.sub("", name)
    s = _SUFFIX_RE.sub(" ", s)
    s = re.sub(r"[.,&]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_team(name):
    """Return canonical team name, or the original if no alias resolves.

    Lookup is tolerant to: case, diacritics, internal whitespace. If the
    direct lookup fails, we retry after aggressive suffix/prefix stripping —
    this is what catches names like 'Aston Villa FC' or 'Atalanta BC' that
    appear in API/scraping sources but aren't worth enumerating as aliases.
    """
    if not name:
        return name
    k = _key(name)
    if k in _ALIAS_MAP:
        return _ALIAS_MAP[k]
    # Fallback: strip suffix tokens and try again
    cleaned = _aggressive_clean(name)
    if cleaned and cleaned != name:
        k2 = _key(cleaned)
        if k2 in _ALIAS_MAP:
            return _ALIAS_MAP[k2]
        # Last resort: return the cleaned form (so downstream lookups are at
        # least consistent across sources, even if no canonical was found)
        return cleaned
    return name


def teams_match(name_a, name_b):
    """Check if two team names refer to the same team."""
    if not name_a or not name_b:
        return False
    return normalize_team(name_a) == normalize_team(name_b)
