"""MTO (Marketable Trade Orders) parser for NSE delivery data.

Parses NSE MTO files (`MTO_DDMMYYYY.DAT`) into DataFrames ready to T+1 update
fact_eod_price.delivery_qty / delivery_pct. The MTO file is published on T+1
(the day after the trading day) and carries the deliverable-quantity breakdown
of the prior session.

NSE MTO file layout:
    Line 1 : <YYYYMMDD>,NSE,CASH,MTO     (metadata header)
    Line 2 : column-header row           (7 fields)
    Line 3+: data rows, one per security

Header columns:
    Record Type | Sr No | Name of Security | Type | Quantity Traded |
    Deliverable Quantity | % of Deliverable Quantity to Traded Quantity

Usage::

    from ingestion.mto_parser import MTOParser
    parser = MTOParser()
    df = parser.parse("MTO_15012024.DAT", trade_date=date(2024, 1, 15))
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from config.thresholds import get_series_filter

logger = logging.getLogger(__name__)


EXPECTED_HEADER_COLUMNS = {
    "Name of Security",
    "Type",
    "Quantity Traded",
    "Deliverable Quantity",
    "% of Deliverable Quantity to Traded Quantity",
}

METADATA_DATE_FORMAT = "%Y%m%d"


class MTOParseError(Exception):
    """Raised when the MTO file cannot be parsed."""


class MTOParser:
    """Parse NSE MTO .DAT files into delivery DataFrames.

    The output DataFrame matches the columns we need to update
    fact_eod_price: ``trade_date``, ``symbol``, ``delivery_qty``,
    ``delivery_pct``. The series filter is applied so we only keep the
    same series rows the bhavcopy keeps (default EQ / BE / BL / SM / ST).
    """

    def __init__(self, series_filter: list[str] | None = None):
        self.series_filter = set(series_filter or get_series_filter())

    def parse(
        self,
        file_path: str | Path,
        trade_date: date | None = None,
    ) -> pd.DataFrame:
        """Parse an MTO `.DAT` file.

        Args:
            file_path: Path to ``MTO_<DDMMYYYY>.DAT``.
            trade_date: Trading date the file refers to. If ``None``,
                parsed from the metadata line.

        Returns:
            DataFrame with columns
            ``[trade_date, symbol, delivery_qty, delivery_pct]``.

        Raises:
            MTOParseError: on missing file, bad header, empty result.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise MTOParseError(f"MTO file not found: {file_path}")

        with file_path.open() as fh:
            metadata_line = fh.readline().strip()
            header_line = fh.readline().strip()

        if not metadata_line or not header_line:
            raise MTOParseError(f"MTO file truncated: {file_path}")

        meta_date = self._parse_metadata_date(metadata_line, file_path)
        trade_date = trade_date or meta_date

        df = pd.read_csv(file_path, skiprows=1)
        df.columns = df.columns.str.strip()

        missing = EXPECTED_HEADER_COLUMNS - set(df.columns)
        if missing:
            raise MTOParseError(
                f"MTO header validation FAILED for {file_path.name}. "
                f"Missing columns: {sorted(missing)}. Found: {sorted(df.columns)}."
            )

        if df.empty:
            raise MTOParseError(f"MTO file has metadata + header only: {file_path}")

        df["Type"] = df["Type"].astype(str).str.strip()
        original_count = len(df)
        df = df[df["Type"].isin(self.series_filter)].copy()
        if df.empty:
            raise MTOParseError(
                f"Series filter removed ALL rows from {file_path}. "
                f"Expected series {self.series_filter}; found "
                f"{sorted(set(df['Type']))}."
            )

        result = pd.DataFrame({
            "trade_date": trade_date,
            "symbol": df["Name of Security"].astype(str).str.strip(),
            "delivery_qty": pd.to_numeric(
                df["Deliverable Quantity"], errors="coerce"
            ).astype("Int64"),
            "delivery_pct": pd.to_numeric(
                df["% of Deliverable Quantity to Traded Quantity"], errors="coerce"
            ),
        })

        before = len(result)
        result = result.dropna(subset=["symbol", "delivery_qty", "delivery_pct"])
        dropped = before - len(result)
        if dropped:
            logger.warning(
                "MTO %s: dropped %d rows with null delivery fields",
                file_path.name, dropped,
            )

        logger.info(
            "Parsed %s: %d rows (filtered from %d), date=%s",
            file_path.name, len(result), original_count, trade_date,
        )
        return result.reset_index(drop=True)

    @staticmethod
    def _parse_metadata_date(metadata_line: str, file_path: Path) -> date:
        """Pull the trading date out of the metadata header line.

        Expected shape: ``YYYYMMDD,NSE,CASH,MTO``. Falls back to filename
        ``MTO_DDMMYYYY.DAT`` if the metadata line lacks a parseable date.
        """
        parts = metadata_line.split(",")
        if parts and parts[0].strip().isdigit():
            try:
                return datetime.strptime(parts[0].strip(), METADATA_DATE_FORMAT).date()
            except ValueError:
                pass

        stem = file_path.stem
        if stem.startswith("MTO_") and len(stem) >= 12:
            try:
                return datetime.strptime(stem[4:12], "%d%m%Y").date()
            except ValueError:
                pass

        raise MTOParseError(
            f"Cannot determine trade date for {file_path.name}: "
            f"metadata='{metadata_line}'."
        )
