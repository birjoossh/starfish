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


class TestPipelineProcessedDir:
    def _build(self, src_path, processed_dir):
        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = src_path
        mock_loader = MagicMock()
        mock_loader.load.return_value = 1
        return Pipeline(
            fetcher=mock_fetcher,
            loader=mock_loader,
            ingestion_logger=MagicMock(),
            source_name="dim-stock",
            table_name="dim_stock",
            processed_dir=processed_dir,
        )

    def test_moves_file_after_successful_load(self, tmp_path):
        """After success, source file is moved into processed_dir."""
        raw = tmp_path / "raw"
        raw.mkdir()
        src = raw / "NSE_CM_security_15012099.csv"
        src.write_text("hello")
        processed = tmp_path / "processed"

        pipe = self._build(src, processed)
        pipe.run(date(2099, 1, 15))

        assert not src.exists()
        moved = processed / "NSE_CM_security_15012099.csv"
        assert moved.exists()
        assert moved.read_text() == "hello"

    def test_does_not_move_on_failure(self, tmp_path):
        """On loader failure, the raw file stays put for inspection."""
        raw = tmp_path / "raw"
        raw.mkdir()
        src = raw / "bad.csv"
        src.write_text("x")
        processed = tmp_path / "processed"

        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = src
        mock_loader = MagicMock()
        mock_loader.load.side_effect = ValueError("parse boom")

        pipe = Pipeline(
            fetcher=mock_fetcher,
            loader=mock_loader,
            ingestion_logger=MagicMock(),
            source_name="dim-stock",
            table_name="dim_stock",
            processed_dir=processed,
        )
        with pytest.raises(ValueError):
            pipe.run(date(2099, 1, 15))

        assert src.exists(), "raw file should remain on failure"
        assert not (processed / "bad.csv").exists()

    def test_handles_filename_collision_with_date_suffix(self, tmp_path):
        """Re-running for the same file appends the trade_date suffix."""
        raw = tmp_path / "raw"
        raw.mkdir()
        src = raw / "report.csv"
        src.write_text("v2")
        processed = tmp_path / "processed"
        processed.mkdir()
        # Pre-existing archived file with the same name
        (processed / "report.csv").write_text("v1")

        pipe = self._build(src, processed)
        pipe.run(date(2099, 1, 15))

        # Original archive intact, new copy gets a date-suffixed name
        assert (processed / "report.csv").read_text() == "v1"
        assert (processed / "report.2099-01-15.csv").read_text() == "v2"

    def test_no_op_when_processed_dir_is_none(self, tmp_path):
        """processed_dir=None disables the move (file remains in place)."""
        src = tmp_path / "stays.csv"
        src.write_text("x")

        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = src
        mock_loader = MagicMock()
        mock_loader.load.return_value = 1

        pipe = Pipeline(
            fetcher=mock_fetcher,
            loader=mock_loader,
            ingestion_logger=MagicMock(),
            source_name="x",
            table_name="x",
            processed_dir=None,
        )
        pipe.run(date(2099, 1, 15))
        assert src.exists()


class TestBadRecordsWriter:
    def test_writes_dropped_rows_to_csv(self, tmp_path):
        """BadRecordsWriter persists dropped rows under log_dir."""
        import pandas as pd
        from ingestion.framework.bad_records import BadRecordsWriter

        writer = BadRecordsWriter(source="dim-stock", log_dir=tmp_path)
        df = pd.DataFrame({"symbol": ["FOO", "BAR"], "isin": [None, "INE000A"]})
        out = writer.write(df, original_filename="NSE_CM_security_15012099.csv",
                           reason="missing isin")

        assert out is not None
        assert out.exists()
        content = out.read_text()
        assert "FOO" in content and "BAR" in content
        # _drop_reason column is appended for context
        assert "missing isin" in content

    def test_returns_none_for_empty_df(self, tmp_path):
        """Writing an empty DataFrame is a no-op (no file created)."""
        import pandas as pd
        from ingestion.framework.bad_records import BadRecordsWriter

        writer = BadRecordsWriter(source="x", log_dir=tmp_path)
        result = writer.write(pd.DataFrame(),
                              original_filename="empty.csv", reason="—")

        assert result is None
        assert list(tmp_path.iterdir()) == []

    def test_appends_when_called_multiple_times(self, tmp_path):
        """Second write to the same filename appends rather than overwrites."""
        import pandas as pd
        from ingestion.framework.bad_records import BadRecordsWriter

        writer = BadRecordsWriter(source="x", log_dir=tmp_path)
        writer.write(pd.DataFrame({"a": [1]}), original_filename="f.csv",
                     reason="r1")
        writer.write(pd.DataFrame({"a": [2]}), original_filename="f.csv",
                     reason="r2")

        out = (tmp_path / "f.csv").read_text()
        # Both rows present, header only once
        assert out.count("\n") == 3  # header + 2 rows + trailing \n
        assert "1" in out and "2" in out
        assert "r1" in out and "r2" in out
