#!/usr/bin/env python3
"""
Compare scraped markets vs actual bet365 markets visible in screenshots.
Generate HTML report showing gaps.
"""
import json

# ============================================================
# ACTUAL MARKETS FROM BET365 SCREENSHOTS (Castellón vs Cádiz)
# ============================================================

ACTUAL_MARKETS = {
    "Córners (I5)": [
        "Córners",
        "Córners - Adicionales",
        "Córners - 2 opciones",
        "Córners - Total",
        "1ª mitad - Córners",
        "Hándicap - Córners",
        "Minuto del primer córner",
        "Córners del equipo",
        "Corners - Primero en conseguir",
        "Primer córner",
        "Último córner",
        "Multicórner",
        "Hándicap asiático - Córners",
        "Primeros 10 minutos (00:00 – 09:59)",
        "Asiático - Total de córners",
        "1ª mitad - Córners asiáticos",
    ],
    "Tarjetas (I4)": [
        "Número de tarjetas en el partido",
        "Ambos equipos recibirán tarjetas",
        "Tarjetas con hándicap",
        "Tarjetas con hándicap - Otras opciones",
        "Primera tarjeta recibida",
        "Minuto de la primera tarjeta",
        "Tarjetas del equipo",
        "Hándicap asiático - Total de tarjetas",
        "Hándicap asiático - Tarjetas",
    ],
    "Goles (I6)": [
        "Goles - Más/Menos de",
        "Total de goles - Otras opciones",
        "Resultado/Total de goles",
        "Total de goles/ambos equipos anotarán",
        "Número total exacto de goles",
        "Número de goles en el partido",
        "Ambos equipos anotarán",
        "Equipos que anotarán",
        "1ª mitad - Ambos equipos anotarán",
        "2ª mitad - Ambos equipos anotarán",
        "Ambos equipos anotarán en la 1ª mitad - 2ª mitad",
        "1ª mitad - Goles",
        "1ª mitad - Número exacto de goles",
        "Total de los minutos de los goles",
        "Primer equipo que anotará",
        "Gol temprano",
        "Gol tardío",
        "Momento del 1° gol",
        "2ª mitad - Goles",
        "2ª mitad - Número total exacto de goles",
        "Mitad con más goles",
        "Equipo local - Mitad con mayor nº de goles",
        "Equipo visitante - Mitad con mayor nº de goles",
        "Portería a 0",
        "Equipo - Total de goles",
        "Equipo local - Número exacto de goles",
        "Equipo visitante - Número exacto de goles",
        "Margen de victoria",
        "Encuentro - Goles - Intervalo",
        "Equipo - Goles - Intervalo",
        "Minuto del 1° gol del equipo",
        "Goles - Nº par o impar",
        "Equipo local - Goles - Impar/par",
        "Equipo visitante - Goles - Impar/par",
        "1ª mitad - Goles - Impar/Par",
        "1ª mitad - Goles - Intervalo",
        "2ª mitad - Goles - Intervalo",
        "Resultado/Goles - Intervalo",
        "Doble oportunidad/Goles - Intervalo",
        "Último equipo en anotar",
        "Primeros 10 minutos (00:00 – 09:59)",
    ],
}

# Load scraped data
data = json.load(open("odds/match_193003587.json"))
scraped_names = set(data["markets"].keys())

# Normalize for comparison
def norm(s):
    return s.lower().strip().replace("  ", " ").replace("°", "°").replace("–", "-").replace("—", "-")

scraped_norm = {norm(n): n for n in scraped_names}

# Build comparison
results = {}
total_actual = 0
total_found = 0
total_missing = 0

for tab, markets in ACTUAL_MARKETS.items():
    found = []
    missing = []
    for m in markets:
        mn = norm(m)
        # Try exact match first
        matched = None
        if mn in scraped_norm:
            matched = scraped_norm[mn]
        else:
            # Try partial match
            for sn, orig in scraped_norm.items():
                if mn in sn or sn in mn:
                    matched = orig
                    break
                # Try without accents/special chars
                mn_simple = mn.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("ñ","n")
                sn_simple = sn.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("ñ","n")
                if mn_simple in sn_simple or sn_simple in mn_simple:
                    matched = orig
                    break

        if matched:
            sel_count = len(data["markets"][matched].get("selections", []))
            found.append((m, matched, sel_count))
            total_found += 1
        else:
            missing.append(m)
            total_missing += 1
        total_actual += 1

    results[tab] = {"found": found, "missing": missing}

