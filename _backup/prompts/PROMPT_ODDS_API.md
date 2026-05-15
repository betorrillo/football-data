# Acceso a cuotas de bet365 y datos arbitrales

Tienes acceso a un servidor local que sirve cuotas de partidos de fútbol scrapeadas de bet365 y datos de árbitros con estadísticas de tarjetas.

## Endpoints

- **Listar partidos**: `GET http://localhost:8080/odds/`
- **Obtener cuotas de un partido**: `GET http://localhost:8080/odds/{filename}`
- **Listar árbitros por jornada**: `GET http://localhost:8080/referees/`
- **Obtener datos de árbitros**: `GET http://localhost:8080/referees/{filename}`

Usa la herramienta web fetch para acceder a estos endpoints.

## Paso 1: Listar partidos disponibles

```
GET http://localhost:8080/odds/
```

Respuesta:
```json
{
  "files": [
    {
      "filename": "la-liga_sevilla-vs-atletico-de-madrid_2026-04-11.json",
      "match": "Sevilla vs Atlético de Madrid",
      "competition": "España - La Liga",
      "date": "11 abr 21:00",
      "isLive": false,
      "total_markets": 16
    }
  ],
  "count": 1
}
```

## Paso 2: Obtener cuotas de un partido

```
GET http://localhost:8080/odds/{filename}
```

## Estructura del JSON de cuotas

Cada archivo JSON tiene esta estructura:

```json
{
  "match": "Sevilla vs Atlético de Madrid",
  "home": "Sevilla",
  "away": "Atlético de Madrid",
  "competition": "España - La Liga",
  "date": "11 abr 21:00",
  "scraped_at": "2026-04-11T18:34:37",
  "source": "bet365",
  "isLive": false,
  "markets": { ... }
}
```

### Mercados disponibles

| Clave | Descripción |
|-------|-------------|
| `over_under_goals` | Más/menos goles (total, por equipo, por mitad) |
| `btts` | Ambos equipos marcan (sí/no) |
| `corners` | Más/menos córners (total, por equipo, por mitad) |
| `cards` | Más/menos tarjetas (total, por equipo, por mitad) |
| `shots` | Más/menos remates totales |
| `shots_on_target` | Más/menos remates a puerta |
| `goalkeeper_saves` | Paradas del portero |
| `goals_interval` | Goles por intervalo de tiempo |
| `double_chance` | Doble oportunidad |
| `result` | Resultado 1X2 |
| `correct_score` | Marcador exacto |
| `ht_ft` | Descanso/Final |
| `winning_margin` | Margen de victoria |
| `half_most_goals` | Mitad con más goles |
| `btts_cards` | Ambos equipos reciben tarjetas |

### Estructura de mercados Over/Under

Los mercados `over_under_goals`, `corners`, `cards`, `shots`, `shots_on_target` comparten esta estructura:

```json
{
  "over_under_goals": {
    "total": {
      "0.5": {"over": 1.06, "under": 10.0},
      "1.5": {"over": 1.28, "under": 3.75},
      "2.5": {"over": 1.90, "under": 1.90},
      "3.5": {"over": 3.40, "under": 1.33},
      "4.5": {"over": 6.00, "under": 1.12},
      "5.5": {"over": 13.0, "under": 1.04},
      "6.5": {"over": 26.0, "under": 1.01}
    },
    "total_first_half": {
      "0.5": {"over": 1.40, "under": 2.75},
      "1.5": {"over": 2.75, "under": 1.40},
      "2.5": {"over": 8.00, "under": 1.08}
    },
    "total_second_half": {
      "0.5": {"over": 1.22, "under": 4.00},
      "1.5": {"over": 2.10, "under": 1.66}
    },
    "total_first_10min": {
      "0.5": {"over": 4.50, "under": 1.18}
    },
    "home_team": {
      "0.5": {"over": 1.25, "under": 3.75},
      "1.5": {"over": 2.20, "under": 1.61},
      "2.5": {"over": 5.50, "under": 1.14}
    },
    "home_team_first_half": {
      "0.5": {"over": 1.83, "under": 1.83}
    },
    "away_team": {
      "0.5": {"over": 1.50, "under": 2.50},
      "1.5": {"over": 3.25, "under": 1.33}
    },
    "away_team_first_half": {
      "0.5": {"over": 2.25, "under": 1.57}
    }
  }
}
```

Sub-claves de cada mercado O/U:
- `total` → ambos equipos, partido completo
- `total_first_half` → ambos equipos, 1ª mitad
- `total_second_half` → ambos equipos, 2ª mitad
- `total_first_10min` → ambos equipos, primeros 10 minutos
- `home_team` → solo equipo local, partido completo
- `home_team_first_half` → solo equipo local, 1ª mitad
- `home_team_second_half` → solo equipo local, 2ª mitad
- `away_team` → solo equipo visitante, partido completo
- `away_team_first_half` → solo equipo visitante, 1ª mitad
- (y todas las combinaciones disponibles)

