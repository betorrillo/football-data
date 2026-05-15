#!/usr/bin/env python3
"""
Fast scrape of all open bet365 tabs.
Phase 1: Open all groups at once, extract default view (5s)
Phase 2: Iterate dropdown combos only for groups that have them (~2min)
NO navigation, NO tab switching — reads what's on screen.
"""
import sys, json, time, os, re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from cdp_client import CDPClient
import requests

CDP_PORT = 9222

JS_MATCH_INFO = r"""(() => {
    let h='',a='',comp='',dt='';
    const t=document.querySelectorAll('.sph-FixturePodHeader_TeamName');
    if(t.length>=2){h=t[0].textContent.trim();a=t[1].textContent.trim();}
    const c=document.querySelector('.sph-FixturePodHeader_Competition');
    if(c)comp=c.textContent.trim();
    const d=document.querySelector('.sph-ExtraData_TimeStamp');
    if(d)dt=d.textContent.trim();
    return JSON.stringify({home:h,away:a,match:h+' vs '+a,competition:comp,datetime:dt,url:location.href,isLive:location.hash.includes('/IP/')});
})()"""

JS_OPEN_ALL = """(() => {
    let n=0;
    document.querySelectorAll('.gl-MarketGroupPod,[class*="MarketGroupPod"]').forEach(p=>{
        const b=p.querySelector('.gl-MarketGroupButton,[class*="MarketGroupButton"]');
        if(b&&!b.className.includes('Open')){b.click();n++;}
    });
    return n;
})()"""

JS_CLOSE_ALL = """(() => {
    document.querySelectorAll('.gl-MarketGroupPod,[class*="MarketGroupPod"]').forEach(p=>{
        const b=p.querySelector('.gl-MarketGroupButton,[class*="MarketGroupButton"]');
        if(b&&b.className.includes('Open'))b.click();
    });
})()"""

JS_SHOW_MORE = """(() => {
    let c=0;
    document.querySelectorAll('[class*="ShowMore"]').forEach(el=>{
        if(/ver más|show more/i.test(el.textContent.trim())){try{el.click();c++;}catch(e){}}
    });
    return c;
})()"""

JS_EXTRACT_ALL = r"""(() => {
    const rx=/^\d{1,3}\.\d{2}$/;
    const results=[];
    document.querySelectorAll('.gl-MarketGroupPod,[class*="MarketGroupPod"]').forEach(pod=>{
        const btn=pod.querySelector('.gl-MarketGroupButton,[class*="MarketGroupButton"]');
        if(!btn||!btn.className.includes('Open'))return;
        const ne=btn.querySelector('.gl-MarketGroupButton_Text,[class*="MarketGroupButton_Text"],[class*="HeaderText"]');
        const gn=ne?ne.textContent.trim():btn.textContent.trim();
        const odds=[],seen=new Set();
        const w=document.createTreeWalker(pod,NodeFilter.SHOW_TEXT,null);
        let nd;
        while(nd=w.nextNode()){
            const t=nd.textContent.trim();
            if(!rx.test(t))continue;
            let ctx='',p=nd.parentElement;
            for(let i=0;i<6&&p&&p!==pod;i++){const pt=p.textContent.trim();if(pt.length>t.length+1&&pt.length<200){ctx=pt;break;}p=p.parentElement;}
            const k=ctx+'|'+t;
            if(seen.has(k))continue;seen.add(k);
            let sel='',col='';
            const pe=nd.parentElement;
            if(pe){
                const br=pe.closest('[class*="BetBuilderParticipant"]');
                if(br){const l=br.querySelector('[class*="ParticipantLabel_Name"],[class*="Label_Name"]');if(l)sel=l.textContent.trim();const m=br.closest('.gl-Market_General,[class*="gl-Market"]');if(m){const ch=m.querySelector('[class*="StickyMarketColumnHeader_Label"],[class*="ColumnHeader"]');if(ch)col=ch.textContent.trim();}}
                if(!sel){const gr=pe.closest('[class*="gl-Participant"]');if(gr){const n2=gr.querySelector('[class*="Name"]');if(n2)sel=n2.textContent.trim();}}
                if(!sel)sel=ctx.replace(t,'').trim().substring(0,80);
            }
            odds.push({sel,col,odds:parseFloat(t)});
        }
        if(odds.length>0)results.push({name:gn.substring(0,80),odds});
    });
    return JSON.stringify(results);
})()"""

