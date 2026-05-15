#!/usr/bin/env python3
"""
bet365 Odds Scraper v6 - Multi-match with new-tab navigation.

Each match opens in a NEW Chrome tab (via CDP Target.createTarget),
avoiding SPA navigation issues. Supports both live and pre-match.

Usage:
  python3 scrape_bet365.py -o odds.json
  python3 scrape_bet365.py --priority -o odds.json
  python3 scrape_bet365.py --groups "Total de goles" "Tarjetas" -o odds.json
  python3 scrape_bet365.py --urls URL1 URL2 ... -o odds.json
  python3 scrape_bet365.py --groups-only
  python3 scrape_bet365.py --list
"""

import argparse, json, sys, time, re
from datetime import datetime
from cdp_client import CDPClient
import requests as req

CDP_PORT = 9222
CDP_HOST = 'localhost'

# ===================================================================
# JavaScript
# ===================================================================

JS_MATCH_INFO = r"""
(() => {
    let home = '', away = '', comp = '', dt = '';

    // Pre-match selectors
    const pmTeams = document.querySelectorAll('.sph-FixturePodHeader_TeamName');
    if (pmTeams.length >= 2) {
        home = pmTeams[0].textContent.trim();
        away = pmTeams[1].textContent.trim();
    }
    const pmComp = document.querySelector('.sph-FixturePodHeader_Competition');
    if (pmComp) comp = pmComp.textContent.trim();
    const pmDt = document.querySelector('.sph-ExtraData_TimeStamp');
    if (pmDt) dt = pmDt.textContent.trim();

    // Live/in-play fallback: extract from body text "TeamA v TeamB" pattern
    if (!home || !away) {
        const bodyText = document.body.textContent;
        // Look for "< Competition\nTeamA v TeamB" pattern
        const m = bodyText.match(/([A-ZÀ-Úa-zà-ú0-9. ]+?)\s+v\s+([A-ZÀ-Úa-zà-ú0-9. ]+?)(?:\s*\d{1,3}:\d{2}|\s*(?:Todos|Crear))/);
        if (m) {
            home = m[1].trim();
            away = m[2].trim();
        }
    }

    // Live: competition from breadcrumb
    if (!comp) {
        const bc = document.body.textContent.match(/[<‹]\s*(.*?(?:Liga|League|Serie|Ligue|Bundesliga|Champions)[^<\n]*)/i);
        if (bc) comp = bc[1].trim();
    }

    const isLive = window.location.hash.includes('/IP/');
    return JSON.stringify({
        match: (home && away) ? home + ' vs ' + away : '',
        home, away, competition: comp, datetime: dt,
        url: window.location.href, isLive,
    });
})()
"""

JS_LIST_GROUPS = """
(() => {
    const groups = [], seen = new Set();
    document.querySelectorAll(
        '.gl-MarketGroupPod, [class*="MarketGroupPod"], [class*="ip-MarketGroup"]'
    ).forEach((pod, i) => {
        const btn = pod.querySelector('.gl-MarketGroupButton, [class*="MarketGroupButton"]');
        if (!btn) return;
        const el = btn.querySelector(
            '.gl-MarketGroupButton_Text, [class*="MarketGroupButton_Text"], [class*="HeaderText"]'
        );
        const name = el ? el.textContent.trim() : btn.textContent.trim();
        if (!name || seen.has(name)) return;
        seen.add(name);
        groups.push({ index: i, name: name.substring(0, 80), isOpen: btn.className.includes('Open') });
    });
    return JSON.stringify(groups);
})()
"""

JS_LIST_TABS = """
(() => {
    const tabs = [], seen = new Set();
    document.querySelectorAll('.sph-MarketGroupNavBarButton, [class*="MarketGroupNavBarButton"]').forEach(el => {
        const n = el.textContent.trim();
        if (n && !seen.has(n)) { seen.add(n); tabs.push({ name: n, isActive: el.className.includes('Selected') || el.className.includes('ctive') }); }
    });
    return JSON.stringify(tabs);
})()
"""