### BTTS (Ambos marcan)

```json
{
  "btts": {
    "match": {"yes": 1.75, "no": 2.00},
    "first_half": {"yes": 4.50, "no": 1.18},
    "second_half": {"yes": 3.40, "no": 1.30}
  }
}
```

### Córners

Misma estructura que goles O/U. Ejemplo:
```json
{
  "corners": {
    "total": {
      "4.5": {"over": 1.025, "under": 17.0},
      "7.5": {"over": 1.33, "under": 5.0},
      "8.5": {"over": 1.57, "under": 2.62},
      "9.5": {"over": 1.90, "under": 2.62},
      "10.5": {"over": 2.62, "under": 1.44}
    },
    "home_team": {
      "3.5": {"over": 1.44, "under": 2.62},
      "4.5": {"over": 2.10, "under": 1.66}
    }
  }
}
```

### Tarjetas

Misma estructura que goles O/U:
```json
{
  "cards": {
    "total": {
      "2.5": {"over": 1.16, "under": 5.0},
      "3.5": {"over": 1.40, "under": 2.87},
      "4.5": {"over": 1.83, "under": 1.83},
      "5.5": {"over": 2.75, "under": 1.40}
    }
  }
}
```

### Doble oportunidad

```json
{
  "double_chance": {
    "sevilla_o_draw": 1.36,
    "draw_o_atletico_de_madrid": 1.61,
    "sevilla_o_atletico_de_madrid": 1.30
  }
}
```

## Cómo interpretar las cuotas

- **Over/Under**: `"2.5": {"over": 1.90, "under": 1.90}` → la cuota para más de 2.5 goles es 1.90, para menos de 2.5 goles es 1.90
- **La línea decimal (0.5, 1.5, 2.5...)** indica el umbral. Over 2.5 = 3 o más. Under 2.5 = 2 o menos.
- **Cuotas más bajas = más probable** según el mercado. Over 0.5 goles a 1.06 significa que la casa espera al menos 1 gol con altísima probabilidad.
- **isLive: true** indica que las cuotas fueron scrapeadas durante el partido en vivo y pueden tener mercados suspendidos.

## Notas

- Las cuotas se scrapean de bet365 y son un snapshot del momento indicado en `scraped_at`
- Los partidos en vivo (`isLive: true`) tienen menos mercados disponibles (algunos se suspenden durante el juego)
- La fuente es siempre bet365 (campo `source`)
- Todos los mercados que bet365 ofrece están incluidos: cada línea O/U disponible, cada combinación equipo/período

---

## Datos de árbitros

### Listar jornadas disponibles

```
GET http://localhost:8080/referees/
```

Respuesta:
```json
{
  "files": [
    {
      "filename": "laliga_jornada-31_2026-04-11.json",
      "competition": "LaLiga",
      "matchday": 31,
      "total_referees": 10
    }
  ],
  "count": 1
}
```

### Obtener datos de árbitros de una jornada

```
GET http://localhost:8080/referees/{filename}
```

### Estructura del JSON de árbitros

```json
{
  "competition": "LaLiga",
  "matchday": 31,
  "scraped_at": "2026-04-11T10:00:00",
  "total_referees": 10,
  "referees": [
    {
      "match": "Sevilla vs Atlético de Madrid",
      "referee": "Isidro Díaz de Mera",
      "committee": "Manchego",
      "var": "Pablo González",
      "stats": {
        "matches_season": 12,
        "yellow_cards_per_match": 5.2,
        "red_cards_per_match": 0.3,
        "penalties_per_match": 0.25
      },
      "verdict": "ALTO — pick de tarjetas viable (≥ 4.5 TA/p)"
    }
  ]
}
```

### Interpretación del verdict

| Verdict | Criterio | Recomendación |
|---------|----------|---------------|
| **ALTO** | ≥ 4.5 amarillas/partido | Pick de tarjetas viable |
| **MEDIO** | 3.5 - 4.5 amarillas/partido | Evaluar con contexto del partido |
| **BAJO** | < 3.5 amarillas/partido | No recomendar pick de tarjetas |
| **SIN DATOS** | Sin estadísticas | Buscar manualmente |
| **PENDIENTE** | Designación no publicada | Esperar a la RFEF |

### Uso combinado cuotas + árbitros

Para analizar tarjetas de un partido:
1. Consulta `/referees/` para ver el verdict del árbitro (ALTO/MEDIO/BAJO)
2. Consulta `/odds/{partido}` y lee `markets.cards.total` para las cuotas O/U tarjetas
3. Cruza: si el árbitro es ALTO (≥4.5 TA/p) y las cuotas de Over 4.5 tarjetas son ≥1.80, es un pick con valor
