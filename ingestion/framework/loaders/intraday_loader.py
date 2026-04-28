"""Intraday vendor loader — placeholder (Source H).

TrueData / Global Datafeeds vendor API is not yet integrated.
This stub exists to complete the framework coverage audit and will be
implemented when vendor credentials and API access are available.

Target table: ``fact_intraday`` (does not yet exist in schema — will require
a migration when this loader is implemented).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from ingestion.framework.loaders.base import BaseLoader


class IntradayLoader(BaseLoader):
    """Placeholder loader for intraday vendor data (TrueData / Global Datafeeds).

    Raises ``NotImplementedError`` on every call.

    To implement:
    1. Obtain vendor API credentials and store in environment variables.
    2. Create ``fact_intraday`` table via Alembic migration.
    3. Replace this stub with a real implementation following the
       :class:`~ingestion.framework.loaders.base.BaseLoader` contract.
    """

    def load(self, path: Path, trade_date: date) -> int:
        """Not implemented.

        Raises:
            NotImplementedError: Always. Vendor integration pending.
        """
        raise NotImplementedError(
            "IntradayLoader is a placeholder. "
            "Intraday vendor (TrueData/Global Datafeeds) integration is pending. "
            "Set up vendor credentials and create fact_intraday table first."
        )
