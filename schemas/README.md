# JSON Schemas — football-data-agent v2

These schemas validate every JSON produced by the v2 scraper before it is
uploaded to Drive. Each builder calls `jsonschema.validate()` against the
relevant schema; on failure, the partial file is uploaded with
`_partial: true` and the failure logged to `_run_log.json` (see brief §4).

| schema | validates |
|---|---|
| `match_context.schema.json` | one match file in `context/<comp>_<round>/<home>-vs-<away>.json` (brief §5.2) |
| `team_snapshot.schema.json` | one team file in `teams/<slug>.json` (brief §6.2) |
| `teams_index.schema.json` | `teams/_index.json` (brief §6.3) |
| `manifest_agent.schema.json` | `manifest_agent.json` (brief §7.2) |
| `referee.schema.json` | one referee file in `referees/<slug>.json` |
| `run_log.schema.json` | `_run_log.json` |

## Enum sources of truth

Enums declared in `_enums.json` and referenced from the schemas via `$ref`.
This keeps the values in one place (matches PLAYBOOK §3.C dimensions and
brief §5.3 enumerations).
