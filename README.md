# football-data-agent · v2 (WIP)

Pre-computed football data for the **Franken** prediction agent.
The scraper runs on a cron (tue + fri 10:00 CET) and uploads a structured
dataset to a Google Drive folder; the Claude agent reads from there.

The scraper **never** scrapes odds. See `FRANKEN_PLAYBOOK §1.1
PROYECTO_FRANKEN_IDENTIDAD`. The agent reasons about probabilities only;
Beto crosses with odds manually.

## Status

| | |
|---|---|
| Active branch | `v2-restructure` (this branch) |
| Stable branch | `main` (v1, in production) |
| Spec | `BRIEF_v2.md` (provided by Beto, not in repo) |
| Methodology | `FRANKEN_PLAYBOOK.md` (Project Knowledge in Claude.ai) |

## Competitions covered (v2 scope)

- 🇪🇸 LaLiga EA Sports
- 🇪🇸 LaLiga HyperMotion (Segunda)
- 🇪🇸 Copa del Rey
- 🇮🇹 Serie A
- 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League
- 🇵🇹 Primeira Liga
- 🇪🇺 Champions League
- 🇪🇺 Europa League
- 🇪🇺 Conference League

**Excluded** (v2): Bundesliga, Ligue 1.

## Output structure (target — brief §10)

```
manifest_agent.json              # agent entry point
status.json                      # legacy v1 health index
_run_log.json                    # per-run log (errors, duration)

all_referees.json                # universal referee base
analysis_pack.json               # legacy aggregate (kept)
agent_bundle.json                # legacy bundle (kept)

teams/                           # per-team snapshot (v2 mejora 2)
  _index.json
  <slug>.json

context/                         # per-match context (v2 mejora 1)
  <comp>_<round>/
    <home>-vs-<away>.json

h2h/                             # per-match H2H (v2 mejora 1)
  <home>-vs-<away>.json

lineups/                         # per-match lineups (when probables exist)
  <comp>_<round>/
    <home>-vs-<away>.json

referees/                        # per-designated-referee (v2 mejora 1)
  <slug>.json
  all_referees_<date>.json       # legacy v1
  stats_<liga>_<date>.json       # legacy v1

analisis_jornadas/               # agent-writable (scraper never touches)
```

## Validation

Every output is validated against a JSON Schema in `schemas/` before upload.
On validation failure: the file ships with `_partial: true` and a
`_schema_error` field; the run log records it. See
`scripts/utils/schema_validation.py`.

## Access for the agent

Raw URLs: `https://raw.githubusercontent.com/betorrillo/football-data/main/{path}`
Drive folder id (from `FRANKEN_PLAYBOOK §1.1`): `1-oOJeIZZh_CKvZqt2nws77LeKoyMBBti`

## Local dev

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium  # for RFEF scraper
```

## Repo conventions

- Slugs: kebab-case, no accents (`atletico-madrid`, not `Atlético de Madrid`)
- All timestamps UTC ISO 8601 in `last_updated` / `generated_at`
- All JSON files UTF-8 with `ensure_ascii=False`
- Idempotency: re-running the same day yields the same output
- Failure isolation: one match failing does not abort the run