def js_click_group(name):
    e = name.replace('"', '\\"')
    return f'(() => {{ for (const p of document.querySelectorAll(".gl-MarketGroupPod, [class*=\\"MarketGroupPod\\"], [class*=\\"ip-MarketGroup\\"]")) {{ const b = p.querySelector(".gl-MarketGroupButton, [class*=\\"MarketGroupButton\\"]"); if (!b) continue; const t = b.querySelector(".gl-MarketGroupButton_Text, [class*=\\"MarketGroupButton_Text\\"], [class*=\\"HeaderText\\"]"); const n = t ? t.textContent.trim() : b.textContent.trim(); if (n === "{e}" || n.startsWith("{e}")) {{ b.click(); return "ok"; }} }} return "miss"; }})()'

def js_scroll_to(name):
    e = name.replace('"', '\\"')
    return f'(() => {{ for (const p of document.querySelectorAll(".gl-MarketGroupPod, [class*=\\"MarketGroupPod\\"], [class*=\\"ip-MarketGroup\\"]")) {{ const b = p.querySelector(".gl-MarketGroupButton, [class*=\\"MarketGroupButton\\"]"); if (!b) continue; const t = b.querySelector(".gl-MarketGroupButton_Text, [class*=\\"MarketGroupButton_Text\\"], [class*=\\"HeaderText\\"]"); const n = t ? t.textContent.trim() : b.textContent.trim(); if (n === "{e}" || n.startsWith("{e}")) {{ p.scrollIntoView({{behavior:"instant",block:"start"}}); return "ok"; }} }} return "miss"; }})()'

JS_SHOW_MORE = '(() => { let c=0; document.querySelectorAll(\'[class*="ShowMore"]\').forEach(el => { if (/ver más|show more/i.test(el.textContent.trim())) { try { el.click(); c++; } catch(e) {} } }); return c; })()'

# --- Filter triggers and options ---

JS_GET_FILTER_TRIGGERS = """
(() => {
    const result = { team: null, period: null };
    document.querySelectorAll('[class*="bbl-DropDown-left"]').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width > 10 && r.height > 5 && r.top > 0 && !result.team)
            result.team = { text: el.textContent.trim(), x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2) };
    });
    document.querySelectorAll('[class*="bbl-DropDown-right"]').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width > 10 && r.height > 5 && r.top > 0 && !result.period)
            result.period = { text: el.textContent.trim(), x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2) };
    });
    return JSON.stringify(result);
})()
"""

def js_read_dropdown(side):
    cls = 'LeftCont' if side == 'left' else 'RightCon'
    return f"""
    (() => {{
        const opts = [], seen = new Set();
        document.querySelectorAll('[class*="bbl-DropDownSwitcherMarketGroup_{cls}"] div, [class*="bbl-DropDownSwitcherMarketGroup_{cls}"] span').forEach(el => {{
            const t = el.textContent.trim();
            if (!t || t.length<2 || t.length>30 || el.children.length>2 || seen.has(t)) return;
            const r = el.getBoundingClientRect();
            if (r.width<15 || r.height<8 || r.top<=0) return;
            seen.add(t);
            opts.push({{ text:t, x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2) }});
        }});
        return JSON.stringify(opts);
    }})()
    """

def js_click_at(x, y):
    return f'(() => {{ const el=document.elementFromPoint({x},{y}); if(el){{el.click();return el.textContent.trim().substring(0,40);}} return "miss"; }})()'

# --- Odds extraction ---

