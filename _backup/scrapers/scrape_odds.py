#!/usr/bin/env python3
"""
Bet365 odds scraper — optimized for I99 (Build-a-Bet) pages.

Unlike scrape_cdp_fast.py (which picks the biggest FixtureStem),
this script groups ALL FixtureStems by FI (match ID) and extracts
odds from every market for each match.

Usage:
  python3 scrape_odds.py                    # all open bet365 match tabs
  python3 scrape_odds.py --fi 193003368     # specific FI
  python3 scrape_odds.py --summary          # show summary only (no JSON save)
"""
import argparse, json, os, re, sys, time
import websocket, requests

CDP_HOST = 'localhost'
CDP_PORT = 9222
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ODDS_DIR = os.path.join(BASE_DIR, 'odds')

# JS that runs inside the page context
EXTRACT_ALL_JS = r"""
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

    // Group all stems by FI
    const byFI = {};
    for (const fs of fsArray) {
        if (!fs) continue;
        const a = attrs(fs);
        // Try to find FI in the stem or its children
        let fi = a.FI || '';
        if (!fi) {
            const kids = getKids(fs);
            outer: for (const k of kids) {
                for (const ma of getKids(k)) {
                    for (const pa of getKids(ma)) {
                        const paa = attrs(pa);
                        if (paa.FI) { fi = paa.FI; break outer; }
                    }
                }
            }
        }
        if (!fi) continue;

        if (!byFI[fi]) byFI[fi] = [];

        const marketName = a.NA || a.L3 || '?';
        const league = a.L3 || '';
        const mgs = getKids(fs);

        const marketData = {
            name: marketName,
            league: league,
            selections: []
        };

        // Walk MG -> MA -> PA
        for (const mg of mgs) {
            const mga = attrs(mg);
            // MG.LD = dropdown scope options separated by ¬
            // MG.RD = dropdown time options separated by ¬
            const scopeOptions = (mga.LD || '').split('¬').filter(Boolean);
            const timeOptions = (mga.RD || '').split('¬').filter(Boolean);

            // MAs with SY=bbb/bbd are headers (no odds).
            // MAs with SY=bbc/bbe have odds.
            // Groups: (header + N odds MAs) repeat per scope/time combo.
            //
            // Time inference: PA.S3 always has scope. Time is NOT stored
            // in any field. We infer it by counting how many times each
            // scope has appeared — 1st occurrence = timeOptions[0],
            // 2nd = timeOptions[1], etc.
            const allMAs = getKids(mg);

            // First pass: identify which scope each header group belongs to
            // by peeking at the first odds PA in the group after it.
            const groupScopes = []; // scope for each header group
            let inHeader = false;
            for (let mi = 0; mi < allMAs.length; mi++) {
                const maa = attrs(allMAs[mi]);
                if (maa.SY === 'bbb' || maa.SY === 'bbd') {
                    // Find scope from next odds MA's first PA
                    let gScope = '';
                    for (let mj = mi + 1; mj < allMAs.length; mj++) {
                        const nextMaa = attrs(allMAs[mj]);
                        if (nextMaa.SY === 'bbb' || nextMaa.SY === 'bbd') break;
                        const nextPas = getKids(allMAs[mj]);
                        if (nextPas.length > 0) {
                            const pa0 = attrs(nextPas[0]);
                            gScope = pa0.S3 || pa0.B8 || nextMaa.S4 || '';
                            break;
                        }
                    }
                    groupScopes.push(gScope);
                }
            }

            // Count occurrences of each scope to map to time
            const scopeOccurrence = {}; // scope -> count seen so far
            let currentGroupIdx = -1;

            for (const ma of allMAs) {
                const maa = attrs(ma);

                if (maa.SY === 'bbb' || maa.SY === 'bbd') {
                    currentGroupIdx++;
                    continue;
                }

                const maName = maa.NA || maa.S1 || '';

                for (const pa of getKids(ma)) {
                    const paa = attrs(pa);
                    if (!paa.OD && !paa.DO) continue;

                    // Scope: PA.S3 is most reliable, then MA.S4, then MA.S3
                    let scope = paa.S3 || paa.B8 || maa.S4 || '';

                    // Time: try explicit fields first
                    let timeVal = paa.S4 || paa.B5 || '';
                    if (!timeVal && maa.S3 && maa.S3 !== scope) {
                        timeVal = maa.S3;
                    }

                    // If time still empty, infer from scope occurrence
                    if (!timeVal && timeOptions.length > 0 && currentGroupIdx >= 0) {
                        const gs = groupScopes[currentGroupIdx] || scope;
                        if (!scopeOccurrence[gs + '_' + currentGroupIdx]) {
                            scopeOccurrence[gs + '_' + currentGroupIdx] = true;
                            // Count how many groups before this one had same scope
                            let count = 0;
                            for (let gi = 0; gi < currentGroupIdx; gi++) {
                                if (groupScopes[gi] === gs) count++;
                            }
                            scopeOccurrence[gs + '_idx_' + currentGroupIdx] = count;
                        }
                        const timeIdx = scopeOccurrence[gs + '_idx_' + currentGroupIdx] || 0;
                        timeVal = timeOptions[timeIdx] || timeOptions[0] || '';
                    }

                    // Player name: for player markets, S1 or B2 has the name
                    const player = paa.S1 || paa.B2 || '';

                    marketData.selections.push({
                        market: marketName,
                        group: maName,
                        scope: scope,
                        time: timeVal,
                        selection: paa.S2 || paa.NA || paa.B1 || '',
                        player: player,
                        odds_frac: paa.OD || '',
                        odds_dec: paa.DO || '',
                        handicap: paa.HA || '',
                        fi: paa.FI || fi,
                        id: paa.ID || '',
                        suspended: paa.SU || '0'
                    });
                }
            }
        }

        if (marketData.selections.length > 0) {
            byFI[fi].push(marketData);
        }
    }

    // Build result per match
    const result = {};
    for (const [fi, markets] of Object.entries(byFI)) {
        const totalSels = markets.reduce((s, m) => s + m.selections.length, 0);
        result[fi] = {
            fi: fi,
            league: markets[0]?.league || '',
            marketCount: markets.length,
            selectionCount: totalSels,
            markets: markets
        };
    }

    return JSON.stringify(result);
}
"""


