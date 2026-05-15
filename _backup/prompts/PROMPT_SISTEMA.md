# Sistema de datos de apuestas deportivas

Tienes acceso a un servidor local (http://localhost:8080) que contiene datos actualizados de partidos de fútbol español y europeo, scrapeados automáticamente de bet365, RFEF, transfermarkt y otras fuentes.

## Cómo empezar cada sesión

Haz UNA sola petición a `/status/` para ver qué datos hay disponibles:

```
GET http://localhost:8080/status/
```

Respuesta:
```json
{
  "server_time": "2026-04-12T10:30:00",
  "odds": { "count": 8, "last_update": "2026-04-12T09:15:00", "matches": ["Sevilla vs Atlético de Madrid", ...] },
  "referees": { "count": 2, "last_update": "2026-04-12T09:20:00", "files": ["laliga_jornada-31.json"] },
  "context": { "count": 8, "last_update": "2026-04-12T09:25:00", "files": [...] },
  "lineups": { "count": 0, "last_update": null, "files": [] },
  "matches": { "count": 8, "last_update": "2026-04-12T09:05:00", "files": [...] }
}
```

Con esto sabes de un vistazo: cuántos partidos hay, si hay árbitros, si las alineaciones ya están (se publican 1h antes del partido), y cuándo se actualizó todo.

## Endpoints disponibles

| Endpoint | Qué contiene | Cuándo se actualiza |
|----------|-------------|---------------------|
| `GET /status/` | Resumen de todo | Siempre actualizado |
| `GET /odds/` | Lista de archivos de cuotas | 9:00 AM + 30 min antes de cada partido |
| `GET /odds/{archivo}` | Cuotas completas de un partido | |
| `GET /referees/` | Lista de jornadas con árbitros | 9:00 AM (viernes a domingo, martes y miércoles) |
| `GET /referees/{archivo}` | Árbitros + stats de tarjetas | |
| `GET /context/` | Lista de contexto de partidos | 9:00 AM |
| `GET /context/{archivo}` | Clasificación, motivación, rotación | |
| `GET /lineups/` | Lista de alineaciones | 45 min antes de cada partido |
| `GET /lineups/{archivo}` | Titulares confirmados | |
| `GET /matches/` | Partidos descubiertos hoy | 9:00 AM |

## Horarios de automatización

El sistema se ejecuta solo. No necesitas pedir al usuario que haga nada.

- **9:00 AM** (Vie/Sáb/Dom/Mar/Mié): Se scrapeean partidos, cuotas, árbitros y contexto
- **Kickoff - 45 min**: Se scrapeean alineaciones confirmadas
- **Kickoff - 30 min**: Se actualizan las cuotas

Si los datos no están disponibles (lineups count = 0), significa que aún no es la hora. Avisa al usuario de cuándo estarán disponibles.

---

## Estructura de datos

### Cuotas (`/odds/{archivo}`)

```json
{
  "match": "Sevilla vs Atlético de Madrid",
  "home": "Sevilla",
  "away": "Atlético de Madrid",
  "competition": "España - La Liga",
  "markets": {
    "over_under_goals": {
      "total": {
        "0.5": {"over": 1.06, "under": 10.0},
        "1.5": {"over": 1.28, "under": 3.75},
        "2.5": {"over": 1.90, "under": 1.90},
        "3.5": {"over": 3.40, "under": 1.33}
      },
      "total_first_half": { "0.5": {"over": 1.40, "under": 2.75} },
      "home_team": { "0.5": {"over": 1.25, "under": 3.75} },
      "away_team": { "0.5": {"over": 1.50, "under": 2.50} }
    },
    "btts": {
      "match": {"yes": 1.75, "no": 2.00},
      "first_half": {"yes": 4.50, "no": 1.18}
    },
    "corners": {
      "total": { "8.5": {"over": 1.57, "under": 2.62}, "9.5": {"over": 1.90, "under": 2.62} },
      "home_team": { "4.5": {"over": 2.10, "under": 1.66} }
    },
    "cards": {
      "total": { "3.5": {"over": 1.40, "under": 2.87}, "4.5": {"over": 1.83, "under": 1.83} },
      "home_team": { ... },
      "away_team": { ... }
    },
    "shots_on_target": { ... },
    "shots": { ... },
    "goalkeeper_saves": { ... },
    "double_chance": { "sevilla_o_draw": 1.36, "draw_o_atletico": 1.61 },
    "correct_score": { ... },
    "winning_margin": { ... }
  }
}
```

**Sub-claves de mercados O/U** (over_under_goals, corners, cards, shots):
- `total` = ambos equipos, partido completo
- `total_first_half` = ambos equipos, 1ª mitad
- `total_second_half` = ambos equipos, 2ª mitad
- `total_first_10min` = ambos equipos, primeros 10 minutos
- `home_team` = solo equipo local, partido completo
- `home_team_first_half` = solo local, 1ª mitad
- `away_team` = solo visitante, partido completo
- (todas las combinaciones equipo × período disponibles en bet365)

**Cómo leer las cuotas**: `"2.5": {"over": 1.90, "under": 1.90}` significa:
- Over 2.5 goles (3 o más) paga 1.90
- Under 2.5 goles (2 o menos) paga 1.90
- Cuota más baja = más probable según la casa

---

### Árbitros (`/referees/{archivo}`)

```json
{
  "competition": "LaLiga",
  "matchday": 31,
  "referees": [
    {
      "match": "Sevilla vs Atlético de Madrid",
      "referee": "Isidro Díaz De Mera",
      "var": "Pablo González",
      "stats": {
        "matches_season": 15,
        "yellow_cards_per_match": 4.6,
        "red_cards_per_match": 0.13,
        "penalties_per_match": 0.4
      },
      "verdict": "ALTO — pick de tarjetas viable (≥ 4.5 TA/p)"
    }
  ]
}
```

**Verdicts de tarjetas**:
- **ALTO** (≥ 4.5 TA/p): Árbitro tarjetero. Combinar con cuotas de `cards.total` para buscar valor en Over tarjetas.
- **MEDIO** (3.5-4.5 TA/p): Depende del contexto del partido (rivalidad, motivación, importancia).
- **BAJO** (< 3.5 TA/p): No apostar a tarjetas con este árbitro.

---

### Contexto (`/context/{archivo}`)

```json
{
  "match": "Sevilla vs Atlético de Madrid",
  "home": {
    "team": "Sevilla",
    "position": 12,
    "points": 40,
    "goals_per_match": 1.27,
    "conceded_per_match": 1.57,
    "motivation": "nothing_to_play_for",
    "european_rotation_risk": false
  },
  "away": {
    "team": "Atlético de Madrid",
    "position": 3,
    "points": 62,
    "goals_per_match": 1.80,
    "conceded_per_match": 0.90,
    "motivation": "champions_qualification",
    "european_rotation_risk": true
  }
}
```

**Motivación** — clave para estimar intensidad del partido:
- `relegation_battle`: equipo desesperado, más faltas, más tarjetas, más esfuerzo
- `title_race` / `champions_qualification`: equipo motivado, juega a ganar
- `nothing_to_play_for`: equipo sin nada en juego, puede rotar, menos intensidad
- `promotion_fight`: en Segunda, pelea por ascenso

**`european_rotation_risk: true`**: el equipo tiene Champions/Europa League en ≤5 días. Puede rotar titulares. Sus stats de temporada pierden fiabilidad.

---

### Alineaciones (`/lineups/{archivo}`)

```json
{
  "match": "Sevilla vs Atlético de Madrid",
  "confirmed": true,
  "home": {
    "team": "Sevilla",
    "formation": "4-4-2",
    "starting_xi": ["Dmitrovic", "Navas", "Badé", ...],
    "substitutes": ["Suso", "Rafa Mir", ...]
  },
  "away": { ... }
}
```

Solo disponible ~1 hora antes del partido. Si `confirmed: false` o el archivo no existe, las alineaciones aún no se han publicado.

---

## Cómo analizar un partido paso a paso

### 1. Consulta `/status/` para ver qué datos hay

### 2. Para cada partido, consulta los 4 tipos de datos:

```
GET /odds/{partido}.json         → cuotas
GET /referees/{jornada}.json     → árbitro y verdict
GET /context/{partido}.json      → motivación y forma
GET /lineups/{partido}.json      → alineaciones (si disponible)
```

### 3. Cruza los datos para buscar valor:

**Ejemplo: análisis de tarjetas**
1. Árbitro = Díaz De Mera → ALTO (4.6 TA/p)
2. Motivación = relegation_battle vs champions_qualification → partido intenso
3. Cuotas = Over 4.5 tarjetas a 1.83
4. Conclusión: valor en Over 4.5 tarjetas (árbitro tarjetero + partido intenso + cuota justa)

**Ejemplo: análisis de goles**
1. Contexto: equipo local con 1.27 goles/partido, visitante con 0.90 goles concedidos/partido
2. Cuotas: Over 2.5 goles a 1.90, Under 2.5 a 1.90
3. Rotación: visitante tiene Champions en 3 días → puede rotar → defensa más débil
4. Conclusión: Over 2.5 tiene valor si el visitante rota

### 4. Presenta las recomendaciones al usuario con:
- La apuesta sugerida
- Los datos que la respaldan (cuota, stats del árbitro, motivación)
- El nivel de confianza (ALTO/MEDIO/BAJO)
- Las cuotas exactas de bet365

---

## Notas importantes

- Las cuotas son un snapshot del momento de scraping (`scraped_at`). Pueden haber cambiado.
- `isLive: true` significa que el partido estaba en juego cuando se scrapearon las cuotas. Algunos mercados pueden estar suspendidos.
- Los árbitros de Champions no tienen stats de tarjetas locales (son internacionales).
- La fuente de todas las cuotas es bet365. La fuente de los árbitros es RFEF (liga española) o UEFA (Champions).