# Tree walker as PRIMARY method — captures ALL odds from any market type
JS_EXTRACT_ODDS = """
(() => {
    const results = [];
    const oddsRx = /^\\d{1,3}\\.\\d{2}$/;

    document.querySelectorAll('.gl-MarketGroupPod, [class*="MarketGroupPod"], [class*="ip-MarketGroup"]').forEach(pod => {
        const btn = pod.querySelector('.gl-MarketGroupButton, [class*="MarketGroupButton"]');
        if (!btn || !btn.className.includes('Open')) return;
        const nameEl = btn.querySelector('.gl-MarketGroupButton_Text, [class*="MarketGroupButton_Text"], [class*="HeaderText"]');
        const groupName = nameEl ? nameEl.textContent.trim() : btn.textContent.trim();

        const odds = [];
        const seen = new Set();

        // PRIMARY: Tree walker — walks ALL text nodes, finds every decimal odds value
        const walker = document.createTreeWalker(pod, NodeFilter.SHOW_TEXT, null);
        let node;
        while (node = walker.nextNode()) {
            const t = node.textContent.trim();
            if (!oddsRx.test(t)) continue;

            // Build context: walk up to find the selection label
            let ctx = '', p = node.parentElement;
            for (let i = 0; i < 6 && p && p !== pod; i++) {
                const pt = p.textContent.trim();
                if (pt.length > t.length + 1 && pt.length < 200) { ctx = pt; break; }
                p = p.parentElement;
            }

            // Deduplicate by context+value (same odds can appear in nested nodes)
            const key = ctx + '|' + t;
            if (seen.has(key)) continue;
            seen.add(key);

            // Try to get structured label from bbl/gl classes
            let sel = '', col = '';
            const parentEl = node.parentElement;
            if (parentEl) {
                // Check if this is inside a bbl-BetBuilderParticipant
                const bblRow = parentEl.closest('[class*="BetBuilderParticipant"]');
                if (bblRow) {
                    const label = bblRow.querySelector('[class*="ParticipantLabel_Name"], [class*="Label_Name"]');
                    if (label) sel = label.textContent.trim();
                    const market = bblRow.closest('.gl-Market_General, [class*="gl-Market"]');
                    if (market) {
                        const colH = market.querySelector('[class*="StickyMarketColumnHeader_Label"], [class*="ColumnHeader"]');
                        if (colH) col = colH.textContent.trim();
                    }
                }
                // Check gl-Participant
                if (!sel) {
                    const glRow = parentEl.closest('[class*="gl-Participant"]');
                    if (glRow) {
                        const nameEl2 = glRow.querySelector('[class*="Name"]');
                        if (nameEl2) sel = nameEl2.textContent.trim();
                    }
                }
                // Fallback: use context minus the odds value
                if (!sel) {
                    sel = ctx.replace(t, '').trim().substring(0, 80);
                }
            }

            odds.push({ sel, col, odds: parseFloat(t) });
        }

        if (odds.length > 0) results.push({ name: groupName.substring(0, 80), odds });
    });
    return JSON.stringify(results);
})()
"""

# ===================================================================
# Core functions
# ===================================================================

def get_chrome_tabs(host=CDP_HOST, port=CDP_PORT):
    try:
        return req.get(f'http://{host}:{port}/json', timeout=5).json()
    except:
        print(f"ERROR: Chrome not responding on port {port}")
        print(f"  1. Cmd+Q Chrome  2. bash launch_chrome.sh")
        sys.exit(1)


def create_tab(url, host=CDP_HOST, port=CDP_PORT):
    """Create a new Chrome tab with the given URL via CDP HTTP API."""
    try:
        resp = req.put(f'http://{host}:{port}/json/new?{url}', timeout=10)
        tab_info = resp.json()
        return tab_info
    except Exception as e:
        print(f"  ERROR creating tab: {e}")
        return None


def close_tab(tab_id, host=CDP_HOST, port=CDP_PORT):
    """Close a Chrome tab by its ID."""
    try:
        req.put(f'http://{host}:{port}/json/close/{tab_id}', timeout=5)
    except:
        pass


def connect_to_tab(tab_info):
    """Connect CDP client to a tab."""
    ws_url = tab_info.get('webSocketDebuggerUrl', '')
    if not ws_url:
        return None
    cdp = CDPClient(ws_url)
    if cdp.connect():
        return cdp
    return None


