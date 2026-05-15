#!/usr/bin/env python3
"""
Spanish Football Referee Scraper.

1. Finds RFEF designation articles via Chrome CDP
2. Downloads and parses the PDF with referee assignments
3. Fetches card statistics from transfermarkt
4. Generates verdicts (ALTO/MEDIO/BAJO)

Usage:
  python3 scrape_referees.py --competition laliga
  python3 scrape_referees.py --competition segunda
  python3 scrape_referees.py --stats-only "Gil Manzano"
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from random import uniform

import requests
import fitz  # PyMuPDF

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFEREES_DIR = os.path.join(BASE_DIR, 'referees')
CACHE_FILE = os.path.join(REFEREES_DIR, 'referee_stats_cache.json')
CDP_PORT = 9222

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

COMPETITION_MAP = {
    'laliga': {'name': 'LaLiga', 'rfef': 'primera', 'tm_code': 'ES1'},
    'primera': {'name': 'LaLiga', 'rfef': 'primera', 'tm_code': 'ES1'},
    'segunda': {'name': 'LaLiga Hypermotion', 'rfef': 'segunda', 'tm_code': 'ES2'},
    'champions': {'name': 'Champions League', 'rfef': None, 'tm_code': None},
}

UEFA_CL_ARTICLE = 'https://es.uefa.com/uefachampionsleague/news/029d-1eba5de52500-0bf57aa4ef64-1000--quien-es-el-arbitro-que-arbitros-dirigen-los-partidos-de/'


# ===================================================================
# Stage 1: Find and parse RFEF designation PDFs
# ===================================================================

def find_rfef_designation_urls(competition='laliga'):
    """Use Chrome CDP to browse RFEF designations page and find PDF links."""
    comp_info = COMPETITION_MAP.get(competition, {})
    rfef_key = comp_info.get('rfef', 'primera')

    from cdp_client import CDPClient

    # Create new tab on RFEF
    try:
        resp = requests.put(f'http://localhost:{CDP_PORT}/json/new?https://rfef.es/es/noticias/arbitros/designaciones', timeout=10)
        tab = resp.json()
    except Exception as e:
        print(f"  ERROR: Chrome not available on port {CDP_PORT}: {e}")
        return []

    time.sleep(5)
    cdp = CDPClient(tab['webSocketDebuggerUrl'])
    cdp.connect()
    time.sleep(3)

    try:
        # Find all designation article links
        result = cdp.evaluate('''
        (() => {
            const articles = [];
            const seen = new Set();
            document.querySelectorAll("a[href]").forEach(a => {
                const href = a.href || "";
                const text = a.textContent.trim();
                if (href.includes("designaciones-estos") && !seen.has(href)) {
                    seen.add(href);
                    articles.push({ href, text: text.substring(0, 120) });
                }
            });
            return JSON.stringify(articles);
        })()
        ''')
        articles = json.loads(result) if result else []

        # Filter by competition
        filtered = []
        for a in articles:
            url_lower = a['href'].lower()
            text_lower = a['text'].lower()
            if rfef_key == 'primera' and ('primera' in url_lower or 'primera' in text_lower):
                filtered.append(a)
            elif rfef_key == 'segunda' and ('segunda' in url_lower or 'segunda' in text_lower):
                filtered.append(a)

        print(f"  [RFEF] Found {len(filtered)} designation articles for {rfef_key}")
        for a in filtered[:5]:
            print(f"    {a['text'][:80]}")

        # Now visit each article and find the PDF link
        pdf_urls = []
        for article in filtered[:4]:  # Last 4 articles (covers a full matchday)
            cdp.evaluate(f'window.location.href = "{article["href"]}"')
            time.sleep(4)

            pdf_result = cdp.evaluate('''
            (() => {
                const pdfs = [];
                document.querySelectorAll("a[href]").forEach(a => {
                    if (a.href && a.href.includes(".pdf")) {
                        pdfs.push(a.href);
                    }
                });
                return JSON.stringify(pdfs);
            })()
            ''')
            pdfs = json.loads(pdf_result) if pdf_result else []
            for pdf_url in pdfs:
                if 'designacion' in pdf_url.lower():
                    pdf_urls.append({
                        'pdf_url': pdf_url,
                        'article_title': article['text'],
                        'article_url': article['href'],
                    })
                    print(f"    PDF: {pdf_url.split('/')[-1]}")
                    break

            # Go back to listing
            cdp.evaluate('window.history.back()')
            time.sleep(2)

        return pdf_urls

    finally:
        cdp.disconnect()
        requests.put(f'http://localhost:{CDP_PORT}/json/close/{tab["id"]}', timeout=5)


def download_pdf_via_browser(pdf_url):
    """Download a PDF using Chrome's fetch (bypasses 403)."""
    from cdp_client import CDPClient

    try:
        resp = requests.put(f'http://localhost:{CDP_PORT}/json/new?https://rfef.es', timeout=10)
        tab = resp.json()
    except:
        return None

    time.sleep(3)
    cdp = CDPClient(tab['webSocketDebuggerUrl'])
    cdp.connect()

    try:
        # Use relative URL if possible
        path = pdf_url.replace('https://rfef.es', '')
        result = cdp.send_command('Runtime.evaluate', {
            'expression': f'''
            (async () => {{
                const resp = await fetch("{path}");
                const blob = await resp.blob();
                return new Promise((resolve) => {{
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result.split(",")[1]);
                    reader.readAsDataURL(blob);
                }});
            }})()
            ''',
            'returnByValue': True,
            'awaitPromise': True,
            'timeout': 30000,
        })

        if result and result.get('result', {}).get('value'):
            return base64.b64decode(result['result']['value'])
        return None

    finally:
        cdp.disconnect()
        requests.put(f'http://localhost:{CDP_PORT}/json/close/{tab["id"]}', timeout=5)


