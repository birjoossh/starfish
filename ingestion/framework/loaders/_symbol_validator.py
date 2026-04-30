"""Pre-load symbol validation for corporate-event loaders.

The legacy :class:`ingestion.corporate_events_loader.CorporateEventsLoader`
inserts each event row inside a single transaction. Any FK violation
(``fact_corporate_event_symbol_fkey`` — symbol not in ``dim_stock``) aborts
the whole transaction. To stay resilient to symbols that NSE publishes for
non-EQ instruments (REITs, InvITs like ``INDUSINVIT``, etc.) which never
land in ``dim_stock``, we **pre-validate** the classified DataFrame against
``dim_stock.symbol`` and route unknown-symbol rows to a JSON bad-records
file before the legacy loader sees them.

This keeps the legacy code untouched and avoids per-row savepoints.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
from sqlalchemy import text

from ingestion.framework.json_bad_records import JsonBadRecordsWriter
from ingestion.framework.loaders._event_json_adapter import (
    _coalesce, _records_from_json,
)

logger = logging.getLogger(__name__)


def fetch_known_symbols(engine) -> set[str]:
    """Return the set of all symbols in ``dim_stock`` (uppercased)."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT symbol FROM dim_stock"))
        # Defensive: result rows are Row objects; index 0 is the symbol col.
        return {str(r[0]).strip().upper() for r in rows if r[0] is not None}


def filter_unknown_symbols(
    df: pd.DataFrame,
    known_symbols: set[str],
    *,
    json_source_path: Optional[Path],
    bad_records_writer: Optional[JsonBadRecordsWriter],
    reason: str = "symbol not in dim_stock (FK violation would occur)",
) -> pd.DataFrame:
    """Drop rows whose ``symbol`` is not in *known_symbols*.

    If *bad_records_writer* and *json_source_path* are both provided, the
    **original JSON records** for the dropped symbols are written to the
    bad-records file (preserving the source format the operator originally
    received from NSE).

    Args:
        df: Classified events DataFrame. Must have a ``symbol`` column.
        known_symbols: Uppercased set of valid ``dim_stock.symbol`` values.
        json_source_path: Path to the original NSE JSON file. Used to look
            up the original records for dropped symbols. ``None`` for CSV
            sources or unit tests that don't care about JSON pass-through.
        bad_records_writer: Where to persist the dropped originals. ``None``
            disables bad-records writing (rows are still dropped).
        reason: Free-text reason stamped into each bad record.

    Returns:
        The DataFrame with unknown-symbol rows removed.
    """
    if df is None or df.empty:
        return df

    if "symbol" not in df.columns:
        # Nothing to validate against — pass through unchanged.
        logger.debug("filter_unknown_symbols: no 'symbol' column; skipping")
        return df

    df_symbols = df["symbol"].astype(str).str.strip().str.upper()
    bad_mask = ~df_symbols.isin(known_symbols)
    n_bad = int(bad_mask.sum())
    if n_bad == 0:
        return df

    bad_symbols = set(df_symbols[bad_mask].unique())
    logger.warning(
        "filter_unknown_symbols: dropping %d row(s) across %d symbol(s) "
        "not in dim_stock: %s",
        n_bad, len(bad_symbols),
        sorted(bad_symbols)[:10] + (["..."] if len(bad_symbols) > 10 else []),
    )

    # Persist the original JSON records (not the classified DataFrame rows)
    # so the bad-records file matches the format the operator received.
    if (
        bad_records_writer is not None
        and json_source_path is not None
        and json_source_path.exists()
        and json_source_path.suffix.lower() == ".json"
    ):
        try:
            originals = _select_originals_for_symbols(json_source_path, bad_symbols)
            bad_records_writer.write(
                originals,
                original_filename=json_source_path.name,
                reason=reason,
            )
        except Exception as exc:  # noqa: BLE001 — diagnostic, never fatal
            logger.error(
                "filter_unknown_symbols: failed to write JSON bad records "
                "for %s: %s", json_source_path.name, exc,
            )

    return df[~bad_mask].reset_index(drop=True)


def _select_originals_for_symbols(
    json_path: Path, target_symbols: Iterable[str]
) -> list[dict]:
    """Return original JSON records whose symbol is in *target_symbols*."""
    targets = {s.upper() for s in target_symbols}
    out: list[dict] = []
    for rec in _records_from_json(json_path):
        sym = _coalesce(rec, "symbol", "scrip", "ticker").upper()
        if sym and sym in targets:
            out.append(rec)
    return out
