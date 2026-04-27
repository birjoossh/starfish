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