def frac_to_dec(frac_str):
    """Convert fractional odds '5/6' to decimal 1.83."""
    if not frac_str:
        return None
    try:
        if '/' in frac_str:
            num, den = frac_str.split('/')
            return round(1 + float(num) / float(den), 3)
        return float(frac_str)
    except:
        return None


def scrape_tab(tab_info):
    """Scrape all FixtureStems from one Chrome tab."""
    ws_url = tab_info['webSocketDebuggerUrl']
    url = tab_info.get('url', '')
    t0 = time.time()

    ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=30)
    try:
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable', 'params': {}}))
        time.sleep(0.3)
        # Drain events
        ws.settimeout(0.2)
        try:
            while True: ws.recv()
        except: pass
        ws.settimeout(45)

        # Check ns_gen5_data exists
        ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {
            'expression': '!!ns_gen5_data && !!ns_gen5_data.FixtureStem',
            'returnByValue': True
        }}))
        r = json.loads(ws.recv())
        if not r.get('result', {}).get('result', {}).get('value'):
            return {'error': 'ns_gen5_data.FixtureStem not found', '_tab_url': url}

        # Get FixtureStem prototype and queryObjects
        ws.send(json.dumps({'id': 3, 'method': 'Runtime.evaluate', 'params': {
            'expression': 'ns_gen5_data.FixtureStem.prototype',
            'returnByValue': False
        }}))
        r = json.loads(ws.recv())
        proto_id = r['result']['result'].get('objectId')
        if not proto_id:
            return {'error': 'queryObjects setup failed', '_tab_url': url}

        ws.send(json.dumps({'id': 4, 'method': 'Runtime.queryObjects', 'params': {
            'prototypeObjectId': proto_id
        }}))
        r = json.loads(ws.recv())
        arr_id = r['result']['objects'].get('objectId')
        if not arr_id:
            return {'error': 'queryObjects failed', '_tab_url': url}

        # Extract all markets grouped by FI
        ws.send(json.dumps({'id': 5, 'method': 'Runtime.callFunctionOn', 'params': {
            'objectId': arr_id,
            'functionDeclaration': EXTRACT_ALL_JS,
            'returnByValue': True,
            'awaitPromise': False
        }}))
        r = json.loads(ws.recv())
        val = r.get('result', {}).get('result', {}).get('value', '')
        if not val:
            return {'error': f'no value returned: {r}', '_tab_url': url}

        data = json.loads(val) if isinstance(val, str) else val
        data['_elapsed'] = round(time.time() - t0, 1)
        data['_tab_url'] = url
        return data
    finally:
        ws.close()


