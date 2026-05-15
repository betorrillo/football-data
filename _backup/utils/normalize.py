"""
Normalizes raw bet365 scraper JSON into a clean, structured format.

Maps bet365's Spanish market names and filter combinations into
standardized English keys with proper over/under line pairing.
"""

import re
import json


def normalize_match(raw):
    """Transform raw scraper JSON into normalized format."""
    home = raw.get('home', '')
    away = raw.get('away', '')

    output = {
        'match': raw.get('match', ''),
        'home': home,
        'away': away,
        'competition': raw.get('competition', ''),
        'date': raw.get('datetime', ''),
        'scraped_at': raw.get('scraped_at', ''),
        'url': raw.get('url', ''),
        'isLive': raw.get('isLive', False),
        'source': 'bet365',
        'markets': {},
    }

    raw_markets = raw.get('markets', {})

    # --- Over/Under Goals ---
    if 'Total de goles' in raw_markets:
        output['markets']['over_under_goals'] = _normalize_ou_market(
            raw_markets['Total de goles'], home, away, 'goles'
        )

    # --- BTTS ---
    if 'Ambos equipos anotarán' in raw_markets:
        output['markets']['btts'] = _normalize_btts(raw_markets['Ambos equipos anotarán'])

    # --- Corners ---
    if 'Córners' in raw_markets:
        output['markets']['corners'] = _normalize_ou_market(
            raw_markets['Córners'], home, away, 'córners'
        )

    # --- Cards ---
    if 'Tarjetas' in raw_markets:
        output['markets']['cards'] = _normalize_ou_market(
            raw_markets['Tarjetas'], home, away, 'tarjetas'
        )

    # --- Goals Interval ---
    if 'Goles - Intervalo' in raw_markets:
        output['markets']['goals_interval'] = _normalize_interval(
            raw_markets['Goles - Intervalo'], home, away
        )

    # --- Shots on target ---
    if 'Total - Remates a puerta' in raw_markets:
        output['markets']['shots_on_target'] = _normalize_ou_market(
            raw_markets['Total - Remates a puerta'], home, away, 'remates'
        )

    # --- Shots ---
    if 'Total - Remates' in raw_markets:
        output['markets']['shots'] = _normalize_ou_market(
            raw_markets['Total - Remates'], home, away, 'remates'
        )

    # --- Goalkeeper saves ---
    if 'Paradas del portero' in raw_markets:
        output['markets']['goalkeeper_saves'] = _normalize_simple_list(
            raw_markets['Paradas del portero']
        )

    # --- Both teams cards ---
    if 'Ambos equipos recibirán tarjetas' in raw_markets:
        output['markets']['btts_cards'] = _normalize_btts(
            raw_markets['Ambos equipos recibirán tarjetas']
        )

    # --- Team most ---
    if 'Equipo - Mayor número' in raw_markets:
        output['markets']['team_most'] = _normalize_simple_list(
            raw_markets['Equipo - Mayor número']
        )

    # --- Double chance ---
    if 'Doble oportunidad' in raw_markets:
        output['markets']['double_chance'] = _normalize_double_chance(
            raw_markets['Doble oportunidad']
        )

    # --- Result ---
    if 'Resultado' in raw_markets:
        output['markets']['result'] = _normalize_result(
            raw_markets['Resultado']
        )

    # --- HT/FT ---
    if 'Descanso/Resultado final' in raw_markets:
        output['markets']['ht_ft'] = _normalize_simple_list(
            raw_markets['Descanso/Resultado final']
        )

    # --- Correct score ---
    if 'Marcador' in raw_markets:
        output['markets']['correct_score'] = _normalize_simple_list(
            raw_markets['Marcador']
        )

    # --- Half with most goals ---
    if 'Mitad con el mayor número de goles' in raw_markets:
        output['markets']['half_most_goals'] = _normalize_simple_list(
            raw_markets['Mitad con el mayor número de goles']
        )

    # --- Winning margin ---
    if 'Margen de victoria' in raw_markets:
        output['markets']['winning_margin'] = _normalize_simple_list(
            raw_markets['Margen de victoria']
        )

    # --- Any remaining markets (live-specific, etc.) ---
    handled = {
        'Total de goles', 'Ambos equipos anotarán', 'Córners', 'Tarjetas',
        'Goles - Intervalo', 'Total - Remates a puerta', 'Total - Remates',
        'Paradas del portero', 'Ambos equipos recibirán tarjetas',
        'Equipo - Mayor número', 'Doble oportunidad', 'Resultado',
        'Descanso/Resultado final', 'Marcador',
        'Mitad con el mayor número de goles', 'Margen de victoria',
    }
    for mname, mdata in raw_markets.items():
        if mname not in handled:
            key = _slugify(mname)
            output['markets'][key] = _normalize_simple_list(mdata)

    return output