def wait_for_page(cdp, timeout=30):
    """Wait for bet365 SPA to fully load (market content, not just shell)."""
    for i in range(int(timeout / 0.5)):
        # Check for bet365-specific elements that indicate the SPA is loaded
        result = cdp.evaluate("""
        (() => {
            const sph = document.querySelectorAll('[class*="sph-"]').length;
            const gl = document.querySelectorAll('[class*="gl-"]').length;
            const ip = document.querySelectorAll('[class*="ip-"]').length;
            const bl = document.body ? document.body.textContent.length : 0;
            return JSON.stringify({ sph, gl, ip, bl });
        })()
        """)
        try:
            info = json.loads(result) if result else {}
        except:
            info = {}

        sph = info.get('sph', 0)
        gl = info.get('gl', 0)
        ip = info.get('ip', 0)
        bl = info.get('bl', 0)

        # Page is ready when we see market-related elements
        if sph > 5 or gl > 5 or ip > 5:
            return True

        time.sleep(0.5)
        if i % 6 == 5:
            print(f"    [{(i+1)*0.5:.0f}s] sph={sph} gl={gl} ip={ip} body={bl}")
    return False


def open_dropdown_read(cdp, trigger, side):
    cdp.evaluate(js_click_at(trigger['x'], trigger['y']))
    time.sleep(0.8)
    raw = cdp.evaluate(js_read_dropdown(side))
    opts = json.loads(raw) if raw else []
    cdp.evaluate('document.body.click()')
    time.sleep(0.4)
    return opts


def select_filter(cdp, trigger, option_text, side):
    cdp.evaluate(js_click_at(trigger['x'], trigger['y']))
    time.sleep(0.6)
    raw = cdp.evaluate(js_read_dropdown(side))
    for opt in json.loads(raw) if raw else []:
        if opt['text'] == option_text:
            cdp.evaluate(js_click_at(opt['x'], opt['y']))
            time.sleep(1.0)
            return True
    cdp.evaluate('document.body.click()')
    time.sleep(0.3)
    return False


def extract_open_odds(cdp, group_name):
    raw = cdp.evaluate(JS_EXTRACT_ODDS)
    for g in json.loads(raw or '[]'):
        if g['name'].startswith(group_name[:25]):
            return g.get('odds', [])
    return []


def ensure_markets_view(cdp, is_live):
    """Check that markets are loaded. If already on Bet Builder with groups, don't touch anything."""
    raw = cdp.evaluate(JS_LIST_GROUPS)
    n = len(json.loads(raw or '[]'))
    if n > 5:
        return True

    # Try clicking Bet Builder / Crear apuesta (safe: just clicks a nav button)
    if not is_live:
        clicked = cdp.evaluate("""
        (() => {
            for (const el of document.querySelectorAll('[class*="MarketGroupNavBarButton"], [class*="NavBarButton"]')) {
                const t = el.textContent.trim();
                if (t === 'Crear apuesta' || t === 'Crear apuestas' || t === 'Bet Builder') {
                    if (el.className.includes('Selected') || el.className.includes('ctive')) return 'already';
                    el.click(); return t;
                }
            }
            return 'miss';
        })()
        """)
        if clicked and clicked not in ('miss', 'already'):
            print(f"    Clicked '{clicked}'")
            for attempt in range(20):
                time.sleep(1)
                raw = cdp.evaluate(JS_LIST_GROUPS)
                n = len(json.loads(raw or '[]'))
                if n > 5:
                    print(f"    Loaded {n} groups after {attempt+1}s")
                    return True
                if attempt % 5 == 4:
                    print(f"    [{attempt+1}s] waiting... {n} groups")
        elif clicked == 'already':
            # Already on Bet Builder, wait a bit for lazy load
            for attempt in range(10):
                time.sleep(1)
                raw = cdp.evaluate(JS_LIST_GROUPS)
                n = len(json.loads(raw or '[]'))
                if n > 5:
                    return True

    # Try "Todos" tab (live default)
    if is_live:
        cdp.evaluate("""
        (() => {
            for (const el of document.querySelectorAll('[class*="MarketGroupNavBarButton"], [class*="NavBarButton"]')) {
                if (el.textContent.trim() === 'Todos') { el.click(); return; }
            }
        })()
        """)
        time.sleep(2)

    return len(json.loads(cdp.evaluate(JS_LIST_GROUPS) or '[]')) > 0


