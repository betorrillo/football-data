# AUDIT.md — Estado actual del sistema bet365-scraper / value-betting

Fecha de auditoría: 2026-04-26
Rama: `refactor/server-status-v2`
Auditor: refactor agent (lectura sin modificar código)

---

## 0. Resumen ejecutivo (lee esto primero)

El sistema funciona pero arrastra **5 problemas serios que ROMPEN el caso de uso descrito** ("una sola llamada a /status/ y mapa completo del fin de semana"):

1. **Contaminación masiva de /context/ con datos de TENIS** — 30+ archivos de jugadores ATP/WTA escritos bajo el slug `laliga-hypermotion_` por un scraper que confunde dropdown de "Próximos eventos" de bet365 con partidos de fútbol.
2. **3 convenciones de competición distintas** según la carpeta:
   - `/odds/` usa `spanish-primera`, `spain-segunda`, `italy-serie-a`
   - `/context/`, `/lineups/`, `/news/` usan `laliga`, `segunda`, `serie-a` (también `laliga-hypermotion`)
   - `/referees/` usa una mezcla, incluyendo entradas no-por-partido como `laliga_jornada-31_*.json`
3. **Naming inconsistente de partidos**: algunos archivos tienen FI bet365 (`_192612595`), otros no. Algunos tienen acentos (`cádiz`), otros no (`cadiz`). Imposible cruzar carpetas con un solo `match_id`.
4. **/status/ actual NO da el mapa que el agente externo necesita** — solo lista archivos por carpeta sin agruparlos por partido, sin kickoff, sin age, sin warnings de degradación.
5. **No hay schemas formales ni validación** — cada scraper escribe su forma libremente. Los `_data_gaps`/`source_stats`/`betting_stats` que añadí en este último ciclo no existen en archivos viejos.

Recomendación: ejecutar tareas 1→4 del plan original sí, pero **pausar tareas 7 (fallback árbitros) y 6 (baselines)** hasta validar las hipótesis del bug del tenis.

---

## 1. Inventario de archivos

```
odds/         8 files    (8 partidos del finde, 213-617 KB cada uno)
referees/    21 files    (8 nuevos por-partido + 13 históricos por-jornada)
context/    159 files    (~30 contaminados con TENIS, resto histórico)
news/         8 files    (todos del finde 2026-04-26/27)
lineups/      8 files    (todos del finde)
matches/     16 files    (no expuesto correctamente en /status/ histórico)
schemas/      —          (NO existe)
baselines/    —          (NO existe)
logs/         —          (NO existe)
tests/        —          (NO existe)
```

### Archivos top-level Python (scrapers)
```
scrape.py                       (legacy, no usar)
scrape_bet365.py                (DOM-based, lento, deprecado por scrape_cdp_fast)
scrape_cdp_fast.py              (CDP, intermedio)
scrape_all_evs.py               ★ versión actual y óptima — walk all EVs
scrape_fast.py                  (legacy)
scrape_now.py                   (orquestador legacy)
scrape_context.py               (presunta fuente del bug del tenis — REVISAR)
scrape_designations.py          (árbitros)
scrape_referees.py              (stats árbitros)
scrape_referees_international.py
scrape_lineups.py               (sin fetch reciente)
scrape_matches.py               (descubrimiento)
scrape_all_weekend.py           (orquestador)
cdp_client.py                   (utilidad)
run_cl_scrape.py / run_full_scrape_3matches.py  (one-shots históricos)
server.py                       (FastAPI, 212 LOC)
_generate_context_files.py      ★ nuevo — escribió los 8 contexts del finde a mano
_enrich_context.py              ★ nuevo — añadió betting_stats por mercado
_enrich_news.py                 ★ nuevo — escribió news con key_facts_for_betting
```

---

## 2. Endpoints expuestos por server.py

| Path | Método | Devuelve |
|------|--------|----------|
| `/` | GET | Listado de endpoints disponibles (texto fijo) |
| `/status/` | GET | Por cada carpeta: count, last_update, lista de filenames, lista de matches (extraído de `match` key) |
| `/odds/` | GET | Lista archivos de /odds/ con metadata |
| `/odds/{filename}` | GET | JSON literal del archivo |
| `/referees/` | GET | Lista de archivos /referees/ |
| `/referees/{filename}` | GET | JSON literal |
| `/lineups/` | GET | Lista |
| `/lineups/{filename}` | GET | JSON literal |
| `/context/` | GET | Lista |
| `/context/{filename}` | GET | JSON literal |
| `/matches/` | GET | Lista |
| `/matches/{filename}` | GET | JSON literal |
| `/news/` | GET | Lista *(añadido hoy)* |
| `/news/{filename}` | GET | JSON literal *(añadido hoy)* |