JS_GET_DROPDOWNS = """(() => {
    const r={team:null,period:null};
    document.querySelectorAll('[class*="bbl-DropDown-left"]').forEach(el=>{
        const b=el.getBoundingClientRect();
        if(b.width>10&&b.height>5&&!r.team){
            el.scrollIntoView({behavior:'instant',block:'center'});
            const b2=el.getBoundingClientRect();
            r.team={text:el.textContent.trim(),x:Math.round(b2.x+b2.width/2),y:Math.round(b2.y+b2.height/2)};
        }
    });
    document.querySelectorAll('[class*="bbl-DropDown-right"]').forEach(el=>{
        const b=el.getBoundingClientRect();
        if(b.width>10&&b.height>5&&!r.period){
            const b2=el.getBoundingClientRect();
            r.period={text:el.textContent.trim(),x:Math.round(b2.x+b2.width/2),y:Math.round(b2.y+b2.height/2)};
        }
    });
    return JSON.stringify(r);
})()"""

JS_EXTRACT_OPEN_GROUP = r"""(() => {
    const rx=/^\d{1,3}\.\d{2}$/;
    let result=[];
    document.querySelectorAll('.gl-MarketGroupPod,[class*="MarketGroupPod"]').forEach(pod=>{
        const btn=pod.querySelector('.gl-MarketGroupButton,[class*="MarketGroupButton"]');
        if(!btn||!btn.className.includes('Open'))return;
        const odds=[],seen=new Set();
        const w=document.createTreeWalker(pod,NodeFilter.SHOW_TEXT,null);
        let nd;
        while(nd=w.nextNode()){
            const t=nd.textContent.trim();
            if(!rx.test(t))continue;
            let ctx='',p=nd.parentElement;
            for(let i=0;i<6&&p&&p!==pod;i++){const pt=p.textContent.trim();if(pt.length>t.length+1&&pt.length<200){ctx=pt;break;}p=p.parentElement;}
            const k=ctx+'|'+t;
            if(seen.has(k))continue;seen.add(k);
            let sel='';
            const pe=nd.parentElement;
            if(pe){const br=pe.closest('[class*="BetBuilderParticipant"]');if(br){const l=br.querySelector('[class*="ParticipantLabel_Name"],[class*="Label_Name"]');if(l)sel=l.textContent.trim();}if(!sel){const gr=pe.closest('[class*="gl-Participant"]');if(gr){const n2=gr.querySelector('[class*="Name"]');if(n2)sel=n2.textContent.trim();}}if(!sel)sel=ctx.replace(t,'').trim().substring(0,80);}
            odds.push({sel,odds:parseFloat(t)});
        }
        result=odds;
    });
    return JSON.stringify(result);
})()"""


def js_click_at(x, y):
    return f'(()=>{{const el=document.elementFromPoint({x},{y});if(el){{el.click();return el.textContent.trim().substring(0,40);}}return"miss";}})()'

def js_read_dropdown(side):
    cls = 'LeftCont' if side == 'left' else 'RightCon'
    return f"""(()=>{{const o=[],s=new Set();document.querySelectorAll('[class*="bbl-DropDownSwitcherMarketGroup_{cls}"] div,[class*="bbl-DropDownSwitcherMarketGroup_{cls}"] span').forEach(el=>{{const t=el.textContent.trim();if(!t||t.length<2||t.length>30||el.children.length>2||s.has(t))return;const r=el.getBoundingClientRect();if(r.width<15||r.height<8||r.top<=0)return;s.add(t);o.push({{text:t,x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}});}});return JSON.stringify(o);}})()"""