# Also check: markets we scraped that aren't in any tab shown
tabs_not_shown = [
    "Populares (I1)", "Crear apuesta (I99/I2)",
    "1ª/2ª mitad (I7)", "Especiales (I9)", "Asiáticos (I3)",
    "Jugadores", "Minutos"
]

# Generate HTML
html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Gap Analysis — Mercados faltantes</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #1a1a2e; color: #e0e0e0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; }
h1 { color: #f0c040; margin-bottom: 5px; }
.subtitle { color: #888; margin-bottom: 20px; }
.summary {
    background: #16213e; border: 1px solid #333; border-radius: 12px;
    padding: 20px; margin-bottom: 25px; display: flex; gap: 30px;
}
.stat { text-align: center; }
.stat-num { font-size: 36px; font-weight: bold; }
.stat-label { font-size: 12px; color: #888; margin-top: 4px; }
.green { color: #4caf50; }
.red { color: #ff5252; }
.yellow { color: #f0c040; }
.tab-section {
    background: #16213e; border: 1px solid #333; border-radius: 12px;
    padding: 20px; margin-bottom: 20px;
}
.tab-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #333;
}
.tab-title { font-size: 20px; font-weight: bold; color: #60a0ff; }
.badge {
    padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: bold;
}
.badge-ok { background: #1b5e20; color: #4caf50; }
.badge-partial { background: #4a3000; color: #f0c040; }
.badge-bad { background: #4a0000; color: #ff5252; }
.market-row {
    display: flex; align-items: center; padding: 8px 12px;
    border-radius: 6px; margin-bottom: 4px;
}
.market-found { background: #0d2818; }
.market-missing { background: #2a0a0a; }
.market-name { flex: 1; }
.market-status { width: 30px; text-align: center; font-size: 18px; }
.market-detail { color: #888; font-size: 12px; margin-left: 10px; }
.scraped-match { color: #666; font-size: 11px; }
.diagnosis {
    background: #1a1a3e; border: 2px solid #f0c040; border-radius: 12px;
    padding: 20px; margin-top: 25px;
}
.diagnosis h2 { color: #f0c040; margin-bottom: 15px; }
.diagnosis li { margin-bottom: 8px; line-height: 1.5; }
.diagnosis code { background: #333; padding: 2px 6px; border-radius: 3px; color: #4caf50; }
</style>
</head>
<body>

<h1>🔍 Gap Analysis — Mercados faltantes</h1>
<p class="subtitle">CD Castellón vs Cádiz · Comparación capturas bet365 vs datos scrapeados</p>

<div class="summary">
    <div class="stat">
        <div class="stat-num yellow">""" + str(total_actual) + """</div>
        <div class="stat-label">Mercados en capturas<br>(3 tabs: Córners, Tarjetas, Goles)</div>
    </div>
    <div class="stat">
        <div class="stat-num green">""" + str(total_found) + """</div>
        <div class="stat-label">Encontrados<br>en scraping</div>
    </div>
    <div class="stat">
        <div class="stat-num red">""" + str(total_missing) + """</div>
        <div class="stat-label">FALTAN<br>en scraping</div>
    </div>
    <div class="stat">
        <div class="stat-num yellow">52</div>
        <div class="stat-label">Total scrapeados<br>(todos los tabs)</div>
    </div>
    <div class="stat">
        <div class="stat-num">""" + f"{round(total_found/total_actual*100)}%" + """</div>
        <div class="stat-label">Cobertura<br>(3 tabs vistos)</div>
    </div>
</div>
"""

for tab, data_tab in results.items():
    found = data_tab["found"]
    missing = data_tab["missing"]
    total = len(found) + len(missing)
    pct = round(len(found)/total*100) if total else 0

    if pct >= 90:
        badge_class = "badge-ok"
        badge_text = f"{pct}% ✓"
    elif pct >= 50:
        badge_class = "badge-partial"
        badge_text = f"{pct}% parcial"
    else:
        badge_class = "badge-bad"
        badge_text = f"{pct}% ✗"

    html += f"""
<div class="tab-section">
    <div class="tab-header">
        <span class="tab-title">{tab}</span>
        <span>
            <span class="green">{len(found)}</span> / {total} mercados
            <span class="badge {badge_class}">{badge_text}</span>
        </span>
    </div>
"""

    # Found markets
    for actual_name, scraped_name, sel_count in found:
        match_note = f" → scrapeado como: {scraped_name}" if actual_name != scraped_name else ""
        html += f"""    <div class="market-row market-found">
        <span class="market-status">✅</span>
        <span class="market-name">{actual_name} <span class="market-detail">{sel_count} sel{match_note}</span></span>
    </div>
"""

    # Missing markets
    for m in missing:
        html += f"""    <div class="market-row market-missing">
        <span class="market-status">❌</span>
        <span class="market-name">{m}</span>
    </div>
"""

    html += "</div>\n"

# Diagnosis section
html += """
<div class="diagnosis">
    <h2>🔧 Diagnóstico y solución</h2>
    <p style="margin-bottom: 15px;">El problema principal: <strong>cada tab I tiene múltiples mercados (FixtureStems o MGs) pero el scraper solo captura algunos.</strong></p>

    <h3 style="color: #60a0ff; margin: 15px 0 10px;">Causa raíz por tab:</h3>
    <ul style="padding-left: 20px;">
        <li><strong style="color: #ff5252;">Córners (I5)</strong> — Solo 6/16 mercados. La mayoría de mercados del tab (Hándicap-Córners, Primer/Último córner, Multicórner, Asiáticos) son FixtureStems separados que NO se están capturando. Probablemente tienen diferente FI o están en sub-containers.</li>
        <li><strong style="color: #ff5252;">Tarjetas (I4)</strong> — Solo 2/9 mercados. Muy pobre. Tarjetas con hándicap, Primera tarjeta recibida, Minuto de tarjeta, Tarjetas del equipo, Asiáticos de tarjetas — todos faltan.</li>
        <li><strong style="color: #f0c040;">Goles (I6)</strong> — Muchos mercados de Goles están en I99/I1 pero faltan ~15+ mercados propios de I6 como: Número exacto, Equipos que anotarán, Gol temprano/tardío, Portería a 0, Par/Impar, etc.</li>
    </ul>

    <h3 style="color: #4caf50; margin: 15px 0 10px;">Plan de solución:</h3>
    <ol style="padding-left: 20px;">
        <li><strong>Problema 1: FixtureStems con sub-FIs</strong> — Dentro de un mismo tab I, bet365 puede cargar múltiples FixtureStems con diferentes <code>FI</code> values. Nuestro JS filtra por el FI principal del match, pero los mercados secundarios (Hándicap córners, Primer córner, etc.) pueden tener sus propios FIs internos o estar bajo un container diferente.</li>
        <li><strong>Problema 2: Lazy loading</strong> — Algunos mercados solo cargan sus datos cuando el accordion se expande (click en la fila). El scraper captura lo que está en memoria al momento del scrape, pero los mercados colapsados pueden no tener datos cargados.</li>
        <li><strong>Solución: Capturar TODOS los FixtureStems</strong> — En vez de filtrar estrictamente por FI, capturar todos los FS que estén presentes en la página y agruparlos. Los mercados del tab actual deberían estar todos en memoria aunque el accordion esté cerrado.</li>
        <li><strong>Solución alternativa: Expandir accordions</strong> — Si los datos no están en memoria, simular click en cada accordion antes de extraer. Pero esto es arriesgado en la SPA.</li>
    </ol>
</div>

</body>
</html>
"""

with open("/Users/beto/Desktop/gap-analysis.html", "w") as f:
    f.write(html)

print(f"Total en capturas: {total_actual}")
print(f"Encontrados: {total_found}")
print(f"FALTAN: {total_missing}")
print(f"Cobertura: {round(total_found/total_actual*100)}%")
print()
for tab, d in results.items():
    print(f"{tab}: {len(d['found'])}/{len(d['found'])+len(d['missing'])}")
    if d['missing']:
        for m in d['missing']:
            print(f"  ❌ {m}")