**Limitaciones del /status/ actual** vs lo que el agente necesita:
- ❌ NO agrupa por partido — el agente debe deducir match_id desde los filenames
- ❌ NO hay `kickoff_utc`, `minutes_to_kickoff`
- ❌ NO hay `age_minutes` por dato (solo `last_update` agregado por carpeta)
- ❌ NO hay `markets_count` por archivo de odds
- ❌ NO hay `warnings` de degradación
- ❌ NO hay agregado `weekend_summary`
- ❌ NO declara `expected_at_utc` cuando un archivo falta

CORS: ya configurado con `allow_origins=["*"]` y todos los métodos. ✓
Cache headers: ❌ NO se envían explícitamente (FastAPI default).

---

## 3. Schema actual de cada tipo de archivo (sin formalizar)

### /odds/ (estandarizado, generado por `scrape_all_evs.py` hoy)
```json
{
  "ok": true,
  "fi": "192612595",
  "match": "Osasuna vs Sevilla",
  "home": "Osasuna",
  "away": "Sevilla",
  "league": "Spanish Primera",          // string libre — NO normalizado
  "kickoff": "",                        // ⚠ vacío en mayoría
  "meta": {"IT": "..."},
  "url": "https://www.bet365.com/...",
  "scraped_at": "2026-04-26T18:24:32",  // sin TZ
  "source": "bet365",
  "market_count": 31,
  "selection_count": 2241,
  "markets": { ... }                     // 31 mercados con variantes
}
```
Naming actual: `{league_slug}_{home-vs-away}_{FI}_{YYYY-MM-DD}.json`
**FI incluido SIEMPRE en odds (✓), pero league_slug es `spanish-primera`/`spain-segunda` (≠ resto del repo).**

### /context/ (tras enrichment de hoy)
```json
{
  "match": "Osasuna vs Sevilla", "FI": "192612595",
  "competition": "LaLiga", "kickoff": "2026-04-26T18:30:00",
  "stadium": "El Sadar (Pamplona)",
  "home_team": { "table_position":10, "form_last_5":["D","D","L","L","W"],
                 "motivation":"midtable", "european_rotation_risk":false,
                 "key_injuries":[], "goals_for_avg_home":1.80, ... },
  "away_team": { ... mismos campos },
  "h2h_last_5": [],
  "weather": {"city":"...","temp_celsius":null,...},
  "betting_stats": { "over_2_5":{...}, "btts":{...}, "corners_total":{...}, "h2h_summary":{...} },
  "_data_gaps": [],
  "source": "...", "source_stats": "..."
}
```
Naming actual: `{competition}_{home-vs-away}_{FI}_{YYYY-MM-DD}.json` — pero los **históricos NO tienen FI** (`laliga_athletic-club-vs-osasuna_2026-04-11.json`).

### /referees/ (mixto)
Por-partido (nuevos):
```json
{
  "match":"...", "FI":"...", "competition":"LaLiga", "match_date":"2026-04-26",
  "kickoff":"2026-04-26T18:30:00",
  "referee":"Miguel Ángel Ortiz Arias",
  "verified_date":"2026-04-26", "is_same_day":true,
  "source":"...", "stats":{"yellow_cards_per_match":4.04,...},
  "verdict":"MEDIO", "verdict_reason":"...",
  "_data_gaps":[]
}
```
Por-jornada (legacy, siguen vivos): `laliga_jornada-31_2026-04-12.json` — **estos NO encajan en la nueva convención por-partido.**

### /lineups/
```json
{
  "match":"...", "FI":"...", "kickoff":"...",
  "confirmed": true|false,
  "home_xi_confirmed": [...] | null,
  "away_xi_confirmed": [...] | null,
  "home_xi_probable": [...] | null,
  "away_xi_probable": [...] | null,
  "key_absences": {"home":[...], "away":[...]},
  "_data_gaps":[], "source":"..."
}
```
**`confirmed` SIEMPRE presente como bool ✓** — cumple req tarea 5. Falta `expected_confirmation_utc`.

