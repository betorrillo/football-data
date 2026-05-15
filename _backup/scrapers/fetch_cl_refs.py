#!/usr/bin/env python3
"""Fetch CL referee stats from valuestats.com"""
import requests, json, time
from cdp_client import CDPClient

refs = [
    ('Danny Makkelie', 'https://valuestats.com/arbitro/16702-danny-makkelie'),
    ('István Kovács', 'https://valuestats.com/arbitro/16477-istvan-kovacs'),
]

JS_EXTRACT = r"""
(() => {
    const text = document.body.textContent;
    const stats = {};
    const ycm = text.match(/(\d+[\.,]\d+)\s*(?:Yellow Cards? per Match|Tarjetas amarillas por partido)/i);
    if (ycm) stats.yellow_per_match = parseFloat(ycm[1].replace(',','.'));
    if (!stats.yellow_per_match) {
        const ycm2 = text.match(/(?:Yellow Cards? per Match|Tarjetas amarillas por partido)\s*(\d+[\.,]\d+)/i);
        if (ycm2) stats.yellow_per_match = parseFloat(ycm2[1].replace(',','.'));
    }
    const rc = text.match(/(\d+[\.,]\d+)\s*(?:Red Cards? per Match|Tarjetas rojas por partido)/i);
    if (rc) stats.red_per_match = parseFloat(rc[1].replace(',','.'));
    const m = text.match(/(\d+)\s*(?:Matches|Partidos)/i);
    if (m) stats.matches = parseInt(m[1]);
    return JSON.stringify(stats);
})()
"""

results = {}
for name, url in refs:
    print(f'\n=== {name} ===')
    resp = requests.put('http://localhost:9222/json/new?' + url, timeout=10)
    tab = resp.json()
    time.sleep(8)
    tabs = requests.get('http://localhost:9222/json', timeout=5).json()
    for t in tabs:
        if t.get('id') == tab.get('id'):
            tab = t
            break
    cdp = CDPClient(tab['webSocketDebuggerUrl'])
    cdp.connect()
    time.sleep(4)

    result = cdp.evaluate(JS_EXTRACT)
    stats = json.loads(result) if result else {}
    print(f'  Yellow/match: {stats.get("yellow_per_match", "?")}')
    print(f'  Red/match: {stats.get("red_per_match", "?")}')
    print(f'  Matches: {stats.get("matches", "?")}')
    results[name] = stats

    cdp.disconnect()
    requests.put(f'http://localhost:9222/json/close/{tab["id"]}', timeout=5)
    time.sleep(1)

# Update Champions JSON
print('\n=== Updating Champions League JSON ===')
with open('referees/champions-league_cuartos-de-final_2026-04-12.json') as f:
    cl = json.load(f)

for entry in cl['referees']:
    name = entry['referee']
    if name in results and results[name].get('yellow_per_match'):
        ypm = results[name]['yellow_per_match']
        entry['stats'] = {
            'yellow_cards_per_match': ypm,
            'red_cards_per_match': results[name].get('red_per_match', 0),
            'matches_season': results[name].get('matches', 0),
            'source': 'valuestats.com',
        }
        if ypm >= 4.5:
            entry['verdict'] = 'ALTO'
        elif ypm >= 3.5:
            entry['verdict'] = 'MEDIO'
        else:
            entry['verdict'] = 'BAJO'
        print(f'  {name}: {ypm} TA/P -> {entry["verdict"]}')

with open('referees/champions-league_cuartos-de-final_2026-04-12.json', 'w') as f:
    json.dump(cl, f, indent=2, ensure_ascii=False)

# Final
print('\n=== CL Cuartos Vuelta ===')
for e in cl['referees']:
    if any(q in e['match'] for q in ['Barcelona vs Atl', 'Liverpool', 'Arsenal', 'Bayern']):
        ypm = f"{e['stats']['yellow_cards_per_match']:.1f}" if e.get('stats') and e['stats'].get('yellow_cards_per_match') else '?.?'
        print(f'  {e["match"]:45s} | {e["referee"]:25s} | {ypm:>5} TA/P | {e["verdict"]}')
