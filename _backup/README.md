# _backup — Archivos de seguridad

Archivos del scraper bet365 que ya no se usan activamente pero se conservan como referencia.

## Estructura

```
_backup/
  scrapers/     # Versiones anteriores de scrapers (v1-v6, context, referees, etc.)
  prompts/      # Prompts y documentacion del sistema anterior (V4 pivot, agente, etc.)
  utils/        # Utilidades auxiliares (normalizer, enrichers, CDP client)
  data/         # Muestras de datos historicos (Bayern-Real, odds completas)
```

## Nota

El scraper activo es `scrape_odds_v2.py` en la carpeta principal del proyecto bet365-scraper.
Estos archivos se subieron el 2026-05-15 como backup antes de limpieza.
