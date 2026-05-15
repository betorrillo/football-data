#!/usr/bin/env python3
"""
Bet365 odds scraper v2 — full multi-tab extraction with clean data.

Scrapes ALL market categories (I1-I9 + I99) for each match by navigating
through each tab with Page.navigate + Page.reload (the only reliable way
to switch tabs without breaking the bet365 SPA).

Takes ~100 seconds per match (10 tabs × ~10s each) but gets EVERYTHING.

Output: organized JSON with clean market names, proper scope (home/away/total),
proper time period (match/1st half/2nd half/10min), and per-match files.

Usage:
  python3 scrape_odds_v2.py                    # all open bet365 match tabs
  python3 scrape_odds_v2.py --fi 193003368     # specific FI only
  python3 scrape_odds_v2.py --fast             # only scrape current I-value (no tab cycling)
  python3 scrape_odds_v2.py --summary          # don't save JSON
"""
import argparse, json, os, re, sys, time
from datetime import datetime
import websocket, requests

CDP_HOST = 'localhost'
CDP_PORT = 9222
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ODDS_DIR = os.path.join(BASE_DIR, 'odds')

# All I-value tabs to scrape (order: I99 first since it has the most data)
I_VALUES = [99, 1, 2, 3, 4, 5, 6, 7, 8, 9]

# Tab names for display
I_NAMES = {
    1: 'Populares', 2: 'Crear apuesta (alt)', 3: 'Asiáticos',
    4: 'Tarjetas', 5: 'Córners', 6: 'Goles',
    7: '1ª/2ª mitad', 8: 'Minutos', 9: 'Especiales',
    99: 'Crear apuesta (I99)'
}

# ─── JS extraction (runs in page context) ─────────────────────────────────────