def scrape_group(cdp, group_name, is_live=False):
    """Expand group, iterate ALL filter combos (team × period), extract odds via tree walker."""
    # Close any previously open group first
    cdp.evaluate("""
    (() => {
        document.querySelectorAll('.gl-MarketGroupPod, [class*="MarketGroupPod"]').forEach(pod => {
            const btn = pod.querySelector('.gl-MarketGroupButton, [class*="MarketGroupButton"]');
            if (btn && btn.className.includes('Open')) btn.click();
        });
    })()
    """)
    time.sleep(0.5)

    # Scroll to and open this group
    cdp.evaluate(js_scroll_to(group_name))
    time.sleep(0.3)
    cdp.evaluate(js_click_group(group_name))
    time.sleep(1.5)

    # Click all "Ver más" / "Show more" buttons
    cdp.evaluate(JS_SHOW_MORE)
    time.sleep(0.5)

    # Detect dropdown filters (team and period selectors)
    team_opts = []
    period_opts = []

    if not is_live:
        raw = cdp.evaluate(JS_GET_FILTER_TRIGGERS)
        triggers = json.loads(raw) if raw else {}

        if triggers.get('team'):
            team_opts = open_dropdown_read(cdp, triggers['team'], 'left')
            if team_opts:
                print(f"      Team options: {[o['text'] for o in team_opts]}")

        if triggers.get('period'):
            period_opts = open_dropdown_read(cdp, triggers['period'], 'right')
            if period_opts:
                print(f"      Period options: {[o['text'] for o in period_opts]}")

    teams = team_opts if team_opts else [None]
    periods = period_opts if period_opts else [None]
    has_filters = len(team_opts) > 0 or len(period_opts) > 0

    all_data = []
    combo_count = len(teams) * len(periods)

    for ti, t in enumerate(teams):
        for pi, p in enumerate(periods):
            parts = []
            if t: parts.append(t['text'])
            if p: parts.append(p['text'])
            label = ' / '.join(parts) if parts else 'default'

            # Select team filter (always re-read trigger position)
            if t:
                tr = json.loads(cdp.evaluate(JS_GET_FILTER_TRIGGERS) or '{}')
                if tr.get('team'):
                    select_filter(cdp, tr['team'], t['text'], 'left')
                else:
                    print(f"      WARN: team trigger not found for {t['text']}")

            # Select period filter (always re-read trigger position)
            if p:
                tr = json.loads(cdp.evaluate(JS_GET_FILTER_TRIGGERS) or '{}')
                if tr.get('period'):
                    select_filter(cdp, tr['period'], p['text'], 'right')
                else:
                    print(f"      WARN: period trigger not found for {p['text']}")

            # Click "Ver más" again after filter change
            cdp.evaluate(JS_SHOW_MORE)
            time.sleep(0.4)

            # Extract odds using tree walker
            odds = extract_open_odds(cdp, group_name)
            all_data.append({'filter': label, 'odds': odds})

            combo_num = ti * len(periods) + pi + 1
            if has_filters:
                print(f"    [{combo_num}/{combo_count}] {label} -> {len(odds)} odds")
            else:
                print(f"    {len(odds)} odds")

    # Collapse the group
    cdp.evaluate(js_click_group(group_name))
    time.sleep(0.3)
    return all_data


PRIORITY_GROUPS = [
    'Total de goles', 'Ambos equipos anotarán', 'Córners', 'Tarjetas',
    'Ambos equipos recibirán tarjetas', 'Total - Remates a puerta',
    'Total - Remates', 'Paradas del portero', 'Equipo - Mayor número',
    'Goles - Intervalo', 'Resultado', 'Doble oportunidad',
    'Descanso/Resultado final', 'Marcador',
    'Mitad con el mayor número de goles', 'Margen de victoria',
    # Live-specific market names
    'Encuentro - Goles', 'Encuentro - Córners', 'Número de Tarjetas',
    'Resultado final', 'Córners - 2 opciones', 'Marcador final',
    'Hándicap - Córners', 'Más córners',
    '2ª mitad - Ambos equipos anotarán',
    'Encuentro - Remates a puerta', 'Encuentro - Remates',
    'Equipo - Remates a puerta', 'Equipo - Remates',
    'Córners asiáticos',
]


