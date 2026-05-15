#!/usr/bin/env python3
"""
bet365 Fast Scraper — Expert-level optimized approach.

Strategy:
  Phase 1: Open ALL groups at once → single tree-walk extracts everything (5s)
  Phase 2: For groups WITH dropdowns, iterate combos one-by-one (2-3 min)

Total: ~3-4 min per match vs ~15 min with old approach.

Usage:
  python3 scrape_fast.py                    # scrape all open bet365 tabs
  python3 scrape_fast.py --tab 0            # scrape specific tab index
  python3 scrape_fast.py -o odds/out.json   # custom output path
"""

import argparse, json, sys, time, os, re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_client import CDPClient
import requests

CDP_HOST = 'localhost'
CDP_PORT = 9222

# ── JavaScript snippets ──────────────────────────────────────────────

JS_MATCH_INFO = r"""
(() => {
    let home = '', away = '', comp = '', dt = '';
    const pmTeams = document.querySelectorAll('.sph-FixturePodHeader_TeamName');
    if (pmTeams.length >= 2) {
        home = pmTeams[0].textContent.trim();
        away = pmTeams[1].textContent.trim();
    }
    const pmComp = document.querySelector('.sph-FixturePodHeader_Competition');
    if (pmComp) comp = pmComp.textContent.trim();
    const pmDt = document.querySelector('.sph-ExtraData_TimeStamp');
    if (pmDt) dt = pmDt.textContent.trim();
    const isLive = window.location.hash.includes('/IP/');
    return JSON.stringify({ home, away, match: home + ' vs ' + away, competition: comp, datetime: dt, url: window.location.href, isLive });
})()
"""

JS_ENSURE_BET_BUILDER = """
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
"""

JS_OPEN_ALL_GROUPS = """
(() => {
    let clicked = 0;
    document.querySelectorAll('.gl-MarketGroupPod, [class*="MarketGroupPod"]').forEach(pod => {
        const btn = pod.querySelector('.gl-MarketGroupButton, [class*="MarketGroupButton"]');
        if (btn && !btn.className.includes('Open')) { btn.click(); clicked++; }
    });
    return clicked;
})()
"""

JS_CLOSE_ALL_GROUPS = """
(() => {
    let closed = 0;
    document.querySelectorAll('.gl-MarketGroupPod, [class*="MarketGroupPod"]').forEach(pod => {
        const btn = pod.querySelector('.gl-MarketGroupButton, [class*="MarketGroupButton"]');
        if (btn && btn.className.includes('Open')) { btn.click(); closed++; }
    });
    return closed;
})()
"""

JS_SHOW_MORE = """
(() => {
    let c = 0;
    document.querySelectorAll('[class*="ShowMore"]').forEach(el => {
        if (/ver más|show more/i.test(el.textContent.trim())) { try { el.click(); c++; } catch(e) {} }
    });
    return c;
})()
"""

# Phase 1: Extract ALL odds from ALL open groups in ONE pass
JS_EXTRACT_ALL_GROUPS = """
(() => {
    const oddsRx = /^\\d{1,3}\\.\\d{2}$/;
    const results = [];

    document.querySelectorAll('.gl-MarketGroupPod, [class*="MarketGroupPod"]').forEach(pod => {
        const btn = pod.querySelector('.gl-MarketGroupButton, [class*="MarketGroupButton"]');
        if (!btn || !btn.className.includes('Open')) return;
        const nameEl = btn.querySelector('.gl-MarketGroupButton_Text, [class*="MarketGroupButton_Text"], [class*="HeaderText"]');
        const groupName = nameEl ? nameEl.textContent.trim() : btn.textContent.trim();

        // Check for dropdowns
        let hasDropdowns = false;
        const leftDD = pod.parentElement ?
            document.querySelector('[class*="bbl-DropDown-left"]') : null;
        // We'll detect dropdowns per-group later

        const odds = [];
        const seen = new Set();
        const walker = document.createTreeWalker(pod, NodeFilter.SHOW_TEXT, null);
        let node;
        while (node = walker.nextNode()) {
            const t = node.textContent.trim();
            if (!oddsRx.test(t)) continue;
            let ctx = '', p = node.parentElement;
            for (let i = 0; i < 6 && p && p !== pod; i++) {
                const pt = p.textContent.trim();
                if (pt.length > t.length + 1 && pt.length < 200) { ctx = pt; break; }
                p = p.parentElement;
            }
            const key = ctx + '|' + t;
            if (seen.has(key)) continue;
            seen.add(key);

            let sel = '', col = '';
            const parentEl = node.parentElement;
            if (parentEl) {
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
                if (!sel) {
                    const glRow = parentEl.closest('[class*="gl-Participant"]');
                    if (glRow) {
                        const nameEl2 = glRow.querySelector('[class*="Name"]');
                        if (nameEl2) sel = nameEl2.textContent.trim();
                    }
                }
                if (!sel) sel = ctx.replace(t, '').trim().substring(0, 80);
            }
            odds.push({ sel, col, odds: parseFloat(t) });
        }

        if (odds.length > 0) results.push({ name: groupName.substring(0, 80), odds });
    });
    return JSON.stringify(results);
})()
"""

