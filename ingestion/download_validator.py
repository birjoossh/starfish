"""Corrupted-download validation for NSE archive files.

NSE occasionally serves truncated or HTML-error files. Without a gate, those
files slip into the parser and either fail loudly mid-pipeline or — worse —
parse as a tiny set of rows that silently degrades signal quality.

This module exposes:

* :func:`validate_bhavcopy_size` — row-count + byte-size sanity for the daily
  bhavcopy CSV. A bhavcopy with < ~1500 data rows is almost certainly truncated
  (NSE publishes ~2500+ rows on a normal trading day).
* :func:`validate_against_reference` — compare against a prior-day reference
  file; reject if the new file is < 70 % of the reference's data rows.
* :func:`file_sha256` — cheap content fingerprint used for cache validation.

Pure functions; raises :class:`DownloadValidationError` on failure.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


MIN_BHAVCOPY_BYTES = 100_000
MIN_BHAVCOPY_DATA_ROWS = 1500
MIN_RATIO_VS_REFERENCE = 0.70


class DownloadValidationError(Exception):
    """Raised when a downloaded file fails sanity checks."""


@dataclass(frozen=True)
class FileStats:
    """Lightweight stats about a downloaded file."""
    path: Path
    size_bytes: int
    data_rows: int


def _count_data_rows(path: Path) -> int:
    """Count non-empty non-header lines. Header detection is conservative:
    we assume the first line is a header if it has no digits, otherwise
    we treat everything as data and return ``line_count - 1`` as a floor.
    """
    with path.open(errors="replace") as fh:
        first = fh.readline()
        if not first:
            return 0
        is_header = not any(ch.isdigit() for ch in first)
        rows = sum(1 for line in fh if line.strip())
        return rows if is_header else rows + 1


def file_stats(path: str | Path) -> FileStats:
    """Compute ``FileStats(size_bytes, data_rows)`` for ``path``."""
    path = Path(path)
    if not path.exists():
        raise DownloadValidationError(f"File not found: {path}")
    return FileStats(
        path=path,
        size_bytes=path.stat().st_size,
        data_rows=_count_data_rows(path),
    )


def file_sha256(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """Return the SHA-256 hex digest of ``path``."""
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_bhavcopy_size(
    path: str | Path,
    *,
    min_bytes: int = MIN_BHAVCOPY_BYTES,
    min_rows: int = MIN_BHAVCOPY_DATA_ROWS,
) -> FileStats:
    """Raise if the bhavcopy at ``path`` is too small to be trustworthy.

    Args:
        path: Bhavcopy CSV to validate.
        min_bytes: Minimum file size. Defaults to 100 KB — anything smaller
            is almost certainly an NSE error page or truncated download.
        min_rows: Minimum non-header rows. Defaults to 1500 — NSE publishes
            ~2500+ EQ-series symbols per session.

    Returns:
        :class:`FileStats` on success.
    """
    stats = file_stats(path)
    if stats.size_bytes < min_bytes:
        raise DownloadValidationError(
            f"Bhavcopy {stats.path.name} is only {stats.size_bytes} bytes "
            f"(< {min_bytes}). Likely truncated or an error page."
        )
    if stats.data_rows < min_rows:
        raise DownloadValidationError(
            f"Bhavcopy {stats.path.name} has only {stats.data_rows} data rows "
            f"(< {min_rows}). Likely truncated."
        )
    logger.info(
        "validate_bhavcopy_size OK: %s — %d bytes, %d rows",
        stats.path.name, stats.size_bytes, stats.data_rows,
    )
    return stats


def validate_against_reference(
    candidate: str | Path,
    reference: str | Path,
    *,
    min_ratio: float = MIN_RATIO_VS_REFERENCE,
) -> FileStats:
    """Reject ``candidate`` if its row count is < ``min_ratio`` × reference.

    Used to catch silent partial downloads: the candidate parses cleanly but
    has, say, 600 rows vs the prior day's 2600.

    Args:
        candidate: Newly downloaded file under test.
        reference: Trusted prior-day file (typically yesterday's bhavcopy).
        min_ratio: Minimum row-count ratio. Defaults to 0.70 — 30 % drop is
            our outer bound for normal market days (holidays excluded
            upstream).

    Returns:
        :class:`FileStats` for the candidate on success.
    """
    cand = file_stats(candidate)
    ref = file_stats(reference)
    if ref.data_rows == 0:
        raise DownloadValidationError(
            f"Reference file {ref.path.name} has zero data rows — cannot compare."
        )
    ratio = cand.data_rows / ref.data_rows
    if ratio < min_ratio:
        raise DownloadValidationError(
            f"{cand.path.name}: {cand.data_rows} rows is "
            f"only {ratio:.0%} of reference {ref.path.name} ({ref.data_rows} rows). "
            f"Below {min_ratio:.0%} threshold — likely truncated."
        )
    logger.info(
        "validate_against_reference OK: %s (%d) vs %s (%d) — %.0f%%",
        cand.path.name, cand.data_rows, ref.path.name, ref.data_rows, ratio * 100,
    )
    return cand
