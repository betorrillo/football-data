# Datos scrapeados — Lunes 13 a Jueves 16 de abril 2026

## Partidos con cuotas disponibles

### LUNES 13 ABRIL

| Hora | Partido | Liga | Cuotas | Mercados | Árbitro | TA/P | Verdict |
|------|---------|------|--------|----------|---------|------|---------|
| 21:00 | Levante vs Getafe | LaLiga J31 | 1170 | 16 (goles, BTTS, córners, tarjetas, remates, shots OT, saves) | — | — | — |
| 21:00 | Manchester United vs Leeds | Premier League | 1005 | 12 (goles, BTTS, córners, tarjetas, remates, shots OT, saves) | — | — | — |

### MARTES 14 ABRIL — Champions League Cuartos Vuelta

| Hora | Partido | Cuotas | Mercados | Árbitro | TA/P | Verdict |
|------|---------|--------|----------|---------|------|---------|
| 21:00 | **Atlético de Madrid vs Barcelona** | 1285 | 16 | **István Kovács** (ROU) | **5.21** | **ALTO** |
| 21:00 | **Liverpool vs PSG** | 1247 | 16 | **José María Sánchez** (ESP) | **4.60** | **ALTO** |

### MIÉRCOLES 15 ABRIL — Champions League Cuartos Vuelta

| Hora | Partido | Cuotas | Mercados | Árbitro | TA/P | Verdict |
|------|---------|--------|----------|---------|------|---------|
| 21:00 | Arsenal vs Sporting | 1017 | 14 | Danny Makkelie (NED) | 3.03 | BAJO |
| 21:00 | Bayern de Múnich vs Real Madrid | 1114 | 14 | Clément Turpin (FRA) | 3.38 | BAJO |

---

## Archivos de cuotas

Cada archivo contiene todos los mercados con todas las combinaciones equipo × período:

| Archivo | Mercados incluidos |
|---------|-------------------|
| `la-liga_levante-vs-getafe_2026-04-13.json` | over_under_goals, btts, corners, cards, shots, shots_on_target, goalkeeper_saves, goals_interval, double_chance, result, correct_score, ht_ft, winning_margin, half_most_goals, team_most, btts_cards |
| `inglaterra--premier-league_manchester-united-vs-leeds_2026-04-13.json` | over_under_goals, btts, corners, cards, shots, shots_on_target, goalkeeper_saves, goals_interval, double_chance, result, correct_score |
| `uefa-champions-league_atlético-de-madrid-vs-barcelona_2026-04-14.json` | over_under_goals, btts, corners, cards, shots, shots_on_target, goalkeeper_saves, goals_interval, double_chance, result, correct_score, ht_ft, winning_margin, half_most_goals, team_most, btts_cards |
| `uefa-champions-league_liverpool-vs-psg_2026-04-14.json` | (mismos 16 mercados) |
| `uefa-champions-league_arsenal-vs-sporting_2026-04-15.json` | 14 mercados (sin tarjetas desglosadas por equipo) |
| `uefa-champions-league_bayern-de-múnich-vs-real-madrid_2026-04-15.json` | 14 mercados |

---

## Archivos de árbitros

| Archivo | Contenido |
|---------|-----------|
| `champions-league_cuartos-de-final_2026-04-12.json` | 4 árbitros CL cuartos vuelta con stats |
| `international_referee_stats_2026-04-12.json` | 77 árbitros de 6 ligas europeas (base de datos) |
| `laliga_jornada-31_2026-04-12.json` | 8 árbitros LaLiga J31 |

---

## Señales para tarjetas

### PICKS VIABLES (árbitro ALTO + cuotas disponibles)

**1. Atlético de Madrid vs Barcelona** (Martes 14 abr, 21:00)
- Árbitro: István Kovács — **5.21 TA/P (ALTO)**
- Contexto: Cuartos vuelta Champions, derbi español, máxima tensión
- Mercado: `markets.cards.total` tiene líneas Over/Under 3.5, 4.5, 5.5, 6.5...
- Archivo cuotas: `uefa-champions-league_atlético-de-madrid-vs-barcelona_2026-04-14.json`

**2. Liverpool vs PSG** (Martes 14 abr, 21:00)
- Árbitro: José María Sánchez — **4.60 TA/P (ALTO)**
- Contexto: Cuartos vuelta Champions, dos equipos de presión alta
- Mercado: `markets.cards.total` disponible
- Archivo cuotas: `uefa-champions-league_liverpool-vs-psg_2026-04-14.json`

### NO PICKS (árbitro BAJO)

- Arsenal vs Sporting: Makkelie 3.03 TA/P — demasiado permisivo
- Bayern vs Real Madrid: Turpin 3.38 TA/P — no llega al umbral

---

## Acceso a los datos

```bash
# Servidor API
python3 server.py

# Endpoints
GET http://localhost:8080/status/
GET http://localhost:8080/odds/
GET http://localhost:8080/odds/uefa-champions-league_atlético-de-madrid-vs-barcelona_2026-04-14.json
GET http://localhost:8080/referees/champions-league_cuartos-de-final_2026-04-12.json
```

---

## También disponible (próxima semana, ya scrapeado)

| Archivo | Partido | Fecha |
|---------|---------|-------|
| `la-liga_athletic-club-vs-osasuna_2026-04-21.json` | Athletic vs Osasuna | 21 abr |
| `la-liga_mallorca-vs-valencia_2026-04-21.json` | Mallorca vs Valencia | 21 abr |
| `la-liga_barcelona-vs-celta-de-vigo_2026-04-22.json` | Barcelona vs Celta | 22 abr |