# Detect which groups have dropdowns (must open them one by one)
JS_DETECT_DROPDOWN_GROUPS = """
(() => {
    // Close all first
    document.querySelectorAll('.gl-MarketGroupPod, [class*="MarketGroupPod"]').forEach(pod => {
        const btn = pod.querySelector('.gl-MarketGroupButton, [class*="MarketGroupButton"]');
        if (btn && btn.className.includes('Open')) btn.click();
    });
    return 'closed';
})()
"""

def js_open_single_group(name):
    e = name.replace('"', '\\"').replace("'", "\\'")
    return f"""(() => {{
        for (const p of document.querySelectorAll('.gl-MarketGroupPod, [class*="MarketGroupPod"]')) {{
            const b = p.querySelector('.gl-MarketGroupButton, [class*="MarketGroupButton"]');
            if (!b) continue;
            const t = b.querySelector('.gl-MarketGroupButton_Text, [class*="MarketGroupButton_Text"], [class*="HeaderText"]');
            const n = t ? t.textContent.trim() : b.textContent.trim();
            if (n === "{e}" || n.startsWith("{e}")) {{
                if (!b.className.includes('Open')) b.click();
                return 'opened';
            }}
        }}
        return 'miss';
    }})()"""

def js_close_single_group(name):
    e = name.replace('"', '\\"').replace("'", "\\'")
    return f"""(() => {{
        for (const p of document.querySelectorAll('.gl-MarketGroupPod, [class*="MarketGroupPod"]')) {{
            const b = p.querySelector('.gl-MarketGroupButton, [class*="MarketGroupButton"]');
            if (!b) continue;
            const t = b.querySelector('.gl-MarketGroupButton_Text, [class*="MarketGroupButton_Text"], [class*="HeaderText"]');
            const n = t ? t.textContent.trim() : b.textContent.trim();
            if (n === "{e}" || n.startsWith("{e}")) {{
                if (b.className.includes('Open')) b.click();
                return 'closed';
            }}
        }}
        return 'miss';
    }})()"""

