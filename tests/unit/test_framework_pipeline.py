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
