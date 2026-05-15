#!/usr/bin/env python3
"""
Betting Data API Server.

Endpoints:
  GET /status/              → overview of all available data
  GET /odds/{filename}      → match odds
  GET /referees/{filename}  → referee designations + stats
  GET /lineups/{filename}   → confirmed lineups
  GET /context/{filename}   → match context (form, motivation)
  GET /matches/{filename}   → discovered matches

Launch: python3 server.py
"""

import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

BASE = os.path.dirname(os.path.abspath(__file__))
DIRS = {
    'odds': os.path.join(BASE, 'odds'),
    'referees': os.path.join(BASE, 'referees'),
    'lineups': os.path.join(BASE, 'lineups'),
    'context': os.path.join(BASE, 'context'),
    'matches': os.path.join(BASE, 'matches'),
    'news': os.path.join(BASE, 'news'),
}

app = FastAPI(title="Betting Data API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


def _list_dir(dir_path, skip_files=None):
    """Generic: list JSON files in a directory with metadata."""
    skip = skip_files or set()
    if not os.path.isdir(dir_path):
        return []
    files = []
    for fname in sorted(os.listdir(dir_path)):
        if not fname.endswith('.json') or fname in skip:
            continue
        fpath = os.path.join(dir_path, fname)
        stat = os.stat(fpath)
        entry = {
            'filename': fname,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'size_kb': round(stat.st_size / 1024, 1),
        }
        try:
            with open(fpath) as f:
                data = json.load(f)
            # Add top-level summary fields (skip large nested data)
            for key in ['match', 'competition', 'date', 'datetime', 'matchday',
                        'isLive', 'total_markets', 'total_referees', 'total_matches',
                        'confirmed', 'round']:
                if key in data:
                    entry[key] = data[key]
            if 'markets' in data:
                entry['total_markets'] = len(data['markets'])
            if 'home' in data and isinstance(data['home'], dict):
                entry['home'] = data['home'].get('team', data.get('home', ''))
                entry['away'] = data.get('away', {}).get('team', data.get('away', ''))
        except:
            pass
        files.append(entry)
    return files


def _get_file(dir_path, filename):
    """Generic: return a JSON file's content."""
    if not filename.endswith('.json'):
        filename += '.json'
    fpath = os.path.join(dir_path, filename)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail=f"Not found: {filename}")
    try:
        with open(fpath) as f:
            return JSONResponse(content=json.load(f))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Invalid JSON: {filename}")


# ===================================================================
# /status/ — single overview of all data
# ===================================================================

@app.get("/")
def root():
    return {"status": "ok", "endpoints": [
        "/status/", "/odds/", "/referees/", "/lineups/", "/context/", "/matches/"
    ]}


@app.get("/status/")
def status():
    """Overview of all available data across all categories."""
    result = {"server_time": datetime.now().isoformat()}

    for category, dir_path in DIRS.items():
        skip = {'referee_stats_cache.json'} if category == 'referees' else set()
        files = _list_dir(dir_path, skip)
        last_mod = max((f['modified'] for f in files), default=None) if files else None

        section = {
            'count': len(files),
            'last_update': last_mod,
            'files': [f['filename'] for f in files],
        }

        # Add match names for odds
        if category == 'odds':
            section['matches'] = [f.get('match', f['filename']) for f in files if f.get('match')]

        result[category] = section

    return result


# ===================================================================
# /odds/
# ===================================================================

@app.get("/odds/")
def list_odds():
    files = _list_dir(DIRS['odds'])
    return {"files": files, "count": len(files)}

@app.get("/odds/{filename}")
def get_odds(filename: str):
    return _get_file(DIRS['odds'], filename)


# ===================================================================
# /referees/
# ===================================================================

@app.get("/referees/")
def list_referees():
    files = _list_dir(DIRS['referees'], skip_files={'referee_stats_cache.json'})
    return {"files": files, "count": len(files)}

@app.get("/referees/{filename}")
def get_referees(filename: str):
    return _get_file(DIRS['referees'], filename)


# ===================================================================
# /lineups/
# ===================================================================

@app.get("/lineups/")
def list_lineups():
    files = _list_dir(DIRS['lineups'])
    return {"files": files, "count": len(files)}

@app.get("/lineups/{filename}")
def get_lineups(filename: str):
    return _get_file(DIRS['lineups'], filename)


# ===================================================================
# /context/
# ===================================================================

@app.get("/context/")
def list_context():
    files = _list_dir(DIRS['context'])
    return {"files": files, "count": len(files)}

@app.get("/context/{filename}")
def get_context(filename: str):
    return _get_file(DIRS['context'], filename)


# ===================================================================
# /matches/
# ===================================================================

@app.get("/matches/")
def list_matches():
    files = _list_dir(DIRS['matches'])
    return {"files": files, "count": len(files)}

@app.get("/matches/{filename}")
def get_matches(filename: str):
    return _get_file(DIRS['matches'], filename)


# /news/
@app.get("/news/")
def list_news():
    files = _list_dir(DIRS['news'])
    return {"files": files, "count": len(files)}

@app.get("/news/{filename}")
def get_news(filename: str):
    return _get_file(DIRS['news'], filename)


if __name__ == '__main__':
    print(f"\n  Betting Data API Server")
    for name, path in DIRS.items():
        print(f"  /{name}/  -> {path}")
    print(f"\n  http://localhost:8080/status/")
    print(f"  http://localhost:8080/\n")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