def js_open_group(name):
    e = name.replace('"','\\"').replace("'","\\'")
    return f"""(()=>{{for(const p of document.querySelectorAll('.gl-MarketGroupPod,[class*="MarketGroupPod"]')){{const b=p.querySelector('.gl-MarketGroupButton,[class*="MarketGroupButton"]');if(!b)continue;const t=b.querySelector('.gl-MarketGroupButton_Text,[class*="MarketGroupButton_Text"],[class*="HeaderText"]');const n=t?t.textContent.trim():b.textContent.trim();if(n==="{e}"||n.startsWith("{e}")){{if(!b.className.includes('Open'))b.click();p.scrollIntoView({{behavior:'instant',block:'start'}});return'ok';}}}}return'miss';}})()"""

def js_close_group(name):
    e = name.replace('"','\\"').replace("'","\\'")
    return f"""(()=>{{for(const p of document.querySelectorAll('.gl-MarketGroupPod,[class*="MarketGroupPod"]')){{const b=p.querySelector('.gl-MarketGroupButton,[class*="MarketGroupButton"]');if(!b)continue;const t=b.querySelector('.gl-MarketGroupButton_Text,[class*="MarketGroupButton_Text"],[class*="HeaderText"]');const n=t?t.textContent.trim():b.textContent.trim();if(n==="{e}"||n.startsWith("{e}")){{if(b.className.includes('Open'))b.click();return'ok';}}}}return'miss';}})()"""


def open_dropdown_read(cdp, trigger, side):
    cdp.evaluate(js_click_at(trigger['x'], trigger['y']))
    time.sleep(0.5)
    raw = cdp.evaluate(js_read_dropdown(side))
    opts = json.loads(raw) if raw else []
    cdp.evaluate('document.body.click()')
    time.sleep(0.3)
    return opts


def select_filter(cdp, trigger, option_text, side):
    cdp.evaluate(js_click_at(trigger['x'], trigger['y']))
    time.sleep(0.4)
    raw = cdp.evaluate(js_read_dropdown(side))
    for opt in json.loads(raw) if raw else []:
        if opt['text'] == option_text:
            cdp.evaluate(js_click_at(opt['x'], opt['y']))
            time.sleep(0.6)
            return True
    cdp.evaluate('document.body.click()')
    time.sleep(0.2)
    return False


def scrape_match(cdp):
    raw = cdp.evaluate(JS_MATCH_INFO)
    match_info = json.loads(raw) if raw else {}
    is_live = match_info.get('isLive', False)
    print(f"\n  Match: {match_info.get('match','?')} | {match_info.get('competition','')}")

    # ── Phase 1: Open ALL groups, extract default view ──
    print("  Phase 1: bulk extract...")
    t0 = time.time()
    cdp.evaluate(JS_CLOSE_ALL)
    time.sleep(0.3)
    opened = cdp.evaluate(JS_OPEN_ALL)
    time.sleep(4)
    # Wait for body to grow (data loading into DOM)
    for _ in range(10):
        bl = int(cdp.evaluate("document.body.innerHTML.length") or 0)
        if bl > 200000: break
        time.sleep(0.5)
    cdp.evaluate(JS_SHOW_MORE)
    time.sleep(0.5)
    raw = cdp.evaluate(JS_EXTRACT_ALL)
    phase1 = json.loads(raw) if raw else []
    phase1_total = sum(len(g['odds']) for g in phase1)
    print(f"    {phase1_total} odds from {len(phase1)} groups in {time.time()-t0:.1f}s")
    cdp.evaluate(JS_CLOSE_ALL)
    time.sleep(0.3)

    # Build results - phase 1 data goes under 'default'
    all_results = {}
    group_names = []
    for g in phase1:
        name = re.sub(r'Sustituto\+$', '', g['name']).strip()
        all_results[name] = [{'filter': 'default', 'odds': g['odds']}]
        group_names.append(name)

    if is_live:
        return match_info, all_results

    # ── Phase 2: Dropdown iteration ──
    print("  Phase 2: dropdown combos...")
    t1 = time.time()
    dd_count = 0

    for gname in group_names:
        # Close any open group first, then open this one
        cdp.evaluate(JS_CLOSE_ALL)
        time.sleep(0.2)
        cdp.evaluate(js_open_group(gname))
        time.sleep(1.5)
        cdp.evaluate(JS_SHOW_MORE)
        time.sleep(0.3)

        # Check for dropdowns (scroll into view happens inside JS_GET_DROPDOWNS)
        raw = cdp.evaluate(JS_GET_DROPDOWNS)
        triggers = json.loads(raw) if raw else {}

        if not triggers.get('team') and not triggers.get('period'):
            cdp.evaluate(js_close_group(gname))
            time.sleep(0.15)
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
        print(f"    {gname}: {len(team_opts)}×{len(period_opts)}={combos}")

        # Replace default with all combos
        all_results[gname] = []

        for t_opt in teams:
            for p_opt in periods:
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
                time.sleep(0.2)

                raw = cdp.evaluate(JS_EXTRACT_OPEN_GROUP)
                odds = json.loads(raw) if raw else []
                all_results[gname].append({'filter': label, 'odds': odds})

        cdp.evaluate(js_close_group(gname))
        time.sleep(0.15)

    print(f"    {dd_count} groups with dropdowns in {time.time()-t1:.1f}s")
    return match_info, all_results


