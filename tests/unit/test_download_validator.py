"""Unit tests for ingestion.download_validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.download_validator import (
    DownloadValidationError,
    file_sha256,
    file_stats,
    validate_against_reference,
    validate_bhavcopy_size,
)


HEADER = (
    "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,PREVCLOSE,TOTTRDQTY,"
    "TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN,DELIV_QTY,DELIV_PCT,SOURCE\n"
)


def _write_csv(path: Path, *, data_rows: int) -> Path:
    """Write a fake bhavcopy CSV roughly real-shaped (~50 bytes / row)."""
    lines = [HEADER]
    for i in range(data_rows):
        lines.append(
            f"SYM{i:04d},EQ,1234.50,1245.75,1220.10,1230.40,1228.00,"
            f"123456,15234.56,15-JAN-2024,4567,INE002A01018,98765,80.05,bhav.csv\n"
        )
    path.write_text("".join(lines))
    return path


class TestFileStats:
    def test_counts_data_rows_excluding_header(self, tmp_path: Path):
        f = _write_csv(tmp_path / "ok.csv", data_rows=2500)
        stats = file_stats(f)
        assert stats.data_rows == 2500
        assert stats.size_bytes > 0

    def test_handles_data_only_file(self, tmp_path: Path):
        f = tmp_path / "no_header.csv"
        f.write_text("123,456\n789,012\n")
        stats = file_stats(f)
        assert stats.data_rows == 2

    def test_raises_for_missing_file(self, tmp_path: Path):
        with pytest.raises(DownloadValidationError, match="not found"):
            file_stats(tmp_path / "missing.csv")


class TestValidateBhavcopySize:
    def test_passes_normal_bhavcopy(self, tmp_path: Path):
        f = _write_csv(tmp_path / "ok.csv", data_rows=2500)
        stats = validate_bhavcopy_size(f)
        assert stats.data_rows == 2500

    def test_rejects_tiny_file(self, tmp_path: Path):
        f = tmp_path / "tiny.csv"
        f.write_text("nope\n")
        with pytest.raises(DownloadValidationError, match="bytes"):
            validate_bhavcopy_size(f)

    def test_rejects_too_few_rows(self, tmp_path: Path):
        f = _write_csv(tmp_path / "short.csv", data_rows=100)
        with pytest.raises(DownloadValidationError, match="data rows"):
            validate_bhavcopy_size(f, min_bytes=0)

    def test_threshold_arguments_override(self, tmp_path: Path):
        f = _write_csv(tmp_path / "tiny_but_allowed.csv", data_rows=10)
        stats = validate_bhavcopy_size(f, min_bytes=0, min_rows=5)
        assert stats.data_rows == 10


class TestValidateAgainstReference:
    def test_passes_when_close_to_reference(self, tmp_path: Path):
        ref = _write_csv(tmp_path / "ref.csv", data_rows=2500)
        cand = _write_csv(tmp_path / "cand.csv", data_rows=2400)
        validate_against_reference(cand, ref)

    def test_rejects_below_ratio(self, tmp_path: Path):
        ref = _write_csv(tmp_path / "ref.csv", data_rows=2500)
        cand = _write_csv(tmp_path / "cand.csv", data_rows=1000)   # 40 %
        with pytest.raises(DownloadValidationError, match="threshold"):
            validate_against_reference(cand, ref)

    def test_empty_reference_raises(self, tmp_path: Path):
        ref = tmp_path / "empty.csv"
        ref.write_text(HEADER)
        cand = _write_csv(tmp_path / "cand.csv", data_rows=2500)
        with pytest.raises(DownloadValidationError, match="zero data rows"):
            validate_against_reference(cand, ref)

    def test_custom_ratio_threshold(self, tmp_path: Path):
        ref = _write_csv(tmp_path / "ref.csv", data_rows=1000)
        cand = _write_csv(tmp_path / "cand.csv", data_rows=400)   # 40 %
        validate_against_reference(cand, ref, min_ratio=0.30)


class TestSha256:
    def test_returns_64_char_hex(self, tmp_path: Path):
        f = tmp_path / "x.csv"
        f.write_text("hello")
        h = file_sha256(f)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_identical_files_same_hash(self, tmp_path: Path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.write_bytes(b"payload")
        b.write_bytes(b"payload")
        assert file_sha256(a) == file_sha256(b)

    def test_different_files_different_hashes(self, tmp_path: Path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.write_bytes(b"one")
        b.write_bytes(b"two")
        assert file_sha256(a) != file_sha256(b)
