"""Local filesystem fetcher — fallback when HTTP download is unavailable.

Scans a configured source directory for files matching the source's filename
templates. Raises :class:`FetchError` if no match is found.

Each source declares its own filename templates (via :class:`SourceSpec` in
``run_pipeline.py``) so the fetcher does NOT cross-match files belonging to
other sources. For example, ``--source dim-stock`` will only look for
``NSE_CM_security_*.csv``, never for ``sec_bhavdata_full_*.csv``.

Templates may contain the following ``str.format`` placeholders:
    {ddmmyyyy}   — e.g. ``27042026``
    {yyyymmdd}   — e.g. ``20260427``
    {ddmonyyyy}  — e.g. ``27APR2026`` (legacy bhavcopy)

If no templates are passed, a permissive default set is used (covers the
historical pre-source-spec behaviour).
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from ingestion.framework.fetchers.base import BaseFetcher, FetchError

logger = logging.getLogger(__name__)


# Backwards-compatible default — used only when no patterns are passed.
# Kept narrow on purpose; new code should always pass explicit patterns
# via the SourceSpec registry.
_DEFAULT_PATTERNS: tuple[str, ...] = (
    "sec_bhavdata_full_{ddmmyyyy}.csv",
    "CM_52_wk_High_low_{ddmmyyyy}.csv",
    "cm{ddmonyyyy}bhav.csv",
    "ind_nifty50list.csv",
    "*{ddmmyyyy}*.csv",
)


class LocalFetcher(BaseFetcher):
    """Fetch a trading-day file from a local directory.

    Useful when NSE HTTP downloads are unavailable or blocked, or during
    development when files are dropped manually into ``data/raw/<source>/``.

    Args:
        source_dir: Directory to search. Must exist at construction time.
        patterns: Optional list of glob templates. Each template may contain
            ``{ddmmyyyy}``, ``{yyyymmdd}``, ``{ddmonyyyy}`` placeholders.
            Defaults to a permissive multi-source list (legacy behaviour).

    Raises:
        FetchError: At construction if ``source_dir`` does not exist.
    """

    def __init__(
        self,
        source_dir: Path,
        patterns: Optional[Iterable[str]] = None,
    ) -> None:
        source_dir = Path(source_dir)
        if not source_dir.exists():
            raise FetchError(
                f"Local source directory does not exist: {source_dir}"
            )
        self.source_dir = source_dir
        self.patterns: tuple[str, ...] = (
            tuple(patterns) if patterns is not None else _DEFAULT_PATTERNS
        )

    def fetch(self, trade_date: date) -> Path:
        """Return the local file path for *trade_date*.

        Args:
            trade_date: The NSE trading date to look up.

        Returns:
            Path to the found file.

        Raises:
            FetchError: If no matching file is found in ``source_dir``.
        """
        substitutions = {
            "ddmmyyyy": trade_date.strftime("%d%m%Y"),
            "yyyymmdd": trade_date.strftime("%Y%m%d"),
            "ddmonyyyy": trade_date.strftime("%d") + trade_date.strftime("%b").upper()
                          + trade_date.strftime("%Y"),
        }
        resolved = [p.format(**substitutions) for p in self.patterns]

        for pattern in resolved:
            matches = sorted(self.source_dir.glob(pattern))
            if matches:
                logger.info(
                    "LocalFetcher: found %s for %s (pattern: %s)",
                    matches[0].name, trade_date, pattern,
                )
                return matches[0]

        raise FetchError(
            f"No file found for {trade_date} in {self.source_dir}. "
            f"Searched patterns: {resolved}"
        )


class FixedFileFetcher(BaseFetcher):
    """Fetcher that always returns a single user-supplied file path.

    Used by ``--local-file PATH`` to bypass date-based file lookup entirely.
    The trade_date argument is ignored — the same path is returned regardless,
    so the caller is responsible for passing a date that matches the file's
    actual content.

    Args:
        path: Path to the file to return on every :meth:`fetch` call.

    Raises:
        FetchError: At construction if ``path`` does not exist.
    """

    def __init__(self, path: Path) -> None:
        path = Path(path)
        if not path.exists():
            raise FetchError(f"--local-file path does not exist: {path}")
        if not path.is_file():
            raise FetchError(f"--local-file path is not a regular file: {path}")
        self.path = path

    def fetch(self, trade_date: date) -> Path:  # noqa: ARG002 — date intentionally ignored
        logger.info("FixedFileFetcher: using %s for %s", self.path, trade_date)
        return self.path