# ===================================================================
# Filter key mapping
# ===================================================================

def _filter_key(filter_name, home, away):
    """Map filter combo "Team / Period" to structured key."""
    parts = filter_name.split(' / ')
    if len(parts) == 2:
        team_part, period_part = parts
    elif filter_name == 'default':
        return 'total'
    else:
        return _slugify(filter_name)

    # Team mapping
    team_key = 'total'
    if team_part.lower() in ('ambos equipos', 'ambos'):
        team_key = 'total'
    elif home and team_part.lower() == home.lower():
        team_key = 'home_team'
    elif away and team_part.lower() == away.lower():
        team_key = 'away_team'
    else:
        team_key = _slugify(team_part)

    # Period mapping
    period_key = ''
    p = period_part.lower().strip()
    if p in ('encuentro', 'match', ''):
        period_key = ''  # no suffix for full match
    elif p == '1ª mitad':
        period_key = '_first_half'
    elif p == '2ª mitad':
        period_key = '_second_half'
    elif 'primeros' in p:
        m = re.search(r'(\d+)', p)
        mins = m.group(1) if m else '10'
        period_key = f'_first_{mins}min'
    else:
        period_key = '_' + _slugify(period_part)

    return team_key + period_key


# ===================================================================
# Market normalizers
# ===================================================================

def _normalize_ou_market(market_data, home, away, unit_word):
    """Normalize over/under markets (goals, corners, cards, shots)."""
    result = {}

    for filter_name, entries in market_data.items():
        key = _filter_key(filter_name, home, away)

        lines = {}
        for entry in entries:
            sel = entry.get('selection', '')
            col = entry.get('column', '')
            odds = entry.get('odds', 0)

            # Extract the line number from selection: "N goles", "N córners", etc.
            m = re.match(r'(\d+)', sel)
            if not m:
                # No line number in selection - try positional inference
                continue

            n = int(m.group(1))
            col_lower = col.lower().strip()

            if 'más' in col_lower or 'over' in col_lower:
                # "Más de N" = Over (N+0.5) in standard notation
                line = f"{n}.5"
                lines.setdefault(line, {})['over'] = odds
            elif 'menos' in col_lower or 'under' in col_lower:
                # "Menos de N" = Under (N-0.5) in standard notation
                # Which is the same as Under (N-1)+0.5
                line = f"{n - 1}.5" if n > 0 else "0.5"
                lines.setdefault(line, {})['under'] = odds
            elif 'exacta' in col_lower or 'exact' in col_lower:
                line = str(n)
                lines.setdefault(f"{n}_exact", {})['exact'] = odds

        # Only include lines that have at least over or under
        clean_lines = {}
        for line, vals in sorted(lines.items(), key=lambda x: _sort_key(x[0])):
            if '_exact' in line:
                continue  # Skip exact for now, or include separately
            if vals:
                clean_lines[line] = vals

        # Add exact values separately
        exacts = {}
        for line, vals in lines.items():
            if '_exact' in line and 'exact' in vals:
                num = line.replace('_exact', '')
                exacts[num] = vals['exact']
        if exacts:
            clean_lines['_exact'] = exacts

        if clean_lines:
            result[key] = clean_lines

    return result


def _normalize_btts(market_data):
    """Normalize BTTS (both teams to score) market."""
    result = {}
    for filter_name, entries in market_data.items():
        for entry in entries:
            sel = entry.get('selection', '').lower()
            col = entry.get('column', '').lower()
            odds = entry.get('odds', 0)

            period = sel if sel in ('encuentro', '1ª mitad', '2ª mitad') else ''
            side = ''
            if 'sí' in col or 'si' in col or 'yes' in col:
                side = 'yes'
            elif 'no' in col:
                side = 'no'
            else:
                # Try selection
                if 'sí' in sel or 'yes' in sel:
                    side = 'yes'
                elif 'no' in sel:
                    side = 'no'

            if side:
                key = period if period else 'match'
                result.setdefault(_slugify(key) if key != 'match' else 'match', {})[side] = odds

    # Flatten if only one period
    if len(result) == 1 and 'match' in result:
        return result['match']
    return result


def _normalize_double_chance(market_data):
    """Normalize double chance market."""
    result = {}
    for filter_name, entries in market_data.items():
        for entry in entries:
            sel = entry.get('selection', '')
            odds = entry.get('odds', 0)
            key = _slugify(sel)
            result[key] = odds
    return result


