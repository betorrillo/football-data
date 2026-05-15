#!/usr/bin/env python3
"""
Optimal bet365 scraper: walks ALL EVs (each EV = a market with all dropdown variants).
Scrapes every open bet365 match tab in Chrome (CDP on :9222) in parallel.
"""
import json, re, os, time, sys, threading, datetime, requests, websocket

BASE = os.path.dirname(os.path.abspath(__file__))
ODDS_DIR = os.path.join(BASE, 'odds')
os.makedirs(ODDS_DIR, exist_ok=True)


def to_decimal(od):
    if not od: return None
    s = str(od)
    if '/' in s:
        try:
            n, d = s.split('/'); return round(int(n)/int(d) + 1, 3)
        except Exception: return od
    try: return float(s)
    except Exception: return od


def slug(s):
    s = (s or '').lower()
    s = re.sub(r'[^\w\s-]', '', s).strip()
    return re.sub(r'[\s_-]+', '-', s)[:60] or 'match'


EXTRACT_ALL = r'''function(FI_TARGET) {
  return (async () => {
    try {
      const kids = s => { try { return s.getChildren() || []; } catch(e){ return []; } };
      const countAll = s => { const c=kids(s); let n=c.length; for(const x of c) n+=countAll(x); return n; };
      const data = s => (s && s.data) || {};

      // SUBSCRIBE to all sub-tabs (I1..I9, I99, etc.) to force bet365 to push all markets into memory
      try {
        const sm = Locator && Locator.subscriptionManager;
        if (sm) {
          const tabIds = ['I1','I2','I3','I4','I5','I6','I7','I8','I9','I10','I11','I12','I99','BBC','BPS','BTS','BAB'];
          const cb = ()=>{};
          for (const t of tabIds) {
            try { sm.subscribe('#AC#B1#C1#D8#E'+FI_TARGET+'#F3#'+t+'#I^18#', cb, 0); } catch(e){}
            try { sm.subscribe('#AC#B1#C1#D8#E'+FI_TARGET+'#F3#'+t+'#', cb, 0); } catch(e){}
          }
        }
      } catch(e){}

      // Wait for data to arrive — multi-pass with PD-recollection
      function getStems() { return Array.from(this); }
      const subbed = new Set();
      for (let pass = 0; pass < 5; pass++) {
        let prev=-1, stable=0, waited=0;
        while (waited < 4000) {
          await new Promise(r => setTimeout(r, 200));
          waited += 200;
          const cur = Array.from(this).length;
          if (cur === prev) stable += 200; else stable = 0;
          prev = cur;
          if (stable >= 800 && cur > 50) break;
        }
        // Re-collect PDs from all market-shaped EVs and subscribe to new ones
        try {
          const sm = Locator.subscriptionManager;
          const cb = ()=>{};
          const allEVs = Array.from(this).filter(s => s.nodeName === 'EV');
          let added = 0;
          for (const ev of allEVs) {
            for (const mg of kids(ev)) {
              const pd = data(mg).PD;
              if (pd && !subbed.has(pd)) {
                try { sm.subscribe(pd, cb, 0); subbed.add(pd); added++; } catch(e){}
              }
            }
          }
          if (added === 0 && pass >= 2) break;
        } catch(e){}
      }

      const a = Array.from(this);
      const evs_all = a.filter(s => s.nodeName === 'EV');

      // Extract real FI from an EV's IT field. Pattern: ...#E{FI}#... — last occurrence is the actual fixture FI
      function extractFI(ev) {
        const it = data(ev).IT || '';
        const ms = [...String(it).matchAll(/#E(\d+)#/g)].map(m=>m[1]);
        return ms.length ? ms[ms.length-1] : null;
      }

      // Build fixture catalog: NA contains " v " — these reference real matches
      const fixtureMap = {};  // FI -> {NA, L3, IT, total}
      for (const ev of evs_all) {
        const d = data(ev);
        if (!d.NA || !/ v /.test(d.NA)) continue;
        const fi = extractFI(ev);
        if (!fi) continue;
        const total = countAll(ev);
        if (!fixtureMap[fi] || total > fixtureMap[fi].total) {
          fixtureMap[fi] = {NA: d.NA, L3: d.L3 || null, IT: d.IT || null, total};
        }
      }

      // Markets: EVs with NA + L3 + has children with stems. The IT often doesn't carry the FI,
      // so we attribute all markets in this tab's memory to the URL's FI_TARGET.
      // If multiple fixtures coexist, this conflates them — acceptable since one tab usually
      // shows one match.
      const marketEVs = evs_all.filter(s => {
        const d = data(s);
        if (!d.NA || !d.L3) return false;
        return countAll(s) > 0;
      });
      const marketsByFI = {};
      marketsByFI[FI_TARGET] = marketEVs;

      // For target FI, dump everything. Also dump other FIs that have markets.
      function dumpEV(ev) {
        const ed = data(ev);
        const evObj = {
          marketName: ed.NA, id: ed.ID, league: ed.L3,
          stemCount: countAll(ev), groups: []
        };
        for (const mg of kids(ev)) {
          const md = data(mg);
          const group = {
            LD: md.LD || null, RD: md.RD || null, TL: md.TL || null,
            SY: md.SY || null, TE: md.TE || null, ST: md.ST || null,
            mas: []
          };
          for (const ma of kids(mg)) {
            const mad = data(ma);
            const maObj = {
              NA: mad.NA||null, SY: mad.SY||null, HD: mad.HD||null,
              HA: mad.HA||null, OR: mad.OR||null, HW: mad.HW||null,
              pas: []
            };
            for (const pa of kids(ma)) {
              const pd = data(pa);
              maObj.pas.push({
                NA: pd.NA||null, OD: pd.OD||null, HD: pd.HD||null,
                HA: pd.HA||null, SU: pd.SU||null, OR: pd.OR||null,
              });
            }
            group.mas.push(maObj);
          }
          evObj.groups.push(group);
        }
        return evObj;
      }

      const dumps = {};  // FI -> {fixture: {NA,L3,IT,total}, markets: [evObj]}
      for (const fi of Object.keys(marketsByFI)) {
        if (marketsByFI[fi].length === 0) continue;
        dumps[fi] = {
          fixture: fixtureMap[fi] || null,
          markets: marketsByFI[fi].map(dumpEV),
        };
      }
      // Also include the target FI even if no markets, so caller knows the fixture exists
      if (FI_TARGET && fixtureMap[FI_TARGET] && !dumps[FI_TARGET]) {
        dumps[FI_TARGET] = {fixture: fixtureMap[FI_TARGET], markets: []};
      }

      // Legacy outputs for backward compat
      const fixtureEV_target = fixtureMap[FI_TARGET];
      const fixtureNA = fixtureEV_target ? fixtureEV_target.NA : '';
      let teams = [];
      if (fixtureNA) {
        const m = fixtureNA.split(/ v /);
        if (m.length === 2) teams = [m[0].trim(), m[1].trim()];
      }
      const league = fixtureEV_target ? fixtureEV_target.L3 : null;
      const meta = fixtureEV_target ? {IT: fixtureEV_target.IT} : {};
      const kickoff = '';

      // Flat result for target FI
      const targetMarkets = (dumps[FI_TARGET] && dumps[FI_TARGET].markets) || [];
      return JSON.stringify({
        ok:true,
        FI_TARGET,
        evCount: targetMarkets.length,
        fixtureNA, teams, league, kickoff, meta,
        markets: targetMarkets,
        // Bonus: all fixtures discovered in memory and any others with markets
        all_fixtures: fixtureMap,
        all_dumps: dumps,
      });
    } catch(e) { return JSON.stringify({ok:false, err:String(e), stack:String(e.stack)}); }
  })();
}'''