EXTRACT_MATCH_JS = r"""
function() {
    const fsArray = Array.from(this);

    function getKids(s) { try { return s.getChildren() || []; } catch(e) { return []; } }
    function attrs(s) {
        if (!s) return {};
        const a = {};
        const src = s.data || s._attributes;
        if (!src) return a;
        for (const k in src) a[k] = src[k];
        return a;
    }

    const urlMatch = location.hash.match(/\/E(\d+)\//);
    const targetFI = urlMatch ? urlMatch[1] : null;
    const iMatch = location.hash.match(/\/I(\d+)\//);
    const iValue = iMatch ? iMatch[1] : '?';

    function extractMGSelections(mg, marketName, fi) {
        const mga = attrs(mg);
        const scopeOptions = (mga.LD || '').split('\xAC').filter(Boolean);
        const timeOptions = (mga.RD || '').split('\xAC').filter(Boolean);
        const selections = [];
        const allMAs = getKids(mg);

        const groupScopes = [];
        for (let mi = 0; mi < allMAs.length; mi++) {
            const maa = attrs(allMAs[mi]);
            if (maa.SY === 'bbb' || maa.SY === 'bbd') {
                let gScope = '';
                for (let mj = mi + 1; mj < allMAs.length; mj++) {
                    const nMaa = attrs(allMAs[mj]);
                    if (nMaa.SY === 'bbb' || nMaa.SY === 'bbd') break;
                    const nPas = getKids(allMAs[mj]);
                    if (nPas.length > 0) {
                        const pa0 = attrs(nPas[0]);
                        gScope = pa0.S3 || pa0.B8 || nMaa.S4 || '';
                        break;
                    }
                }
                groupScopes.push(gScope);
            }
        }

        const scopeOcc = {};
        let gIdx = -1;

        for (const ma of allMAs) {
            const maa = attrs(ma);
            if (maa.SY === 'bbb' || maa.SY === 'bbd') { gIdx++; continue; }

            const maName = maa.NA || maa.S1 || '';

            for (const pa of getKids(ma)) {
                const paa = attrs(pa);
                if (!paa.OD && !paa.DO) continue;

                let scope = paa.S3 || paa.B8 || maa.S4 || '';
                let timeVal = paa.S4 || paa.B5 || '';
                if (!timeVal && maa.S3 && maa.S3 !== scope) timeVal = maa.S3;

                if (!timeVal && timeOptions.length > 0 && gIdx >= 0) {
                    const gs = groupScopes[gIdx] || scope;
                    const key = gs + '_' + gIdx;
                    if (!scopeOcc[key]) {
                        scopeOcc[key] = true;
                        let count = 0;
                        for (let gi = 0; gi < gIdx; gi++) { if (groupScopes[gi] === gs) count++; }
                        scopeOcc[gs + '_idx_' + gIdx] = count;
                    }
                    const tIdx = scopeOcc[gs + '_idx_' + gIdx] || 0;
                    timeVal = timeOptions[tIdx] || timeOptions[0] || '';
                }

                selections.push({
                    market: marketName,
                    group: maName,
                    scope: scope,
                    time: timeVal,
                    selection: paa.S2 || paa.NA || paa.B1 || '',
                    player: paa.S1 || paa.B2 || '',
                    odds_frac: paa.OD || '',
                    odds_dec: paa.DO || '',
                    handicap: paa.HA || '',
                    fi: paa.FI || fi,
                    id: paa.ID || '',
                    suspended: paa.SU || '0'
                });
            }
        }
        return selections;
    }

    const byFI = {};
    for (const fs of fsArray) {
        if (!fs) continue;
        const a = attrs(fs);
        let fi = a.FI || '';
        if (!fi) {
            const kids = getKids(fs);
            outer: for (const k of kids) {
                for (const ma of getKids(k)) {
                    for (const pa of getKids(ma)) {
                        if (attrs(pa).FI) { fi = attrs(pa).FI; break outer; }
                    }
                }
            }
        }
        if (!fi || (targetFI && fi !== targetFI)) continue;
        if (!byFI[fi]) byFI[fi] = [];

        const stemNA = a.NA || a.L3 || '';
        const league = a.L3 || '';
        const mgs = getKids(fs);
        const isI1Style = !stemNA && mgs.length > 3;

        if (isI1Style) {
            for (const mg of mgs) {
                const mga = attrs(mg);
                const mgName = mga.NA || '';
                if (!mgName) continue;
                const sels = extractMGSelections(mg, mgName, fi);
                if (sels.length > 0) {
                    byFI[fi].push({ name: mgName, league: league, i_value: iValue, selections: sels });
                }
            }
        } else {
            const mktName = stemNA || '?';
            const allSels = [];
            for (const mg of mgs) {
                allSels.push(...extractMGSelections(mg, mktName, fi));
            }
            if (allSels.length > 0) {
                byFI[fi].push({ name: mktName, league: league, i_value: iValue, selections: allSels });
            }
        }
    }

    const result = {};
    for (const [fi, markets] of Object.entries(byFI)) {
        const totalSels = markets.reduce((s, m) => s + m.selections.length, 0);
        result[fi] = {
            fi, league: markets[0]?.league || '', i_value: iValue,
            marketCount: markets.length, selectionCount: totalSels, markets
        };
    }
    return JSON.stringify(result);
}
"""


# ─── Utilities ─────────────────────────────────────────────────────────────────

def frac_to_dec(frac_str):
    if not frac_str: return None
    try:
        if '/' in frac_str:
            n, d = frac_str.split('/')
            return round(1 + float(n) / float(d), 3)
        return float(frac_str)
    except: return None


# ─── CDP scraping ──────────────────────────────────────────────────────────────

def _cdp_scrape(ws_url):
    """Connect to a tab and extract FixtureStem data."""
    ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=30)
    try:
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable', 'params': {}}))
        time.sleep(0.3)
        ws.settimeout(0.2)
        try:
            while True: ws.recv()
        except: pass
        ws.settimeout(30)

        # Check data exists
        ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {
            'expression': '!!ns_gen5_data && !!ns_gen5_data.FixtureStem',
            'returnByValue': True
        }}))
        r = json.loads(ws.recv())
        if not r.get('result', {}).get('result', {}).get('value'):
            return None

        # Get prototype
        ws.send(json.dumps({'id': 3, 'method': 'Runtime.evaluate', 'params': {
            'expression': 'ns_gen5_data.FixtureStem.prototype', 'returnByValue': False
        }}))
        r = json.loads(ws.recv())
        pid = r['result']['result'].get('objectId')
        if not pid: return None

        ws.send(json.dumps({'id': 4, 'method': 'Runtime.queryObjects', 'params': {
            'prototypeObjectId': pid
        }}))
        r = json.loads(ws.recv())
        aid = r['result']['objects'].get('objectId')
        if not aid: return None

        ws.send(json.dumps({'id': 5, 'method': 'Runtime.callFunctionOn', 'params': {
            'objectId': aid,
            'functionDeclaration': EXTRACT_MATCH_JS,
            'returnByValue': True,
            'awaitPromise': False
        }}))
        r = json.loads(ws.recv())
        val = r.get('result', {}).get('result', {}).get('value', '')
        if not val: return None
        return json.loads(val) if isinstance(val, str) else val
    finally:
        ws.close()