def scrape_match_on_tab(cdp, only_groups=None):
    """Scrape all market groups from the currently loaded match tab."""
    raw = cdp.evaluate(JS_MATCH_INFO)
    match_info = json.loads(raw) if raw else {}
    is_live = match_info.get('isLive', False)
    match_name = match_info.get('match', '?')
    print(f"  Match: {match_name} | {match_info.get('competition','')} | {'LIVE' if is_live else match_info.get('datetime','')}")

    ensure_markets_view(cdp, is_live)

    groups = json.loads(cdp.evaluate(JS_LIST_GROUPS) or '[]')
    print(f"  Groups: {len(groups)}")

    if only_groups:
        groups = [g for g in groups if any(og.lower() in g['name'].lower() for og in only_groups)]
        print(f"  Filtered: {len(groups)}")

    all_results = {}
    for i, group in enumerate(groups):
        name = group['name']
        clean = re.sub(r'Sustituto\+$', '', name).strip()
        print(f"\n  [{i+1}/{len(groups)}] {clean}")
        try:
            data = scrape_group(cdp, name, is_live=is_live)
            if data:
                all_results.setdefault(clean, []).extend(data)
        except Exception as e:
            print(f"    ERROR: {e}")
            cdp.evaluate('document.body.click()')
            time.sleep(0.5)

    return match_info, all_results


def build_output(match_info, all_results):
    output = {
        'match': match_info.get('match', ''),
        'home': match_info.get('home', ''),
        'away': match_info.get('away', ''),
        'competition': match_info.get('competition', ''),
        'datetime': match_info.get('datetime', ''),
        'url': match_info.get('url', ''),
        'isLive': match_info.get('isLive', False),
        'scraped_at': datetime.now().isoformat(),
        'markets': {},
    }
    total = 0
    for name, filter_data in all_results.items():
        entry = {}
        for fd in filter_data:
            odds = fd['odds']
            if not odds: continue
            structured = []
            for o in odds:
                e = {'odds': o.get('odds', 0)}
                if o.get('sel'): e['selection'] = o['sel']
                if o.get('col'): e['column'] = o['col']
                structured.append(e)
                total += 1
            entry[fd['filter']] = structured
        if entry:
            output['markets'][name] = entry
    output['summary'] = {
        'total_odds': total,
        'total_markets': len(output['markets']),
        'market_names': list(output['markets'].keys()),
    }
    return output


# ===================================================================
# Multi-match: open each URL in a NEW tab
# ===================================================================

def scrape_single_url(url, only_groups=None, host=CDP_HOST, port=CDP_PORT):
    """Open URL in a new Chrome tab, scrape it, close the tab."""
    print(f"\n{'='*60}")
    print(f"Opening new tab: {url}")

    # Chrome ignores hash fragments when creating tabs via API.
    # So we open bet365.com first, then navigate via JS hash change.
    base_url = 'https://www.bet365.com/'
    hash_part = url.split('#')[1] if '#' in url else ''

    tab_info = create_tab(base_url, host, port)
    if not tab_info:
        print("  FAILED to create tab")
        return None

    tab_id = tab_info.get('id', '')

    cdp = connect_to_tab(tab_info)
    if not cdp:
        print("  FAILED to connect to tab")
        close_tab(tab_id, host, port)
        return None

    try:
        # Wait for bet365 base page to load
        print("  Waiting for bet365 to initialize...")
        time.sleep(3)
        for i in range(20):
            bl = cdp.evaluate('document.body ? document.body.textContent.length : 0')
            try:
                bl = int(bl) if bl else 0
            except:
                bl = 0
            if bl > 3000:
                break
            time.sleep(0.5)

        # Now navigate to the specific match via hash
        if hash_part:
            print(f"  Navigating to #{hash_part[:50]}...")
            cdp.evaluate(f'window.location.hash = "#{hash_part}"')
            time.sleep(3)

        # Wait for match content to load
        print("  Waiting for match content...")
        if not wait_for_page(cdp, timeout=30):
            # Try reloading the hash
            print("  Retrying navigation...")
            cdp.evaluate(f'window.location.hash = "#{hash_part}"')
            time.sleep(3)
            wait_for_page(cdp, timeout=15)

        match_info, results = scrape_match_on_tab(cdp, only_groups)
        output = build_output(match_info, results)
        print(f"\n  >> {output['match'] or '?'}: {output['summary']['total_odds']} odds")
        return output

    finally:
        cdp.disconnect()
        time.sleep(0.5)
        close_tab(tab_id, host, port)
        time.sleep(1)


