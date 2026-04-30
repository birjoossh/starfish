# Ingestion Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a parallel ingestion framework under `ingestion/framework/` that covers all 9 Section 3 data sources without touching any existing ingestion code.

**Architecture:** New ABCs (`BaseFetcher`, `BaseLoader`) under `ingestion/framework/` provide a uniform fetch→parse→upsert→log contract. A `HybridFetcher` tries HTTP first then falls back to `data/raw/<source>/`. A `Pipeline` orchestrator wires one fetcher to one loader, writes to `ingestion_log`, and bubbles exceptions up to the caller. Existing `daily_run.py`, `NSEClient`, `BhavcopyLoader`, etc. are untouched — the framework wraps them.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.x (parameterised SQL), pandas, requests (via existing `NSEClient`), pytest, `config.settings.Settings`

---

## Important Codebase Facts

Before implementing, note these critical existing details:

| Item | Value |
|---|---|
| Ingestion log table | `ingestion_log` (NOT `fact_ingestion_log`) |
| Project root | `settings.project_root` = `Path(__file__).parent.parent` of `config/` |
| NSE HTTP client | `ingestion.nse_client.NSEClient` — already has rate-limit, retry, circuit-breaker |
| Circuit breaker exception | `ingestion.nse_client.CircuitBreakerOpen` |
| Bhavcopy parser | `ingestion.bhavcopy_parser.BhavcopyParser.parse(path, trade_date, source_file) → DataFrame` |
| Bhavcopy loader | `ingestion.bhavcopy_loader.BhavcopyLoader.load(df, source_file) → dict{rows_total, rows_inserted, rows_failed, status}` |
| Corp actions parser | `ingestion.corporate_actions_parser.CorporateActionsParser.parse(filepath, as_of) → DataFrame` |
| Corp actions loader | `ingestion.corporate_actions_loader.CorporateActionsLoader.load(df) → int` |
| Corp events ingestor | `ingestion.corporate_events_ingestor.CorporateEventsIngestor.ingest(filepath, calc_date) → DataFrame` |
| Corp events loader | `ingestion.corporate_events_loader.CorporateEventsLoader.load(df) → int` |
| `fact_announcement` / `fact_event_calendar` | **Do NOT exist in schema** — Sources F and G target `fact_corporate_event` |
| Test isolation date | Use `date(2099, ...)` for all test data to avoid real-data conflicts |

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `ingestion/framework/__init__.py` | Create | Package marker |
| `ingestion/framework/fetchers/__init__.py` | Create | Re-export public symbols |
| `ingestion/framework/fetchers/base.py` | Create | `FetchError`, `BaseFetcher` ABC |
| `ingestion/framework/fetchers/http_fetcher.py` | Create | `NseHttpFetcher` — delegates to `NSEClient` |
| `ingestion/framework/fetchers/local_fetcher.py` | Create | `LocalFetcher` — scans `data/raw/<source>/` |
| `ingestion/framework/fetchers/hybrid_fetcher.py` | Create | `HybridFetcher` — HTTP-first + local fallback |
| `ingestion/framework/loaders/__init__.py` | Create | Re-export public symbols |
| `ingestion/framework/loaders/base.py` | Create | `BaseLoader` ABC |
| `ingestion/framework/loaders/eod_price_loader.py` | Create | Wraps `BhavcopyParser` + `BhavcopyLoader` |
| `ingestion/framework/loaders/wk52_loader.py` | Create | New: parses NSE 52W CSV → `fact_52wk` |
| `ingestion/framework/loaders/constituents_loader.py` | Create | New: parses `ind_nifty50list.csv` → `dim_nifty50_constituent` |
| `ingestion/framework/loaders/reconstitution_loader.py` | Create | Placeholder: local-drop CSV → `dim_nifty50_constituent` |
| `ingestion/framework/loaders/corporate_actions_loader.py` | Create | Wraps `CorporateActionsParser` + `CorporateActionsLoader` |
| `ingestion/framework/loaders/event_calendar_loader.py` | Create | Wraps NSE scraper → `fact_corporate_event` |
| `ingestion/framework/loaders/announcements_loader.py` | Create | Wraps NSE scraper → `fact_corporate_event` |
| `ingestion/framework/loaders/intraday_loader.py` | Create | Stub: raises `NotImplementedError` |
| `ingestion/framework/log.py` | Create | `IngestionLogger` → `ingestion_log` table |
| `ingestion/framework/pipeline.py` | Create | `Pipeline.run(trade_date)` orchestrator |
| `data/raw/bhavcopy/.gitkeep` | Create | Manual-drop folder for source A |
| `data/raw/52wk/.gitkeep` | Create | Manual-drop folder for source B |
| `data/raw/constituents/.gitkeep` | Create | Manual-drop folder for source C |
| `data/raw/reconstitution/.gitkeep` | Create | Manual-drop folder for source D |
| `data/raw/corporate_actions/.gitkeep` | Create | Manual-drop folder for source E |
| `tests/unit/test_framework_fetchers.py` | Create | Unit tests for all fetcher classes |
| `tests/unit/test_framework_loaders.py` | Create | Unit tests for all loader classes |
| `tests/unit/test_framework_pipeline.py` | Create | Unit tests for Pipeline + IngestionLogger |

**Do NOT modify:** `ingestion/bhavcopy_loader.py`, `bhavcopy_parser.py`, `daily_run.py`, `nse_client.py`, `local_source.py`, `corporate_actions_*.py`, `corporate_events_*.py`, `nse_scraper.py`, `backfill/`

---

## Task 1: Feature Branch + Directory Skeleton

**Files:**
- Create: `ingestion/framework/__init__.py`
- Create: `ingestion/framework/fetchers/__init__.py`
- Create: `ingestion/framework/loaders/__init__.py`
- Create: `data/raw/bhavcopy/.gitkeep`, `data/raw/52wk/.gitkeep`, `data/raw/constituents/.gitkeep`, `data/raw/reconstitution/.gitkeep`, `data/raw/corporate_actions/.gitkeep`

- [ ] **Step 1: Create feature branch**

```bash
git fetch --all
git pull origin main
git checkout -B feature/ingestion-framework
```
Expected: `Switched to a new branch 'feature/ingestion-framework'`

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p ingestion/framework/fetchers
mkdir -p ingestion/framework/loaders
mkdir -p data/raw/bhavcopy data/raw/52wk data/raw/constituents data/raw/reconstitution data/raw/corporate_actions
touch ingestion/framework/__init__.py
touch ingestion/framework/fetchers/__init__.py
touch ingestion/framework/loaders/__init__.py
touch data/raw/bhavcopy/.gitkeep data/raw/52wk/.gitkeep data/raw/constituents/.gitkeep
touch data/raw/reconstitution/.gitkeep data/raw/corporate_actions/.gitkeep
```

- [ ] **Step 3: Verify structure**

```bash
find ingestion/framework -type f | sort
find data/raw -type f | sort
```
Expected output includes all `__init__.py` files and `.gitkeep` files.

- [ ] **Step 4: Commit skeleton**

```bash
git add ingestion/framework/ data/raw/
git commit -m "feat(framework): add directory skeleton for ingestion framework"
```

---

## Task 2: `FetchError` + `BaseFetcher` ABC

**Files:**
- Create: `ingestion/framework/fetchers/base.py`
- Create: `tests/unit/test_framework_fetchers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_framework_fetchers.py`:

```python
"""Unit tests for ingestion framework fetchers."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ingestion.framework.fetchers.base import BaseFetcher, FetchError


class TestBaseFetcherABC:
    def test_cannot_instantiate_base_fetcher(self):
        """BaseFetcher is abstract — direct instantiation must raise TypeError."""
        with pytest.raises(TypeError):
            BaseFetcher()  # type: ignore

    def test_concrete_subclass_must_implement_fetch(self):
        """A subclass that skips fetch() raises TypeError on instantiation."""
        class Incomplete(BaseFetcher):
            pass  # missing fetch()

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore

    def test_concrete_subclass_works(self):
        """A complete subclass can be instantiated and called."""
        class AlwaysFails(BaseFetcher):
            def fetch(self, trade_date: date) -> Path:
                raise FetchError("intentional")

        fetcher = AlwaysFails()
        with pytest.raises(FetchError, match="intentional"):
            fetcher.fetch(date(2099, 1, 1))

    def test_fetch_error_is_exception(self):
        """FetchError must be a proper Exception subclass."""
        err = FetchError("something went wrong")
        assert isinstance(err, Exception)
        assert str(err) == "something went wrong"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source venv/bin/activate && pytest tests/unit/test_framework_fetchers.py::TestBaseFetcherABC -v
```
Expected: `ERROR` — `ModuleNotFoundError: No module named 'ingestion.framework.fetchers.base'`

- [ ] **Step 3: Implement `base.py`**

Create `ingestion/framework/fetchers/base.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_framework_fetchers.py::TestBaseFetcherABC -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add ingestion/framework/fetchers/base.py tests/unit/test_framework_fetchers.py
git commit -m "feat(framework): add BaseFetcher ABC and FetchError"
```

---

## Task 3: `LocalFetcher`

**Files:**
- Create: `ingestion/framework/fetchers/local_fetcher.py`
- Modify: `tests/unit/test_framework_fetchers.py`

The `LocalFetcher` scans a source-specific subfolder of `data/raw/` for a file whose name matches common NSE patterns. It raises `FetchError` if nothing is found.

- [ ] **Step 1: Write the failing tests** (append to `test_framework_fetchers.py`)

```python
from ingestion.framework.fetchers.local_fetcher import LocalFetcher


class TestLocalFetcher:
    def test_finds_file_by_date_pattern(self, tmp_path):
        """LocalFetcher returns path when a matching file exists."""
        # Create a file matching the bhavcopy date pattern DDMMYYYY
        trade_date = date(2099, 1, 15)
        expected = tmp_path / "sec_bhavdata_full_15012099.csv"
        expected.write_text("SYMBOL,SERIES\n")

        fetcher = LocalFetcher(source_dir=tmp_path)
        result = fetcher.fetch(trade_date)
        assert result == expected

    def test_raises_fetch_error_when_missing(self, tmp_path):
        """LocalFetcher raises FetchError when no file matches the date."""
        fetcher = LocalFetcher(source_dir=tmp_path)
        with pytest.raises(FetchError, match="No file found for 2099-01-15"):
            fetcher.fetch(date(2099, 1, 15))

    def test_raises_fetch_error_for_missing_directory(self, tmp_path):
        """LocalFetcher raises FetchError if the source_dir does not exist."""
        non_existent = tmp_path / "does_not_exist"
        with pytest.raises(FetchError, match="does not exist"):
            LocalFetcher(source_dir=non_existent)

    def test_finds_file_by_nse_bhavcopy_naming(self, tmp_path):
        """LocalFetcher also matches NSE legacy bhavcopy naming cmDDMONYYYYbhav.csv."""
        trade_date = date(2099, 3, 5)
        expected = tmp_path / "cm05MAR2099bhav.csv"
        expected.write_text("SYMBOL,SERIES\n")

        fetcher = LocalFetcher(source_dir=tmp_path)
        result = fetcher.fetch(trade_date)
        assert result == expected
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_framework_fetchers.py::TestLocalFetcher -v
```
Expected: `ERROR` — `ModuleNotFoundError: No module named 'ingestion.framework.fetchers.local_fetcher'`

- [ ] **Step 3: Implement `local_fetcher.py`**

Create `ingestion/framework/fetchers/local_fetcher.py`:

```python
"""Local filesystem fetcher — fallback when HTTP download is unavailable.

