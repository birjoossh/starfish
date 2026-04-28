"""Base abstractions for the ingestion framework fetcher layer.

Every fetcher — HTTP, local, or hybrid — must implement :class:`BaseFetcher`.
A successful :meth:`BaseFetcher.fetch` call returns a local ``Path`` to the
downloaded/found file. On any failure the fetcher raises :class:`FetchError`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path


class FetchError(Exception):
    """Raised when a fetcher cannot obtain the requested file.

    Both :class:`NseHttpFetcher` and :class:`LocalFetcher` raise this so that
    :class:`HybridFetcher` can catch it uniformly.
    """


class BaseFetcher(ABC):
    """Abstract base class for all ingestion fetchers.

    Implementors must provide :meth:`fetch` which accepts a trading date and
    returns the local path to a ready-to-parse file.

    Args:
        None — configuration is injected in concrete subclasses.
    """

    @abstractmethod
    def fetch(self, trade_date: date) -> Path:
        """Obtain the source file for *trade_date*.

        Args:
            trade_date: The NSE trading date for which data is needed.

        Returns:
            Path to a local file that can be opened for parsing.

        Raises:
            FetchError: If the file cannot be obtained from any source.
        """
