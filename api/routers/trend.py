"""Trend Workbench endpoint — multi-day series for §03 of the dashboard.

`GET /trend?subject=&kind=stock|sector&period=` returns the full payload
needed by ``dashboard/section_trend.py``:

    {
      "subject": str, "kind": "stock"|"sector", "period": str,
      "from_date": ISO, "to_date": ISO,
      "price_series": [{"date","close"}, ...],
      "volume_series": [{"date","volume","ret"}, ...],
      "sma_50": [...], "sma_200": [...],
      "rs_vs_nifty_series": [...] | null,
      "iss_series": [...],
      "events": [...],
      "period_stats": {...},
    }

Backend gaps handled gracefully:
    * Nifty 50 index prices not yet ingested (TODO-106) → `rs_vs_nifty_series`
      is ``None``; the frontend hides the overlay and surfaces a pill.
    * Corporate events table may be empty (TODO-119/120) → `events` is `[]`.
    * ISS factor decomposition not computed (TODO-122) → only the scalar
      ``iss_score`` (which is currently 0.0 for everyone) flows through.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from config.database import read_sql_df
from services.trend_stats import (
    compute_period_stats,
    compute_returns,
    compute_sma,
    period_to_lookback_days,
)


router = APIRouter(prefix="/trend", tags=["trend"])


# ----------------------------- Date helpers ------------------------------ #


def _resolve_window(period: str, as_of: Optional[str]) -> tuple[dt.date, dt.date]:
    """Map ``(period, as_of)`` → ``(from_date, to_date)`` inclusive.

    ``YTD`` is resolved as Jan 1 of the calendar year of ``as_of``.
    Unknown periods default to 6 months. Calendar-day math is used for the
    lookback (not trading days) so weekends/holidays don't shift the window.
    """
    if as_of:
        to_d = dt.date.fromisoformat(as_of)
    else:
        to_d = dt.date.today()

    p = period.upper()
    if p == "YTD":
        from_d = dt.date(to_d.year, 1, 1)
    else:
        # period_to_lookback_days returns trading days; approximate as
        # calendar via 1.4× factor (covers weekends + occasional holidays).
        td = period_to_lookback_days(p)
        cal = int(td * 1.4)
        from_d = to_d - dt.timedelta(days=cal)
    return from_d, to_d


# --------------------------- DB query helpers ---------------------------- #


def _fetch_price_history(
    symbols: list[str], from_d: dt.date, to_d: dt.date
) -> pd.DataFrame:
    """Pull ``fact_eod_price`` rows for one or more symbols in a date range."""
    if not symbols:
        return pd.DataFrame()
    placeholders = ",".join(f":sym_{i}" for i in range(len(symbols)))
    params: dict[str, Any] = {"from_d": from_d, "to_d": to_d}
    for i, s in enumerate(symbols):
        params[f"sym_{i}"] = s
    return read_sql_df(
        f"""
        SELECT trade_date, symbol, close, prev_close, total_traded_qty, delivery_pct
        FROM fact_eod_price
        WHERE symbol IN ({placeholders})
          AND trade_date BETWEEN :from_d AND :to_d
        ORDER BY trade_date ASC, symbol ASC
        """,
        params=params,
    )


def _sector_constituents(sector: str, as_of: dt.date) -> list[str]:
    """Return symbols currently in ``sector`` and marked nifty50_member.

    Point-in-time membership via ``dim_nifty50_constituent`` is preferred but
    that table isn't seeded yet (TODO-111). Fall back to ``dim_stock`` filter.
    """
    df = read_sql_df(
        """
        SELECT symbol FROM dim_stock
        WHERE sector = :sector AND nifty50_member = TRUE
        ORDER BY symbol
        """,
        params={"sector": sector},
    )
    return df["symbol"].astype(str).tolist() if not df.empty else []


def _iss_series(symbol: str, from_d: dt.date, to_d: dt.date) -> pd.DataFrame:
    """ISS daily series for ``symbol`` from ``mart_stock_signals``.

    Until the ISS scoring function lands (TODO-122) the column will be 0.0
    across the board, but we still return it so the frontend can render a
    flat line + "pipeline pending" pill rather than break.
    """
    return read_sql_df(
        """
        SELECT calc_date AS trade_date, iss_score
        FROM mart_stock_signals
        WHERE symbol = :sym AND calc_date BETWEEN :from_d AND :to_d
        ORDER BY calc_date ASC
        """,
        params={"sym": symbol, "from_d": from_d, "to_d": to_d},
    )


# ------------------------------ Endpoint -------------------------------- #


@router.get("")
def get_trend(
    subject: str = Query(..., min_length=1, description="Symbol or sector slug"),
    kind: str = Query("stock", pattern="^(stock|sector)$"),
    period: str = Query("6M", description="1M|3M|6M|1Y|3Y|YTD"),
    as_of: Optional[str] = Query(None, description="ISO date; defaults to today"),
):
    """Return the full Trend Workbench payload for one subject."""
    from_d, to_d = _resolve_window(period, as_of)

    if kind == "stock":
        symbols = [subject.upper()]
        sector_name: Optional[str] = None
    else:
        symbols = _sector_constituents(subject, as_of=to_d)
        sector_name = subject
        if not symbols:
            raise HTTPException(
                status_code=404, detail=f"sector '{subject}' has no members"
            )

    df = _fetch_price_history(symbols, from_d, to_d)
    if df.empty:
        return _empty_payload(subject, kind, period, from_d, to_d)

    # Aggregate to one series per (trade_date) — equal-weight when kind=sector
    if kind == "sector":
        agg = (
            df.groupby("trade_date")
            .agg(close=("close", "mean"), total_traded_qty=("total_traded_qty", "sum"),
                 delivery_pct=("delivery_pct", "mean"))
            .reset_index()
            .sort_values("trade_date")
        )
    else:
        agg = (
            df[df["symbol"] == subject.upper()]
            .copy()
            .sort_values("trade_date")
            .reset_index(drop=True)
        )

    if agg.empty:
        return _empty_payload(subject, kind, period, from_d, to_d)

    closes = agg["close"].astype(float).reset_index(drop=True)
    rets = compute_returns(closes)
    sma50 = compute_sma(closes, 50)
    sma200 = compute_sma(closes, 200)

    dates = pd.to_datetime(agg["trade_date"]).dt.date.astype(str).tolist()

    price_series = [
        {"date": d, "close": float(c)} for d, c in zip(dates, closes)
    ]
    volume_series = [
        {
            "date": d,
            "volume": int(v) if pd.notna(v) else 0,
            "ret": float(r) if pd.notna(r) else 0.0,
        }
        for d, v, r in zip(dates, agg.get("total_traded_qty", []), rets)
    ]
    sma50_series = [
        {"date": d, "value": float(v) if pd.notna(v) else None}
        for d, v in zip(dates, sma50)
    ]
    sma200_series = [
        {"date": d, "value": float(v) if pd.notna(v) else None}
        for d, v in zip(dates, sma200)
    ]

    # ISS series (stock mode only — sector aggregation deferred)
    iss_now = iss_avg = None
    iss_series: list[dict[str, Any]] = []
    if kind == "stock":
        iss_df = _iss_series(subject.upper(), from_d, to_d)
        if not iss_df.empty:
            iss_dates = pd.to_datetime(iss_df["trade_date"]).dt.date.astype(str).tolist()
            iss_vals = iss_df["iss_score"].astype(float).tolist()
            iss_series = [{"date": d, "value": v} for d, v in zip(iss_dates, iss_vals)]
            iss_now = float(iss_df["iss_score"].iloc[-1])
            iss_avg = float(iss_df["iss_score"].mean())

    # Avg delivery % (NaN-tolerant)
    delivery_col = agg.get("delivery_pct")
    avg_delivery = (
        float(delivery_col.dropna().mean())
        if delivery_col is not None and not delivery_col.dropna().empty
        else None
    )

    stats = compute_period_stats(
        agg,
        nifty_df=None,  # TODO-106: wire when nifty50_index_prices is seeded
        avg_delivery_pct=avg_delivery,
        iss_now=iss_now,
        iss_period_avg=iss_avg,
    )

    return {
        "subject": subject,
        "kind": kind,
        "period": period.upper(),
        "from_date": from_d.isoformat(),
        "to_date": to_d.isoformat(),
        "price_series": price_series,
        "volume_series": volume_series,
        "sma_50": sma50_series,
        "sma_200": sma200_series,
        "rs_vs_nifty_series": None,  # blocked on TODO-106
        "iss_series": iss_series,
        "events": [],  # blocked on TODO-119/120 (events table populate)
        "period_stats": stats,
        "constituent_count": len(symbols) if kind == "sector" else 1,
        "sector": sector_name,
    }


def _empty_payload(
    subject: str, kind: str, period: str, from_d: dt.date, to_d: dt.date
) -> dict[str, Any]:
    """Return a structurally-complete but empty payload for graceful UI degradation."""
    return {
        "subject": subject,
        "kind": kind,
        "period": period.upper(),
        "from_date": from_d.isoformat(),
        "to_date": to_d.isoformat(),
        "price_series": [],
        "volume_series": [],
        "sma_50": [],
        "sma_200": [],
        "rs_vs_nifty_series": None,
        "iss_series": [],
        "events": [],
        "period_stats": compute_period_stats(pd.DataFrame()),
        "constituent_count": 0,
        "sector": subject if kind == "sector" else None,
    }