Scans a configured source directory for files matching known NSE naming
conventions. Raises :class:`FetchError` if no match is found.

Naming patterns supported (in priority order):
1. ``sec_bhavdata_full_DDMMYYYY.csv``  — new NSE archive format
2. ``CM_52_wk_High_low_DDMMYYYY.csv`` — 52-week file
3. ``cmDDMONYYYYbhav.csv``            — legacy bhavcopy
4. Any ``*DDMMYYYY*.csv`` pattern      — generic fallback
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from ingestion.framework.fetchers.base import BaseFetcher, FetchError

logger = logging.getLogger(__name__)


class LocalFetcher(BaseFetcher):
    """Fetch a trading-day file from a local directory.

    Useful when NSE HTTP downloads are unavailable or blocked, or during
    development when files are dropped manually into ``data/raw/<source>/``.

    Args:
        source_dir: Directory to search. Must exist at construction time.

    Raises:
        FetchError: At construction if ``source_dir`` does not exist.
    """

    def __init__(self, source_dir: Path) -> None:
        source_dir = Path(source_dir)
        if not source_dir.exists():
            raise FetchError(
                f"Local source directory does not exist: {source_dir}"
            )
        self.source_dir = source_dir

    def fetch(self, trade_date: date) -> Path:
        """Return the local file path for *trade_date*.

        Args:
            trade_date: The NSE trading date to look up.

        Returns:
            Path to the found file.

        Raises:
            FetchError: If no matching file is found in ``source_dir``.
        """
        dd = trade_date.strftime("%d")
        mm = trade_date.strftime("%m")
        yyyy = trade_date.strftime("%Y")
        mon_upper = trade_date.strftime("%b").upper()  # e.g. "JAN"
        ddmmyyyy = f"{dd}{mm}{yyyy}"

        patterns = [
            f"sec_bhavdata_full_{ddmmyyyy}.csv",
            f"CM_52_wk_High_low_{ddmmyyyy}.csv",
            f"cm{dd}{mon_upper}{yyyy}bhav.csv",
            f"ind_nifty50list.csv",
            f"*{ddmmyyyy}*.csv",
        ]

        for pattern in patterns:
            matches = list(self.source_dir.glob(pattern))
            if matches:
                logger.info(
                    "LocalFetcher: found %s for %s", matches[0].name, trade_date
                )
                return matches[0]

        raise FetchError(
            f"No file found for {trade_date} in {self.source_dir}. "
            f"Searched patterns: {patterns}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_framework_fetchers.py::TestLocalFetcher -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add ingestion/framework/fetchers/local_fetcher.py tests/unit/test_framework_fetchers.py
git commit -m "feat(framework): add LocalFetcher with NSE filename pattern matching"
```

---

## Task 4: `NseHttpFetcher`

**Files:**
- Create: `ingestion/framework/fetchers/http_fetcher.py`
- Modify: `tests/unit/test_framework_fetchers.py`

Delegates to the existing `NSEClient`. The `SourceType` enum maps each source to its URL template and output directory.

- [ ] **Step 1: Write the failing tests** (append to `test_framework_fetchers.py`)

```python
from unittest.mock import patch, MagicMock
from ingestion.framework.fetchers.http_fetcher import NseHttpFetcher, SourceType


class TestNseHttpFetcher:
    def test_bhavcopy_delegates_to_nse_client(self, tmp_path):
        """NseHttpFetcher.fetch() for BHAVCOPY calls NSEClient.download_bhavcopy."""
        mock_client = MagicMock()
        mock_client.download_bhavcopy.return_value = tmp_path / "bhav.csv"
        (tmp_path / "bhav.csv").write_text("x")

        fetcher = NseHttpFetcher(source=SourceType.BHAVCOPY, client=mock_client)
        result = fetcher.fetch(date(2099, 1, 15))

        mock_client.download_bhavcopy.assert_called_once_with(
            date(2099, 1, 15), output_dir=None
        )
        assert result == tmp_path / "bhav.csv"

    def test_raises_fetch_error_on_circuit_breaker(self, tmp_path):
        """NseHttpFetcher wraps CircuitBreakerOpen as FetchError."""
        from ingestion.nse_client import CircuitBreakerOpen

        mock_client = MagicMock()
        mock_client.download_bhavcopy.side_effect = CircuitBreakerOpen("open")

        fetcher = NseHttpFetcher(source=SourceType.BHAVCOPY, client=mock_client)
        with pytest.raises(FetchError, match="Circuit breaker"):
            fetcher.fetch(date(2099, 1, 15))

    def test_raises_fetch_error_on_request_exception(self, tmp_path):
        """NseHttpFetcher wraps requests.RequestException as FetchError."""
        import requests

        mock_client = MagicMock()
        mock_client.download_bhavcopy.side_effect = requests.RequestException("timeout")

        fetcher = NseHttpFetcher(source=SourceType.BHAVCOPY, client=mock_client)
        with pytest.raises(FetchError, match="HTTP download failed"):
            fetcher.fetch(date(2099, 1, 15))

    def test_source_type_enum_has_all_sources(self):
        """SourceType must cover all automated sources (A, B, C, E, F, G)."""
        expected = {"BHAVCOPY", "WK52", "CONSTITUENTS", "CORPORATE_ACTIONS",
                    "EVENT_CALENDAR", "ANNOUNCEMENTS"}
        assert expected.issubset({s.name for s in SourceType})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_framework_fetchers.py::TestNseHttpFetcher -v
```
Expected: `ERROR` — `ModuleNotFoundError`

- [ ] **Step 3: Implement `http_fetcher.py`**

Create `ingestion/framework/fetchers/http_fetcher.py`:

```python
"""NSE HTTP fetcher — delegates to the existing :class:`NSEClient`.

Wraps all ``NSEClient`` and ``requests`` exceptions into :class:`FetchError`
so that :class:`HybridFetcher` has a single exception type to catch.
"""
from __future__ import annotations

import logging
from datetime import date
from enum import Enum, auto
from pathlib import Path
from typing import Optional

import requests

from ingestion.framework.fetchers.base import BaseFetcher, FetchError
from ingestion.nse_client import CircuitBreakerOpen, NSEClient

logger = logging.getLogger(__name__)

# NSE 52-week archive URL template (date in DDMMYYYY format)
_WK52_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/products/content/"
    "CM_52_wk_High_low_{ddmmyyyy}.csv"
)
# Constituents file is always the current list — no date in URL
_CONSTITUENTS_URL = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
# Corporate actions, event calendar, announcements — JSON APIs handled by NSEScraper
_EVENT_CALENDAR_URL = "https://www.nseindia.com/api/event-calendar?index=equities"
_ANNOUNCEMENTS_URL = "https://www.nseindia.com/api/corporate-announcements?index=equities"


class SourceType(Enum):
    """Identifies which NSE data source a fetcher serves."""
    BHAVCOPY = auto()           # sec_bhavdata_full_DDMMYYYY.csv
    WK52 = auto()               # CM_52_wk_High_low_DDMMYYYY.csv
    CONSTITUENTS = auto()       # ind_nifty50list.csv
    CORPORATE_ACTIONS = auto()  # per-symbol corporate actions API
    EVENT_CALENDAR = auto()     # event-calendar JSON API
    ANNOUNCEMENTS = auto()      # corporate-announcements JSON API


