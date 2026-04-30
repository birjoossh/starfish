"""JSON → CSV-shape adapter for NSE corporate-event feeds.

The legacy :class:`ingestion.corporate_events_ingestor.CorporateEventsIngestor`
reads CSV via ``pandas.read_csv`` and column-detects ``symbol`` / ``purpose``
/ ``date``. The actual NSE feeds for ``event-calendar`` and
``corporate-announcements`` are JSON arrays with completely different field
names per source. Rather than modify the legacy ingestor, this module
normalizes either JSON shape into a small CSV file (in a temp directory)
that the existing ingestor can consume unchanged.

Two NSE JSON shapes are supported:

**Event Calendar** (``https://www.nseindia.com/api/event-calendar``)::

    [{"symbol": "ACCELYA", "company": "...", "purpose": "Financial Results",
      "bm_desc": "To consider and approve...", "date": "29-Apr-2026"}, ...]

**Corporate Announcements** (``https://www.nseindia.com/api/corporate-announcements``)::

    [{"symbol": "AWL", "desc": "Investor Presentation",
      "an_dt": "28-Apr-2026 21:02:06", "sort_date": "2026-04-28 21:02:06",
      "attchmntText": "...", ...}, ...]

Both are mapped to a 3-column CSV (``symbol``, ``purpose``, ``date``) — the
exact columns the ingestor's column-detection logic looks for.
"""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _records_from_json(path: Path) -> list[dict]:
    """Load a JSON file expected to contain a list of dicts.

    Tolerates two minor variants:
        - A bare JSON array at the top level.
        - An object with a ``data`` (or ``records``) key holding the array.
    """
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "records", "rows"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    raise ValueError(
        f"{path.name}: expected JSON array or {{'data': [...]}}, got {type(payload).__name__}"
    )


def _coalesce(record: dict, *keys: str) -> str:
    """Return the first non-empty string value from *record* among *keys*."""
    for k in keys:
        v = record.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s and s.lower() not in ("nan", "null", "none", "-"):
            return s
    return ""


def _strip_time(date_str: str) -> str:
    """Strip a trailing ``HH:MM:SS`` from a datetime-ish string.

    NSE announcements use ``"28-Apr-2026 21:02:06"`` — the time portion would
    confuse the ingestor's date parser, which only knows date-only formats.
    """
    return date_str.split(" ", 1)[0] if " " in date_str else date_str


def event_calendar_json_to_rows(path: Path) -> list[dict]:
    """Normalize an event-calendar JSON file into ingestor-shape rows.

    Each output row has keys: ``symbol``, ``purpose``, ``date``.
    Rows missing a symbol are skipped — they cannot be classified.
    """
    out: list[dict] = []
    for rec in _records_from_json(path):
        symbol = _coalesce(rec, "symbol", "scrip", "ticker").upper()
        if not symbol:
            continue
        # Prefer the richer free-text description (``bm_desc``) when present;
        # ``purpose`` is the short label.
        bm_desc = _coalesce(rec, "bm_desc")
        short = _coalesce(rec, "purpose", "subject")
        if bm_desc and short and bm_desc.lower() != short.lower():
            purpose = f"{short} — {bm_desc}"
        else:
            purpose = bm_desc or short
        out.append({
            "symbol":  symbol,
            "purpose": purpose,
            "date":    _coalesce(rec, "date", "event_date", "ex_date"),
        })
    return out


def announcements_json_to_rows(path: Path) -> list[dict]:
    """Normalize a corporate-announcements JSON file into ingestor-shape rows.

    Each output row has keys: ``symbol``, ``purpose``, ``date``.
    """
    out: list[dict] = []
    for rec in _records_from_json(path):
        symbol = _coalesce(rec, "symbol", "scrip", "ticker").upper()
        if not symbol:
            continue
        desc = _coalesce(rec, "desc", "subject")
        text = _coalesce(rec, "attchmntText", "attachmentText")
        if desc and text and desc.lower() not in text.lower():
            purpose = f"{desc} — {text}"
        else:
            purpose = text or desc
        # ``an_dt`` and ``sort_date`` carry a trailing time component the
        # ingestor's date parser can't handle — strip it.
        date_str = _coalesce(rec, "an_dt", "sort_date", "date")
        out.append({
            "symbol":  symbol,
            "purpose": purpose,
            "date":    _strip_time(date_str),
        })
    return out


def write_rows_as_csv(rows: Iterable[dict], out_path: Path) -> Path:
    """Write *rows* as a 3-column CSV at *out_path*. Empty input → header-only.

    Returns the path written to.
    """
    df = pd.DataFrame(list(rows), columns=["symbol", "purpose", "date"])
    df.to_csv(out_path, index=False)
    return out_path


def json_to_temp_csv(path: Path, kind: str, dest_dir: Optional[Path] = None) -> Path:
    """Convert *path* (NSE event JSON) to a temp CSV the ingestor can read.

    Args:
        path: The JSON source file.
        kind: ``"event_calendar"`` or ``"announcements"`` — picks the field
            mapping. Anything else raises ``ValueError``.
        dest_dir: Optional directory to place the temp CSV in. Defaults to the
            system temp dir. The caller owns cleanup.

    Returns:
        Path to the temp CSV.
    """
    if kind == "event_calendar":
        rows = event_calendar_json_to_rows(path)
    elif kind == "announcements":
        rows = announcements_json_to_rows(path)
    else:
        raise ValueError(f"Unknown kind={kind!r}; expected 'event_calendar' or 'announcements'")

    base_dir = dest_dir or Path(tempfile.gettempdir())
    base_dir.mkdir(parents=True, exist_ok=True)
    # Reuse the source filename stem so logs/bad-records keep the original
    # provenance, but with .csv extension.
    out = base_dir / f"{path.stem}.csv"
    write_rows_as_csv(rows, out)
    logger.debug(
        "Converted %s (kind=%s) → %s with %d rows",
        path.name, kind, out, len(rows),
    )
    return out