def cdp_call(ws, method, params, timeout=120, _ids=[0]):
    _ids[0] += 1
    mid = _ids[0]
    ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
    t0 = time.time()
    while time.time()-t0 < timeout:
        r = json.loads(ws.recv())
        if r.get('id') == mid:
            if 'error' in r: raise RuntimeError(f"{method}: {r['error']}")
            return r.get('result', r)
    raise TimeoutError(method)


def structure_market(ev):
    """Convert one raw EV into structured market data with variants by dropdown."""
    name = ev['marketName']
    out = {}
    for g in ev['groups']:
        ld = (g.get('LD') or '').split('¬') if g.get('LD') else []
        rd = (g.get('RD') or '').split('¬') if g.get('RD') else []
        tl = (g.get('TL') or '').split('¬') if g.get('TL') else []
        sy = g.get('SY') or ''
        mas = g['mas']

        if sy == 'bbc' and ld and rd:
            # Over/Under with team x period dropdowns
            n_ld, n_rd = len(ld), len(rd)
            expected = n_ld * n_rd
            chunk = max(1, len(mas) // expected) if expected else len(mas)
            idx = 0
            for li, lopt in enumerate(ld):
                for ri, ropt in enumerate(rd):
                    key = f"{lopt} / {ropt}".strip(' /')
                    sels = []
                    for ma in mas[idx:idx+chunk]:
                        for pa in ma['pas']:
                            if pa.get('OD'):
                                sels.append({
                                    'selection': ((ma.get('NA') or '') + ((' — ' + pa['NA']) if pa.get('NA') else '')).strip(' —'),
                                    'odds': to_decimal(pa['OD']),
                                    'line': pa.get('HD'),
                                    'suspended': pa.get('SU') == '1',
                                })
                    idx += chunk
                    if sels: out[key] = sels
        elif sy in ('bbb','bbe','bbf','bbi','bba'):
            # Player matrix or player-prop blocks (header bbb + lines)
            blocks = []; cur = None
            for ma in mas:
                if (ma.get('SY') or '') == 'bbb':
                    if cur: blocks.append(cur)
                    cur = {'header': ma, 'lines': []}
                elif cur:
                    cur['lines'].append(ma)
                else:
                    blocks.append({'header': None, 'lines': [ma]})
            if cur: blocks.append(cur)

            for bi, blk in enumerate(blocks):
                players = [pa.get('NA') or '?' for pa in blk['header']['pas']] if blk['header'] else []
                if tl and bi < len(tl): key = tl[bi]
                elif ld and bi < len(ld): key = ld[bi]
                else: key = f"bloque_{bi}" if len(blocks) > 1 else "principal"
                sels = []
                for line_ma in blk['lines']:
                    line_name = line_ma.get('NA') or ''
                    for pi, pa in enumerate(line_ma['pas']):
                        if pa.get('OD'):
                            player = players[pi] if pi < len(players) else None
                            sels.append({
                                'selection': pa.get('NA') or player or '?',
                                'line': line_name,
                                'player': player,
                                'odds': to_decimal(pa['OD']),
                                'suspended': pa.get('SU') == '1',
                            })
                if sels: out[key] = sels
        else:
            # Generic dump
            sels = []
            for ma in mas:
                for pa in ma['pas']:
                    if pa.get('OD'):
                        sels.append({
                            'selection': ((ma.get('NA') or '') + ((' — ' + pa.get('NA','')) if pa.get('NA') else '')).strip(' —'),
                            'odds': to_decimal(pa['OD']),
                            'line': pa.get('HD'),
                            'suspended': pa.get('SU') == '1',
                        })
            if sels: out['default'] = sels
    return out if out else None


def get_browser_ws():
    info = requests.get('http://localhost:9222/json/version', timeout=5).json()
    return info['webSocketDebuggerUrl']


def scrape_one(tab, activate=True, browser_ws_url=None):
    fi_match = re.search(r'/E(\d+)/', tab['url'])
    fi = fi_match.group(1) if fi_match else 'unknown'
    t0 = time.time()
    try:
        # Activate the tab at BROWSER level — this physically moves it to the front of its window
        if activate and browser_ws_url:
            try:
                bws = websocket.create_connection(browser_ws_url, suppress_origin=True, timeout=10)
                cdp_call(bws, 'Target.activateTarget', {'targetId': tab['id']})
                bws.close()
            except Exception: pass
            time.sleep(10.0)  # let bet365 fetch markets after coming to front

        ws = websocket.create_connection(tab['webSocketDebuggerUrl'], suppress_origin=True, timeout=60)
        cdp_call(ws, 'Runtime.enable', {})
        cdp_call(ws, 'Page.enable', {})
        r = cdp_call(ws, 'Runtime.evaluate', {'expression': 'ns_gen5_data && ns_gen5_data.FixtureStem ? "ok":"missing"', 'returnByValue': True})
        if r['result'].get('value') != 'ok':
            ws.close(); return {'fi': fi, 'error': 'ns_gen5_data missing', 'url': tab['url']}
        r = cdp_call(ws, 'Runtime.evaluate', {'expression': 'ns_gen5_data.FixtureStem.prototype', 'returnByValue': False})
        proto_id = r['result']['objectId']
        arr_id = cdp_call(ws, 'Runtime.queryObjects', {'prototypeObjectId': proto_id})['objects']['objectId']
        r = cdp_call(ws, 'Runtime.callFunctionOn', {
            'objectId': arr_id, 'functionDeclaration': EXTRACT_ALL,
            'arguments': [{'value': fi}],
            'returnByValue': True, 'awaitPromise': True,
        }, timeout=90)
        val = r.get('result',{}).get('value')
        d = json.loads(val) if val else {'ok': False, 'err': 'no value'}
        ws.close()
    except Exception as e:
        return {'fi': fi, 'error': str(e), 'url': tab['url']}

    if not d.get('ok'):
        return {'fi': fi, 'error': d.get('err','?'), 'url': tab['url']}

    teams = d.get('teams', [])
    home = teams[0] if len(teams)>0 else None
    away = teams[1] if len(teams)>1 else None
    match_name = (f"{home} vs {away}") if home and away else (d.get('fixtureNA') or f"FI_{fi}")

    markets = {}
    for ev in d.get('markets', []):
        m = structure_market(ev)
        if m: markets[ev['marketName']] = m

    sel_count = sum(len(v) for mk in markets.values() for v in mk.values())
    # Bonus: dump neighboring fixtures with markets (other matches loaded in this tab's memory)
    neighbors = []
    for nfi, ndump in (d.get('all_dumps') or {}).items():
        if nfi == fi: continue
        if not ndump.get('markets'): continue
        nm = {}
        for ev in ndump['markets']:
            sm = structure_market(ev)
            if sm: nm[ev['marketName']] = sm
        if not nm: continue
        nfix = ndump.get('fixture') or {}
        nteams = nfix.get('NA','').split(' v ') if nfix.get('NA') else []
        neighbors.append({
            'fi': nfi,
            'match': nfix.get('NA') or f"FI_{nfi}",
            'home': nteams[0].strip() if len(nteams)>0 else None,
            'away': nteams[1].strip() if len(nteams)>1 else None,
            'league': nfix.get('L3'),
            'market_count': len(nm),
            'selection_count': sum(len(v) for mk in nm.values() for v in mk.values()),
            'markets': nm,
        })

    return {
        'ok': True, 'fi': fi, 'match': match_name, 'home': home, 'away': away,
        'league': d.get('league'), 'kickoff': d.get('kickoff'), 'meta': d.get('meta'),
        'url': tab['url'],
        'scraped_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'source': 'bet365',
        'market_count': len(markets), 'selection_count': sel_count,
        'markets': markets,
        '_neighbors': neighbors,
        '_all_fixtures': d.get('all_fixtures'),
        '_elapsed': round(time.time()-t0, 2),
    }


def main():
    tabs = requests.get('http://localhost:9222/json', timeout=5).json()
    bet = [t for t in tabs if '/AC/B1/C1/D8/' in t.get('url','')]
    if not bet:
        print('No bet365 tabs found.'); sys.exit(1)

    print(f"Scraping {len(bet)} tabs in parallel (no activation, reading data already in memory)...\n")
    results = [None]*len(bet); ths = []
    for i, t in enumerate(bet):
        def run(i=i, t=t):
            fi = re.search(r'/E(\d+)/', t['url'])
            fi = fi.group(1) if fi else '?'
            r = scrape_one(t, activate=False, browser_ws_url=None)
            results[i] = r
            print(f"  FI={fi} {'OK' if r.get('ok') else 'FAIL'} {r.get('match','?')[:40]:<40} | {r.get('market_count',0):>3} mkts {r.get('selection_count',0):>5} sels +{len(r.get('_neighbors') or []):>2} nbr {r.get('_elapsed',0):>5}s", flush=True)
        th = threading.Thread(target=run); th.start(); ths.append(th)
    for th in ths: th.join()

    today = datetime.date.today().isoformat()
    print(f"\n{'FI':<12} {'Match':<45} {'Mkts':>5} {'Sels':>6} {'+Nbr':>5} {'Sec':>5}")
    print('-'*82)
    saved_fis = set()
    saved_paths = []
    for r in results:
        if not r or not r.get('ok'):
            print(f"  FAIL FI={(r or {}).get('fi','?')}: {(r or {}).get('error','?')}")
            continue
        # Save the target fixture
        league_slug = slug(r.get('league') or 'unknown')
        match_slug = slug(r['match'])
        path = os.path.join(ODDS_DIR, f"{league_slug}_{match_slug}_{r['fi']}_{today}.json")
        out = {k:v for k,v in r.items() if not k.startswith('_')}
        out['_elapsed'] = r['_elapsed']
        with open(path, 'w') as f: json.dump(out, f, ensure_ascii=False, indent=2)
        if r['fi'] not in saved_fis:
            saved_fis.add(r['fi']); saved_paths.append(path)
        print(f"{r['fi']:<12} {r['match'][:45]:<45} {r['market_count']:>5} {r['selection_count']:>6} {len(r.get('_neighbors') or []):>5} {r['_elapsed']:>5}")

        # Save neighbor fixtures discovered in same memory
        for n in (r.get('_neighbors') or []):
            if n['fi'] in saved_fis: continue
            nl = slug(n.get('league') or 'unknown')
            nm = slug(n['match'])
            npath = os.path.join(ODDS_DIR, f"{nl}_{nm}_{n['fi']}_{today}.json")
            n_out = {
                'ok': True, 'fi': n['fi'], 'match': n['match'],
                'home': n['home'], 'away': n['away'], 'league': n['league'],
                'source': 'bet365', 'discovered_via_FI': r['fi'],
                'scraped_at': r['scraped_at'],
                'market_count': n['market_count'], 'selection_count': n['selection_count'],
                'markets': n['markets'],
            }
            with open(npath, 'w') as f: json.dump(n_out, f, ensure_ascii=False, indent=2)
            saved_fis.add(n['fi']); saved_paths.append(npath)
            print(f"  +nbr  FI={n['fi']:<10} {n['match'][:40]:<40} {n['market_count']:>3} mkts {n['selection_count']:>4} sels")

    print('-'*82)
    for p in saved_paths: print(f"  -> {p}")


if __name__ == '__main__':
    main()
