# Key mapping — v1 → v2

Brief §8. Every v2 builder applies the **short key** form below. Keys are
shortened **only** when they (a) repeat 3+ times in the same file OR
(b) appear in every match (high aggregate volume). One-off keys stay
descriptive (brief §8.3).

## Applied in v2

| v1 (do not use) | v2 |
|---|---|
| `home_team`, `home_team_name`, `home_team_slug` | `home` (always slug) |
| `away_team`, `away_team_name`, `away_team_slug` | `away` (always slug) |
| `competition` | `comp` |
| `home_goals` / `away_goals` | `gh` / `ga` |
| `total_goals` | `g_tot` |
| `home_corners` / `away_corners` | `ch` / `ca` |
| `total_corners` | `c_tot` |
| `home_cards` / `away_cards` | `cards_h` / `cards_a` |
| `total_cards` | `cards_tot` |
| `expected_goals_for_per_game` | `xgf_pp` |
| `expected_goals_against_per_game` | `xga_pp` |
| `shots_per_game` | `shots_pp` |
| `shots_on_target_per_game` | `sot_pp` |
| `corners_per_game` | `corners_pp` |
| `cards_per_game` | `cards_pp` |
| `last_5_form` | `ult5` |
| `last_10_form` | `ult10` |
| `head_to_head` | `h2h` |
| `referee_yellow_cards_per_game` | `ref.ta_p` |
| `referee_red_cards_per_game` | `ref.tr_p` |
| `kickoff_time_iso` | `kickoff` |
| `last_updated_at` | `last_updated` |

## Kept long (brief §8.3)

Auto-explanatory and appearing 1-2× per file. The token saving would be
negligible and the readability hit non-trivial. Keep as-is:

- `id`, `nombre_oficial`, `liga`, `venue_principal`, `coach_actual`,
  `comp_base`
- `motivacion`, `asimetria`, `rotacion`, `lesiones_largas_actuales`
- `verdict`, `validez`, `bajas`, `status`, `confirmed`, `source`,
  `source_url`

## Enforcement

The JSON Schemas in `schemas/` reference both the short keys (in the
properties block) and reject the long forms (no v1 keys allowed in any
v2 schema). The v2 builders must produce output that validates against
these schemas before upload (brief §4 failure handling).

## Backwards compatibility

The v1 monolithic files (`analysis_pack.json`, `agent_bundle.json`) keep
their long keys for the rest of the v1 lifecycle. The v2 builders write
fresh per-match files alongside; v1 files remain untouched (brief §12.3,
"legacy files are never deleted").

When the agent fully cuts over to v2, the v1 builders can be retired.
Until then, both sets of keys coexist in different files.
