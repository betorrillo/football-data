# analisis_jornadas/

**Agent-writable. The scraper MUST NEVER touch this folder.**

This is where the Claude agent stores checkpoint files when an analysis
session is interrupted (see `FRANKEN_PLAYBOOK §5.7`).

File naming: `<comp>_<round>_<YYYY-MM-DD>.json`
Format: see `FRANKEN_PLAYBOOK §5.7` (`status`, `pending`, `matches[]`).

The `.gitkeep` is preserved so the folder ships with the repo.
