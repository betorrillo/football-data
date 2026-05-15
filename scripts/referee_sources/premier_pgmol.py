"""Scraper for Premier League referee appointments.

PGMOL (the official body) does not publish per-fixture appointments in HTML.
referee-equipment.com republishes the official PGMOL list every matchweek
in a stable, parseable format. The Rate The Ref Forum is cited as their
source — these are the official PGMOL designations, just hosted elsewhere.

Block layout:
    Friday 15th May 2026                              # date (verbose English)
    Aston Villa v Liverpool                           # fixture (separator: " v ")
    Referee: Kavanagh, Christopher
    Assistant Referee: Cook, Dan
    Assistant Referee: Betts, Lee
    Fourth Official: Madley, Andrew
    Video Assistant Referee: Davies, Neil
    Additional Video Assistant Referee: Howard, Paul

The date applies to every fixture that follows until a new date line appears.
"""

import re
from datetime import datetime

from ._common import fetch, strip_html

BLOG_INDEX_URL = "https://referee-equipment.com/blogs/the-ah-blog"
ARTICLE_BASE = "https://referee-equipment.com"

_ARTICLE_LINK_RE = re.compile(
    r'href="(/blogs/the-ah-blog/premier-league-referee-appointments-matchweek-(\d+)-[^"]+)"'
)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_DATE_RE = re.compile(
    r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})$",
    re.IGNORECASE,
)
# Fixture line: "Aston Villa v Liverpool" — single " v " separator
_FIXTURE_RE = re.compile(r"^([A-Z][\w &'.\-]+?)\s+v\s+([A-Z][\w &'.\-]+?)$")
_REFEREE_RE = re.compile(r"^Referee:\s*(.+?)\s*$", re.IGNORECASE)
_VAR_RE = re.compile(r"^Video Assistant Referee:\s*(.+?)\s*$", re.IGNORECASE)


def _swap_surname_first(name):
    """Turn 'Kavanagh, Christopher' into 'Christopher Kavanagh'."""
    if "," in name:
        last, first = (p.strip() for p in name.split(",", 1))
        return f"{first} {last}"
    return name


def _find_latest_article_url():
    raw = fetch(BLOG_INDEX_URL)
    if not raw:
        return None
    matches = _ARTICLE_LINK_RE.findall(raw)
    if not matches:
        return None
    # Highest matchweek wins (assuming current season)
    slug, _ = max(matches, key=lambda x: int(x[1]))
    return ARTICLE_BASE + slug


def fetch_designations(date_hint=None):
    article_url = _find_latest_article_url()
    if not article_url:
        return []
    raw = fetch(article_url)
    if not raw:
        return []
    lines = strip_html(raw)

    results = []
    current_date = None  # "YYYY-MM-DD" sticky across fixtures

    i = 0
    while i < len(lines):
        line = lines[i]

        md = _DATE_RE.match(line)
        if md:
            day = int(md.group(1))
            month = _MONTHS[md.group(2).lower()]
            year = int(md.group(3))
            current_date = f"{year}-{month:02d}-{day:02d}"
            i += 1
            continue

        mf = _FIXTURE_RE.match(line)
        if mf and current_date:
            home = mf.group(1).strip()
            away = mf.group(2).strip()

            referee = None
            var = None
            # Officials are within the next ~7 lines
            for j in range(i + 1, min(i + 9, len(lines))):
                if not referee:
                    mr = _REFEREE_RE.match(lines[j])
                    if mr:
                        referee = _swap_surname_first(mr.group(1).strip())
                        continue
                if not var:
                    mv = _VAR_RE.match(lines[j])
                    if mv:
                        var = _swap_surname_first(mv.group(1).strip())

            if referee:
                results.append({
                    "home": home,
                    "away": away,
                    "date": current_date,
                    "kickoff_time": None,  # source omits times
                    "referee": referee,
                    "var": var,
                    "source_url": article_url,
                    "league": "epl",
                })
            i += 1
            continue

        i += 1

    return results


if __name__ == "__main__":
    designations = fetch_designations()
    print(f"Found {len(designations)} Premier League designations")
    for d in designations:
        print(
            f"  [{d['date']} {d['kickoff_time'] or '--:--'}] "
            f"{d['home']:32} vs {d['away']:32} -> {d['referee']}"
            f"  (VAR: {d['var'] or '-'})"
        )
