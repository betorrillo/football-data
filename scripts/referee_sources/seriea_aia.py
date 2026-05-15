"""Scraper for AIA-FIGC Serie A referee designations.

Source: https://www.aia-figc.it/news/ — articles titled
"SERIE A ENILIVE - DESIGNAZIONI Xa GIORNATA".

The page lists fixtures in blocks of consecutive lines:
    TEAM_HOME – TEAM_AWAY     (en-dash separator)
    [Day DD/MM] h. HH.MM      (day is optional, may be in same or next line)
    REFEREE_NAME              (often in CAPS, sometimes followed by "(foto)")
    ASSISTANT1 – ASSISTANT2
    IV:    NAME
    VAR:   NAME
    AVAR:  NAME

The article's publication date and the intro text ("in programma domenica 18 maggio")
provide year context for kickoff dates.
"""

import re
from datetime import datetime

from ._common import fetch, strip_html

NEWS_LIST_URL = "https://www.aia-figc.it/news/"
SLUG_PATTERN = re.compile(
    r'href="(/news/serie-a-enilive-designazioni-[^"]+)"', re.IGNORECASE
)

# Article block markers
_PUBDATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
# Fixture-and-time on the SAME line after HTML strip:
#   "COMO – PARMA h. 12.00"
#   "GENOA – ATALANTA Sabato 17/05 h. 20.45"
_FIXTURE_LINE_RE = re.compile(
    r"^([A-ZÀ-ÿ' .]+?)\s*[–—-]\s*([A-ZÀ-ÿ' .]+?)"
    r"\s+(?:(?:Luned[ìi]|Marted[ìi]|Mercoled[ìi]|Gioved[ìi]|Venerd[ìi]|Sabato|Domenica)\s+)?"
    r"(?:(\d{1,2})/(\d{1,2})\s+)?h\.?\s*(\d{1,2})[.:](\d{2})\s*$",
    re.IGNORECASE,
)
_REF_OFFICIAL_RE = re.compile(r"^(IV|VAR|AVAR)\s*:", re.IGNORECASE)


def _find_latest_article_url():
    """Scan the news listing and return the most recent Serie A designation article."""
    html = fetch(NEWS_LIST_URL)
    if not html:
        return None
    slugs = SLUG_PATTERN.findall(html)
    if not slugs:
        return None
    # Prefer slugs with the highest trailing numeric id (assumed to be article id, monotonic)
    def _aid(slug):
        m = re.search(r"-(\d+)/?$", slug)
        return int(m.group(1)) if m else 0
    latest = max(set(slugs), key=_aid)
    return f"https://www.aia-figc.it{latest}"


def _parse_pub_date(lines):
    """Return (year, month, day) parsed from the article publication date line."""
    for line in lines:
        if _PUBDATE_RE.match(line):
            try:
                d, mo, y = line.split("/")
                return int(y), int(mo), int(d)
            except ValueError:
                return datetime.now().year, None, None
    return datetime.now().year, None, None


def fetch_designations(date_hint=None):
    """Return list of Serie A designations from the latest published article.

    Strategy: walk lines, anchor on lines matching the kickoff-time pattern
    "h. HH.MM" (optionally with day + DD/MM prefix). The line IMMEDIATELY
    BEFORE the kickoff line is the fixture (HOME – AWAY); the line
    IMMEDIATELY AFTER is the main referee.
    """
    article_url = _find_latest_article_url()
    if not article_url:
        return []

    raw = fetch(article_url)
    if not raw:
        return []
    lines = strip_html(raw)

    pub_year, _, _ = _parse_pub_date(lines)
    results = []

    # When the day/DD/MM isn't on the fixture line, the article intro often
    # says "in programma domenica 18 maggio" or similar. Capture month+day
    # from there as a fallback for fixtures that only show "h. HH.MM".
    intro_date = _parse_intro_date(lines, pub_year)

    # Italian months -> number, for "Sabato 17/05" we already have the digits.
    # We carry the most recently seen explicit DD/MM forward to subsequent
    # fixtures so they share the same matchday date if only time was on the line.
    last_explicit = intro_date  # (year, month, day) or None

    for i, line in enumerate(lines):
        m = _FIXTURE_LINE_RE.match(line)
        if not m:
            continue
        home, away, day, month, hh, mm = m.groups()
        home_cased = home.strip().title()
        away_cased = away.strip().title()

        date_iso = None
        if day and month:
            try:
                last_explicit = (pub_year, int(month), int(day))
            except ValueError:
                pass
        if last_explicit:
            y, mo, d = last_explicit
            try:
                date_iso = f"{y}-{int(mo):02d}-{int(d):02d}"
            except ValueError:
                date_iso = None

        kickoff_time = f"{int(hh):02d}:{mm}"

        # Main referee: next non-empty line, strip "(foto)" markers
        referee_line = None
        for k in range(i + 1, min(i + 4, len(lines))):
            cand = re.sub(r"\(.*?\)", "", lines[k]).strip()
            if cand and not _REF_OFFICIAL_RE.match(cand) and "–" not in cand:
                referee_line = cand
                break
        if not referee_line:
            continue

        # VAR: scan a small window forward
        var_name = None
        for j in range(i + 2, min(i + 8, len(lines))):
            mo_ = _REF_OFFICIAL_RE.match(lines[j])
            if mo_ and mo_.group(1).upper() == "VAR":
                var_name = re.sub(r"\(.*?\)", "", lines[j].split(":", 1)[1]).strip()
                break

        results.append({
            "home": home_cased,
            "away": away_cased,
            "date": date_iso,
            "kickoff_time": kickoff_time,
            "referee": referee_line,
            "var": var_name,
            "source_url": article_url,
            "league": "seriea",
        })

    return results


_IT_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}


def _parse_intro_date(lines, pub_year):
    """Look for "in programma domenica 18 maggio" pattern in the article intro."""
    pat = re.compile(
        r"in programma\s+\S+\s+(\d{1,2})\s+(" + "|".join(_IT_MONTHS) + ")",
        re.IGNORECASE,
    )
    for line in lines[:30]:
        m = pat.search(line)
        if m:
            day = int(m.group(1))
            month = _IT_MONTHS[m.group(2).lower()]
            return (pub_year, month, day)
    return None


if __name__ == "__main__":
    designations = fetch_designations()
    print(f"Found {len(designations)} Serie A designations")
    for d in designations:
        print(
            f"  [{d['date']} {d['kickoff_time'] or '--:--'}] "
            f"{d['home']:25} vs {d['away']:25} -> {d['referee']}"
            f"  (VAR: {d['var'] or '-'})"
        )
