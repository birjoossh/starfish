"""Base abstraction for the ingestion framework loader layer.

Every loader must implement :class:`BaseLoader`. A successful
:meth:`BaseLoader.load` call parses the file at *path*, upserts rows
into the target table, and returns the number of rows inserted/updated.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path


class BaseLoader(ABC):
    """Abstract base class for all ingestion loaders.

    Each loader owns one source file format and one target database table.
    It is responsible for parsing, validating, and upserting data.

    Args:
        None — configuration is injected in concrete subclasses.
    """

    @abstractmethod
    def load(self, path: Path, trade_date: date) -> int:
        """Parse *path* and upsert its contents into the target table.

        Args:
            path: Local path to the source file (CSV or JSON).
            trade_date: The NSE trading date this file represents.

        Returns:
            Number of rows inserted or updated.

        Raises:
            Exception: Any parse or database error propagates to the
                :class:`~ingestion.framework.pipeline.Pipeline` caller.
        """