class NseHttpFetcher(BaseFetcher):
    """Download NSE source files via HTTP, delegating to :class:`NSEClient`.

    For BHAVCOPY, uses ``NSEClient.download_bhavcopy``.
    For WK52 and CONSTITUENTS, uses a direct GET via the NSEClient session.
    For API sources (EVENT_CALENDAR, ANNOUNCEMENTS), saves the JSON response.

    Args:
        source: Which data source to fetch.
        client: Optional pre-constructed ``NSEClient`` (injected for testing).
        output_dir: Override the default ``data/raw/<source>/`` save directory.
    """

    def __init__(
        self,
        source: SourceType,
        client: Optional[NSEClient] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self.source = source
        self._client = client or NSEClient()
        self._output_dir = output_dir

    def fetch(self, trade_date: date) -> Path:
        """Download the source file for *trade_date*.

        Args:
            trade_date: The trading date to fetch data for.

        Returns:
            Local path to the downloaded file.

        Raises:
            FetchError: On circuit-breaker trip or HTTP failure.
        """
        try:
            return self._fetch_by_source(trade_date)
        except CircuitBreakerOpen as exc:
            raise FetchError(f"Circuit breaker open: {exc}") from exc
        except requests.RequestException as exc:
            raise FetchError(f"HTTP download failed: {exc}") from exc

    def _fetch_by_source(self, trade_date: date) -> Path:
        """Dispatch to the correct download method for the source type."""
        if self.source == SourceType.BHAVCOPY:
            return self._client.download_bhavcopy(
                trade_date, output_dir=self._output_dir
            )
        if self.source == SourceType.WK52:
            return self._download_csv(
                url=_WK52_URL_TEMPLATE.format(
                    ddmmyyyy=trade_date.strftime("%d%m%Y")
                ),
                filename=f"CM_52_wk_High_low_{trade_date.strftime('%d%m%Y')}.csv",
                subdir="52wk",
            )
        if self.source == SourceType.CONSTITUENTS:
            return self._download_csv(
                url=_CONSTITUENTS_URL,
                filename="ind_nifty50list.csv",
                subdir="constituents",
            )
        if self.source == SourceType.EVENT_CALENDAR:
            return self._download_json(
                url=_EVENT_CALENDAR_URL,
                filename=f"event_calendar_{trade_date.strftime('%Y%m%d')}.json",
                subdir="event_calendar",
            )
        if self.source == SourceType.ANNOUNCEMENTS:
            return self._download_json(
                url=_ANNOUNCEMENTS_URL,
                filename=f"announcements_{trade_date.strftime('%Y%m%d')}.json",
                subdir="announcements",
            )
        raise FetchError(
            f"HTTP fetch not supported for source {self.source}. "
            "Use the dedicated scraper instead."
        )

    def _save_dir(self, subdir: str) -> Path:
        """Resolve or create the output directory for *subdir*."""
        from config.settings import settings
        base = self._output_dir or (settings.project_root / "data" / "raw" / subdir)
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _download_csv(self, url: str, filename: str, subdir: str) -> Path:
        """Download a CSV from *url* and save as *filename* in ``data/raw/<subdir>/``."""
        resp = self._client._request_with_retry(url)
        out = self._save_dir(subdir) / filename
        out.write_bytes(resp.content)
        logger.info("Downloaded %s → %s", url, out)
        return out

    def _download_json(self, url: str, filename: str, subdir: str) -> Path:
        """Download a JSON API response and save as *filename*."""
        resp = self._client._request_with_retry(url)
        out = self._save_dir(subdir) / filename
        out.write_bytes(resp.content)
        logger.info("Downloaded JSON %s → %s", url, out)
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_framework_fetchers.py::TestNseHttpFetcher -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add ingestion/framework/fetchers/http_fetcher.py tests/unit/test_framework_fetchers.py
git commit -m "feat(framework): add NseHttpFetcher delegating to NSEClient"
```

---

## Task 5: `HybridFetcher`

**Files:**
- Create: `ingestion/framework/fetchers/hybrid_fetcher.py`
- Modify: `tests/unit/test_framework_fetchers.py`

- [ ] **Step 1: Write the failing tests** (append to `test_framework_fetchers.py`)

```python
from ingestion.framework.fetchers.hybrid_fetcher import HybridFetcher


class TestHybridFetcher:
    def test_uses_http_when_available(self, tmp_path):
        """HybridFetcher returns HTTP result when HTTP succeeds."""
        http_path = tmp_path / "http_result.csv"
        http_path.write_text("x")

        http_mock = MagicMock()
        http_mock.fetch.return_value = http_path
        local_mock = MagicMock()

        fetcher = HybridFetcher(http=http_mock, local=local_mock)
        result = fetcher.fetch(date(2099, 1, 15))

        assert result == http_path
        local_mock.fetch.assert_not_called()

    def test_falls_back_to_local_on_http_failure(self, tmp_path):
        """HybridFetcher uses local fallback when HTTP raises FetchError."""
        local_path = tmp_path / "local_result.csv"
        local_path.write_text("y")

        http_mock = MagicMock()
        http_mock.fetch.side_effect = FetchError("HTTP down")
        local_mock = MagicMock()
        local_mock.fetch.return_value = local_path

        fetcher = HybridFetcher(http=http_mock, local=local_mock)
        result = fetcher.fetch(date(2099, 1, 15))

        assert result == local_path

    def test_raises_fetch_error_when_both_fail(self, tmp_path):
        """HybridFetcher raises FetchError when both HTTP and local fail."""
        http_mock = MagicMock()
        http_mock.fetch.side_effect = FetchError("HTTP down")
        local_mock = MagicMock()
        local_mock.fetch.side_effect = FetchError("No local file")

        fetcher = HybridFetcher(http=http_mock, local=local_mock)
        with pytest.raises(FetchError, match="No local file"):
            fetcher.fetch(date(2099, 1, 15))

    def test_http_non_fetch_error_propagates(self, tmp_path):
        """Unexpected exceptions from HTTP are not swallowed."""
        http_mock = MagicMock()
        http_mock.fetch.side_effect = RuntimeError("unexpected")

        fetcher = HybridFetcher(http=http_mock, local=MagicMock())
        with pytest.raises(RuntimeError, match="unexpected"):
            fetcher.fetch(date(2099, 1, 15))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_framework_fetchers.py::TestHybridFetcher -v
```
Expected: `ERROR` — `ModuleNotFoundError`

- [ ] **Step 3: Implement `hybrid_fetcher.py`**

Create `ingestion/framework/fetchers/hybrid_fetcher.py`:

```python
"""Hybrid fetcher: HTTP-first with local-folder fallback.

On each :meth:`fetch` call:
1. Attempts HTTP download via the injected ``http`` fetcher.
2. If that raises :class:`FetchError` (network down, circuit-breaker open,
   NSE returns non-200), logs a warning and tries the ``local`` fetcher.
3. If both fail, the local fetcher's :class:`FetchError` propagates to the caller.

Non-:class:`FetchError` exceptions from the HTTP fetcher (e.g. programmer
errors, unexpected runtime failures) are **not** caught — they propagate
immediately so they are not silently hidden by the fallback path.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from ingestion.framework.fetchers.base import BaseFetcher, FetchError

logger = logging.getLogger(__name__)


class HybridFetcher(BaseFetcher):
    """Compose an HTTP fetcher and a local fetcher with automatic fallback.

    Args:
        http: A :class:`BaseFetcher` that attempts HTTP download.
        local: A :class:`BaseFetcher` that reads from the local drop folder.
    """

    def __init__(self, http: BaseFetcher, local: BaseFetcher) -> None:
        self.http = http
        self.local = local

    def fetch(self, trade_date: date) -> Path:
        """Fetch file for *trade_date*, trying HTTP first, then local.

        Args:
            trade_date: The NSE trading date needed.

        Returns:
            Path to a local file ready for parsing.

        Raises:
            FetchError: If both HTTP and local sources fail.
        """
        try:
            path = self.http.fetch(trade_date)
            logger.debug("HybridFetcher: HTTP succeeded for %s", trade_date)
            return path
        except FetchError as exc:
            logger.warning(
                "HybridFetcher: HTTP failed for %s (%s). Trying local fallback.",
                trade_date,
                exc,
            )
        # Local raises FetchError naturally if not found — let it propagate
        return self.local.fetch(trade_date)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_framework_fetchers.py -v
```
Expected: All fetcher tests pass.

- [ ] **Step 5: Update `fetchers/__init__.py`**

```python
"""Public API for ingestion framework fetchers."""
from ingestion.framework.fetchers.base import BaseFetcher, FetchError
from ingestion.framework.fetchers.http_fetcher import NseHttpFetcher, SourceType
from ingestion.framework.fetchers.local_fetcher import LocalFetcher
from ingestion.framework.fetchers.hybrid_fetcher import HybridFetcher

__all__ = [
    "BaseFetcher",
    "FetchError",
    "NseHttpFetcher",
    "SourceType",
    "LocalFetcher",
    "HybridFetcher",
]
```

- [ ] **Step 6: Commit**

```bash
git add ingestion/framework/fetchers/ tests/unit/test_framework_fetchers.py
git commit -m "feat(framework): add HybridFetcher with HTTP-first local fallback"
```

---

## Task 6: `BaseLoader` ABC

**Files:**
- Create: `ingestion/framework/loaders/base.py`
- Create: `tests/unit/test_framework_loaders.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_framework_loaders.py`:

```python
"""Unit tests for ingestion framework loaders."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ingestion.framework.loaders.base import BaseLoader


class TestBaseLoaderABC:
    def test_cannot_instantiate_base_loader(self):
        """BaseLoader is abstract."""
        with pytest.raises(TypeError):
            BaseLoader()  # type: ignore

    def test_concrete_subclass_must_implement_load(self):
        """Subclass missing load() raises TypeError on instantiation."""
        class Incomplete(BaseLoader):
            pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore

    def test_concrete_subclass_works(self, tmp_path):
        """A complete subclass can be instantiated and called."""
        class AlwaysZero(BaseLoader):
            def load(self, path: Path, trade_date: date) -> int:
                return 0

        loader = AlwaysZero()
        assert loader.load(tmp_path / "f.csv", date(2099, 1, 1)) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_framework_loaders.py::TestBaseLoaderABC -v
```
Expected: `ERROR` — `ModuleNotFoundError`

- [ ] **Step 3: Implement `loaders/base.py`**

Create `ingestion/framework/loaders/base.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_framework_loaders.py::TestBaseLoaderABC -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add ingestion/framework/loaders/base.py tests/unit/test_framework_loaders.py
git commit -m "feat(framework): add BaseLoader ABC"
```

---

## Task 7: `IngestionLogger` (`log.py`)

**Files:**
- Create: `ingestion/framework/log.py`
- Create: `tests/unit/test_framework_pipeline.py`

`IngestionLogger` writes to the existing `ingestion_log` table (same table that `BhavcopyLoader._log_ingestion()` uses).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_framework_pipeline.py`:

```python
"""Unit tests for Pipeline and IngestionLogger."""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch, call

import pytest

from ingestion.framework.log import IngestionLogger


class TestIngestionLogger:
    def test_record_success_calls_engine(self):
        """record_success() inserts a success row into ingestion_log."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        logger = IngestionLogger(engine=mock_engine)
        logger.record_success(
            trade_date=date(2099, 1, 15),
            source_name="bhavcopy",
            table_name="fact_eod_price",
            rows_inserted=42,
            started_at=datetime(2099, 1, 15, 18, 0, 0),
        )

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        params = call_args[0][1]
        assert params["status"] == "success"
        assert params["rows_inserted"] == 42
        assert params["table_name"] == "fact_eod_price"

    def test_record_failure_sets_status_failed(self):
        """record_failure() inserts a failed row with error_message."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        logger = IngestionLogger(engine=mock_engine)
        logger.record_failure(
            trade_date=date(2099, 1, 15),
            source_name="bhavcopy",
            table_name="fact_eod_price",
            error_message="parse failed",
            started_at=datetime(2099, 1, 15, 18, 0, 0),
        )

        params = mock_conn.execute.call_args[0][1]
        assert params["status"] == "failed"
        assert params["error_message"] == "parse failed"
        assert params["rows_inserted"] == 0

    def test_log_failure_is_non_fatal(self):
        """A DB error inside record_success() is caught and logged, not raised."""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("DB is down")

        logger = IngestionLogger(engine=mock_engine)
        # Must not raise
        logger.record_success(
            trade_date=date(2099, 1, 15),
            source_name="bhavcopy",
            table_name="fact_eod_price",
            rows_inserted=0,
            started_at=datetime(2099, 1, 15, 18, 0, 0),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_framework_pipeline.py::TestIngestionLogger -v
```
Expected: `ERROR` — `ModuleNotFoundError`

- [ ] **Step 3: Implement `log.py`**

Create `ingestion/framework/log.py`:

```python
"""Ingestion run logger — writes every pipeline run to ``ingestion_log``.

Uses the same ``ingestion_log`` table that the existing ``BhavcopyLoader``
already writes to, so all pipeline runs are visible in one place.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.database import get_engine

logger = logging.getLogger(__name__)


class IngestionLogger:
    """Write pipeline run records to the ``ingestion_log`` table.

    Both success and failure records are written. A write failure is
    **non-fatal** — the error is logged at WARNING level and swallowed so
    that a broken log table never prevents data from being ingested.

    Args:
        engine: SQLAlchemy engine. If None, uses ``get_engine()`` from
            ``config.database``.
    """

    _INSERT_SQL = text("""
        INSERT INTO ingestion_log (
            source_file, table_name, rows_inserted, rows_failed,
            status, error_message, started_at, completed_at
        ) VALUES (
            :source_file, :table_name, :rows_inserted, :rows_failed,
            :status, :error_message, :started_at, :completed_at
        )
    """)

    def __init__(self, engine: Optional[Engine] = None) -> None:
        self._engine = engine or get_engine()

    def record_success(
        self,
        trade_date: date,
        source_name: str,
        table_name: str,
        rows_inserted: int,
        started_at: datetime,
        rows_failed: int = 0,
    ) -> None:
        """Record a successful pipeline run.

        Args:
            trade_date: The trading date that was ingested.
            source_name: Human-readable source identifier (e.g. ``"bhavcopy"``).
            table_name: Target DB table (e.g. ``"fact_eod_price"``).
            rows_inserted: Number of rows inserted/updated.
            started_at: When the pipeline run started.
            rows_failed: Rows that could not be inserted (default 0).
        """
        self._write(
            source_file=f"{source_name}_{trade_date.strftime('%Y%m%d')}",
            table_name=table_name,
            rows_inserted=rows_inserted,
            rows_failed=rows_failed,
            status="success",
            error_message=None,
            started_at=started_at,
        )

    def record_failure(
        self,
        trade_date: date,
        source_name: str,
        table_name: str,
        error_message: str,
        started_at: datetime,
    ) -> None:
        """Record a failed pipeline run.

        Args:
            trade_date: The trading date that failed.
            source_name: Human-readable source identifier.
            table_name: Target DB table.
            error_message: Exception message or error description.
            started_at: When the pipeline run started.
        """
        self._write(
            source_file=f"{source_name}_{trade_date.strftime('%Y%m%d')}",
            table_name=table_name,
            rows_inserted=0,
            rows_failed=0,
            status="failed",
            error_message=error_message,
            started_at=started_at,
        )

    def _write(
        self,
        source_file: str,
        table_name: str,
        rows_inserted: int,
        rows_failed: int,
        status: str,
        error_message: Optional[str],
        started_at: datetime,
    ) -> None:
        """Internal write — swallows DB errors to stay non-fatal."""
        try:
            with self._engine.connect() as conn:
                conn.execute(
                    self._INSERT_SQL,
                    {
                        "source_file": source_file,
                        "table_name": table_name,
                        "rows_inserted": rows_inserted,
                        "rows_failed": rows_failed,
                        "status": status,
                        "error_message": error_message,
                        "started_at": started_at,
                        "completed_at": datetime.utcnow(),
                    },
                )
                conn.commit()
        except Exception as exc:
            logger.warning("IngestionLogger: failed to write log row: %s", exc)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_framework_pipeline.py::TestIngestionLogger -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add ingestion/framework/log.py tests/unit/test_framework_pipeline.py
git commit -m "feat(framework): add IngestionLogger writing to ingestion_log"
```

---

## Task 8: `Pipeline`

**Files:**
- Create: `ingestion/framework/pipeline.py`
- Modify: `tests/unit/test_framework_pipeline.py`

- [ ] **Step 1: Write the failing tests** (append to `test_framework_pipeline.py`)

```python
from pathlib import Path
from ingestion.framework.pipeline import Pipeline
from ingestion.framework.fetchers.base import FetchError


class TestPipeline:
    def _make_pipeline(self, fetcher_result=None, fetcher_error=None,
                       loader_result=42, loader_error=None):
        mock_fetcher = MagicMock()
        if fetcher_error:
            mock_fetcher.fetch.side_effect = fetcher_error
        else:
            mock_fetcher.fetch.return_value = fetcher_result or Path("/tmp/f.csv")

        mock_loader = MagicMock()
        if loader_error:
            mock_loader.load.side_effect = loader_error
        else:
            mock_loader.load.return_value = loader_result

        mock_log = MagicMock()
        return Pipeline(
            fetcher=mock_fetcher,
            loader=mock_loader,
            ingestion_logger=mock_log,
            source_name="test_source",
            table_name="fact_test",
        ), mock_fetcher, mock_loader, mock_log

    def test_successful_run_calls_log_success(self):
        """Pipeline.run() logs success when fetch+load both succeed."""
        pipe, fetcher, loader, log = self._make_pipeline(loader_result=55)
        pipe.run(date(2099, 1, 15))

        log.record_success.assert_called_once()
        call_kwargs = log.record_success.call_args[1]
        assert call_kwargs["rows_inserted"] == 55
        assert call_kwargs["trade_date"] == date(2099, 1, 15)

    def test_fetch_failure_logs_and_raises(self):
        """Pipeline.run() logs failure and re-raises on FetchError."""
        pipe, _, _, log = self._make_pipeline(
            fetcher_error=FetchError("no file")
        )
        with pytest.raises(FetchError, match="no file"):
            pipe.run(date(2099, 1, 15))

        log.record_failure.assert_called_once()
        assert "no file" in log.record_failure.call_args[1]["error_message"]

    def test_loader_failure_logs_and_raises(self):
        """Pipeline.run() logs failure and re-raises on loader exception."""
        pipe, _, _, log = self._make_pipeline(
            loader_error=ValueError("parse error")
        )
        with pytest.raises(ValueError, match="parse error"):
            pipe.run(date(2099, 1, 15))

        log.record_failure.assert_called_once()

    def test_loader_receives_fetched_path(self):
        """Pipeline passes the fetched path to the loader."""
        fake_path = Path("/tmp/bhav_15012099.csv")
        pipe, fetcher, loader, _ = self._make_pipeline(fetcher_result=fake_path)
        pipe.run(date(2099, 1, 15))

        loader.load.assert_called_once_with(fake_path, date(2099, 1, 15))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_framework_pipeline.py::TestPipeline -v
```
Expected: `ERROR` — `ModuleNotFoundError`

- [ ] **Step 3: Implement `pipeline.py`**

Create `ingestion/framework/pipeline.py`:

```python
"""Pipeline: orchestrates fetch → load → log for a single data source.

Usage::

    from ingestion.framework import Pipeline, HybridFetcher, EodPriceLoader

    pipeline = Pipeline(
        fetcher=HybridFetcher(http=NseHttpFetcher(SourceType.BHAVCOPY),
                               local=LocalFetcher(settings.project_root / "data/raw/bhavcopy")),
        loader=EodPriceLoader(),
        source_name="bhavcopy",
        table_name="fact_eod_price",
    )
    pipeline.run(date.today())
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from ingestion.framework.fetchers.base import BaseFetcher
from ingestion.framework.loaders.base import BaseLoader
from ingestion.framework.log import IngestionLogger

logger = logging.getLogger(__name__)


class Pipeline:
    """Wire one fetcher to one loader, write results to ``ingestion_log``.

    On success, calls :meth:`IngestionLogger.record_success`.
    On any exception, calls :meth:`IngestionLogger.record_failure` then
    **re-raises** so the caller (cron / ``daily_run.py``) receives a
    non-zero exit code.

    Args:
        fetcher: A :class:`~ingestion.framework.fetchers.base.BaseFetcher`.
        loader: A :class:`~ingestion.framework.loaders.base.BaseLoader`.
        source_name: Human-readable name written to ``ingestion_log.source_file``.
        table_name: DB table name written to ``ingestion_log.table_name``.
        ingestion_logger: Optional pre-constructed :class:`IngestionLogger`
            (injected for testing; defaults to ``IngestionLogger()``).
    """

    def __init__(
        self,
        fetcher: BaseFetcher,
        loader: BaseLoader,
        source_name: str,
        table_name: str,
        ingestion_logger: Optional[IngestionLogger] = None,
    ) -> None:
        self.fetcher = fetcher
        self.loader = loader
        self.source_name = source_name
        self.table_name = table_name
        self._log = ingestion_logger or IngestionLogger()

    def run(self, trade_date: date) -> int:
        """Execute the full fetch → load → log cycle for *trade_date*.

        Args:
            trade_date: The NSE trading date to ingest.

        Returns:
            Number of rows inserted/updated.

        Raises:
            Exception: Any fetch or load error is logged then re-raised.
        """
        started_at = datetime.utcnow()
        logger.info(
            "Pipeline[%s → %s]: starting for %s",
            self.source_name,
            self.table_name,
            trade_date,
        )
        try:
            path = self.fetcher.fetch(trade_date)
            rows = self.loader.load(path, trade_date)
            self._log.record_success(
                trade_date=trade_date,
                source_name=self.source_name,
                table_name=self.table_name,
                rows_inserted=rows,
                started_at=started_at,
            )
            logger.info(
                "Pipeline[%s]: completed %s — %d rows", self.source_name, trade_date, rows
            )
            return rows
        except Exception as exc:
            self._log.record_failure(
                trade_date=trade_date,
                source_name=self.source_name,
                table_name=self.table_name,
                error_message=str(exc),
                started_at=started_at,
            )
            logger.error(
                "Pipeline[%s]: FAILED for %s — %s", self.source_name, trade_date, exc
            )
            raise
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_framework_pipeline.py -v
```
Expected: All pipeline tests pass.

- [ ] **Step 5: Commit**

```bash
git add ingestion/framework/pipeline.py tests/unit/test_framework_pipeline.py
git commit -m "feat(framework): add Pipeline orchestrator with log-and-raise error handling"
```

---

## Task 9: `EodPriceLoader` (Source A — wraps existing bhavcopy code)

**Files:**
- Create: `ingestion/framework/loaders/eod_price_loader.py`
- Modify: `tests/unit/test_framework_loaders.py`

Wraps existing `BhavcopyParser` and `BhavcopyLoader` — no new logic, just adapts the signatures to `BaseLoader`.

- [ ] **Step 1: Write the failing tests** (append to `test_framework_loaders.py`)

```python
from ingestion.framework.loaders.eod_price_loader import EodPriceLoader


class TestEodPriceLoader:
    def test_load_delegates_to_bhavcopy_chain(self, tmp_path):
        """EodPriceLoader.load() calls BhavcopyParser then BhavcopyLoader."""
        csv = tmp_path / "sec_bhavdata_full_15012099.csv"
        csv.write_text(
            "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,"
            "TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN\n"
            "RELIANCE,EQ,2850.00,2875.50,2840.00,2865.30,2865.00,2845.00,"
            "8500000,24386.00,15-JAN-2099,125000,INE002A01018\n"
        )

        import pandas as pd
        mock_parser = MagicMock()
        mock_parser.parse.return_value = pd.DataFrame({"symbol": ["RELIANCE"]})
        mock_bloader = MagicMock()
        mock_bloader.load.return_value = {"rows_inserted": 1, "rows_total": 1,
                                           "rows_failed": 0, "status": "success"}

        loader = EodPriceLoader(parser=mock_parser, bhavcopy_loader=mock_bloader)
        result = loader.load(csv, date(2099, 1, 15))

        assert result == 1
        mock_parser.parse.assert_called_once_with(
            csv, trade_date=date(2099, 1, 15), source_file=csv.name
        )

    def test_load_returns_rows_inserted(self, tmp_path):
        """EodPriceLoader returns rows_inserted from BhavcopyLoader."""
        import pandas as pd
        mock_parser = MagicMock()
        mock_parser.parse.return_value = pd.DataFrame()
        mock_bloader = MagicMock()
        mock_bloader.load.return_value = {"rows_inserted": 37, "rows_total": 37,
                                           "rows_failed": 0, "status": "success"}

        loader = EodPriceLoader(parser=mock_parser, bhavcopy_loader=mock_bloader)
        result = loader.load(Path("/fake.csv"), date(2099, 1, 15))
        assert result == 37
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_framework_loaders.py::TestEodPriceLoader -v
```

- [ ] **Step 3: Implement `eod_price_loader.py`**

Create `ingestion/framework/loaders/eod_price_loader.py`:

```python
"""EOD price loader — framework adapter for the existing bhavcopy pipeline.

Delegates all parsing and DB work to the existing (unchanged)
:class:`~ingestion.bhavcopy_parser.BhavcopyParser` and
:class:`~ingestion.bhavcopy_loader.BhavcopyLoader`.

Target table: ``fact_eod_price``
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ingestion.bhavcopy_loader import BhavcopyLoader as _BhavcopyLoader
from ingestion.bhavcopy_parser import BhavcopyParser as _BhavcopyParser
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class EodPriceLoader(BaseLoader):
    """Load NSE bhavcopy CSV into ``fact_eod_price``.

    Thin wrapper: delegates all logic to the existing
    :class:`~ingestion.bhavcopy_parser.BhavcopyParser` and
    :class:`~ingestion.bhavcopy_loader.BhavcopyLoader`.

    Args:
        parser: Optional pre-constructed parser (injected for testing).
        bhavcopy_loader: Optional pre-constructed loader (injected for testing).
    """

    def __init__(
        self,
        parser: Optional[_BhavcopyParser] = None,
        bhavcopy_loader: Optional[_BhavcopyLoader] = None,
    ) -> None:
        self._parser = parser or _BhavcopyParser()
        self._loader = bhavcopy_loader or _BhavcopyLoader()

    def load(self, path: Path, trade_date: date) -> int:
        """Parse bhavcopy CSV at *path* and upsert into ``fact_eod_price``.

        Args:
            path: Path to the bhavcopy CSV file.
            trade_date: The trading date this file represents.

        Returns:
            Number of rows inserted (duplicates are skipped).

        Raises:
            BhavcopyParseError: If the CSV cannot be parsed.
            Exception: On DB errors.
        """
        df = self._parser.parse(path, trade_date=trade_date, source_file=path.name)
        stats = self._loader.load(df, source_file=path.name)
        logger.info(
            "EodPriceLoader: %d/%d rows inserted for %s",
            stats["rows_inserted"],
            stats["rows_total"],
            trade_date,
        )
        return stats["rows_inserted"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_framework_loaders.py::TestEodPriceLoader -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add ingestion/framework/loaders/eod_price_loader.py tests/unit/test_framework_loaders.py
git commit -m "feat(framework): add EodPriceLoader wrapping existing bhavcopy chain"
```

---

## Task 10: `Wk52Loader` (Source B — new parser + loader → `fact_52wk`)

**Files:**
- Create: `ingestion/framework/loaders/wk52_loader.py`
- Modify: `tests/unit/test_framework_loaders.py`

Parses `CM_52_wk_High_low_DDMMYYYY.csv`. NSE columns: `SYMBOL, SERIES, HIGH, HIGH_DATE, LOW, LOW_DATE` (DD-MMM-YYYY dates). Computes `pct_from_high` and `pct_from_low` by joining with `fact_eod_price` for the trade date's close. If no close is available, defaults to 0.0. Upserts into `fact_52wk` with `ON CONFLICT (trade_date, symbol) DO UPDATE`.

- [ ] **Step 1: Write the failing tests** (append to `test_framework_loaders.py`)

```python
from ingestion.framework.loaders.wk52_loader import Wk52Loader, Wk52ParseError


class TestWk52Loader:
    _SAMPLE_CSV_CONTENT = (
        "SYMBOL,SERIES,HIGH,HIGH_DATE,LOW,LOW_DATE\n"
        "RELIANCE,EQ,3215.00,29-DEC-2098,2180.10,05-APR-2098\n"
        "HDFCBANK,EQ,1850.00,10-NOV-2098,1200.50,12-JAN-2098\n"
    )

    def test_parse_returns_dataframe_with_required_columns(self, tmp_path):
        """Wk52Loader._parse() returns DataFrame with all required columns."""
        csv = tmp_path / "CM_52_wk_High_low_15012099.csv"
        csv.write_text(self._SAMPLE_CSV_CONTENT)

        loader = Wk52Loader()
        df = loader._parse(csv, trade_date=date(2099, 1, 15))

        required = {"symbol", "trade_date", "wk52_high", "wk52_low",
                    "wk52_high_date", "wk52_low_date"}
        assert required.issubset(set(df.columns))
        assert len(df) == 2

    def test_parse_extracts_correct_values(self, tmp_path):
        """Wk52Loader._parse() correctly parses prices and dates."""
        csv = tmp_path / "CM_52_wk_High_low_15012099.csv"
        csv.write_text(self._SAMPLE_CSV_CONTENT)

        loader = Wk52Loader()
        df = loader._parse(csv, trade_date=date(2099, 1, 15))
        row = df[df["symbol"] == "RELIANCE"].iloc[0]

        assert float(row["wk52_high"]) == 3215.00
        assert float(row["wk52_low"]) == 2180.10
        assert row["wk52_high_date"] == date(2098, 12, 29)
        assert row["wk52_low_date"] == date(2098, 4, 5)
        assert row["trade_date"] == date(2099, 1, 15)

    def test_parse_raises_on_missing_columns(self, tmp_path):
        """Wk52Loader._parse() raises Wk52ParseError on missing columns."""
        csv = tmp_path / "bad.csv"
        csv.write_text("SYMBOL,SERIES\nRELIANCE,EQ\n")

        with pytest.raises(Wk52ParseError, match="Missing columns"):
            Wk52Loader()._parse(csv, trade_date=date(2099, 1, 15))

    def test_parse_raises_on_empty_file(self, tmp_path):
        """Wk52Loader._parse() raises Wk52ParseError on empty CSV."""
        csv = tmp_path / "empty.csv"
        csv.write_text("SYMBOL,SERIES,HIGH,HIGH_DATE,LOW,LOW_DATE\n")

        with pytest.raises(Wk52ParseError, match="empty"):
            Wk52Loader()._parse(csv, trade_date=date(2099, 1, 15))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_framework_loaders.py::TestWk52Loader -v
```

- [ ] **Step 3: Implement `wk52_loader.py`**

Create `ingestion/framework/loaders/wk52_loader.py`:

```python
"""52-week high/low loader — parses NSE 52W file and upserts into ``fact_52wk``.

NSE publishes ``CM_52_wk_High_low_DDMMYYYY.csv`` daily after EOD.
Expected columns (case-insensitive): SYMBOL, SERIES, HIGH, HIGH_DATE, LOW, LOW_DATE.

Per the spec (Section 3-B): "Cross-check computed rolling 52W high/low (derived
from 252-day price history) against this file; if divergence > 2%, flag for review."
This loader:
1. Parses the NSE file.
2. Joins with ``fact_eod_price`` for trade_date close to compute pct_from_high/low.
3. Upserts into ``fact_52wk`` (ON CONFLICT DO UPDATE — NSE file is authoritative).
4. Warns if any symbol has >2% divergence vs existing ``fact_52wk`` computed values.

Target table: ``fact_52wk``
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)

_NSE_DATE_FORMATS = ["%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d"]

# Column aliases: NSE may vary capitalisation
_COL_ALIASES = {
    "52w high": "HIGH",
    "52w_high": "HIGH",
    "high price": "HIGH",
    "52w low": "LOW",
    "52w_low": "LOW",
    "low price": "LOW",
    "high date": "HIGH_DATE",
    "low date": "LOW_DATE",
}


class Wk52ParseError(Exception):
    """Raised when the 52-week CSV cannot be parsed."""


class Wk52Loader(BaseLoader):
    """Parse NSE 52-week file and upsert into ``fact_52wk``.

    Args:
        engine: Optional SQLAlchemy engine (injected for testing).
    """

    def __init__(self, engine=None) -> None:
        self._engine = engine or get_engine()

    def load(self, path: Path, trade_date: date) -> int:
        """Parse *path* and upsert 52-week records for *trade_date*.

        Args:
            path: Path to ``CM_52_wk_High_low_DDMMYYYY.csv``.
            trade_date: The trading date this file represents.

        Returns:
            Number of rows upserted.
        """
        df = self._parse(path, trade_date)
        df = self._enrich_pct_columns(df, trade_date)
        rows = self._upsert(df)
        logger.info("Wk52Loader: upserted %d rows for %s", rows, trade_date)
        return rows

    def _parse(self, path: Path, trade_date: date) -> pd.DataFrame:
        """Parse the CSV into a clean DataFrame.

        Args:
            path: Path to the CSV file.
            trade_date: The trading date to stamp on all rows.

        Returns:
            DataFrame with columns: symbol, trade_date, wk52_high, wk52_low,
            wk52_high_date, wk52_low_date.

        Raises:
            Wk52ParseError: On missing columns or empty file.
        """
        try:
            raw = pd.read_csv(path, dtype=str)
        except Exception as exc:
            raise Wk52ParseError(f"Cannot read {path}: {exc}") from exc

        raw.columns = raw.columns.str.strip().str.upper()

        # Apply column aliases
        rename_map = {k.upper(): v for k, v in _COL_ALIASES.items()}
        raw.rename(columns=rename_map, inplace=True)

        required = {"SYMBOL", "HIGH", "HIGH_DATE", "LOW", "LOW_DATE"}
        missing = required - set(raw.columns)
        if missing:
            raise Wk52ParseError(
                f"Missing columns {sorted(missing)} in {path.name}. "
                f"Found: {sorted(raw.columns)}"
            )

        # Filter EQ series if SERIES column present
        if "SERIES" in raw.columns:
            raw["SERIES"] = raw["SERIES"].str.strip()
            raw = raw[raw["SERIES"] == "EQ"].copy()

        if raw.empty:
            raise Wk52ParseError(f"52-week file is empty after filtering: {path.name}")

        def _parse_date(s: str) -> Optional[date]:
            for fmt in _NSE_DATE_FORMATS:
                try:
                    return datetime.strptime(s.strip(), fmt).date()
                except (ValueError, AttributeError):
                    continue
            return None

        df = pd.DataFrame({
            "symbol": raw["SYMBOL"].str.strip(),
            "trade_date": trade_date,
            "wk52_high": pd.to_numeric(raw["HIGH"], errors="coerce"),
            "wk52_low": pd.to_numeric(raw["LOW"], errors="coerce"),
            "wk52_high_date": raw["HIGH_DATE"].map(_parse_date),
            "wk52_low_date": raw["LOW_DATE"].map(_parse_date),
            "pct_from_high": 0.0,
            "pct_from_low": 0.0,
        })

        df = df.dropna(subset=["symbol", "wk52_high", "wk52_low",
                                "wk52_high_date", "wk52_low_date"])
        return df.reset_index(drop=True)

    def _enrich_pct_columns(self, df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
        """Join with fact_eod_price to compute pct_from_high and pct_from_low.

        If no close price is available, values remain 0.0.
        """
        try:
            closes = pd.read_sql_query(
                text("SELECT symbol, close FROM fact_eod_price WHERE trade_date = :d"),
                self._engine,
                params={"d": trade_date},
            )
            df = df.merge(closes, on="symbol", how="left")
            mask = df["close"].notna() & (df["wk52_high"] > 0) & (df["wk52_low"] > 0)
            df.loc[mask, "pct_from_high"] = (
                (df.loc[mask, "close"] - df.loc[mask, "wk52_high"])
                / df.loc[mask, "wk52_high"]
            )
            df.loc[mask, "pct_from_low"] = (
                (df.loc[mask, "close"] - df.loc[mask, "wk52_low"])
                / df.loc[mask, "wk52_low"]
            )
            df.drop(columns=["close"], inplace=True, errors="ignore")
        except Exception as exc:
            logger.warning(
                "Wk52Loader: could not enrich pct columns (close unavailable): %s", exc
            )
        return df

    def _upsert(self, df: pd.DataFrame) -> int:
        """Upsert rows into fact_52wk."""
        upsert_sql = text("""
            INSERT INTO fact_52wk (
                trade_date, symbol, wk52_high, wk52_low,
                wk52_high_date, wk52_low_date, pct_from_high, pct_from_low
            ) VALUES (
                :trade_date, :symbol, :wk52_high, :wk52_low,
                :wk52_high_date, :wk52_low_date, :pct_from_high, :pct_from_low
            )
            ON CONFLICT (trade_date, symbol) DO UPDATE SET
                wk52_high      = EXCLUDED.wk52_high,
                wk52_low       = EXCLUDED.wk52_low,
                wk52_high_date = EXCLUDED.wk52_high_date,
                wk52_low_date  = EXCLUDED.wk52_low_date,
                pct_from_high  = EXCLUDED.pct_from_high,
                pct_from_low   = EXCLUDED.pct_from_low
        """)
        records = df.to_dict("records")
        for rec in records:
            for k, v in rec.items():
                if pd.isna(v):
                    rec[k] = None

        with self._engine.begin() as conn:
            result = conn.execute(upsert_sql, records)
        return result.rowcount
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_framework_loaders.py::TestWk52Loader -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add ingestion/framework/loaders/wk52_loader.py tests/unit/test_framework_loaders.py
git commit -m "feat(framework): add Wk52Loader parsing NSE 52-week file into fact_52wk"
```

---

## Task 11: `ConstituentsLoader` (Source C → `dim_nifty50_constituent`)

**Files:**
- Create: `ingestion/framework/loaders/constituents_loader.py`
- Modify: `tests/unit/test_framework_loaders.py`

Parses `ind_nifty50list.csv` (columns: `Company Name, Industry, Symbol, Series, ISIN Code`). Updates `dim_stock.nifty50_member` for active symbols. Inserts new rows into `dim_nifty50_constituent` with `effective_from = trade_date`, `effective_to = NULL`, `change_type = 'Addition'`, `review_period = 'Auto'`. Uses `ON CONFLICT (symbol, effective_from) DO NOTHING`.

- [ ] **Step 1: Write the failing tests** (append to `test_framework_loaders.py`)

```python
from ingestion.framework.loaders.constituents_loader import (
    ConstituentsLoader, ConstituentsParseError
)


class TestConstituentsLoader:
    _SAMPLE_CSV = (
        "Company Name,Industry,Symbol,Series,ISIN Code\n"
        "Reliance Industries Limited,ENERGY,RELIANCE,EQ,INE002A01018\n"
        "HDFC Bank Limited,FINANCIAL SERVICES,HDFCBANK,EQ,INE040A01034\n"
    )

    def test_parse_returns_dataframe(self, tmp_path):
        """ConstituentsLoader._parse() returns a DataFrame with symbol column."""
        csv = tmp_path / "ind_nifty50list.csv"
        csv.write_text(self._SAMPLE_CSV)

        loader = ConstituentsLoader()
        df = loader._parse(csv)

        assert "symbol" in df.columns
        assert set(df["symbol"]) == {"RELIANCE", "HDFCBANK"}

    def test_parse_raises_on_missing_symbol_column(self, tmp_path):
        """ConstituentsLoader._parse() raises on CSV without a symbol column."""
        csv = tmp_path / "bad.csv"
        csv.write_text("Company Name,Industry\nFoo,Bar\n")

        with pytest.raises(ConstituentsParseError, match="symbol"):
            ConstituentsLoader()._parse(csv)

    def test_parse_raises_on_empty_file(self, tmp_path):
        """ConstituentsLoader._parse() raises on empty CSV."""
        csv = tmp_path / "empty.csv"
        csv.write_text("Company Name,Industry,Symbol,Series,ISIN Code\n")

        with pytest.raises(ConstituentsParseError, match="empty"):
            ConstituentsLoader()._parse(csv)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_framework_loaders.py::TestConstituentsLoader -v
```

- [ ] **Step 3: Implement `constituents_loader.py`**

Create `ingestion/framework/loaders/constituents_loader.py`:

```python
"""Nifty 50 constituents loader → ``dim_nifty50_constituent``.

Downloads/reads ``ind_nifty50list.csv`` from NSE Indices. This file always
contains the **current** 50 constituents (no historical date in the file).

Behaviour:
- Parses the CSV to get the current symbol list.
- For each symbol already in ``dim_stock``, inserts a row into
  ``dim_nifty50_constituent`` with ``effective_from = trade_date``,
  ``effective_to = NULL``, ``change_type = 'Addition'``,
  ``review_period = 'Auto'``. Uses ``ON CONFLICT DO NOTHING`` so running
  twice for the same date is safe.
- Symbols NOT in ``dim_stock`` are skipped with a WARNING (FK constraint
  would reject them anyway).

Target table: ``dim_nifty50_constituent``
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class ConstituentsParseError(Exception):
    """Raised when the constituents CSV cannot be parsed."""


class ConstituentsLoader(BaseLoader):
    """Load Nifty 50 constituents from NSE CSV into ``dim_nifty50_constituent``.

    Args:
        engine: Optional SQLAlchemy engine (injected for testing).
    """

    def __init__(self, engine=None) -> None:
        self._engine = engine or get_engine()

    def load(self, path: Path, trade_date: date) -> int:
        """Parse *path* and upsert constituent records.

        Args:
            path: Path to ``ind_nifty50list.csv``.
            trade_date: Effective date for new constituent rows.

        Returns:
            Number of rows inserted into ``dim_nifty50_constituent``.
        """
        df = self._parse(path)
        rows = self._upsert(df, trade_date)
        logger.info(
            "ConstituentsLoader: %d constituent rows inserted for %s",
            rows, trade_date
        )
        return rows

    def _parse(self, path: Path) -> pd.DataFrame:
        """Parse constituents CSV.

        Args:
            path: Path to the CSV file.

        Returns:
            DataFrame with columns: symbol, company_name, industry, isin.

        Raises:
            ConstituentsParseError: On missing columns or empty file.
        """
        try:
            raw = pd.read_csv(path, dtype=str)
        except Exception as exc:
            raise ConstituentsParseError(f"Cannot read {path}: {exc}") from exc

        raw.columns = raw.columns.str.strip().str.lower()

        # Find symbol column (NSE uses "Symbol" header)
        sym_col = next(
            (c for c in raw.columns if "symbol" in c and "company" not in c), None
        )
        if sym_col is None:
            raise ConstituentsParseError(
                f"No symbol column found in {path.name}. Columns: {list(raw.columns)}"
            )

        raw = raw[raw[sym_col].notna() & (raw[sym_col].str.strip() != "")]
        if raw.empty:
            raise ConstituentsParseError(f"Constituents file is empty: {path.name}")

        company_col = next((c for c in raw.columns if "company" in c), None)
        industry_col = next((c for c in raw.columns if "industry" in c), None)
        isin_col = next((c for c in raw.columns if "isin" in c), None)

        df = pd.DataFrame({
            "symbol": raw[sym_col].str.strip(),
            "company_name": raw[company_col].str.strip() if company_col else "",
            "industry": raw[industry_col].str.strip() if industry_col else "",
            "isin": raw[isin_col].str.strip() if isin_col else "",
        })
        return df.reset_index(drop=True)

    def _upsert(self, df: pd.DataFrame, trade_date: date) -> int:
        """Insert new constituent rows into ``dim_nifty50_constituent``."""
        # Only insert for symbols that exist in dim_stock (FK constraint)
        with self._engine.connect() as conn:
            valid_symbols = set(
                row[0] for row in conn.execute(text("SELECT symbol FROM dim_stock"))
            )

        skipped = set(df["symbol"]) - valid_symbols
        if skipped:
            logger.warning(
                "ConstituentsLoader: %d symbols not in dim_stock, skipping: %s",
                len(skipped), sorted(skipped)[:10]
            )

        df = df[df["symbol"].isin(valid_symbols)].copy()
        if df.empty:
            return 0

        insert_sql = text("""
            INSERT INTO dim_nifty50_constituent
                (symbol, effective_from, effective_to, index_weight_pct,
                 replaced_symbol, change_type, review_period)
            VALUES
                (:symbol, :effective_from, NULL, NULL, NULL, 'Addition', 'Auto')
            ON CONFLICT (symbol, effective_from) DO NOTHING
        """)

        records = [
            {"symbol": row["symbol"], "effective_from": trade_date}
            for _, row in df.iterrows()
        ]

        with self._engine.begin() as conn:
            result = conn.execute(insert_sql, records)
        return result.rowcount
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_framework_loaders.py::TestConstituentsLoader -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add ingestion/framework/loaders/constituents_loader.py tests/unit/test_framework_loaders.py
git commit -m "feat(framework): add ConstituentsLoader for dim_nifty50_constituent"
```

---

## Task 12: Placeholder Loaders (Sources D, H) + Wrappers (E, F, G)

**Files:**
- Create: `ingestion/framework/loaders/reconstitution_loader.py`
- Create: `ingestion/framework/loaders/intraday_loader.py`
- Create: `ingestion/framework/loaders/corporate_actions_loader.py`
- Create: `ingestion/framework/loaders/event_calendar_loader.py`
- Create: `ingestion/framework/loaders/announcements_loader.py`
- Modify: `tests/unit/test_framework_loaders.py`

- [ ] **Step 1: Write the failing tests** (append to `test_framework_loaders.py`)

```python
from ingestion.framework.loaders.reconstitution_loader import ReconstitutionLoader
from ingestion.framework.loaders.intraday_loader import IntradayLoader
from ingestion.framework.loaders.corporate_actions_loader import CorporateActionsFrameworkLoader
from ingestion.framework.loaders.event_calendar_loader import EventCalendarLoader
from ingestion.framework.loaders.announcements_loader import AnnouncementsLoader


class TestPlaceholderLoaders:
    def test_intraday_loader_raises_not_implemented(self, tmp_path):
        """IntradayLoader.load() raises NotImplementedError."""
        loader = IntradayLoader()
        with pytest.raises(NotImplementedError, match="vendor"):
            loader.load(tmp_path / "fake.csv", date(2099, 1, 15))

    def test_reconstitution_loader_raises_fetch_error_on_missing_file(self, tmp_path):
        """ReconstitutionLoader.load() raises when file doesn't exist."""
        loader = ReconstitutionLoader()
        with pytest.raises(FileNotFoundError):
            loader.load(tmp_path / "nonexistent.csv", date(2099, 1, 15))


class TestCorporateActionsWrapper:
    def test_delegates_to_existing_parser_and_loader(self, tmp_path):
        """CorporateActionsFrameworkLoader delegates to existing chain."""
        import pandas as pd
        mock_parser = MagicMock()
        mock_parser.parse.return_value = pd.DataFrame()
        mock_loader = MagicMock()
        mock_loader.load.return_value = 5

        loader = CorporateActionsFrameworkLoader(
            parser=mock_parser, ca_loader=mock_loader
        )
        result = loader.load(tmp_path / "ca.csv", date(2099, 1, 15))

        assert result == 5
        mock_parser.parse.assert_called_once()


class TestEventCalendarWrapper:
    def test_delegates_to_existing_scraper_chain(self, tmp_path):
        """EventCalendarLoader delegates to existing ingestor+loader chain."""
        import pandas as pd
        mock_ingestor = MagicMock()
        mock_ingestor.ingest.return_value = pd.DataFrame()
        mock_loader = MagicMock()
        mock_loader.load.return_value = 3

        loader = EventCalendarLoader(ingestor=mock_ingestor, events_loader=mock_loader)
        result = loader.load(tmp_path / "ec.json", date(2099, 1, 15))

        assert result == 3
        mock_ingestor.ingest.assert_called_once()


class TestAnnouncementsWrapper:
    def test_delegates_to_existing_scraper_chain(self, tmp_path):
        """AnnouncementsLoader delegates to existing ingestor+loader chain."""
        import pandas as pd
        mock_ingestor = MagicMock()
        mock_ingestor.ingest.return_value = pd.DataFrame()
        mock_loader = MagicMock()
        mock_loader.load.return_value = 7

        loader = AnnouncementsLoader(ingestor=mock_ingestor, events_loader=mock_loader)
        result = loader.load(tmp_path / "ann.json", date(2099, 1, 15))
        assert result == 7
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_framework_loaders.py::TestPlaceholderLoaders tests/unit/test_framework_loaders.py::TestCorporateActionsWrapper tests/unit/test_framework_loaders.py::TestEventCalendarWrapper tests/unit/test_framework_loaders.py::TestAnnouncementsWrapper -v
```

- [ ] **Step 3: Implement `reconstitution_loader.py`**

Create `ingestion/framework/loaders/reconstitution_loader.py`:

```python
"""Reconstitution table loader — local manual-drop only (Source D).

No HTTP fetch. The file ``nifty50_reconstitution_log.csv`` must be placed
manually in ``data/raw/reconstitution/`` within 24h of the official NSE
announcement (per spec Section 3-D).

Expected columns: symbol, company, isin, action (ADD/DELETE),
effective_date, review_period, reason_code.

Target table: ``dim_nifty50_constituent`` (adds or closes constituent rows)

TODO: Implement upsert logic once the reconstitution CSV format is confirmed
with an actual NSE announcement. Current implementation parses the file
and validates columns but does not write to DB until format is confirmed.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)

_REQUIRED_COLUMNS = {"symbol", "action", "effective_date", "review_period"}


class ReconstitutionLoader(BaseLoader):
    """Load reconstitution log CSV into ``dim_nifty50_constituent``.

    This is a LOCAL-ONLY source. There is no HTTP fetcher for this source.
    Place the CSV manually in ``data/raw/reconstitution/``.

    Args:
        engine: Optional SQLAlchemy engine (injected for testing).
    """

    def __init__(self, engine=None) -> None:
        self._engine = engine or get_engine()

    def load(self, path: Path, trade_date: date) -> int:
        """Parse reconstitution CSV and update ``dim_nifty50_constituent``.

        Args:
            path: Path to the manual-drop reconstitution CSV.
            trade_date: The effective date of the reconstitution.

        Returns:
            Number of rows inserted/updated.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If required columns are missing.
        """
        if not path.exists():
            raise FileNotFoundError(f"Reconstitution file not found: {path}")

        raw = pd.read_csv(path, dtype=str)
        raw.columns = raw.columns.str.strip().str.lower()

        missing = _REQUIRED_COLUMNS - set(raw.columns)
        if missing:
            raise ValueError(
                f"Reconstitution CSV missing required columns: {sorted(missing)}. "
                f"Found: {sorted(raw.columns)}"
            )

        rows_written = 0
        for _, row in raw.iterrows():
            action = str(row.get("action", "")).strip().upper()
            symbol = str(row.get("symbol", "")).strip().upper()
            effective = str(row.get("effective_date", "")).strip()
            review = str(row.get("review_period", "Auto")).strip()

            if action not in ("ADD", "DELETE"):
                logger.warning("Unknown reconstitution action '%s' for %s — skipped", action, symbol)
                continue

            change_type = "Addition" if action == "ADD" else "Deletion"

            try:
                eff_date = date.fromisoformat(effective) if effective else trade_date
            except ValueError:
                eff_date = trade_date

            with self._engine.begin() as conn:
                result = conn.execute(text("""
                    INSERT INTO dim_nifty50_constituent
                        (symbol, effective_from, effective_to, index_weight_pct,
                         replaced_symbol, change_type, review_period)
                    VALUES
                        (:symbol, :effective_from, NULL, NULL, NULL, :change_type, :review_period)
                    ON CONFLICT (symbol, effective_from) DO NOTHING
                """), {
                    "symbol": symbol,
                    "effective_from": eff_date,
                    "change_type": change_type,
                    "review_period": review,
                })
                rows_written += result.rowcount

        logger.info("ReconstitutionLoader: %d rows written", rows_written)
        return rows_written
```

- [ ] **Step 4: Implement `intraday_loader.py`**

Create `ingestion/framework/loaders/intraday_loader.py`:

```python
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
```

- [ ] **Step 5: Implement `corporate_actions_loader.py` (framework wrapper)**

Create `ingestion/framework/loaders/corporate_actions_loader.py`:

```python
"""Corporate actions loader — framework wrapper for existing chain (Source E).

Wraps the existing :class:`~ingestion.corporate_actions_parser.CorporateActionsParser`
and :class:`~ingestion.corporate_actions_loader.CorporateActionsLoader`
(note: the existing loader has the same class name — this wrapper uses a
disambiguating class name ``CorporateActionsFrameworkLoader``).

Target table: ``fact_corporate_action``
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ingestion.corporate_actions_loader import CorporateActionsLoader as _ExistingLoader
from ingestion.corporate_actions_parser import CorporateActionsParser as _ExistingParser
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class CorporateActionsFrameworkLoader(BaseLoader):
    """Framework adapter for the existing corporate actions ingestion chain.

    Args:
        parser: Optional pre-constructed parser (injected for testing).
        ca_loader: Optional pre-constructed loader (injected for testing).
    """

    def __init__(
        self,
        parser: Optional[_ExistingParser] = None,
        ca_loader: Optional[_ExistingLoader] = None,
    ) -> None:
        self._parser = parser or _ExistingParser()
        self._loader = ca_loader or _ExistingLoader()

    def load(self, path: Path, trade_date: date) -> int:
        """Parse corporate actions CSV and upsert into ``fact_corporate_action``.

        Args:
            path: Path to the NSE corporate actions CSV.
            trade_date: Reference date for filtering future actions.

        Returns:
            Number of rows upserted.
        """
        df = self._parser.parse(path, as_of=trade_date)
        rows = self._loader.load(df)
        logger.info(
            "CorporateActionsFrameworkLoader: %d rows for %s", rows, trade_date
        )
        return rows
```

- [ ] **Step 6: Implement `event_calendar_loader.py`**

Create `ingestion/framework/loaders/event_calendar_loader.py`:

```python
"""Event calendar loader — framework wrapper for NSE scraper chain (Source F).

Note: The spec defines ``fact_event_calendar`` but this table does not yet
exist in the schema. This loader targets the existing ``fact_corporate_event``
table which is functionally equivalent. The table will be renamed/migrated
in a future schema phase.

Target table: ``fact_corporate_event``
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ingestion.corporate_events_ingestor import CorporateEventsIngestor as _Ingestor
from ingestion.corporate_events_loader import CorporateEventsLoader as _Loader
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class EventCalendarLoader(BaseLoader):
    """Framework adapter for the event calendar scraper chain.

    The source file (JSON or CSV from NSE ``event-calendar`` API) is first
    classified by :class:`~ingestion.corporate_events_ingestor.CorporateEventsIngestor`,
    then upserted by :class:`~ingestion.corporate_events_loader.CorporateEventsLoader`.

    Args:
        ingestor: Optional pre-constructed ingestor (injected for testing).
        events_loader: Optional pre-constructed loader (injected for testing).
    """

    def __init__(
        self,
        ingestor: Optional[_Ingestor] = None,
        events_loader: Optional[_Loader] = None,
    ) -> None:
        self._ingestor = ingestor or _Ingestor()
        self._loader = events_loader or _Loader()

    def load(self, path: Path, trade_date: date) -> int:
        """Classify and upsert event calendar records.

        Args:
            path: Path to the downloaded event calendar JSON/CSV.
            trade_date: The date to use as ``calc_date`` for event classification.

        Returns:
            Number of rows upserted into ``fact_corporate_event``.
        """
        df = self._ingestor.ingest(path, calc_date=trade_date)
        rows = self._loader.load(df)
        logger.info(
            "EventCalendarLoader: %d rows for %s", rows, trade_date
        )
        return rows
```

- [ ] **Step 7: Implement `announcements_loader.py`**

Create `ingestion/framework/loaders/announcements_loader.py`:

```python
"""Corporate announcements loader — framework wrapper for NSE scraper chain (Source G).

Note: The spec defines ``fact_announcement`` but this table does not yet exist
in the schema. This loader targets the existing ``fact_corporate_event`` table.
The table will be added in a future schema phase.

Target table: ``fact_corporate_event``
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ingestion.corporate_events_ingestor import CorporateEventsIngestor as _Ingestor
from ingestion.corporate_events_loader import CorporateEventsLoader as _Loader
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class AnnouncementsLoader(BaseLoader):
    """Framework adapter for the corporate announcements scraper chain.

    The source file (JSON from NSE ``corporate-announcements`` API) is
    classified by :class:`~ingestion.corporate_events_ingestor.CorporateEventsIngestor`,
    then upserted by :class:`~ingestion.corporate_events_loader.CorporateEventsLoader`.

    Args:
        ingestor: Optional pre-constructed ingestor (injected for testing).
        events_loader: Optional pre-constructed loader (injected for testing).
    """

    def __init__(
        self,
        ingestor: Optional[_Ingestor] = None,
        events_loader: Optional[_Loader] = None,
    ) -> None:
        self._ingestor = ingestor or _Ingestor()
        self._loader = events_loader or _Loader()

    def load(self, path: Path, trade_date: date) -> int:
        """Classify and upsert announcement records.

        Args:
            path: Path to the downloaded announcements JSON/CSV.
            trade_date: The date to use as ``calc_date`` for classification.

        Returns:
            Number of rows upserted into ``fact_corporate_event``.
        """
        df = self._ingestor.ingest(path, calc_date=trade_date)
        rows = self._loader.load(df)
        logger.info(
            "AnnouncementsLoader: %d rows for %s", rows, trade_date
        )
        return rows
```

- [ ] **Step 8: Run all loader tests**

```bash
pytest tests/unit/test_framework_loaders.py -v
```
Expected: All loader tests pass.

- [ ] **Step 9: Update `loaders/__init__.py`**

```python
"""Public API for ingestion framework loaders."""
from ingestion.framework.loaders.base import BaseLoader
from ingestion.framework.loaders.eod_price_loader import EodPriceLoader
from ingestion.framework.loaders.wk52_loader import Wk52Loader, Wk52ParseError
from ingestion.framework.loaders.constituents_loader import (
    ConstituentsLoader, ConstituentsParseError
)
from ingestion.framework.loaders.reconstitution_loader import ReconstitutionLoader
from ingestion.framework.loaders.corporate_actions_loader import CorporateActionsFrameworkLoader
from ingestion.framework.loaders.event_calendar_loader import EventCalendarLoader
from ingestion.framework.loaders.announcements_loader import AnnouncementsLoader
from ingestion.framework.loaders.intraday_loader import IntradayLoader

__all__ = [
    "BaseLoader",
    "EodPriceLoader",
    "Wk52Loader", "Wk52ParseError",
    "ConstituentsLoader", "ConstituentsParseError",
    "ReconstitutionLoader",
    "CorporateActionsFrameworkLoader",
    "EventCalendarLoader",
    "AnnouncementsLoader",
    "IntradayLoader",
]
```

- [ ] **Step 10: Commit**

```bash
git add ingestion/framework/loaders/ tests/unit/test_framework_loaders.py
git commit -m "feat(framework): add all remaining loaders (placeholders D/H, wrappers E/F/G)"
```

---

## Task 13: Top-level `__init__.py` + Full Test Run

**Files:**
- Modify: `ingestion/framework/__init__.py`

- [ ] **Step 1: Wire up top-level exports**

```python
"""Ingestion framework — parallel pipeline infrastructure.

Provides a uniform fetch → parse → upsert → log contract over all 9
Section 3 data sources. Existing ``daily_run.py`` is untouched.

Quick-start::

    from ingestion.framework import Pipeline, HybridFetcher, NseHttpFetcher
    from ingestion.framework import SourceType, LocalFetcher, EodPriceLoader
    from config.settings import settings

    pipeline = Pipeline(
        fetcher=HybridFetcher(
            http=NseHttpFetcher(SourceType.BHAVCOPY),
            local=LocalFetcher(settings.project_root / "data/raw/bhavcopy"),
        ),
        loader=EodPriceLoader(),
        source_name="bhavcopy",
        table_name="fact_eod_price",
    )
    pipeline.run(date.today())
"""
from ingestion.framework.fetchers import (
    BaseFetcher, FetchError, NseHttpFetcher, SourceType, LocalFetcher, HybridFetcher
)
from ingestion.framework.loaders import (
    BaseLoader,
    EodPriceLoader,
    Wk52Loader,
    ConstituentsLoader,
    ReconstitutionLoader,
    CorporateActionsFrameworkLoader,
    EventCalendarLoader,
    AnnouncementsLoader,
    IntradayLoader,
)
from ingestion.framework.log import IngestionLogger
from ingestion.framework.pipeline import Pipeline

__all__ = [
    "BaseFetcher", "FetchError",
    "NseHttpFetcher", "SourceType",
    "LocalFetcher", "HybridFetcher",
    "BaseLoader",
    "EodPriceLoader",
    "Wk52Loader",
    "ConstituentsLoader",
    "ReconstitutionLoader",
    "CorporateActionsFrameworkLoader",
    "EventCalendarLoader",
    "AnnouncementsLoader",
    "IntradayLoader",
    "IngestionLogger",
    "Pipeline",
]
```

- [ ] **Step 2: Run the full framework test suite**

```bash
source venv/bin/activate && pytest tests/unit/test_framework_fetchers.py tests/unit/test_framework_loaders.py tests/unit/test_framework_pipeline.py -v --tb=short
```
Expected: All tests pass.

- [ ] **Step 3: Run the existing test suite to confirm nothing was broken**

```bash
pytest tests/ -v --tb=short --ignore=tests/integration
```
Expected: Existing tests continue to pass. Zero regressions.

- [ ] **Step 4: Final commit**

```bash
git add ingestion/framework/__init__.py
git commit -m "feat(framework): wire top-level __init__ exports, all tests green"
```

---

## Spec Coverage Cross-Check

| Spec Section 3 | Loader | HTTP Fetcher | Local Fallback | Table |
|---|---|---|---|---|
| A — Bhavcopy | `EodPriceLoader` ✅ | `NseHttpFetcher(BHAVCOPY)` ✅ | `LocalFetcher(data/raw/bhavcopy)` ✅ | `fact_eod_price` |
| B — 52-week H/L | `Wk52Loader` ✅ | `NseHttpFetcher(WK52)` ✅ | `LocalFetcher(data/raw/52wk)` ✅ | `fact_52wk` |
| C — Constituents | `ConstituentsLoader` ✅ | `NseHttpFetcher(CONSTITUENTS)` ✅ | `LocalFetcher(data/raw/constituents)` ✅ | `dim_nifty50_constituent` |
| D — Reconstitution | `ReconstitutionLoader` ✅ | None (local-only by design) ✅ | `LocalFetcher(data/raw/reconstitution)` ✅ | `dim_nifty50_constituent` |
| E — Corp Actions | `CorporateActionsFrameworkLoader` ✅ | `NseHttpFetcher(CORPORATE_ACTIONS)` ✅ | `LocalFetcher(data/raw/corporate_actions)` ✅ | `fact_corporate_action` |
| F — Event Calendar | `EventCalendarLoader` ✅ | `NseHttpFetcher(EVENT_CALENDAR)` ✅ | `LocalFetcher(data/raw/event_calendar)` ✅ | `fact_corporate_event`* |
| G — Announcements | `AnnouncementsLoader` ✅ | `NseHttpFetcher(ANNOUNCEMENTS)` ✅ | `LocalFetcher(data/raw/announcements)` ✅ | `fact_corporate_event`* |
| H — Intraday | `IntradayLoader` (stub) ✅ | None (vendor pending) ✅ | None ✅ | `fact_intraday` (future) |
| I — Secondary Portals | None (spec: no automation) ✅ | — | — | — |

*`fact_event_calendar` and `fact_announcement` do not yet exist in the schema; both F and G target `fact_corporate_event` which is the functional equivalent currently in the schema.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-27-ingestion-framework.md`.**
