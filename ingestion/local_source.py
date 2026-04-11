"""Local file source — fallback when NSE download fails.

Reads bhavcopy CSVs from a local directory instead of downloading from NSE.
Used when the circuit breaker trips or for development/testing.

Usage:
    from ingestion.local_source import LocalSource
    source = LocalSource(Path("/path/to/csvs"))
    filepath = source.get_bhavcopy(date(2024, 1, 15))
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


class LocalSource:
    """Read bhavcopy CSVs from a local directory.

    Directory structure: flat or YYYY/MON/ pattern matching NSE layout.
    Filenames must match NSE convention: cm<DD><MON><YYYY>bhav.csv
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Local data directory not found: {self.data_dir}")

    def get_bhavcopy(self, trade_date: date) -> Path:
        """Find and return the bhavcopy CSV for a given date.

        Searches for files matching the NSE naming convention.
        """
        # Try exact NSE naming patterns
        patterns = [
            f"cm{trade_date.strftime('%d%b%Y').upper()}bhav.csv",
            f"cm{trade_date.strftime('%d%b%Y').upper()}bhav.csv.zip",
            f"sec_bhavdata_full_{trade_date.strftime('%Y%m%d')}.csv",
            f"bhav_{trade_date.strftime('%Y%m%d')}.csv",
        ]

        for pattern in patterns:
            # Search recursively
            matches = list(self.data_dir.rglob(pattern))
            if matches:
                logger.info(f"Found local file: {matches[0]}")
                return matches[0]

        raise FileNotFoundError(
            f"No bhavcopy found for {trade_date} in {self.data_dir}. "
            f"Searched for: {patterns}"
        )

    def list_available_dates(self) -> list[date]:
        """List all dates with available bhavcopy files."""
        dates = []
        for csv_file in self.data_dir.rglob("*.csv"):
            # Try to extract date from filename
            name = csv_file.stem
            # cm15JAN2024bhav format
            if name.startswith("cm") and name.endswith("bhav"):
                date_part = name[2:-5]  # "15JAN2024"
                try:
                    from datetime import datetime
                    d = datetime.strptime(date_part, "%d%b%Y").date()
                    dates.append(d)
                except ValueError:
                    continue
        return sorted(dates)
