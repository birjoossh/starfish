"""Synthetic data factories for integration tests.

All generated data uses far-future dates (2099+) so it never overlaps
with real production data in the dev database.

Usage:
    from tests.integration.fixtures.factories import (
        build_bhavcopy_csv,
        build_bhavcopy_csv_bad_headers,
        build_corp_actions_csv,
        build_price_dataframe,
        INTG_TEST_DATE,
    )
"""

from __future__ import annotations

import io
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# ─── sentinel dates — never overlap real data ──────────────────────────────
INTG_TEST_DATE = date(2099, 6, 1)   # base date for single-day tests
INTG_TEST_DATE_2 = date(2099, 6, 2)
INTG_TEST_DATE_3 = date(2099, 6, 3)

# Symbols guaranteed to be in dim_stock (seeded during Phase-1 setup)
NIFTY50_SYMBOLS = [
    "RELIANCE", "HDFCBANK", "INFY", "TCS", "ICICIBANK",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "HINDUNILVR",
]

# Representative symbols for targeted tests
SYM_A = "RELIANCE"
SYM_B = "HDFCBANK"
SYM_C = "INFY"


# ─── NSE bhavcopy CSV helpers ───────────────────────────────────────────────

def _bhavcopy_header() -> str:
    return "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN"


def _bhavcopy_row(
    symbol: str,
    trade_date: date,
    open_: float = 1000.0,
    high: float = 1050.0,
    low: float = 980.0,
    close: float = 1020.0,
    prev_close: float = 1000.0,
    qty: int = 5_000_000,
    isin: str = "INE000X01000",
) -> str:
    ts = trade_date.strftime("%d-%b-%Y").upper()
    val = round(close * qty / 1e5, 2)          # total value in lakh
    trades = qty // 50
    return (
        f"{symbol},EQ,{open_},{high},{low},{close},{close},{prev_close},"
        f"{qty},{val},{ts},{trades},{isin}"
    )


def build_bhavcopy_csv(
    tmp_path: Path,
    symbols: list[str] | None = None,
    trade_date: date = INTG_TEST_DATE,
    rows: dict[str, dict] | None = None,
    filename: str | None = None,
) -> Path:
    """Build a valid NSE bhavcopy CSV with full expected headers.

    Args:
        tmp_path: Directory to write the file into.
        symbols: List of symbols. Defaults to NIFTY50_SYMBOLS[:3].
        trade_date: Date for the TIMESTAMP column.
        rows: Optional per-symbol overrides {symbol: {close, prev_close, qty, …}}.
        filename: Override the generated filename.

    Returns:
        Path to the generated CSV file.
    """
    syms = symbols or NIFTY50_SYMBOLS[:3]
    overrides = rows or {}
    fname = filename or f"bhav_{trade_date.strftime('%Y%m%d')}.csv"
    csv_path = tmp_path / fname

    lines = [_bhavcopy_header()]
    for sym in syms:
        extra = overrides.get(sym, {})
        lines.append(_bhavcopy_row(sym, trade_date, **extra))

    csv_path.write_text("\n".join(lines) + "\n")
    return csv_path


def build_bhavcopy_csv_bad_headers(tmp_path: Path, trade_date: date = INTG_TEST_DATE) -> Path:
    """Build a bhavcopy CSV with a missing required header (TOTALTRADES removed)."""
    bad_header = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,ISIN"
    csv_path = tmp_path / "bad_headers.csv"
    csv_path.write_text(
        bad_header + "\n"
        + f"RELIANCE,EQ,1000,1050,980,1020,1020,1000,5000000,51.00,"
          f"{trade_date.strftime('%d-%b-%Y').upper()},INE002A01018\n"
    )
    return csv_path


def build_bhavcopy_csv_all_filtered(tmp_path: Path, trade_date: date = INTG_TEST_DATE) -> Path:
    """Build a bhavcopy CSV where all rows have a non-EQ series (gets filtered out)."""
    csv_path = tmp_path / "all_filtered.csv"
    ts = trade_date.strftime("%d-%b-%Y").upper()
    csv_path.write_text(
        _bhavcopy_header() + "\n"
        f"RELIANCE,MF,1000,1050,980,1020,1020,1000,5000000,51.00,{ts},100000,INE002A01018\n"
    )
    return csv_path


# ─── Multi-day price DataFrames ──────────────────────────────────────────────

