"""JSON bad-records writer — captures dropped JSON records.

Companion to :class:`ingestion.framework.bad_records.BadRecordsWriter`, but
preserves the *original* JSON record shape rather than re-encoding to CSV.

This is needed for the corporate-event pipelines (event-calendar,
announcements) which receive their data as nested JSON arrays from NSE — a
CSV bad-records file would lose the original field structure that operators
rely on for re-ingestion or vendor follow-up.

Output format::

    logs/<source>/bad_records/<original_filename>

is a JSON array. Each entry is the verbatim NSE record plus a ``_drop_reason``
key explaining why it was filtered out. Subsequent writes to the same path
*append* to the existing array (so multiple drop-causes in one run produce
a single consolidated file).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


class JsonBadRecordsWriter:
    """Persist dropped JSON records to ``logs/<source>/bad_records/<filename>``.

    Args:
        source: Source name (matches :class:`SourceSpec.name`,
            e.g. ``"event-calendar"``).
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
        records: Iterable[dict],
        original_filename: str,
        reason: str = "",
    ) -> Optional[Path]:
        """Write *records* (with reason) to ``log_dir/<original_filename>``.

        Args:
            records: The original JSON dicts that were dropped. If empty,
                nothing is written and ``None`` is returned.
            original_filename: Source filename being processed; reused
                verbatim as the bad-records filename so operators can
                correlate by name. Forced to ``.json`` extension.
            reason: Free-text explanation. Stamped into each record as
                ``_drop_reason``.

        Returns:
            Path written to, or ``None`` if there were no records.
        """
        records = list(records)
        if not records:
            return None

        # Force .json extension so the file is unambiguously machine-readable.
        name = original_filename
        if not name.lower().endswith(".json"):
            stem = Path(name).stem
            name = f"{stem}.json"

        self.log_dir.mkdir(parents=True, exist_ok=True)
        out = self.log_dir / name

        # Stamp the reason on each record (non-destructive copy so the
        # caller's dicts aren't mutated).
        stamped = [{**rec, "_drop_reason": reason} for rec in records]

        # Append-on-existing: read the existing array (if any), extend, rewrite.
        if out.exists():
            try:
                existing = json.loads(out.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    logger.warning(
                        "JsonBadRecordsWriter[%s]: %s exists but is not a JSON "
                        "array — overwriting", self.source, out,
                    )
                    existing = []
            except json.JSONDecodeError:
                logger.warning(
                    "JsonBadRecordsWriter[%s]: %s exists but is malformed JSON "
                    "— overwriting", self.source, out,
                )
                existing = []
            existing.extend(stamped)
            payload = existing
        else:
            payload = stamped

        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                       encoding="utf-8")

        logger.warning(
            "JsonBadRecordsWriter[%s]: wrote %d bad records → %s (reason: %s)",
            self.source, len(stamped), out, reason,
        )
        return out