def scrape_single_tab(tab_info):
    """Scrape current I-value of a tab (no navigation)."""
    t0 = time.time()
    data = _cdp_scrape(tab_info['webSocketDebuggerUrl'])
    elapsed = round(time.time() - t0, 1)
    if data:
        data['_elapsed'] = elapsed
    return data


def scrape_all_i_values(tab_info, fi):
    """Navigate through I1-I9 + I99, reload each, scrape. Returns combined data."""
    ws_url = tab_info['webSocketDebuggerUrl']
    base_url = re.sub(r'/I\d+/', '/I{i}/', tab_info['url'])

    all_data = {}  # i_value -> extraction result

    for i_val in I_VALUES:
        url = base_url.replace('{i}', str(i_val))
        t0 = time.time()

        try:
            ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=30)
            # Navigate
            ws.send(json.dumps({'id': 1, 'method': 'Page.navigate', 'params': {'url': url}}))
            ws.recv()
            # Reload for clean state
            time.sleep(1)
            ws.send(json.dumps({'id': 2, 'method': 'Page.reload', 'params': {'ignoreCache': False}}))
            ws.recv()
            ws.close()
        except Exception as e:
            print(f"    I{i_val}: navigate error: {e}")
            continue

        # Wait for SPA to load
        time.sleep(7)

        # Scrape
        try:
            data = _cdp_scrape(ws_url)
        except Exception as e:
            print(f"    I{i_val}: scrape error: {e}")
            continue

        elapsed = round(time.time() - t0, 1)

        if data and fi in data:
            match = data[fi]
            mc = match.get('marketCount', 0)
            sc = match.get('selectionCount', 0)
            if sc > 0:
                all_data[i_val] = match
                i_name = I_NAMES.get(i_val, f'I{i_val}')
                print(f"    I{i_val:>2} ({i_name:20s}): {mc:>3} mkts, {sc:>5} sels ({elapsed:.1f}s)")
            else:
                print(f"    I{i_val:>2}: empty ({elapsed:.1f}s)")
        else:
            print(f"    I{i_val:>2}: no data ({elapsed:.1f}s)")

    return all_data


# ─── Data cleanup ──────────────────────────────────────────────────────────────

PLAYER_MKT_KW = {'jugador', 'anotará', 'remates', 'goleador', 'asistirá',
                 'joueur', 'buteur', 'tirs', 'player', 'scorer', 'shots'}
GENERIC_SCOPES = {'ambos equipos', 'les deux équipes', 'both teams', ''}
SKIP_WORDS = {'empate', 'draw', 'nul', 'match nul', 'sí', 'no', 'yes', ''}
TIME_KW = {'encuentro', 'partido', 'mitad', 'minutos', 'match', 'half', 'minutes', 'mi-temps'}

# Canonical time names (normalize variants)
TIME_CANONICAL = {
    'encuentro': 'Encuentro', 'partido': 'Encuentro', 'match': 'Encuentro',
    '1ª mitad': '1ª mitad', '1ère mi-temps': '1ª mitad', '1st half': '1ª mitad',
    '2ª mitad': '2ª mitad', '2ème mi-temps': '2ª mitad', '2nd half': '2ª mitad',
    'primeros 10 minutos': 'Primeros 10 min', 'first 10 minutes': 'Primeros 10 min',
    '10 minutos': 'Primeros 10 min',
}

# Canonical scope names
SCOPE_CANONICAL = {
    'ambos equipos': 'Total', 'les deux équipes': 'Total', 'both teams': 'Total',
}


def _is_time(v):
    if not v: return False
    return any(kw in v.strip().lower() for kw in TIME_KW)