def build_price_dataframe(
    symbols: list[str] | None = None,
    start_date: date = INTG_TEST_DATE,
    n_days: int = 30,
    base_close: float = 1000.0,
    vol_multiplier: float = 1.0,
) -> pd.DataFrame:
    """Build a synthetic multi-symbol, multi-day price DataFrame.

    Prices grow by 0.1% per day. Volume is constant × vol_multiplier for each day.

    Args:
        symbols: List of symbols.
        start_date: First trade date.
        n_days: Number of calendar days to generate.
        base_close: Starting close price.
        vol_multiplier: Multiply to the base volume (5_000_000).

    Returns:
        DataFrame with columns matching fact_eod_price schema (plus source_file).
    """
    syms = symbols or [SYM_A, SYM_B]
    records = []
    base_qty = int(5_000_000 * vol_multiplier)

    for sym in syms:
        price = base_close
        prev = price
        for i in range(n_days):
            d = start_date + timedelta(days=i)
            price = round(price * 1.001, 2)
            records.append({
                "trade_date": d,
                "symbol": sym,
                "open": round(prev * 1.0005, 2),
                "high": round(price * 1.005, 2),
                "low": round(prev * 0.995, 2),
                "close": price,
                "prev_close": prev,
                "total_traded_qty": base_qty,
                "total_traded_value_lakh": round(price * base_qty / 1e5, 2),
                "total_trades": base_qty // 50,
                "series": "EQ",
                "delivery_qty": None,
                "delivery_pct": None,
                "source_file": f"test_{d.strftime('%Y%m%d')}.csv",
            })
            prev = price

    return pd.DataFrame(records)


def build_price_dataframe_with_spike(
    symbol: str,
    base_date: date,
    n_days: int = 25,
    spike_multiplier: float = 3.0,
) -> pd.DataFrame:
    """Build a price DataFrame where the last day has a volume spike.

    The volume on the last day is spike_multiplier × the 20-day average,
    which will trigger a Volume Anomaly signal.
    """
    base_qty = 2_000_000
    records = []
    price = 1000.0
    prev = price

    for i in range(n_days):
        d = base_date + timedelta(days=i)
        price = round(price * 1.001, 2)
        is_spike_day = i == n_days - 1
        qty = int(base_qty * spike_multiplier) if is_spike_day else base_qty
        records.append({
            "trade_date": d,
            "symbol": symbol,
            "open": round(prev * 1.0005, 2),
            "high": round(price * 1.005, 2),
            "low": round(prev * 0.995, 2),
            "close": price,
            "prev_close": prev,
            "total_traded_qty": qty,
            "total_traded_value_lakh": round(price * qty / 1e5, 2),
            "total_trades": qty // 50,
            "series": "EQ",
            "delivery_qty": None,
            "delivery_pct": None,
            "source_file": f"test_{d.strftime('%Y%m%d')}.csv",
        })
        prev = price

    return pd.DataFrame(records)


def build_price_dataframe_drawdown(
    symbol: str,
    base_date: date,
    n_days: int = 265,
    peak_day: int = 250,
    drawdown_pct: float = 0.25,
) -> pd.DataFrame:
    """Build a price DataFrame where the price peaks then drops by drawdown_pct.

    Used to test the Drawdown Scanner: stock ≥20% off 52-week high.
    """
    records = []
    peak_price = 2000.0
    trough_price = round(peak_price * (1 - drawdown_pct), 2)

    for i in range(n_days):
        d = base_date + timedelta(days=i)
        if i < peak_day:
            price = round(peak_price * (1 + 0.0001 * i), 2)
        else:
            # Smooth decline
            pct = (i - peak_day) / (n_days - peak_day)
            price = round(peak_price - pct * (peak_price - trough_price), 2)
        prev_price = price * 0.999

        records.append({
            "trade_date": d,
            "symbol": symbol,
            "open": round(prev_price * 1.001, 2),
            "high": round(price * 1.002, 2),
            "low": round(prev_price * 0.998, 2),
            "close": price,
            "prev_close": round(prev_price, 2),
            "total_traded_qty": 5_000_000,
            "total_traded_value_lakh": round(price * 5_000_000 / 1e5, 2),
            "total_trades": 100_000,
            "series": "EQ",
            "delivery_qty": None,
            "delivery_pct": None,
            "source_file": f"test_{d.strftime('%Y%m%d')}.csv",
        })

    return pd.DataFrame(records)


# ─── Corporate actions CSV helpers ───────────────────────────────────────────

def build_corp_actions_csv(
    tmp_path: Path,
    rows: list[dict] | None = None,
) -> Path:
    """Build a corporate actions CSV.

    Args:
        tmp_path: Directory to write into.
        rows: List of dicts with keys: symbol, purpose, ex_date, record_date.
    """
    default_rows = [
        {
            "Symbol": SYM_A,
            "Company Name": "Test Corp A",
            "Purpose": "INTERIM DIVIDEND - RS 10 PER SHARE",
            "Ex-Date": "01-Jun-2099",
            "Record Date": "03-Jun-2099",
        },
        {
            "Symbol": SYM_B,
            "Company Name": "Test Corp B",
            "Purpose": "BONUS 1:1",
            "Ex-Date": "02-Jun-2099",
            "Record Date": "04-Jun-2099",
        },
    ]
    data = rows or default_rows
    csv_path = tmp_path / "corp_actions_2099.csv"
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False)
    return csv_path
