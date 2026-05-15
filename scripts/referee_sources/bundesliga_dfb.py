"""Scraper for DFB Datencenter Bundesliga referee designations.

Source: https://datencenter.dfb.de/global_referee_schedule

The page lists ALL competitions in one HTML; we slice the Bundesliga block.
Within the Bundesliga block, each fixture is exactly nine consecutive lines:

    Samstag, 16.05.2026 15:30 Uhr        # weekday, date DD.MM.YYYY, time
    1. FC Heidenheim                      # home
    - : -                                 # score placeholder
    1. FSV Mainz 05                       # away
    Robert Hartmann (SR)                  # main referee
    Tobias Schultes (SR-A. 1)
    Marco Achmüller (SR-A. 2)
    Patrick Schwengers (4. Offizieller)
    Guido Winkmann (VA)
    Frederick Assmuth (VA-A)
"""

import re

from ._common import fetch, strip_html

SOURCE_URL = "https://datencenter.dfb.de/global_referee_schedule"

# Anchor pattern that marks the start of a fixture block
_KICKOFF_RE = re.compile(
    r"^(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag),"
    r"\s+(\d{2})\.(\d{2})\.(\d{4})\s+(\d{1,2}):(\d{2})\s+Uhr$"
)
_REF_RE = re.compile(r"^(.+?)\s*\(\s*SR\s*\)$")
_VAR_RE = re.compile(r"^(.+?)\s*\(\s*VA\s*\)$")
_SCORE_PLACEHOLDER = "- : -"


# Headlines that mark the start of *other* competitions in the same page —
# everything after one of these (or end-of-document) is no longer Bundesliga.
_OTHER_COMPS = (
    "2. Bundesliga",
    "3. Liga",
    "Google Pixel Frauen-Bundesliga",
    "Regionalliga",
    "DFB-Pokal",
)


def _bundesliga_slice(lines):
    """Return only the lines belonging to the Bundesliga section."""
    out = []
    in_block = False
    for line in lines:
        if line == "Bundesliga":
            in_block = True
            continue
        if in_block and any(line.startswith(o) for o in _OTHER_COMPS):
            break
        if in_block:
            out.append(line)
    return out


def fetch_designations(date_hint=None):
    raw = fetch(SOURCE_URL)
    if not raw:
        return []
    lines = strip_html(raw)
    bl_lines = _bundesliga_slice(lines)

    results = []
    i = 0
    while i < len(bl_lines):
        m = _KICKOFF_RE.match(bl_lines[i])
        if not m:
            i += 1
            continue
        day, month, year, hh, mm = m.groups()

        # Look ahead: home, "- : -", away, referee, ...
        if i + 4 >= len(bl_lines):
            break

        home = bl_lines[i + 1]
        # The placeholder line should be "- : -"; if not, this isn't a fixture block
        if _SCORE_PLACEHOLDER not in bl_lines[i + 2]:
            i += 1
            continue
        away = bl_lines[i + 3]

        referee = None
        var = None
        # Officials are in lines i+4..i+9
        for j in range(i + 4, min(i + 10, len(bl_lines))):
            mr = _REF_RE.match(bl_lines[j])
            if mr and not referee:
                referee = mr.group(1).strip()
                continue
            mv = _VAR_RE.match(bl_lines[j])
            if mv and not var:
                var = mv.group(1).strip()
                continue

        if referee:
            results.append({
                "home": home,
                "away": away,
                "date": f"{year}-{int(month):02d}-{int(day):02d}",
                "kickoff_time": f"{int(hh):02d}:{mm}",
                "referee": referee,
                "var": var,
                "source_url": SOURCE_URL,
                "league": "bundesliga",
            })
        i += 10  # advance past the consumed block

    return results


if __name__ == "__main__":
    designations = fetch_designations()
    print(f"Found {len(designations)} Bundesliga designations")
    for d in designations:
        print(
            f"  [{d['date']} {d['kickoff_time']}] "
            f"{d['home']:30} vs {d['away']:30} -> {d['referee']}"
            f"  (VAR: {d['var'] or '-'})"
        )
