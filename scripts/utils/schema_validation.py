"""Schema validation helper for v2 builders.

Every v2 builder calls `validate_or_partial(payload, schema_name)` before
writing the JSON. On validation failure the payload is marked `_partial: true`
and the error is appended to the in-memory run log for `_run_log.json`.

Dependency: `jsonschema` (added to requirements.txt in v2).
"""

import json
import os
from typing import Tuple

try:
    import jsonschema
    _HAVE_JSONSCHEMA = True
except ImportError:
    _HAVE_JSONSCHEMA = False

SCHEMAS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "schemas",
)

_SCHEMA_CACHE: dict = {}


def _load_schema(name: str) -> dict:
    """Load a schema and resolve local $refs against the schemas/ directory."""
    if name in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[name]
    path = os.path.join(SCHEMAS_DIR, name)
    with open(path) as f:
        schema = json.load(f)
    _SCHEMA_CACHE[name] = schema
    return schema


def _build_store() -> dict:
    """Pre-load every schema in schemas/ keyed by both its $id and its filename.

    This stops the resolver from trying to fetch remote URLs declared in $id.
    """
    store: dict = {}
    for fname in os.listdir(SCHEMAS_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(SCHEMAS_DIR, fname)) as f:
            schema = json.load(f)
        # Key by both forms so $ref "_enums.json#/..." (relative) and the
        # absolute $id form both resolve
        if "$id" in schema:
            store[schema["$id"]] = schema
        store[fname] = schema
    return store


_STORE_CACHE: dict = None  # type: ignore


def validate_payload(payload: dict, schema_name: str) -> Tuple[bool, str]:
    """Return (ok, error_message). If jsonschema is not installed, return (True, '').

    schema_name examples: "match_context.schema.json", "team_snapshot.schema.json".
    """
    global _STORE_CACHE
    if not _HAVE_JSONSCHEMA:
        return True, ""
    try:
        schema = _load_schema(schema_name)
    except FileNotFoundError as e:
        return False, f"schema not found: {e}"

    if _STORE_CACHE is None:
        _STORE_CACHE = _build_store()

    base_uri = schema.get("$id", "file://" + SCHEMAS_DIR.rstrip("/") + "/")
    resolver = jsonschema.RefResolver(
        base_uri=base_uri,
        referrer=schema,
        store=_STORE_CACHE,
    )

    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema, resolver=resolver)

    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if not errors:
        return True, ""

    # Compact error message
    first = errors[0]
    path = "/".join(str(p) for p in first.absolute_path) or "<root>"
    return False, f"{path}: {first.message}"


def validate_or_partial(payload: dict, schema_name: str) -> dict:
    """Validate. If invalid, set `_partial = True` and add `_schema_error`.

    The builder still writes the payload — but downstream consumers can see
    it was not fully valid (brief §4 failure handling).
    """
    ok, err = validate_payload(payload, schema_name)
    if ok:
        return payload
    payload = dict(payload)  # don't mutate caller's reference
    payload["_partial"] = True
    payload["_schema_error"] = err
    return payload
