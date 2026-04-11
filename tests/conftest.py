"""Shared test fixtures."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_CSV = FIXTURES_DIR / "sample_bhavcopy.csv"
SAMPLE_CSV_JAN16 = FIXTURES_DIR / "sample_bhavcopy_jan16.csv"
SAMPLE_CSV_JAN17 = FIXTURES_DIR / "sample_bhavcopy_jan17.csv"


@pytest.fixture
def sample_csv_path():
    return SAMPLE_CSV


@pytest.fixture
def sample_csv_jan16():
    return SAMPLE_CSV_JAN16


@pytest.fixture
def sample_csv_jan17():
    return SAMPLE_CSV_JAN17


@pytest.fixture
def parsed_df(sample_csv_path):
    """Parse the sample bhavcopy CSV."""
    from ingestion.bhavcopy_parser import BhavcopyParser

    parser = BhavcopyParser()
    return parser.parse(sample_csv_path, trade_date=date(2024, 1, 15))


@pytest.fixture
def three_days_prices():
    """Load 3 days of price data from test fixtures."""
    from ingestion.bhavcopy_parser import BhavcopyParser

    parser = BhavcopyParser()
    dfs = []
    for d, path in [
        (date(2024, 1, 15), SAMPLE_CSV),
        (date(2024, 1, 16), SAMPLE_CSV_JAN16),
        (date(2024, 1, 17), SAMPLE_CSV_JAN17),
    ]:
        dfs.append(parser.parse(path, trade_date=d))
    return pd.concat(dfs, ignore_index=True)
