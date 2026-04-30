"""Bad-records writer — captures rows dropped during parsing.

When a loader silently drops rows (e.g. missing required fields, dedupe,
malformed values), the dropped rows are written to a CSV at::

    logs/<source>/bad_records/<original_filename>.csv

so the operator can inspect them after the fact. This is purely diagnostic
— the loader does not block on bad records.

Usage::

    writer = BadRecordsWriter(source="dim-stock")
    # inside loader._parse(...)
    bad = df[df["isin"].isna()]
    df = df.dropna(subset=["isin"])
    writer.write(bad, original_filename=path.name, reason="missing isin")
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class BadRecordsWriter:
    """Persist dropped rows to ``logs/<source>/bad_records/<filename>.csv``.

    Args:
        source: Source name (matches :class:`SourceSpec.name`, e.g. ``"dim-stock"``).
        log_dir: Override the destination directory. Defaults to
            ``<project_root>/logs/<source>/bad_records/``.
    """

    def __init__(self, source: str, log_dir: Optional[Path] = None) -> None:
        self.source = source
        if log_dir is None:
            from config.settings import settings
            log_dir = settings.project_root / "logs" / source / "bad_records"
        self.log_dir = Path(log_dir)

    def write(
        self,
        df: pd.DataFrame,
        original_filename: str,
        reason: str = "",
    ) -> Optional[Path]:
        """Write *df* to ``log_dir/<original_filename>.csv``.

        Args:
            df: Rows dropped from the main pipeline. If empty, nothing is
                written and ``None`` is returned.
            original_filename: Source filename being processed; used as the
                bad-records filename (``.csv`` appended if missing).
            reason: Free-text explanation written to the log line for context.

        Returns:
            Path to the written file, or ``None`` if *df* was empty.
        """
        if df is None or df.empty:
            return None

        self.log_dir.mkdir(parents=True, exist_ok=True)
        # Mirror the original filename so operators can correlate easily.
        # If original already ends with .csv we keep it; else append.
        name = original_filename
        if not name.lower().endswith(".csv"):
            name = f"{name}.csv"
        out = self.log_dir / name

        # Append reason as a column so multiple drop-causes per file are visible.
        out_df = df.copy()
        if "_drop_reason" not in out_df.columns:
            out_df["_drop_reason"] = reason

        # If file already exists (e.g. multiple drop calls on same file in one
        # run), append without re-writing the header.
        if out.exists():
            out_df.to_csv(out, mode="a", header=False, index=False)
        else:
            out_df.to_csv(out, mode="w", header=True, index=False)

        logger.warning(
            "BadRecordsWriter[%s]: wrote %d bad records → %s (reason: %s)",
            self.source, len(out_df), out, reason,
        )
        return out