def process_match(fi, match_data):
    """Convert fractional odds to decimal and organize market data."""
    organized = {
        'fi': fi,
        'league': match_data.get('league', ''),
        'market_count': match_data.get('marketCount', 0),
        'selection_count': match_data.get('selectionCount', 0),
        'markets': {}
    }

    for market in match_data.get('markets', []):
        market_name = market['name']
        if market_name not in organized['markets']:
            organized['markets'][market_name] = []

        for sel in market.get('selections', []):
            odds_dec = frac_to_dec(sel.get('odds_frac')) or sel.get('odds_dec')
            entry = {
                'group': sel.get('group', ''),
                'scope': sel.get('scope', ''),
                'time': sel.get('time', ''),
                'selection': sel.get('selection', ''),
                'odds': odds_dec,
                'odds_frac': sel.get('odds_frac', ''),
                'handicap': sel.get('handicap', ''),
                'suspended': sel.get('suspended') == '1',
            }
            # Include player name when available (goalkeeper, card recipient, etc.)
            if sel.get('player'):
                entry['player'] = sel['player']
            organized['markets'][market_name].append(entry)

    return organized


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fi', help='Specific FI to extract')
    ap.add_argument('--summary', action='store_true', help='Summary only, no JSON save')
    args = ap.parse_args()

    # Get Chrome tabs
    try:
        tabs = requests.get(f'http://{CDP_HOST}:{CDP_PORT}/json', timeout=5).json()
    except Exception as e:
        print(f"ERROR: Cannot connect to Chrome CDP at port {CDP_PORT}: {e}")
        print("Launch Chrome with: --remote-debugging-port=9222 --user-data-dir=$HOME/.chrome-debug")
        sys.exit(1)

    match_tabs = [t for t in tabs if '/AC/B1/C1/D8/' in t.get('url', '')]
    if args.fi:
        match_tabs = [t for t in match_tabs if f'/E{args.fi}/' in t.get('url', '')]

    if not match_tabs:
        print("No bet365 match tabs found.")
        sys.exit(1)

    print(f"Found {len(match_tabs)} match tab(s)")
    print("=" * 80)

    all_matches = {}

    for tab in match_tabs:
        url = tab.get('url', '')
        fi_match = re.search(r'/E(\d+)/', url)
        tab_fi = fi_match.group(1) if fi_match else '?'
        print(f"\nScraping tab FI={tab_fi}...")

        try:
            result = scrape_tab(tab)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        if 'error' in result:
            print(f"  FAIL: {result['error']}")
            continue

        elapsed = result.pop('_elapsed', 0)
        tab_url = result.pop('_tab_url', '')

        for fi, match_data in result.items():
            if fi.startswith('_'): continue  # Skip metadata keys
            processed = process_match(fi, match_data)

            if fi in all_matches:
                # Merge markets from multiple tabs
                for mname, sels in processed['markets'].items():
                    if mname not in all_matches[fi]['markets']:
                        all_matches[fi]['markets'][mname] = sels
                    else:
                        all_matches[fi]['markets'][mname].extend(sels)
                all_matches[fi]['market_count'] = len(all_matches[fi]['markets'])
                all_matches[fi]['selection_count'] = sum(
                    len(s) for s in all_matches[fi]['markets'].values()
                )
            else:
                all_matches[fi] = processed

            mkt_count = processed['market_count']
            sel_count = processed['selection_count']
            print(f"  FI={fi}: {mkt_count} markets, {sel_count} selections ({elapsed:.1f}s)")

    # Print summary
    print(f"\n{'=' * 80}")
    print(f"{'Match FI':<15} {'League':<25} {'Markets':>8} {'Selections':>11}")
    print("-" * 60)

    total_markets = 0
    total_sels = 0
    for fi, m in sorted(all_matches.items()):
        mc = m['market_count']
        sc = m['selection_count']
        total_markets += mc
        total_sels += sc
        print(f"{fi:<15} {m['league'][:25]:<25} {mc:>8} {sc:>11}")

    print("-" * 60)
    print(f"{'TOTAL':<15} {len(all_matches)} matches{' '*17} {total_markets:>8} {total_sels:>11}")

    # Show sample odds
    for fi, m in list(all_matches.items())[:2]:
        print(f"\n--- Sample: FI={fi} ({m['league']}) ---")
        for mname, sels in list(m['markets'].items())[:3]:
            print(f"  {mname}:")
            for s in sels[:4]:
                susp = " [SUSPENDED]" if s['suspended'] else ""
                scope = f" ({s['scope']})" if s['scope'] else ""
                time_lbl = f" [{s['time']}]" if s['time'] else ""
                print(f"    {s['group']} {s['selection']}: {s['odds']}{scope}{time_lbl}{susp}")

    # Save
    if not args.summary:
        os.makedirs(ODDS_DIR, exist_ok=True)
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

        output = {
            'scraped_at': datetime.now().isoformat(),
            'match_count': len(all_matches),
            'total_markets': total_markets,
            'total_selections': total_sels,
            'matches': all_matches
        }

        path = os.path.join(ODDS_DIR, f'odds_{today}.json')
        with open(path, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\nSaved: {path}")

        # Also save latest
        latest = os.path.join(ODDS_DIR, 'odds_latest.json')
        with open(latest, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Saved: {latest}")


if __name__ == '__main__':
    main()
