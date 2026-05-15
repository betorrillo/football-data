# PLAN: Pivote a Sistema de Predicción Online
## Versión 4.0 — Mayo 2026

---

## RESUMEN EJECUTIVO

**Antes**: Sistema local (localhost:8080) centrado en scrapear cuotas de bet365 + estadísticas. Frágil, lento, requiere Chrome CDP, solo funciona en desktop.

**Ahora**: Sistema online centrado en ESTADÍSTICAS y PREDICCIÓN DE PROBABILIDADES. Sin cuotas. Datos en GitHub (accesible desde móvil). Claude AI estima probabilidades y flaggea eventos ≥70%.

**Cambio filosófico**: El usuario ya no necesita cuotas del scraper. El agente produce probabilidades puras. El usuario cruza esas probabilidades con las cuotas manualmente en bet365.

---

## PASO 1: ALMACENAMIENTO ONLINE

### Decisión: GitHub repo público

**Por qué GitHub**:
- Gratis (50MB necesarios, límite 1GB)
- Sin autenticación para leer: `raw.githubusercontent.com/{user}/football-data/main/...`
- Claude.ai (móvil/web) puede leer URLs directas con WebFetch
- Claude Code (desktop) puede git push
- Versionado automático con cada commit
- Estructura de carpetas familiar (mismo layout que localhost)

**Estructura del repo**:
```
football-data/
├── manifest.json           # índice de TODOS los archivos disponibles
├── referees/
│   ├── laliga_jornada34.json
│   ├── champions_semifinal.json
│   └── international_stats.json
├── context/
│   ├── laliga_athletic-vs-osasuna_2026-05-10.json
│   └── champions_bayern-vs-real_2026-05-13.json
├── stats/                  # NUEVO: estadísticas avanzadas
│   ├── xg_laliga_2025-26.json         # xG por equipo (FBRef)
│   ├── shots_laliga_2025-26.json      # remates por equipo
│   ├── corners_laliga_2025-26.json    # córners por equipo
│   ├── cards_laliga_2025-26.json      # tarjetas por equipo
│   └── form_all_leagues.json          # forma reciente
├── lineups/
│   └── laliga_athletic-vs-osasuna_2026-05-10.json
├── injuries/               # NUEVO: lesiones y bajas
│   └── laliga_jornada34.json
├── h2h/                    # NUEVO: head-to-head
│   └── athletic-vs-osasuna.json
└── predictions/            # NUEVO: predicciones generadas
    └── laliga_jornada34_predictions.json
```

### Setup necesario (una vez):
1. Crear repo en GitHub: `football-data` (público)
2. Clonar localmente
3. Configurar remote en Claude Code
4. Script de sync: `git add . && git commit -m "update $(date)" && git push`

---

## PASO 2: ANÁLISIS Y MEJORAS

### Problemas del sistema actual

| Problema | Impacto | Solución |
|----------|---------|----------|
| bet365 scraping inestable | 80% del tiempo de desarrollo gastado en CDP/SPA | ELIMINAR - no scrapear cuotas |
| Datos solo en local | Inaccesible desde móvil | GitHub repo |
| Pocos datos de contexto | Solo clasificación + forma básica | FBRef, Understat, Football-data.co.uk |
| Sin xG por equipo | Predicciones de goles sin base estadística | FBRef: xG, xGA, npxG |
| Sin stats de córners | Mercado de córners a ciegas | FBRef + FootyStats |
| Sin stats de remates | Mercado de remates sin datos | FBRef: Sh, SoT por equipo |
| Sin lesiones/bajas | Contexto incompleto | API-Football free tier / Transfermarkt |
| Sin noticias | El agente no sabe cambios recientes | Web search en tiempo real |
| Árbitros solo RFEF | Solo ligas españolas | Transfermarkt (ya funciona para 7 ligas) |

### Datos que el agente NECESITA y no tiene

1. **xG por equipo** (expected goals for/against) — FBRef
2. **Remates por equipo** (Sh, SoT, Sh/90) — FBRef
3. **Córners por equipo** (CK for/against) — FBRef
4. **Tarjetas por equipo** (CrdY, CrdR, Fls) — FBRef
5. **Posesión y pases** (Poss%, pass completion) — FBRef
6. **PDO** (shooting + save %) — FBRef/Understat
7. **Lesiones activas** — Transfermarkt / API-Football
8. **Clima y hora local** — OpenWeatherMap / Google
9. **Noticias recientes** del equipo — web search en vivo
10. **H2H con mismo entrenador** — FBRef/Transfermarkt

### Fuentes de datos recomendadas

| Fuente | Datos | Acceso | Coste |
|--------|-------|--------|-------|
| **FBRef.com** | xG, remates, córners, tarjetas, pases, árbitros | Scrape HTML (2 req/min) | Gratis |
| **Understat.com** | xG por tiro, modelos xG | JSON en `<script>` tags | Gratis |
| **Football-data.co.uk** | Histórico CSV (resultados, goles, BTTS) | Descarga directa | Gratis |
| **API-Football** | Lineups, lesiones, standings, fixtures | REST API (100 req/día) | Gratis |
| **Transfermarkt** | Árbitros, plantillas, valores, lesiones | Scrape HTML | Gratis |
| **Flashscore/Sofascore** | Forma, H2H, stats por partido | API interna | Gratis |
| **Web Search** | Noticias, alineaciones, designaciones | Claude built-in | Gratis |

### Nueva pipeline de datos

```
SCRAPING (Claude Code desktop, semanal/diario)
  │
  ├─ FBRef → xG, shots, corners, cards, referees → stats/
  ├─ Understat → xG models → stats/
  ├─ Football-data.co.uk → historical CSV → stats/
  ├─ Transfermarkt → referee stats, injuries → referees/, injuries/
  ├─ API-Football → fixtures, lineups → lineups/
  │
  └─ git push → GitHub repo
  
ANÁLISIS (Claude AI agent, móvil o desktop)
  │
  ├─ Lee manifest.json de GitHub
  ├─ Lee stats pre-scrapeadas de GitHub
  ├─ Web search en vivo: noticias, alineaciones día del partido
  ├─ Estima probabilidades para CADA mercado
  └─ Flagea eventos ≥ 70%
```

---

## PASO 3: CAMBIOS EN EL PROMPT DEL AGENTE

### Cambios principales vs prompt actual:

1. **Eliminar TODA referencia a localhost:8080** → reemplazar con URLs de GitHub
2. **Eliminar TODA referencia a Chrome MCP** → el agente usa web search + WebFetch
3. **Eliminar el concepto de "value betting" como core** → el core es PREDICCIÓN DE PROBABILIDAD
4. **Eliminar mercado 1x2 excluido** → TODOS los mercados relevantes
5. **Añadir análisis multi-línea** → para cada mercado, analizar TODAS las líneas (O1.5, O2.5, O3.5, O4.5)
6. **Añadir más fuentes de datos** que el agente debe buscar activamente
7. **Añadir noticias como paso obligatorio** → el agente DEBE buscar noticias recientes
8. **Hora local del partido** como variable
9. **Clima** como variable (lluvia → menos córners, más tarjetas?)
10. **El agente puede funcionar SIN datos pre-scrapeados** → búsqueda web como fallback universal

---

## VERIFICACIÓN

- [ ] GitHub repo creado y accesible
- [ ] Primer dataset subido (stats actuales de LaLiga)
- [ ] Prompt V4 escrito y probado
- [ ] Claude.ai móvil puede leer datos de GitHub
- [ ] Scraper de FBRef funciona (stats básicas)
- [ ] manifest.json se actualiza automáticamente