def _is_player_mkt(n):
    if not n: return False
    return any(kw in n.lower() for kw in PLAYER_MKT_KW)


def _is_team(v, teams):
    if not v or not teams: return False
    vl = v.strip().lower()
    return any(t.lower() in vl or vl in t.lower() for t in teams if t)


def _canon_time(t):
    if not t: return ''
    return TIME_CANONICAL.get(t.strip().lower(), t.strip())


def _canon_scope(s, home, away):
    if not s: return ''
    sl = s.strip().lower()
    if sl in SCOPE_CANONICAL:
        return SCOPE_CANONICAL[sl]
    # Map team names to "Local"/"Visitante"
    if home and (sl == home.lower() or home.lower() in sl):
        return f"Local ({home})"
    if away and (sl == away.lower() or away.lower() in sl):
        return f"Visitante ({away})"
    return s.strip()


def detect_teams(all_markets):
    """Detect home/away from all market data across all I-values."""
    candidates = {}
    for mkt_list in all_markets:
        for market in mkt_list:
            mname = market['name'].lower()

            if 'resultado' in mname and 'goles' not in mname and 'ambos' not in mname:
                for sel in market.get('selections', []):
                    for field in ('group', 'selection'):
                        v = sel.get(field, '').strip()
                        if v and v.lower() not in SKIP_WORDS:
                            candidates[v] = candidates.get(v, 0) + 5

            if 'sin empate' in mname:
                for sel in market.get('selections', []):
                    v = sel.get('selection', '').strip()
                    if v and v.lower() not in SKIP_WORDS:
                        candidates[v] = candidates.get(v, 0) + 4

            if 'doble' in mname and 'goles' not in mname:
                for sel in market.get('selections', []):
                    for part in re.split(r'\s+o\s+|\s+or\s+|\s+ou\s+', sel.get('selection', '')):
                        p = part.strip()
                        if p.lower() not in SKIP_WORDS:
                            candidates[p] = candidates.get(p, 0) + 3

            if 'marcador' in mname:
                for sel in market.get('selections', []):
                    m = re.match(r'^(.+?)\s+\d+-\d+$', sel.get('selection', ''))
                    if m:
                        t = m.group(1).strip()
                        if t.lower() not in SKIP_WORDS:
                            candidates[t] = candidates.get(t, 0) + 2

            for sel in market.get('selections', []):
                scope = sel.get('scope', '').strip()
                if scope and scope.lower() not in GENERIC_SCOPES and scope.lower() not in SKIP_WORDS:
                    candidates[scope] = candidates.get(scope, 0) + 1

    sorted_t = sorted(candidates.items(), key=lambda x: -x[1])
    teams = [t[0] for t in sorted_t[:2]]
    return (teams[0] if len(teams) >= 1 else '', teams[1] if len(teams) >= 2 else '')


def clean_selection(sel, market_name, home, away):
    """Fix field misassignments and normalize values."""
    c = dict(sel)
    teams = [home, away]

    # Fix player field when it's not a player market
    player = c.get('player', '')
    if player and not _is_player_mkt(market_name):
        if _is_time(player):
            if not c.get('time'): c['time'] = player
            c['player'] = ''
        elif _is_team(player, teams):
            c['team'] = player
            c['player'] = ''
        elif re.match(r'^\d+-\d+\s*gol', player, re.I) or 'goles' in player.lower():
            c['range'] = player
            c['player'] = ''
        elif any(kw in player.lower() for kw in ('tarjeta', 'card')):
            c['threshold'] = player
            c['player'] = ''
        elif player.lower() in SKIP_WORDS:
            c['player'] = ''

    # Fix Equipo-Goleador: time has team name
    if 'goleador' in market_name.lower() or 'scorer' in market_name.lower():
        t = c.get('time', '')
        if t and _is_team(t, teams):
            c['team'] = t
            c['time'] = ''

    # Merge split group+selection: "Más de" + "5 córners" → "Más de 5 córners"
    g, s = c.get('group', ''), c.get('selection', '')
    if g and s:
        gl = g.lower().strip()
        if gl in ('más de', 'menos de', 'exactamente', 'al menos', 'over', 'under', 'exactly',
                   'plus de', 'moins de'):
            c['selection'] = f"{g} {s}"
            c['group'] = ''
        elif re.match(r'^\d+\+?$', gl):
            c['selection'] = f"{g} {s}"
            c['group'] = ''

    # Normalize time and scope
    c['time'] = _canon_time(c.get('time', ''))
    c['scope'] = _canon_scope(c.get('scope', ''), home, away)

    # Clean empty fields
    for key in ('player', 'handicap', 'group', 'range', 'threshold', 'team'):
        if key in c and not c[key]:
            del c[key]

    return c


