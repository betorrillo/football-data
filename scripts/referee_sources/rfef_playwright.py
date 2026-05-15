"""Scraper for RFEF (Real Federación Española de Fútbol) referee designations.

Covers LaLiga EA Sports (Primera) and LaLiga HyperMotion (Segunda).

The RFEF site is protected by Cloudflare AND lazy-loads the article body
via JavaScript, so `cloudscraper` reaches the page (HTTP 200) but the
article body is empty in the static HTML. We use Playwright (headless
Chromium) to evaluate the JS and read the DOM after hydration.

Designation articles look like:
    "Designaciones | Estos son los árbitros designados para los partidos
     del jueves 14 de mayo en Primera División"

The category index at rfef.es/es/noticias/arbitros/designaciones is the
discovery point — Cloudflare-protected but cloudscraper passes it. From
there we extract recent designation slugs and pick the latest matching
the league/date hint.

If Playwright is not installed (e.g. running locally without the binary),
this module returns [] and the pipeline degrades to the existing pool
fallback — it never crashes the workflow.
"""

import re
from datetime import datetime, timedelta

BASE = "https://rfef.es"
CATEGORY_URL = "https://rfef.es/es/noticias/arbitros/designaciones"
PRIMERA_KEYWORDS = ("primera-division", "primera ")
SEGUNDA_KEYWORDS = ("segunda-division", "segunda ", "en-segunda")

# Designation slugs roughly look like:
#   /es/noticias/designaciones-estos-son-los-arbitros-...-en-primera
#   /es/noticias/designaciones-estos-son-los-arbitros-para-los-partidos-del-sabado-16-de-mayo-en-segunda
_SLUG_RE = re.compile(
    r'href="(/es/noticias/designaciones-[^"]+)"', re.IGNORECASE
)

# Spanish month names found in slugs and body text
_ES_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _is_playwright_available():
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


def _list_designation_slugs():
    """Use cloudscraper (passes Cloudflare without JS) to list slugs."""
    try:
        import cloudscraper
    except ImportError:
        return []
    try:
        scraper = cloudscraper.create_scraper()
        r = scraper.get(CATEGORY_URL, timeout=30)
        if r.status_code != 200:
            return []
        slugs = _SLUG_RE.findall(r.text)
        return sorted(set(slugs))
    except Exception as e:
        print(f"  ! RFEF index fetch failed: {e}")
        return []


def _classify_slug(slug):
    """Return ('primera' | 'segunda' | None, parsed_date_or_None)."""
    s = slug.lower()
    league = None
    if any(k in s for k in PRIMERA_KEYWORDS):
        league = "primera"
    elif any(k in s for k in SEGUNDA_KEYWORDS):
        league = "segunda"
    if not league:
        return None, None
    # Extract "del <weekday> <DD> de <mes>" or "el <weekday> <DD> de <mes>"
    m = re.search(
        r"(?:del?|el)-(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)-(\d{1,2})-de-(" + "|".join(_ES_MONTHS) + ")",
        s, re.IGNORECASE,
    )
    if not m:
        return league, None
    day = int(m.group(1))
    month = _ES_MONTHS[m.group(2).lower()]
    year = datetime.now().year
    return league, f"{year}-{month:02d}-{day:02d}"