JS_GET_DROPDOWNS = """
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
    return f"""(() => {{
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
    }})()"""

def js_click_at(x, y):
    return f'(() => {{ const el=document.elementFromPoint({x},{y}); if(el){{el.click();return el.textContent.trim().substring(0,40);}} return "miss"; }})()'

JS_EXTRACT_SINGLE_GROUP = """
(() => {
    const oddsRx = /^\\d{1,3}\\.\\d{2}$/;
    let result = null;

    document.querySelectorAll('.gl-MarketGroupPod, [class*="MarketGroupPod"]').forEach(pod => {
        const btn = pod.querySelector('.gl-MarketGroupButton, [class*="MarketGroupButton"]');
        if (!btn || !btn.className.includes('Open')) return;
        if (result) return; // only first open group

        const odds = [];
        const seen = new Set();
        const walker = document.createTreeWalker(pod, NodeFilter.SHOW_TEXT, null);
        let node;
        while (node = walker.nextNode()) {
            const t = node.textContent.trim();
            if (!oddsRx.test(t)) continue;
            let ctx = '', p = node.parentElement;
            for (let i = 0; i < 6 && p && p !== pod; i++) {
                const pt = p.textContent.trim();
                if (pt.length > t.length + 1 && pt.length < 200) { ctx = pt; break; }
                p = p.parentElement;
            }
            const key = ctx + '|' + t;
            if (seen.has(key)) continue;
            seen.add(key);

            let sel = '', col = '';
            const parentEl = node.parentElement;
            if (parentEl) {
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
                if (!sel) {
                    const glRow = parentEl.closest('[class*="gl-Participant"]');
                    if (glRow) {
                        const nameEl2 = glRow.querySelector('[class*="Name"]');
                        if (nameEl2) sel = nameEl2.textContent.trim();
                    }
                }
                if (!sel) sel = ctx.replace(t, '').trim().substring(0, 80);
            }
            odds.push({ sel, col, odds: parseFloat(t) });
        }
        result = odds;
    });
    return JSON.stringify(result || []);
})()
"""


# ── Core functions ────────────────────────────────────────────────────

def get_bet365_tabs():
    tabs = requests.get(f'http://{CDP_HOST}:{CDP_PORT}/json', timeout=5).json()
    return [t for t in tabs if 'bet365' in t.get('url', '').lower() and '/AC/B1/' in t.get('url', '')]


def open_dropdown_read(cdp, trigger, side):
    """Click dropdown trigger, read options, close dropdown."""
    cdp.evaluate(js_click_at(trigger['x'], trigger['y']))
    time.sleep(0.6)
    raw = cdp.evaluate(js_read_dropdown(side))
    opts = json.loads(raw) if raw else []
    cdp.evaluate('document.body.click()')
    time.sleep(0.3)
    return opts


def select_filter(cdp, trigger, option_text, side):
    """Open dropdown, click specific option."""
    cdp.evaluate(js_click_at(trigger['x'], trigger['y']))
    time.sleep(0.5)
    raw = cdp.evaluate(js_read_dropdown(side))
    for opt in json.loads(raw) if raw else []:
        if opt['text'] == option_text:
            cdp.evaluate(js_click_at(opt['x'], opt['y']))
            time.sleep(0.8)
            return True
    cdp.evaluate('document.body.click()')
    time.sleep(0.2)
    return False


def scrape_match(cdp):
    """
    Full match scrape — two-phase approach.
    Phase 1: Bulk extract (open all → tree walk → close all) ~6s
    Phase 2: Dropdown iteration for markets that have them ~2-3 min
    """
    # ── Match info ──
    raw = cdp.evaluate(JS_MATCH_INFO)
    match_info = json.loads(raw) if raw else {}
    is_live = match_info.get('isLive', False)
    print(f"  Match: {match_info.get('match', '?')} | {match_info.get('competition', '')}")

    # ── Ensure Bet Builder view ──
    clicked = cdp.evaluate(JS_ENSURE_BET_BUILDER)
    if clicked and clicked not in ('miss', 'already'):
        print(f"    Clicked '{clicked}', waiting for load...")
        for i in range(15):
            time.sleep(1)
            n = int(cdp.evaluate("""document.querySelectorAll('.gl-MarketGroupPod, [class*="MarketGroupPod"]').length""") or 0)
            if n > 5:
                print(f"    Loaded {n} groups after {i+1}s")
                break

    # ── Phase 1: BULK EXTRACT ──
    print("\n  ── Phase 1: Bulk extract (all groups at once) ──")
    t0 = time.time()

    opened = cdp.evaluate(JS_OPEN_ALL_GROUPS)
    print(f"    Opened {opened} groups")
    time.sleep(4)

    # Wait for content to load
    for i in range(10):
        body_len = int(cdp.evaluate("document.body.innerHTML.length") or 0)
        if body_len > 200000:
            break
        time.sleep(1)

    cdp.evaluate(JS_SHOW_MORE)
    time.sleep(1)

    raw = cdp.evaluate(JS_EXTRACT_ALL_GROUPS)
    phase1_groups = json.loads(raw) if raw else []
    phase1_odds = sum(len(g['odds']) for g in phase1_groups)
    print(f"    Extracted {phase1_odds} odds from {len(phase1_groups)} groups in {time.time()-t0:.1f}s")

    # Close all
    cdp.evaluate(JS_CLOSE_ALL_GROUPS)
    time.sleep(0.5)

    # Build results dict — phase 1 goes under 'default' filter
    all_results = {}
    group_names = []
    for g in phase1_groups:
        name = re.sub(r'Sustituto\+$', '', g['name']).strip()
        all_results[name] = [{'filter': 'default', 'odds': g['odds']}]
        group_names.append(name)

    # ── Phase 2: DROPDOWN ITERATION ──
    if not is_live:
        print(f"\n  ── Phase 2: Dropdown iteration ──")
        t1 = time.time()
        dd_count = 0

        for gname in group_names:
            # Open this group
            cdp.evaluate(js_open_single_group(gname))
            time.sleep(1.2)
            cdp.evaluate(JS_SHOW_MORE)
            time.sleep(0.3)

            # Check for dropdowns
            raw = cdp.evaluate(JS_GET_DROPDOWNS)
            triggers = json.loads(raw) if raw else {}

            if not triggers.get('team') and not triggers.get('period'):
                # No dropdowns — skip (already captured in phase 1)
                cdp.evaluate(js_close_single_group(gname))
                time.sleep(0.2)
                continue

            dd_count += 1
            team_opts = []
            period_opts = []

            if triggers.get('team'):
                team_opts = open_dropdown_read(cdp, triggers['team'], 'left')
            if triggers.get('period'):
                period_opts = open_dropdown_read(cdp, triggers['period'], 'right')

            teams = team_opts if team_opts else [None]
            periods = period_opts if period_opts else [None]
            combos = len(teams) * len(periods)
            print(f"    {gname}: {len(team_opts)}t × {len(period_opts)}p = {combos} combos")

            # Replace default with all combos
            all_results[gname] = []

            for ti, t_opt in enumerate(teams):
                for pi, p_opt in enumerate(periods):
                    parts = []
                    if t_opt: parts.append(t_opt['text'])
                    if p_opt: parts.append(p_opt['text'])
                    label = ' / '.join(parts) if parts else 'default'

                    if t_opt:
                        tr = json.loads(cdp.evaluate(JS_GET_DROPDOWNS) or '{}')
                        if tr.get('team'):
                            select_filter(cdp, tr['team'], t_opt['text'], 'left')

                    if p_opt:
                        tr = json.loads(cdp.evaluate(JS_GET_DROPDOWNS) or '{}')
                        if tr.get('period'):
                            select_filter(cdp, tr['period'], p_opt['text'], 'right')

                    cdp.evaluate(JS_SHOW_MORE)
                    time.sleep(0.3)

                    raw = cdp.evaluate(JS_EXTRACT_SINGLE_GROUP)
                    odds = json.loads(raw) if raw else []
                    all_results[gname].append({'filter': label, 'odds': odds})

            # Close group
            cdp.evaluate(js_close_single_group(gname))
            time.sleep(0.2)

        print(f"    {dd_count} groups with dropdowns processed in {time.time()-t1:.1f}s")

    return match_info, all_results


def build_output(match_info, all_results):
    """Build final JSON output."""
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
            if not odds:
                continue
            structured = []
            for o in odds:
                e = {'odds': o.get('odds', 0) if isinstance(o, dict) else o}
                if isinstance(o, dict):
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


def make_filename(output):
    """Generate filename from match info."""
    home = output.get('home', 'unknown').lower().replace(' ', '-')
    away = output.get('away', 'unknown').lower().replace(' ', '-')
    comp = output.get('competition', '').lower()

    if 'champions' in comp:
        comp_slug = 'uefa-champions-league'
    elif 'europa league' in comp:
        comp_slug = 'uefa-europa-league'
    elif 'conference' in comp:
        comp_slug = 'uefa-conference-league'
    elif 'liga' in comp or 'laliga' in comp:
        comp_slug = 'spain-la-liga'
    elif 'premier' in comp:
        comp_slug = 'england-premier-league'
    elif 'bundesliga' in comp:
        comp_slug = 'germany-bundesliga'
    elif 'serie a' in comp:
        comp_slug = 'italy-serie-a'
    elif 'ligue 1' in comp:
        comp_slug = 'france-ligue-1'
    else:
        comp_slug = re.sub(r'[^a-z0-9]+', '-', comp).strip('-') or 'unknown'

    dt = output.get('datetime', '')
    date_match = re.search(r'(\d{1,2})\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)', dt, re.I)
    if date_match:
        day = int(date_match.group(1))
        months = {'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sep':9,'oct':10,'nov':11,'dic':12}
        month = months.get(date_match.group(2).lower(), 1)
        date_slug = f"2026-{month:02d}-{day:02d}"
    else:
        date_slug = datetime.now().strftime('%Y-%m-%d')

    return f"odds/{comp_slug}_{home}-vs-{away}_{date_slug}.json"


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='bet365 Fast Scraper')
    parser.add_argument('--tab', type=int, default=None, help='Specific tab index')
    parser.add_argument('-o', '--output', help='Output file (only for single tab)')
    args = parser.parse_args()

    bet_tabs = get_bet365_tabs()
    if not bet_tabs:
        print("ERROR: No bet365 tabs found. Open matches in Chrome first.")
        sys.exit(1)

    print(f"Found {len(bet_tabs)} bet365 match tabs")

    if args.tab is not None:
        tabs_to_scrape = [bet_tabs[args.tab]]
    else:
        tabs_to_scrape = bet_tabs

    os.makedirs('odds', exist_ok=True)

    for i, tab in enumerate(tabs_to_scrape):
        print(f"\n{'='*60}")
        print(f"Tab {i}")
        print(f"{'='*60}")

        cdp = CDPClient(tab['webSocketDebuggerUrl'])
        if not cdp.connect():
            print("  FAILED to connect")
            continue

        try:
            match_info, results = scrape_match(cdp)
            output = build_output(match_info, results)

            fname = args.output if args.output and len(tabs_to_scrape) == 1 else make_filename(output)
            with open(fname, 'w') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            print(f"\n  ✓ {output['match']}: {output['summary']['total_odds']} cuotas, {output['summary']['total_markets']} mercados")
            print(f"  → {fname}")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()
        finally:
            cdp.disconnect()
            time.sleep(1)

    print(f"\n{'='*60}")
    print("COMPLETADO")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