### /news/ (nuevo)
```json
{
  "match":"...", "FI":"...",
  "summary":"...",
  "headlines":[{date,title,source,relevance,url?}],
  "key_facts_for_betting": {
    "1X2_X2":[...], "goles":[...], "corners":[...], "remates":[...],
    "tarjetas":[...], "jugadores":[...]
  },
  "_data_gaps":[]
}
```

---

## 4. Convenciones de nombres por carpeta — INCONSISTENTES

| Carpeta | Patrón observado | Ejemplos |
|---------|------------------|----------|
| odds | `{spanish-primera/spain-segunda/italy-serie-a}_{home}-vs-{away}_{FI}_{date}.json` | `spanish-primera_osasuna-vs-sevilla_192612595_2026-04-26.json` |
| context | `{laliga/segunda/serie-a/laliga-hypermotion}_{home}-vs-{away}[_{FI}]_{date}.json` | `laliga_osasuna-vs-sevilla_192612595_2026-04-26.json` *vs* `laliga_athletic-club-vs-osasuna_2026-04-11.json` (sin FI) |
| referees | dos convenciones: `{liga}_{home}-vs-{away}_{FI}_{date}.json` Y `{liga}_jornada-{N}_{date}.json` | `laliga_jornada-31_2026-04-15.json` |
| lineups | `{liga}_{home}-vs-{away}_{FI}_{date}.json` | OK |
| news | `{liga}_{home}-vs-{away}_{FI}_{date}.json` | OK |

**Problemas concretos detectados:**
- 🐛 **Bug 1: TENIS en context** — `context/laliga-hypermotion_alex-de-minaurhamad-medjedovic-vs-alex-de-minaur_2026-04-15.json` (Alex de Minaur vs Hamad Medjedovic, ATP). Slug malformado por concatenación sin separador (`-de-minaurhamad-` = `-de-minaur` + `hamad-` sin guión). **30+ archivos así.**
  - Hipótesis: `scrape_context.py` lee el carrusel de "Próximos eventos" de bet365 cuando el tab actual NO es de fútbol (ej. ATP Madrid). El catch-all `bet365_navigation_state` mete tenis bajo el bucket de la última liga consultada.