def _fetch_article_body_html(article_url):
    """Render the JS body via Playwright. Returns the rendered HTML or None."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = ctx.new_page()
            page.goto(article_url, timeout=30000, wait_until="networkidle")
            # The body normally hydrates within 3-5s; give it a moment.
            page.wait_for_timeout(2000)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f"  ! RFEF Playwright failed for {article_url}: {e}")
        return None


_FIXTURE_RE = re.compile(
    r"^([A-ZÀ-ÿ][\wÀ-ÿ.'\s]{1,60}?)\s*[-–]\s*([A-ZÀ-ÿ][\wÀ-ÿ.'\s]{1,60}?)\s*$"
)


def _parse_body(html_text, league_name):
    """Extract designations from a Playwright-rendered RFEF article."""
    # Reuse the generic strip helper from _common
    from ._common import strip_html
    lines = strip_html(html_text)

    # The article body has lines like:
    #   ÁRBITRO PRINCIPAL: NAME
    #   ÁRBITRO ASISTENTE Nº1: NAME
    #   ÁRBITRO VAR: NAME
    # ...preceded by the fixture line "TEAM1 - TEAM2"
    results = []
    n = len(lines)
    i = 0
    while i < n - 5:
        # The fixture line typically has "-" between team names (NOT en-dash)
        mf = _FIXTURE_RE.match(lines[i])
        if not mf:
            i += 1
            continue
        # Look forward for "ÁRBITRO PRINCIPAL" within 8 lines
        ref_idx = None
        for k in range(i + 1, min(i + 8, n)):
            if re.match(r"^ÁRBITRO PRINCIPAL\s*:", lines[k], re.IGNORECASE):
                ref_idx = k
                break
        if ref_idx is None:
            i += 1
            continue
        referee = re.sub(r"^ÁRBITRO PRINCIPAL\s*:\s*", "", lines[ref_idx], flags=re.IGNORECASE).strip()

        var = None
        for k in range(ref_idx + 1, min(ref_idx + 8, n)):
            mv = re.match(r"^ÁRBITRO VAR\s*:\s*(.+)$", lines[k], re.IGNORECASE)
            if mv:
                var = mv.group(1).strip()
                break

        results.append({
            "home": mf.group(1).strip(),
            "away": mf.group(2).strip(),
            "referee": referee,
            "var": var,
            "league": "laliga" if league_name == "primera" else "segunda",
        })
        i = ref_idx + 1

    return results


def fetch_designations(date_hint=None):
    """Return RFEF designations for Primera + Segunda from latest articles.

    Strategy:
      1. List recent /es/noticias/designaciones-* slugs (via cloudscraper).
      2. Bucket by league + parsed date.
      3. For each league, pick the slug whose date is closest to today
         (or to date_hint if given).
      4. Render the body via Playwright and parse.
    """
    if not _is_playwright_available():
        print("  ! RFEF scraper: playwright not installed — skipping")
        return []

    slugs = _list_designation_slugs()
    if not slugs:
        return []

    # Bucket per league
    buckets = {"primera": [], "segunda": []}
    for slug in slugs:
        league, slug_date = _classify_slug(slug)
        if league:
            buckets[league].append((slug_date, slug))

    target = date_hint or datetime.now().strftime("%Y-%m-%d")

    selected_articles = []
    for league, entries in buckets.items():
        if not entries:
            continue
        dated = [e for e in entries if e[0]]
        # Pick the slug whose date is closest to target, preferring same or
        # next 7 days
        def _score(e):
            if not e[0]:
                return 9999
            try:
                d = datetime.strptime(e[0], "%Y-%m-%d")
                t = datetime.strptime(target, "%Y-%m-%d")
                return abs((d - t).days)
            except ValueError:
                return 9999
        candidates = dated or entries
        candidates = sorted(candidates, key=_score)
        # RFEF often splits one journey across days; collect up to 3 articles
        # closest to the target (covers Fri/Sat/Sun)
        for slug_date, slug in candidates[:3]:
            selected_articles.append((league, slug_date, BASE + slug))

    results = []
    for league, slug_date, url in selected_articles:
        html = _fetch_article_body_html(url)
        if not html:
            continue
        entries = _parse_body(html, league)
        for e in entries:
            e["date"] = slug_date
            e["kickoff_time"] = None
            e["source_url"] = url
            results.append(e)

    return results


if __name__ == "__main__":
    designations = fetch_designations()
    print(f"Found {len(designations)} RFEF designations")
    for d in designations:
        print(
            f"  [{d['date']} {d['league']}] "
            f"{d['home']:30} vs {d['away']:30} -> {d['referee']}"
            f"  (VAR: {d['var'] or '-'})"
        )
