"""Scraper for Primeira Liga (Liga Portugal Betclic) referee designations.

The Federação Portuguesa de Futebol publishes Conselho de Arbitragem
nominations weekly, but fpf.pt blocks scraping. Record.pt republishes the
official list with the same content and a stable, plain-HTML format.

Article body layout:
    Moreirense-AVS SAD                       # fixture (separator "-")
    Árbitro: Sérgio Guelho                   # main referee
    Assistentes: Hugo Santos e Alexandre…
    4.º árbitro: Tiago Sá
    VAR: Rui Silva
    AVAR: Álvaro Mesquita

The article rarely includes per-fixture kickoff dates (says "no sábado")
so we return date=None and let build_referee match by (home_norm, away_norm).
"""

import re

from ._common import fetch, strip_html

CATEGORY_URL = "https://www.record.pt/futebol/arbitragem/"
ARTICLE_LINK_RE = re.compile(
    r'href="(/futebol/(?:arbitragem|futebol-nacional/liga-betclic)/detalhe/[^"]*(?:arbitros|nomeacoes)[^"]*-liga-(?:betclic|portugal-betclic)[^"]*)"',
    re.IGNORECASE,
)
BASE = "https://www.record.pt"

_REFEREE_LINE_RE = re.compile(r"^Árbitro:\s*(.+)\s*$")
_VAR_LINE_RE = re.compile(r"^VAR:\s*(.+)\s*$")
# Fixture line: two names separated by a single hyphen, capital first letter
# Stricter than en-dash to avoid matching headlines.
_FIXTURE_LINE_RE = re.compile(
    r"^([A-ZÀ-ÿ][\wÀ-ÿ.'\s]{1,40}?)-([A-ZÀ-ÿ][\wÀ-ÿ.'\s]{1,40}?)$"
)


def _find_latest_article_url():
    raw = fetch(CATEGORY_URL)
    if not raw:
        return None
    # The category page lists article cards in document order, newest first.
    matches = ARTICLE_LINK_RE.findall(raw)
    if not matches:
        return None
    return BASE + matches[0]


def fetch_designations(date_hint=None):
    article_url = _find_latest_article_url()
    if not article_url:
        return []
    raw = fetch(article_url)
    if not raw:
        return []
    lines = strip_html(raw)

    results = []
    i = 0
    while i < len(lines):
        line = lines[i]
        mf = _FIXTURE_LINE_RE.match(line)
        if not mf:
            i += 1
            continue
        # Must be followed by an "Árbitro:" line within next 2 lines
        ref_idx = None
        for k in range(i + 1, min(i + 3, len(lines))):
            if _REFEREE_LINE_RE.match(lines[k]):
                ref_idx = k
                break
        if ref_idx is None:
            i += 1
            continue

        home, away = mf.group(1).strip(), mf.group(2).strip()
        referee = _REFEREE_LINE_RE.match(lines[ref_idx]).group(1).strip()
        var = None
        for k in range(ref_idx + 1, min(ref_idx + 6, len(lines))):
            mv = _VAR_LINE_RE.match(lines[k])
            if mv:
                var = mv.group(1).strip()
                break

        results.append({
            "home": home,
            "away": away,
            "date": None,
            "kickoff_time": None,
            "referee": referee,
            "var": var,
            "source_url": article_url,
            "league": "portugal",
        })
        i = ref_idx + 1

    return results


if __name__ == "__main__":
    designations = fetch_designations()
    print(f"Found {len(designations)} Primeira Liga designations")
    for d in designations:
        print(
            f"  {d['home']:25} vs {d['away']:25} -> {d['referee']}"
            f"  (VAR: {d['var'] or '-'})"
        )
