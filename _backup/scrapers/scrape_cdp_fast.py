#!/usr/bin/env python3
"""
Fast CDP-based bet365 scraper.

Reads match data directly from bet365 SPA JavaScript memory via CDP:
  1. Runtime.queryObjects(FixtureStem) to find live match instances
  2. Runtime.callFunctionOn — in a single JS call:
     - Pick the most populated FixtureStem
     - Batch-subscribe to all tabs (I1..I9, BBC) + shell MG topics
     - Event-driven wait until stem tree stabilizes
     - Walk tree -> tabs -> MGs -> MAs -> PAs
     - Return full JSON

Usage:
  python3 scrape_cdp_fast.py                    # all open bet365 match tabs
  python3 scrape_cdp_fast.py --fi 191538681     # specific FI
  python3 scrape_cdp_fast.py --parallel         # scrape tabs concurrently
"""
import argparse, json, os, re, sys, time, threading
import websocket, requests

CDP_HOST = 'localhost'
CDP_PORT = 9222
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ODDS_DIR = os.path.join(BASE_DIR, 'odds')


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=30)
        self._id = 0
        self._lock = threading.Lock()

    def call(self, method, params=None, timeout=30):
        with self._lock:
            self._id += 1
            mid = self._id
            self.ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
            t0 = time.time()
            while time.time() - t0 < timeout:
                r = json.loads(self.ws.recv())
                if r.get('id') == mid:
                    if 'error' in r:
                        raise RuntimeError(f"CDP {method}: {r['error']}")
                    return r['result']
            raise TimeoutError(f"CDP timeout on {method}")

    def query_objects(self, ctor_expr):
        r = self.call('Runtime.evaluate', {'expression': ctor_expr + '.prototype', 'returnByValue': False})
        proto_id = r['result'].get('objectId')
        if not proto_id:
            return None
        r = self.call('Runtime.queryObjects', {'prototypeObjectId': proto_id})
        return r['objects'].get('objectId')

    def close(self):
        try: self.ws.close()
        except: pass


EXTRACT_JS = r"""
function() {
  const fsArray = Array.from(this);
  return (async () => {
    try {
      if (!fsArray || !fsArray.length)
        return JSON.stringify({ok:false, err:'no FixtureStem instances'});

      function getKids(s) {
        try { return s.getChildren() || []; } catch(e) { return []; }
      }
      function countAll(s) {
        const ch = getKids(s); let n = ch.length;
        for (const c of ch) n += countAll(c);
        return n;
      }
      function attrs(s) {
        const a = {};
        // Try s.data first (new bet365), then s._attributes (legacy)
        const src = s.data || s._attributes;
        if (!src) return a;
        for (const k in src) a[k] = src[k];
        return a;
      }
      function getAttr(s, key) {
        // Try getAttribute method first, then s.data, then s._attributes
        if (s.getAttribute) { const v = s.getAttribute(key); if (v) return v; }
        if (s.data && s.data[key]) return s.data[key];
        if (s._attributes && s._attributes[key]) return s._attributes[key];
        return '';
      }
      function collectShells(s, out) {
        if (!s) return;
        const pd = getAttr(s, 'PD');
        if (pd && pd.indexOf('#S^1#') !== -1) out.push(pd);
        for (const c of getKids(s)) collectShells(c, out);
      }

      // Pick the most populated FixtureStem
      const sorted = fsArray.slice().sort((a,b) => countAll(b) - countAll(a));
      const target = sorted[0];
      const FI = getAttr(target, 'FI') || (getAttr(target, 'IT')||'').replace(/[^0-9]/g,'') || '?';
      const CI = getAttr(target, 'CI') || getAttr(target, 'CC');
      const matchName = getAttr(target, 'NA');
      const kickoff = getAttr(target, 'BC') || getAttr(target, 'TI');

      // Build topic list: all tabs + current shell MGs
      const tabIds = ['I1','I2','I3','I4','I5','I6','I7','I8','I9','BBC'];
      const tabTopics = tabIds.map(t => '#AC#B1#C1#D8#E'+FI+'#F3#'+t+'#I^18#');
      const shell1 = []; collectShells(target, shell1);

      const sm = Locator.subscriptionManager;
      const cb = function(){};
      for (const t of tabTopics) { try { sm.subscribe(t, cb, 0); } catch(e){} }
      for (const t of shell1)    { try { sm.subscribe(t, cb, 0); } catch(e){} }

      // Event-driven wait #1: stem tree stabilizes after tab subscribes
      let prev = -1, stable = 0, waited = 0;
      while (waited < 8000) {
        await new Promise(r => setTimeout(r, 200));
        waited += 200;
        const cur = countAll(target);
        if (cur === prev) stable += 200; else stable = 0;
        prev = cur;
        if (stable >= 600 && cur > 100) break;
      }

      // Re-collect shells (new ones may have appeared after tab subscribes)
      const shell2raw = []; collectShells(target, shell2raw);
      const shell1set = new Set(shell1);
      const shell2 = shell2raw.filter(t => !shell1set.has(t));
      for (const t of shell2) { try { sm.subscribe(t, cb, 0); } catch(e){} }

      // Event-driven wait #2
      prev = -1; stable = 0; waited = 0;
      while (waited < 5000) {
        await new Promise(r => setTimeout(r, 200));
        waited += 200;
        const cur = countAll(target);
        if (cur === prev) stable += 200; else stable = 0;
        prev = cur;
        if (stable >= 600) break;
      }

      // Walk: FS -> tabs (Ix) -> MGs -> MAs -> PAs
      const tree = [];
      for (const tab of getKids(target)) {
        const tabNode = { nn: tab.nodeName || '?', a: attrs(tab), mgs: [] };
        for (const mg of getKids(tab)) {
          const mgNode = { a: attrs(mg), mas: [] };
          for (const ma of getKids(mg)) {
            const maNode = { a: attrs(ma), pas: [] };
            for (const pa of getKids(ma)) {
              maNode.pas.push(attrs(pa));
            }
            mgNode.mas.push(maNode);
          }
          tabNode.mgs.push(mgNode);
        }
        tree.push(tabNode);
      }

      return JSON.stringify({
        ok: true,
        FI, CI, matchName, kickoff,
        stemCount: countAll(target),
        fsCandidates: fsArray.length,
        tabsSubscribed: tabTopics.length,
        shellsSubscribed: shell1.length + shell2.length,
        tree
      });
    } catch(e) {
      return JSON.stringify({ok:false, err: String(e), stack: e.stack});
    }
  })();
}
"""