def build_output(match_info, all_results):
    output = {
        'match': match_info.get('match',''),
        'home': match_info.get('home',''),
        'away': match_info.get('away',''),
        'competition': match_info.get('competition',''),
        'datetime': match_info.get('datetime',''),
        'url': match_info.get('url',''),
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
                e = {'odds': o.get('odds',0) if isinstance(o,dict) else o}
                if isinstance(o,dict):
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
    home = output.get('home','x').lower().replace(' ','-')
    away = output.get('away','x').lower().replace(' ','-')
    comp = output.get('competition','').lower()
    if 'champions' in comp: cs = 'uefa-champions-league'
    elif 'europa' in comp: cs = 'uefa-europa-league'
    elif 'liga' in comp: cs = 'spain-la-liga'
    elif 'premier' in comp: cs = 'england-premier-league'
    elif 'bundesliga' in comp: cs = 'germany-bundesliga'
    elif 'serie' in comp: cs = 'italy-serie-a'
    elif 'ligue' in comp: cs = 'france-ligue-1'
    else: cs = re.sub(r'[^a-z0-9]+','-',comp).strip('-') or 'unknown'
    dt = output.get('datetime','')
    dm = re.search(r'(\d{1,2})\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)', dt, re.I)
    if dm:
        months = {'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sep':9,'oct':10,'nov':11,'dic':12}
        ds = f"2026-{months.get(dm.group(2).lower(),1):02d}-{int(dm.group(1)):02d}"
    else: ds = datetime.now().strftime('%Y-%m-%d')
    return f"odds/{cs}_{home}-vs-{away}_{ds}.json"


def main():
    tabs = requests.get(f'http://localhost:{CDP_PORT}/json', timeout=5).json()
    bet_tabs = [t for t in tabs if 'bet365' in t.get('url','').lower() and '/AC/B1/' in t.get('url','')]

    if not bet_tabs:
        print("No bet365 tabs found"); sys.exit(1)

    print(f"Found {len(bet_tabs)} bet365 tabs")
    os.makedirs('odds', exist_ok=True)

    for i, tab in enumerate(bet_tabs):
        print(f"\n{'='*60}")
        cdp = CDPClient(tab['webSocketDebuggerUrl'])
        if not cdp.connect():
            print(f"  Tab {i}: FAILED to connect"); continue

        try:
            match_info, results = scrape_match(cdp)
            output = build_output(match_info, results)
            fname = make_filename(output)
            with open(fname, 'w') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"  => {output['match']}: {output['summary']['total_odds']} odds, {output['summary']['total_markets']} markets")
            print(f"  => {fname}")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()
        finally:
            cdp.disconnect()
            time.sleep(1)

    print(f"\n{'='*60}\nDONE\n{'='*60}")


if __name__ == '__main__':
    main()