def parse_rfef_pdf(pdf_bytes):
    """Parse an RFEF designation PDF into structured data."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    designations = []

    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"

    # Extract competition and matchday from footer
    comp_match = re.search(r'Competición:.*?(Primera|Segunda)\s+División', full_text, re.IGNORECASE)
    jornada_match = re.search(r'Jornada\s*-?\s*(\d+)', full_text, re.IGNORECASE)

    competition = ''
    if comp_match:
        competition = 'LaLiga' if 'primera' in comp_match.group(1).lower() else 'LaLiga Hypermotion'
    matchday = int(jornada_match.group(1)) if jornada_match else 0

    # Parse match blocks
    # Format: date, home team, away team, time, then Árbitro:, VAR:, etc.
    lines = [l.strip() for l in full_text.split('\n') if l.strip()]

    i = 0
    while i < len(lines):
        # Look for date pattern (dd-mm-yyyy)
        if re.match(r'\d{2}-\d{2}-\d{4}', lines[i]):
            date_str = lines[i]
            # Next lines: home team, away team, time
            if i + 3 < len(lines):
                home = lines[i + 1]
                away = lines[i + 2]
                match_time = lines[i + 3] if re.match(r'\d{2}:\d{2}', lines[i + 3]) else ''

                # Parse the rest (referee info)
                referee = ''
                var_ref = ''
                j = i + 4
                while j < len(lines) and not re.match(r'\d{2}-\d{2}-\d{4}', lines[j]):
                    line = lines[j]
                    if line.startswith('Árbitro:'):
                        referee = line.replace('Árbitro:', '').strip()
                    elif line.startswith('VAR:'):
                        var_ref = line.replace('VAR:', '').strip()
                    j += 1

                if home and away:
                    designations.append({
                        'match': f"{_clean_team(home)} vs {_clean_team(away)}",
                        'home': _clean_team(home),
                        'away': _clean_team(away),
                        'date': date_str,
                        'time': match_time,
                        'referee': referee,
                        'var': var_ref,
                    })

                i = j
                continue
        i += 1

    return {
        'competition': competition,
        'matchday': matchday,
        'designations': designations,
    }


def _clean_team(name):
    """Clean up team names from RFEF format."""
    # Remove common suffixes
    name = re.sub(r'\s*(S\.?A\.?D\.?|CF|FC|Club|de Fútbol|SAD)\s*$', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'^(Real|Deportivo|Unión)\s+', r'\1 ', name)  # Keep prefixes
    # Common shortenings
    replacements = {
        'RCD Espanyol de Barcelona': 'Espanyol',
        'RCD Mallorca': 'Mallorca',
        'Club Atlético de Madrid': 'Atlético de Madrid',
        'Real Sociedad de Fútbol': 'Real Sociedad',
        'Athletic Club': 'Athletic',
        'Rayo Vallecano de Madrid': 'Rayo Vallecano',
    }
    for full, short in replacements.items():
        if name.lower() == full.lower():
            return short
    return name


# ===================================================================
# Stage 2: Fetch referee statistics from transfermarkt
# ===================================================================

def load_stats_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_stats_cache(cache):
    os.makedirs(REFEREES_DIR, exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def fetch_all_referee_stats(competition='laliga'):
    """Fetch ALL referee stats from transfermarkt in one request."""
    cache = load_stats_cache()
    bulk_key = f'_bulk_{competition}'

    if bulk_key in cache:
        try:
            age = (datetime.now() - datetime.fromisoformat(cache[bulk_key])).days
            if age < 3:
                count = sum(1 for k in cache if not k.startswith('_'))
                print(f"  [cache] Using cached stats ({count} referees, < 3 days old)")
                return cache
        except:
            pass

    comp_info = COMPETITION_MAP.get(competition, {})
    tm_code = comp_info.get('tm_code', 'ES1')

    url = f'https://www.transfermarkt.es/laliga/schiedsrichter/wettbewerb/{tm_code}/saison_id/2025'
    print(f"  [transfermarkt] Fetching referee stats...")

    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [transfermarkt] HTTP {resp.status_code}")
            return cache

        soup = BeautifulSoup(resp.text, 'lxml')
        table = soup.select_one('table.items')
        if not table:
            return cache

        count = 0
        for row in table.select('tbody tr'):
            cells = row.select('td')
            if len(cells) < 8:
                continue

            name = cells[2].get_text(strip=True) if len(cells) > 2 else ''
            if not name:
                continue

            try:
                matches = int(cells[5].get_text(strip=True) or '0')
                yellows = int(cells[6].get_text(strip=True) or '0')
                reds = int(cells[7].get_text(strip=True) or '0')
                penalties = int(cells[9].get_text(strip=True) or '0') if len(cells) > 9 else 0
            except (ValueError, IndexError):
                continue

            if matches == 0:
                continue

            stats = {
                'matches_season': matches,
                'yellow_cards_total': yellows,
                'red_cards_total': reds,
                'penalties_total': penalties,
                'yellow_cards_per_match': round(yellows / matches, 2),
                'red_cards_per_match': round(reds / matches, 2),
                'penalties_per_match': round(penalties / matches, 2),
            }

            cache[_normalize_name(name)] = {**stats, '_name': name, '_cached_at': datetime.now().isoformat()}
            count += 1

        cache[bulk_key] = datetime.now().isoformat()
        save_stats_cache(cache)
        print(f"  [transfermarkt] Loaded stats for {count} referees")

    except Exception as e:
        print(f"  [transfermarkt] Error: {e}")

    return cache


def fetch_referee_stats(referee_name, competition='laliga', all_stats=None):
    """Look up stats for a specific referee."""
    if all_stats is None:
        all_stats = fetch_all_referee_stats(competition)

    cache_key = _normalize_name(referee_name)

    # Exact match
    if cache_key in all_stats and not cache_key.startswith('_'):
        entry = all_stats[cache_key]
        return {k: v for k, v in entry.items() if not k.startswith('_')}

    # Fuzzy match
    best_match = None
    best_ratio = 0.0
    for key, entry in all_stats.items():
        if key.startswith('_'):
            continue
        stored_name = entry.get('_name', key)
        if _names_match(referee_name, stored_name, threshold=0.55):
            ratio = SequenceMatcher(None, cache_key, _normalize_name(stored_name)).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = entry

    if best_match:
        return {k: v for k, v in best_match.items() if not k.startswith('_')}
    return None


# ===================================================================
# International referee stats (for Champions League)
# ===================================================================

def _fetch_international_stats(referee_names):
    """Fetch stats for international referees from transfermarkt.com (global version)."""
    cache = load_stats_cache()
    results = {}
    names_to_fetch = []

    # Check cache first
    for name in referee_names:
        key = _normalize_name(name)
        if key in cache and not key.startswith('_'):
            cached = cache[key]
            try:
                age = (datetime.now() - datetime.fromisoformat(cached.get('_cached_at', ''))).days
                if age < 7:
                    results[key] = {k: v for k, v in cached.items() if not k.startswith('_')}
                    continue
            except:
                pass
        names_to_fetch.append(name)

    if not names_to_fetch:
        return results

    # Try fetching from transfermarkt.com Champions League referee page
    try:
        from bs4 import BeautifulSoup
        url = 'https://www.transfermarkt.com/uefa-champions-league/schiedsrichter/pokalwettbewerb/CL/saison_id/2025'
        resp = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }, timeout=15)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            table = soup.select_one('table.items')
            if table:
                for row in table.select('tbody tr'):
                    cells = row.select('td')
                    if len(cells) < 8:
                        continue
                    name = cells[2].get_text(strip=True) if len(cells) > 2 else ''
                    if not name:
                        continue
                    try:
                        matches = int(cells[5].get_text(strip=True) or '0')
                        yellows = int(cells[6].get_text(strip=True) or '0')
                        reds = int(cells[7].get_text(strip=True) or '0')
                        penalties = int(cells[9].get_text(strip=True) or '0') if len(cells) > 9 else 0
                    except (ValueError, IndexError):
                        continue
                    if matches == 0:
                        continue

                    stats = {
                        'matches_season': matches,
                        'yellow_cards_total': yellows,
                        'red_cards_total': reds,
                        'penalties_total': penalties,
                        'yellow_cards_per_match': round(yellows / matches, 2),
                        'red_cards_per_match': round(reds / matches, 2),
                        'penalties_per_match': round(penalties / matches, 2),
                    }
                    key = _normalize_name(name)
                    cache[key] = {**stats, '_name': name, '_cached_at': datetime.now().isoformat()}
                    results[key] = stats

                print(f"  [transfermarkt.com] Loaded {len(results)} international referees")
                save_stats_cache(cache)
        else:
            print(f"  [transfermarkt.com] HTTP {resp.status_code}")

    except Exception as e:
        print(f"  [transfermarkt.com] Error: {e}")

    # Match requested names to fetched stats (fuzzy)
    final = {}
    for name in referee_names:
        key = _normalize_name(name)
        if key in results:
            final[key] = results[key]
            continue
        # Fuzzy match
        best_ratio = 0
        best_stats = None
        for rkey, rstats in results.items():
            ratio = SequenceMatcher(None, key, rkey).ratio()
            if ratio > best_ratio and ratio > 0.55:
                best_ratio = ratio
                best_stats = rstats
        if best_stats:
            final[key] = best_stats

    return final


# ===================================================================
# Stage 3: Verdicts
# ===================================================================

def calculate_verdict(stats):
    if not stats:
        return "SIN DATOS — no se encontraron estadísticas"
    ypm = stats.get('yellow_cards_per_match', 0)
    if ypm >= 4.5:
        return f"ALTO — pick de tarjetas viable (≥ 4.5 TA/p)"
    elif ypm >= 3.5:
        return f"MEDIO — evaluar con contexto (3.5-4.5 TA/p)"
    else:
        return f"BAJO — no pick de tarjetas (< 3.5 TA/p)"


# ===================================================================
# Name utilities
# ===================================================================

def _normalize_name(name):
    name = name.strip().lower()
    nfkd = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _names_match(name1, text, threshold=0.6):
    n1 = _normalize_name(name1)
    n2 = _normalize_name(text)
    if n1 in n2 or n2 in n1:
        return True
    words = n1.split()
    if len(words) >= 2:
        matches = sum(1 for w in words if w in n2)
        if matches >= len(words) - 1:
            return True
    return SequenceMatcher(None, n1, n2).ratio() >= threshold


# ===================================================================
# Champions League: parse UEFA article
# ===================================================================

def scrape_champions_league():
    """Scrape Champions League referee designations from UEFA article."""
    from cdp_client import CDPClient

    print(f"\n{'='*60}")
    print(f"  Champions League - Referee Designations")
    print(f"{'='*60}")

    print("\n[1] Fetching UEFA article...")
    try:
        resp = requests.put(f'http://localhost:{CDP_PORT}/json/new?https://es.uefa.com', timeout=10)
        tab = resp.json()
    except Exception as e:
        print(f"  ERROR: Chrome not available: {e}")
        return None

    time.sleep(4)
    cdp = CDPClient(tab['webSocketDebuggerUrl'])
    cdp.connect()

    try:
        cdp.evaluate(f'window.location.href = "{UEFA_CL_ARTICLE}"')
        time.sleep(10)

        text = cdp.evaluate('document.body ? document.body.textContent : ""')
        if not text or len(text) < 1000:
            print("  Page didn't load")
            return None

        print(f"  Page loaded ({len(text)} chars)")

        # Parse the article text for referee assignments
        # Format: "TeamA - TeamB - Referee Name (Country)"
        designations = _parse_uefa_article(text)
        print(f"  Found {len(designations)} matches with referees")

    finally:
        cdp.disconnect()
        requests.put(f'http://localhost:{CDP_PORT}/json/close/{tab["id"]}', timeout=5)

    if not designations:
        return None

    # Fetch international referee stats from transfermarkt.com (global)
    print(f"\n[2] Fetching international referee stats...")
    intl_stats = _fetch_international_stats([d['referee'] for d in designations])

    referees_output = []
    for d in designations:
        referee_name = d['referee']
        stats = intl_stats.get(_normalize_name(referee_name))
        verdict = calculate_verdict(stats) if stats else 'SIN DATOS — buscar manualmente'

        if stats:
            ypm = stats.get('yellow_cards_per_match', 0)
            print(f"  {d['match']:45s} | {referee_name:25s} | {ypm:.1f} TA/P | {verdict.split(' — ')[0]}")
        else:
            print(f"  {d['match']:45s} | {referee_name:25s} | ?.?  TA/P | SIN DATOS")

        referees_output.append({
            'match': d['match'],
            'home': d.get('home', ''),
            'away': d.get('away', ''),
            'date': d.get('date', ''),
            'referee': referee_name,
            'country': d.get('country', ''),
            'round': d.get('round', ''),
            'leg': d.get('leg', ''),
            'var': '',
            'stats': stats,
            'verdict': verdict,
        })

    # Determine round name for filename
    rounds = [d.get('round', '') for d in designations if d.get('round')]
    round_name = rounds[0] if rounds else 'unknown'

    output = {
        'competition': 'Champions League',
        'round': round_name,
        'scraped_at': datetime.now().isoformat(),
        'total_referees': len([r for r in referees_output if r['referee']]),
        'referees': referees_output,
    }
    return output


def _parse_uefa_article(text):
    """Parse UEFA Champions League article text for referee assignments."""
    designations = []
    full_text = ' '.join(text.split('\n'))

    # Parse "TeamA - TeamB - Referee (COUNTRY)" patterns
    match_pattern = re.compile(
        r'([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:de\s+)?[A-ZÀ-Ú]?[a-zà-ú.]+)*)'  # Team 1
        r'\s*-\s*'
        r'([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:de\s+)?[A-ZÀ-Ú]?[a-zà-ú.]+)*)'  # Team 2
        r'\s*-\s*'
        r'([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú]?[a-zà-ú]+)*)'  # Referee
        r'\s*\((\w{3})\)'  # Country code
    )

    for match in match_pattern.finditer(full_text):
        team1 = match.group(1).strip()
        team2 = match.group(2).strip()
        referee = match.group(3).strip()
        country = match.group(4).strip()

        # Look backwards for round/leg/date context
        before = full_text[max(0, match.start() - 300):match.start()]

        # Round
        round_name = ''
        for rnd in ['Semifinales', 'Cuartos de final', 'Octavos de final', 'Dieciseisavos']:
            if rnd.lower() in before.lower():
                round_name = rnd
                break

        # Leg
        leg = ''
        if 'Vuelta' in before:
            leg = 'Vuelta'
        elif 'Ida' in before:
            leg = 'Ida'

        # Date
        date_m = re.search(r'(?:Martes|Miércoles|Jueves|Viernes|Lunes|Sábado|Domingo)\s+\d+\s+de\s+\w+', before)
        date_str = date_m.group(0) if date_m else ''

        designations.append({
            'match': f"{team1} vs {team2}",
            'home': team1, 'away': team2,
            'referee': referee, 'country': country,
            'round': round_name, 'leg': leg, 'date': date_str,
        })

    return designations


# ===================================================================
# Main orchestrator
# ===================================================================

def scrape_competition(competition):
    """Full pipeline: find PDFs → parse → stats → verdicts."""
    comp_info = COMPETITION_MAP.get(competition)
    if not comp_info:
        print(f"ERROR: Unknown competition '{competition}'")
        return None

    # Champions League has its own pipeline
    if competition == 'champions':
        return scrape_champions_league()

    comp_name = comp_info['name']
    print(f"\n{'='*60}")
    print(f"  {comp_name} - Referee Designations")
    print(f"{'='*60}")

    # Stage 1: Find RFEF designation PDFs
    print("\n[1] Finding RFEF designation articles...")
    pdf_entries = find_rfef_designation_urls(competition)

    if not pdf_entries:
        print("  No designation PDFs found")
        return None

    # Download and parse each PDF
    all_designations = []
    matchday = 0

    for entry in pdf_entries:
        print(f"\n[2] Downloading PDF: {entry['pdf_url'].split('/')[-1]}")
        pdf_bytes = download_pdf_via_browser(entry['pdf_url'])

        if not pdf_bytes:
            print("  Failed to download PDF")
            continue

        parsed = parse_rfef_pdf(pdf_bytes)
        if parsed['matchday']:
            matchday = parsed['matchday']
        all_designations.extend(parsed['designations'])
        print(f"  Parsed {len(parsed['designations'])} matches (Jornada {parsed['matchday']})")

    if not all_designations:
        print("  No designations parsed from PDFs")
        return None

    # Stage 2: Fetch stats
    print(f"\n[3] Fetching referee statistics...")
    all_stats = fetch_all_referee_stats(competition)

    # Stage 3: Build output with verdicts
    referees_output = []
    for d in all_designations:
        referee_name = d.get('referee', '')
        stats = fetch_referee_stats(referee_name, competition, all_stats) if referee_name else None
        verdict = calculate_verdict(stats)

        if stats:
            ypm = stats.get('yellow_cards_per_match', 0)
            print(f"  {d['match']:40s} | {referee_name:25s} | {ypm:4.1f} TA/P | {verdict.split(' — ')[0]}")
        else:
            print(f"  {d['match']:40s} | {referee_name:25s} | ?.?  TA/P | {verdict.split(' — ')[0]}")

        referees_output.append({
            'match': d['match'],
            'home': d.get('home', ''),
            'away': d.get('away', ''),
            'date': d.get('date', ''),
            'time': d.get('time', ''),
            'referee': referee_name,
            'var': d.get('var', ''),
            'stats': stats,
            'verdict': verdict,
        })

    output = {
        'competition': comp_name,
        'matchday': matchday,
        'scraped_at': datetime.now().isoformat(),
        'total_referees': len([r for r in referees_output if r['referee']]),
        'referees': referees_output,
    }

    return output


def save_output(output):
    """Save to referees/ directory."""
    os.makedirs(REFEREES_DIR, exist_ok=True)
    comp = output['competition'].lower().replace(' ', '-')
    date_str = datetime.now().strftime('%Y-%m-%d')
    if output.get('matchday'):
        fname = f"{comp}_jornada-{output['matchday']}_{date_str}.json"
    elif output.get('round'):
        round_slug = output['round'].lower().replace(' ', '-').replace('á', 'a')
        fname = f"{comp}_{round_slug}_{date_str}.json"
    else:
        fname = f"{comp}_{date_str}.json"
    fpath = os.path.join(REFEREES_DIR, fname)

    with open(fpath, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved: referees/{fname}")
    return fname


def lookup_single_referee(name, competition='laliga'):
    """Lookup stats for a single referee."""
    print(f"\nLooking up: {name}")
    all_stats = fetch_all_referee_stats(competition)
    stats = fetch_referee_stats(name, competition, all_stats)
    if stats:
        verdict = calculate_verdict(stats)
        print(f"\n  Stats: {json.dumps(stats, indent=2)}")
        print(f"  Verdict: {verdict}")
    else:
        print(f"  No stats found for '{name}'")
        norm = _normalize_name(name)
        close = [(k, SequenceMatcher(None, norm, k).ratio())
                 for k in all_stats if not k.startswith('_')]
        close.sort(key=lambda x: -x[1])
        print(f"  Closest matches:")
        for k, r in close[:5]:
            print(f"    {all_stats[k].get('_name', k)} (sim: {r:.2f})")
    return stats


# ===================================================================
# CLI
# ===================================================================

def main():
    parser = argparse.ArgumentParser(description='Spanish Football Referee Scraper')
    parser.add_argument('--competition', '-c', default='laliga',
                        choices=['laliga', 'primera', 'segunda', 'champions'])
    parser.add_argument('--stats-only', help='Only fetch stats for this referee')
    args = parser.parse_args()

    if args.stats_only:
        lookup_single_referee(args.stats_only, args.competition)
        return

    output = scrape_competition(args.competition)
    if output:
        save_output(output)

        label = output['competition']
        if output.get('matchday'):
            label += f" Jornada {output['matchday']}"
        elif output.get('round'):
            label += f" - {output['round']}"

        print(f"\n{'='*60}")
        print(f"  RESUMEN - {label}")
        print(f"{'='*60}")
        for r in output['referees']:
            ypm = f"{r['stats']['yellow_cards_per_match']:.1f}" if r.get('stats') else '?.?'
            v = r['verdict'].split(' — ')[0]
            print(f"  {r['match']:40s} | {r['referee']:25s} | {ypm:>5} TA/P | {v}")


if __name__ == '__main__':
    main()