- 🐛 **Bug 2: acentos no normalizados** — `cádiz`, `leganés`, `málaga`, `alavés`, `atlético`. Algunos archivos sí están normalizados (`cadiz`, `leganes`). Convivencia. Imposible deduplicar.
- 🐛 **Bug 3: tres slugs distintos para LaLiga Primera**: `laliga`, `spanish-primera`, `laliga-ea-sports`. Cada scraper inventa el suyo.
- 🐛 **Bug 4: kickoff vacío en /odds/** — el extractor CDP no encuentra `BC` ni `TI` ni `DT` en `data` del fixture EV. Hay que sacarlo del DOM (clase `[class*=StartTime]`) — ya está documentado en una sesión previa pero no implementado.

---

## 5. Errores conocidos / silenciados

Buscando `try:` `except:` `pass` en scrapers:
- `scrape_all_evs.py` — múltiples `try/except: pass` en `cdp_call` y suscripciones (correcto: WebSocket puede fallar transitorio).
- `scrape_designations.py`, `scrape_referees.py` — sin revisar a fondo en esta auditoría (no se modifican en este refactor por orden del usuario).
- `_generate_context_files.py` (mío) — escribe context con campos hardcodeados; si fallan, no hay validación.

Campos opcionales sin default detectados:
- `kickoff` puede ser `""` en /odds/ (no null, string vacío)
- `home`/`away` pueden ser `null` cuando el fixture EV no se identifica
- `_data_gaps` array vacío vs ausente — inconsistente entre tipos de archivo
- `is_same_day` solo en referees nuevos, ausente en históricos por-jornada

---

## 6. Lo que NO existe y la tarea pide

| Artefacto | Estado |
|-----------|--------|
| `schemas/*.schema.json` | ❌ No existe |
| `baselines/markets_per_league.json` | ❌ No existe |
| `start.sh`, `healthcheck.sh` | ❌ No existe |
| `migrate_filenames.py` | ❌ No existe |
| `tests/test_schema_validation.py` | ❌ No existe |
| `logs/scraper_errors.log` | ❌ No existe |
| Versión semántica `schema_version`, `scraper_version` en archivos | ❌ Ningún archivo lo lleva |
| Validación con `jsonschema` antes de escribir | ❌ |
| Fallback en cascada para árbitros (rfef → iusport → ...) | ❌ Solo búsqueda manual ad-hoc |
| Cabeceras `Cache-Control` | ❌ |
| `expected_confirmation_utc` en lineups | ❌ |

---

## 7. Decisiones que necesito que confirmes ANTES de seguir (tareas 2-10)

Como dice tu regla: *"Si encuentras algo que no esperabas en la auditoría, párate y reporta."*

### Q1 — Limpieza del bug del tenis en /context/
Hay **~30 archivos de tenis** contaminando `/context/laliga-hypermotion_*`. ¿Los elimino o los archivo en `/context/_quarantine/`? Mi recomendación: **mover a `_quarantine/`** + abrir issue para investigar `scrape_context.py` (no tocar la lógica del scraper aún por orden tuya).

### Q2 — Convención única de competición
Propongo:
- `laliga` (LaLiga Primera EA Sports)
- `segunda` (LaLiga Hypermotion / Segunda División)
- `champions` (UEFA Champions League)
- `europa` (Europa League)
- `conference` (Conference League)
- `copa-del-rey`
- `serie-a` (Italia)
- `bundesliga`, `premier`, `ligue-1`

¿Confirmas estos slugs o prefieres otros? (afecta a la tarea 2 entera).

### Q3 — Match_id global cross-folder
Propongo: `{competition}_{home_slug}-vs-{away_slug}_{YYYY-MM-DD}` (sin FI, sin acentos). El FI bet365 puede ir como **campo dentro del JSON** (`bet365_fi: "192612595"`) pero NO en el filename. Razón: el FI es específico de bet365 y rompe si añadimos otra fuente de cuotas mañana.
**Riesgo:** dos partidos del mismo día con mismos equipos (caso raro: ida/vuelta copa). Mitigación: añadir sufijo `_leg2` cuando sea necesario.
¿OK?

### Q4 — Históricos por-jornada en /referees/
Tengo `laliga_jornada-31_*.json` (designaciones de toda una jornada en un archivo). ¿Mantengo este formato como índice agregado y además genero los por-partido? ¿O migro todo a por-partido y borro los por-jornada?
Mi recomendación: **mantener ambos**. Por-partido es lo que /status/ usa; por-jornada queda como `referees/_indexes/jornada-{N}.json` para auditoría.

### Q5 — Lineups con `confirmed: false` actuales
Mis 8 lineups del finde están con `confirmed: false` para 7 de 8 (solo Osasuna-Sevilla está jugándose ahora). El cron necesita reescribirlos cuando se confirmen ~45 min antes de cada kickoff. ¿Quieres que el cron lo gestione `scrape_lineups.py --refresh`, o construyo un servicio `lineup_watcher.py` independiente?

### Q6 — Scope de la tarea 4 (validación schema)
Si introduzco `jsonschema.validate()` en cada `write()` de cada scraper, **algunos archivos viejos van a fallar la validación al ser leídos por /status/**. ¿Marco los viejos como `schema_version: "0.x"` y los excluyo de la validación, o los renormalizo retroactivamente?

---

## 8. Orden de ejecución propuesto (tras tu OK)

1. ⏸ ESPERAR respuestas Q1-Q6
2. Crear `schemas/`, `baselines/`, `logs/` vacíos
3. Tarea 2: `migrate_filenames.py --dry-run` → muestro plan → ejecuto
4. Tarea 6: poner `baselines/markets_per_league.json`
5. Tarea 4: schemas formales + validación en cada scraper de escritura
6. Tarea 3: nuevo `/status/` rico
7. Tarea 5: lineups confirmed flag + expected_confirmation_utc
8. Tarea 8: CORS + Cache-Control headers
9. Tarea 9: `start.sh` + `healthcheck.sh`
10. Tarea 10: README actualizado
11. Tarea 7 ⚠ (fallback árbitros): solo si confirmas — implica modificar `scrape_designations.py`/`scrape_referees.py` que dijiste no tocar sin permiso

---

**FIN DEL AUDIT — PARO AQUÍ A LA ESPERA DE TU RESPUESTA A Q1-Q6.**