# ===================================================================
# CLI
# ===================================================================

def main():
    parser = argparse.ArgumentParser(description='bet365 Odds Scraper v6')
    parser.add_argument('--host', default=CDP_HOST)
    parser.add_argument('--port', type=int, default=CDP_PORT)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--tab', type=int, default=0)
    parser.add_argument('--output', '-o', help='Output JSON file')
    parser.add_argument('--tabs-only', action='store_true')
    parser.add_argument('--groups-only', action='store_true')
    parser.add_argument('--groups', nargs='+', help='Only these groups')
    parser.add_argument('--priority', action='store_true')
    parser.add_argument('--urls', nargs='+', help='Multiple match URLs (each opens in new tab)')
    args = parser.parse_args()

    host = args.host
    port = args.port

    all_tabs = get_chrome_tabs(host, port)
    bet365_tabs = [t for t in all_tabs if 'bet365' in t.get('url', '').lower()]

    if args.list:
        for i, t in enumerate(all_tabs):
            print(f"[{i}] {t.get('title','')}{' [bet365]' if t in bet365_tabs else ''}")
        return

    if not bet365_tabs:
        print("ERROR: No bet365 tab open"); sys.exit(1)

    only = args.groups or (PRIORITY_GROUPS if args.priority else None)

    # Quick info commands: connect to existing tab
    if args.tabs_only or args.groups_only:
        cdp = connect_to_tab(bet365_tabs[0])
        if not cdp: sys.exit(1)
        try:
            if args.tabs_only:
                for t in json.loads(cdp.evaluate(JS_LIST_TABS) or '[]'):
                    print(f"  {'*' if t.get('isActive') else ' '} {t['name']}")
            elif args.groups_only:
                ensure_markets_view(cdp, False)
                for g in json.loads(cdp.evaluate(JS_LIST_GROUPS) or '[]'):
                    print(f"  [{'OPEN' if g['isOpen'] else 'closed':6}] {g['name']}")
        finally:
            cdp.disconnect()
        return

    # --- Multi-match mode: each URL in a new tab ---
    if args.urls:
        all_matches = []
        for url in args.urls:
            output = scrape_single_url(url, only, host, port)
            if output:
                all_matches.append(output)
            else:
                all_matches.append({'url': url, 'error': 'Failed to scrape', 'markets': {}, 'summary': {'total_odds': 0}})

        final = {
            'scraped_at': datetime.now().isoformat(),
            'total_matches': len(all_matches),
            'matches': all_matches,
        }
        out_json = json.dumps(final, indent=2, ensure_ascii=False)

    # --- Single match mode: use existing tab ---
    else:
        cdp = connect_to_tab(bet365_tabs[min(args.tab, len(bet365_tabs)-1)])
        if not cdp: sys.exit(1)
        try:
            mi, res = scrape_match_on_tab(cdp, only)
            output = build_output(mi, res)
            out_json = json.dumps(output, indent=2, ensure_ascii=False)
        finally:
            cdp.disconnect()

    if args.output:
        with open(args.output, 'w') as f:
            f.write(out_json)
        print(f"\n{'='*60}")
        if args.urls:
            total = sum(m.get('summary', {}).get('total_odds', 0) for m in all_matches)
            print(f"Done! {len(all_matches)} matches, {total} total odds -> {args.output}")
        else:
            print(f"Done! {output['summary']['total_odds']} odds, {output['summary']['total_markets']} markets -> {args.output}")
    else:
        print(f"\n{'='*60}")
        print(out_json)


if __name__ == '__main__':
    main()