# ─── Match assembly ───────────────────────────────────────────────────────────

def build_match(fi, all_i_data, home, away, league):
    """Assemble clean match data from all I-values."""
    match = {
        'fi': fi,
        'league': league,
        'home': home,
        'away': away,
        'scraped_at': datetime.now().isoformat(),
        'sources': sorted([f'I{iv}' for iv in all_i_data.keys()]),
        'markets': {},
    }

    seen_market_keys = {}  # deduplicate across I-values

    for i_val, i_data in sorted(all_i_data.items()):
        for market in i_data.get('markets', []):
            mname = market['name']
            if mname == '?' or not mname:
                mname = f'Desconocido (I{i_val})'

            if mname not in match['markets']:
                match['markets'][mname] = {
                    'name': mname,
                    'source': f'I{i_val}',
                    'selections': [],
                    'scopes': set(),
                    'times': set(),
                }

            for sel in market.get('selections', []):
                odds_dec = frac_to_dec(sel.get('odds_frac')) or sel.get('odds_dec')
                entry = {
                    'selection': sel.get('selection', ''),
                    'odds': odds_dec,
                    'odds_frac': sel.get('odds_frac', ''),
                    'group': sel.get('group', ''),
                    'scope': sel.get('scope', ''),
                    'time': sel.get('time', ''),
                    'player': sel.get('player', ''),
                    'handicap': sel.get('handicap', ''),
                    'suspended': sel.get('suspended') == '1',
                }
                entry = clean_selection(entry, mname, home, away)

                # Deduplicate by content
                dedup_key = f"{mname}|{entry.get('selection','')}|{entry.get('odds','')}|{entry.get('scope','')}|{entry.get('time','')}|{entry.get('player','')}"
                if dedup_key in seen_market_keys:
                    continue
                seen_market_keys[dedup_key] = True

                if entry.get('scope'):
                    match['markets'][mname]['scopes'].add(entry['scope'])
                if entry.get('time'):
                    match['markets'][mname]['times'].add(entry['time'])

                match['markets'][mname]['selections'].append(entry)

    # Finalize
    for mdata in match['markets'].values():
        mdata['scopes'] = sorted(mdata['scopes'])
        mdata['times'] = sorted(mdata['times'])
        mdata['count'] = len(mdata['selections'])

    match['market_count'] = len(match['markets'])
    match['selection_count'] = sum(m['count'] for m in match['markets'].values())

    return match


# ─── Display ───────────────────────────────────────────────────────────────────

