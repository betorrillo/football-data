"""Per-league official referee-designation scrapers.

Each module exposes:
    fetch_designations(date_hint: str | None = None) -> list[Designation]

Where Designation is a dict with keys:
    home          str   exact name as scraped (pre-normalization)
    away          str   exact name as scraped (pre-normalization)
    date          str   "YYYY-MM-DD" of kickoff (may be None if unknown)
    kickoff_time  str   "HH:MM" (may be None)
    referee       str   main referee name (CAPS or as published)
    var           str   VAR official (may be None)
    source_url    str   the page the data was scraped from
    league        str   one of: "epl", "laliga", "segunda", "bundesliga",
                        "seriea", "ligue1", "portugal", "fa_cup"

date_hint: optional "YYYY-MM-DD" the caller wants. The scraper may use it
to pick the right matchweek page; if None, the scraper returns the most
recent designations it can find.
"""