def _normalize_result(market_data):
    """Normalize result/1x2 market."""
    result = {}
    for filter_name, entries in market_data.items():
        for entry in entries:
            sel = entry.get('selection', '')
            col = entry.get('column', '')
            odds = entry.get('odds', 0)

            period = _slugify(sel) if sel else 'match'
            side = _slugify(col) if col else sel

            result.setdefault(period, {})[side] = odds

    return result


def _normalize_interval(market_data, home, away):
    """Normalize goals interval market."""
    result = {}
    for filter_name, entries in market_data.items():
        key = _filter_key(filter_name, home, away)
        intervals = {}
        for entry in entries:
            sel = entry.get('selection', '')
            col = entry.get('column', '')
            odds = entry.get('odds', 0)
            interval_key = _slugify(sel) if sel else str(odds)
            intervals.setdefault(interval_key, {})[_slugify(col) if col else 'odds'] = odds
        if intervals:
            result[key] = intervals
    return result


def _normalize_simple_list(market_data):
    """Generic normalizer: just clean up the entries."""
    result = {}
    for filter_name, entries in market_data.items():
        items = {}
        for entry in entries:
            sel = entry.get('selection', '')
            col = entry.get('column', '')
            odds = entry.get('odds', 0)

            if sel and col:
                key = f"{sel} ({col})" if col else sel
            elif sel:
                key = sel
            elif col:
                key = col
            else:
                key = str(odds)

            # Handle duplicates by appending
            if key in items:
                if isinstance(items[key], list):
                    items[key].append(odds)
                else:
                    items[key] = [items[key], odds]
            else:
                items[key] = odds

        fkey = _filter_key(filter_name, '', '') if filter_name != 'default' else 'default'
        if items:
            result[fkey] = items

    # Flatten if only one filter
    if len(result) == 1:
        return list(result.values())[0]
    return result


# ===================================================================
# Helpers
# ===================================================================

def _slugify(text):
    """Convert text to a clean key."""
    text = text.lower().strip()
    # Common Spanish → English
    replacements = {
        'encuentro': 'match', '1ª mitad': 'first_half', '2ª mitad': 'second_half',
        'empate': 'draw', 'córners': 'corners', 'tarjetas': 'cards',
        'goles': 'goals', 'más de': 'over', 'menos de': 'under',
        'exactamente': 'exact', 'sí': 'yes',
    }
    for es, en in replacements.items():
        text = text.replace(es, en)

    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


def _sort_key(line_str):
    """Sort key for line strings like '0.5', '1.5', '10.5'."""
    try:
        return float(line_str)
    except ValueError:
        return 999


def make_filename(raw):
    """Generate normalized filename: {comp}_{home}-vs-{away}_{date}.json"""
    comp = raw.get('competition', 'unknown')
    home = raw.get('home', 'unknown')
    away = raw.get('away', 'unknown')
    dt = raw.get('datetime', '')

    # Clean competition
    comp = re.sub(r'España\s*-\s*', '', comp)
    comp = re.sub(r'[^a-zA-ZÀ-ÿ0-9 ]', '', comp).strip()
    comp = comp.lower().replace(' ', '-') or 'unknown'

    # Clean team names
    home = re.sub(r'[^a-zA-ZÀ-ÿ0-9 ]', '', home).strip().lower().replace(' ', '-') or 'unknown'
    away = re.sub(r'[^a-zA-ZÀ-ÿ0-9 ]', '', away).strip().lower().replace(' ', '-') or 'unknown'

    # Parse date
    date_str = ''
    if dt:
        m = re.match(r'(\d+)\s+(\w+)\s+(\d+:\d+)', dt)
        if m:
            months = {'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04', 'may': '05',
                       'jun': '06', 'jul': '07', 'ago': '08', 'sep': '09', 'oct': '10',
                       'nov': '11', 'dic': '12'}
            day = m.group(1).zfill(2)
            month = months.get(m.group(2)[:3].lower(), '00')
            date_str = f"2026-{month}-{day}"

    if not date_str:
        from datetime import datetime
        date_str = datetime.now().strftime('%Y-%m-%d')

    is_live = raw.get('isLive', False)
    suffix = '_LIVE' if is_live else ''

    return f"{comp}_{home}-vs-{away}_{date_str}{suffix}.json"


# ===================================================================
# CLI for standalone use
# ===================================================================

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 normalize.py <raw_file.json> [output_file.json]")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        raw = json.load(f)

    normalized = normalize_match(raw)
    out_file = sys.argv[2] if len(sys.argv) > 2 else None

    if out_file:
        with open(out_file, 'w') as f:
            json.dump(normalized, f, indent=2, ensure_ascii=False)
        print(f"Saved to {out_file}")
    else:
        print(json.dumps(normalized, indent=2, ensure_ascii=False))