def print_match(fi, m):
    src = ', '.join(m.get('sources', []))
    print(f"\n{'='*70}")
    print(f"  {m['home']} vs {m['away']}")
    print(f"  FI={fi} | {m['league']} | {m['market_count']} markets | {m['selection_count']} selections")
    print(f"  Sources: {src}")
    print(f"{'='*70}")

    for mname, md in sorted(m['markets'].items()):
        s_str = ', '.join(md['scopes']) if md['scopes'] else ''
        t_str = ', '.join(md['times']) if md['times'] else ''
        print(f"\n  [{md['count']:>3}] {mname} ({md['source']})")
        if s_str: print(f"        scope: {s_str}")
        if t_str: print(f"        time:  {t_str}")
        for s in md['selections'][:3]:
            parts = []
            if s.get('selection'): parts.append(s['selection'])
            if s.get('scope'): parts.append(f"({s['scope']})")
            if s.get('time'): parts.append(f"[{s['time']}]")
            if s.get('player'): parts.append(f"@ {s['player']}")
            if s.get('team'): parts.append(f"<{s['team']}>")
            if s.get('range'): parts.append(f"#{s['range']}")
            if s.get('threshold'): parts.append(f"~{s['threshold']}")
            odds_s = f"{s['odds']}" if s.get('odds') else '?'
            susp = " [SUSP]" if s.get('suspended') else ""
            print(f"        {odds_s:>8}  {' '.join(parts)}{susp}")
        if md['count'] > 3:
            print(f"        ... +{md['count'] - 3} more")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fi', help='Specific FI to extract')
    ap.add_argument('--fast', action='store_true', help='Only scrape current tab (no I-value cycling)')
    ap.add_argument('--summary', action='store_true', help='Print summary, no JSON save')
    args = ap.parse_args()

    try:
        tabs = requests.get(f'http://{CDP_HOST}:{CDP_PORT}/json', timeout=5).json()
    except Exception as e:
        print(f"ERROR: Cannot connect to Chrome CDP at port {CDP_PORT}: {e}")
        sys.exit(1)

    match_tabs = [t for t in tabs if '/AC/B1/C1/D8/' in t.get('url', '')]
    if args.fi:
        match_tabs = [t for t in match_tabs if f'/E{args.fi}/' in t.get('url', '')]

    if not match_tabs:
        print("No bet365 match tabs found.")
        sys.exit(1)

    # Group by FI (only take first tab per FI)
    seen_fis = {}
    for tab in match_tabs:
        fi_m = re.search(r'/E(\d+)/', tab.get('url', ''))
        if fi_m:
            fi = fi_m.group(1)
            if fi not in seen_fis:
                seen_fis[fi] = tab

    fis = list(seen_fis.keys())
    mode = "fast (current tab only)" if args.fast else f"full (I1-I9 + I99)"
    print(f"Found {len(fis)} match(es) — mode: {mode}")
    for fi in fis:
        url = seen_fis[fi]['url']
        i_m = re.search(r'/I(\d+)/', url)
        print(f"  FI={fi} (currently on I{i_m.group(1) if i_m else '?'})")
    print("=" * 70)

    all_matches = {}

    for fi in fis:
        tab = seen_fis[fi]
        print(f"\n--- FI={fi} ---")

        if args.fast:
            # Only scrape current tab
            data = scrape_single_tab(tab)
            if not data or fi not in data:
                print(f"  No data")
                continue
            all_i_data = {int(data[fi].get('i_value', 0)): data[fi]}
        else:
            # Full multi-I scrape
            all_i_data = scrape_all_i_values(tab, fi)
            if not all_i_data:
                print(f"  No data from any I-value")
                continue

        # Detect teams from all data
        all_market_lists = [d.get('markets', []) for d in all_i_data.values()]
        home, away = detect_teams(all_market_lists)
        league = next((d.get('league', '') for d in all_i_data.values() if d.get('league')), '')

        # Build clean match
        match = build_match(fi, all_i_data, home, away, league)
        all_matches[fi] = match

        print(f"\n  => {match['home']} vs {match['away']}: {match['market_count']} markets, {match['selection_count']} selections")

    # Print all matches
    for fi, m in all_matches.items():
        print_match(fi, m)

    # Save
    if not args.summary and all_matches:
        os.makedirs(ODDS_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")

        # Serialize (convert sets to lists)
        def serialize(m):
            sm = dict(m)
            sm['markets'] = {}
            for mname, md in m['markets'].items():
                sd = dict(md)
                if isinstance(sd.get('scopes'), set): sd['scopes'] = sorted(sd['scopes'])
                if isinstance(sd.get('times'), set): sd['times'] = sorted(sd['times'])
                sm['markets'][mname] = sd
            return sm

        serialized = {fi: serialize(m) for fi, m in all_matches.items()}

        # Combined
        output = {
            'scraped_at': datetime.now().isoformat(),
            'match_count': len(serialized),
            'total_markets': sum(m['market_count'] for m in serialized.values()),
            'total_selections': sum(m['selection_count'] for m in serialized.values()),
            'matches': serialized,
        }
        path = os.path.join(ODDS_DIR, f'odds_v2_{today}.json')
        with open(path, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\nSaved: {path}")

        # Per-match
        for fi, m in serialized.items():
            mp = os.path.join(ODDS_DIR, f'match_{fi}.json')
            with open(mp, 'w') as f:
                json.dump(m, f, indent=2, ensure_ascii=False)
            print(f"Saved: {mp}")


if __name__ == '__main__':
    main()