def count_markets_sels(tree):
    mgs = mas = pas = with_odds = 0
    for tab in tree:
        for mg in tab.get('mgs', []):
            mgs += 1
            for ma in mg.get('mas', []):
                mas += 1
                for pa in ma.get('pas', []):
                    pas += 1
                    if pa.get('OD') or pa.get('DO'):
                        with_odds += 1
    return mgs, mas, pas, with_odds


def sanitize(s):
    s = s or ''
    s = re.sub(r'[^\w\s-]', '', s).strip().lower()
    s = re.sub(r'\s+', '-', s)
    return s[:60]


def scrape_tab(tab_info):
    ws_url = tab_info['webSocketDebuggerUrl']
    url = tab_info.get('url', '')
    t0 = time.time()
    cdp = CDP(ws_url)
    try:
        cdp.call('Runtime.enable')
        chk = cdp.call('Runtime.evaluate', {
            'expression': "(typeof ns_gen5_data !== 'undefined' && !!ns_gen5_data.FixtureStem) ? 'ok' : 'missing'",
            'returnByValue': True,
        })['result'].get('value')
        if chk != 'ok':
            return {'url': url, 'error': f'ns_gen5_data {chk}'}

        array_id = cdp.query_objects('ns_gen5_data.FixtureStem')
        if not array_id:
            return {'url': url, 'error': 'queryObjects failed'}

        r = cdp.call('Runtime.callFunctionOn', {
            'objectId': array_id,
            'functionDeclaration': EXTRACT_JS,
            'returnByValue': True,
            'awaitPromise': True,
        }, timeout=45)
        val = r.get('result', {}).get('value')
        if val is None:
            return {'url': url, 'error': f'no value: {r}'}
        data = json.loads(val) if isinstance(val, str) else val
        data['_elapsed'] = round(time.time() - t0, 1)
        data['_tab_url'] = url
        return data
    finally:
        cdp.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fi', help='Specific FI')
    ap.add_argument('--parallel', action='store_true')
    args = ap.parse_args()

    tabs = requests.get(f'http://{CDP_HOST}:{CDP_PORT}/json', timeout=5).json()
    match_tabs = [t for t in tabs if '/AC/B1/C1/D8/' in t.get('url','')]
    if args.fi:
        match_tabs = [t for t in match_tabs if f'/E{args.fi}/' in t.get('url','')]
    if not match_tabs:
        print("No match tabs found."); sys.exit(1)

    print(f"Found {len(match_tabs)} match tab(s)")
    os.makedirs(ODDS_DIR, exist_ok=True)

    results = []
    if args.parallel and len(match_tabs) > 1:
        outs = [None]*len(match_tabs); ths = []
        def run(i,t):
            try: outs[i] = scrape_tab(t)
            except Exception as e: outs[i] = {'error': str(e), '_tab_url': t.get('url')}
        for i,t in enumerate(match_tabs):
            th = threading.Thread(target=run, args=(i,t))
            th.start(); ths.append(th)
        for th in ths: th.join()
        results = outs
    else:
        for t in match_tabs:
            try: results.append(scrape_tab(t))
            except Exception as e: results.append({'error': str(e), '_tab_url': t.get('url')})

    print(f"\n{'='*75}")
    print(f"{'Match':<40} {'MGs':>4} {'Mkts':>5} {'Sels':>5} {'Odds':>5} {'Stem':>6} {'sec':>5}")
    print('-'*75)
    for r in results:
        if not r or not r.get('ok'):
            print(f"  FAIL: {(r or {}).get('error') or r.get('err','?')} :: {(r or {}).get('_tab_url','')[-40:]}")
            continue
        mgs, mas, pas, wo = count_markets_sels(r.get('tree', []))
        name = r.get('matchName') or '?'
        print(f"{name[:40]:<40} {mgs:>4} {mas:>5} {pas:>5} {wo:>5} {r.get('stemCount',0):>6} {r.get('_elapsed',0):>5}")
        fi = r.get('FI','?')
        fname = f"cdp_full_{fi}_{sanitize(name)}.json"
        path = os.path.join(ODDS_DIR, fname)
        with open(path, 'w') as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        r['_saved'] = path
    print('='*75)
    for r in results:
        if r and r.get('_saved'): print(f"  -> {r['_saved']}")


if __name__ == '__main__':
    main()
