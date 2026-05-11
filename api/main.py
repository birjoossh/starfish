"""FastAPI application — Nifty 50 Dashboard API.

Endpoints:
    GET /health          — DB connectivity and table row counts
    GET /constituents    — All Nifty 50 stocks with metadata
    GET /prices/{symbol} — Full price history for a symbol
    GET /prices/{symbol}/range — Filtered price history by date range

    /events              — Corporate events router
    /watchlist           — Watchlist management router

Usage:
    uvicorn api.main:app --reload
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.database import check_db_health, read_sql_df

# Import routers
from api.routers import events, trend, watchlist


def _sanitize_api_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace NaN/inf numeric placeholders so JSON encoding succeeds."""
    out: list[dict[str, Any]] = []
    for rec in records:
        row: dict[str, Any] = {}
        for k, v in rec.items():
            if v is None:
                row[k] = None
                continue
            try:
                fv = float(v)
                if math.isnan(fv) or math.isinf(fv):
                    row[k] = None
                    continue
            except (TypeError, ValueError):
                pass
            row[k] = v
        out.append(row)
    return out


app = FastAPI(
    title="Nifty 50 Dashboard API",
    description="Investment monitoring dashboard for Nifty 50 constituents",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(events.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")
app.include_router(trend.router)  # exposed at /trend (no /api/v1 prefix for Streamlit)


# ---- Response models ----

class Stock(BaseModel):
    symbol: str
    company_name: str
    sector: str
    industry: Optional[str] = None
    nifty50_member: bool
    isin: str


class PriceRow(BaseModel):
    trade_date: date
    symbol: str
    open: float
    high: float
    low: float
    close: float
    prev_close: float
    total_traded_qty: int
    total_traded_value_lakh: float
    total_trades: int
    series: str


class HealthResponse(BaseModel):
    status: str
    tables: dict


# ---- Endpoints ----

@app.get("/health", response_model=HealthResponse)
def health():
    """Check DB connectivity and return table row counts."""
    return check_db_health()


@app.get("/constituents", response_model=list[Stock])
def get_constituents():
    """Return all Nifty 50 stock master data."""
    df = read_sql_df("""
        SELECT symbol, company_name, sector, industry, nifty50_member, isin
        FROM dim_stock
        WHERE nifty50_member = TRUE
        ORDER BY symbol COLLATE "C"
    """)
    if df.empty:
        return []
    return df.to_dict("records")


@app.get("/prices/{symbol}", response_model=list[PriceRow])
def get_prices(symbol: str):
    """Return full price history for a symbol."""
    df = read_sql_df("""
        SELECT trade_date, symbol, open, high, low, close, prev_close,
               total_traded_qty, total_traded_value_lakh, total_trades, series
        FROM fact_eod_price
        WHERE symbol = :symbol
        ORDER BY trade_date
    """, params={"symbol": symbol.upper()})

    if df.empty:
        raise HTTPException(status_code=404, detail=f"No price data found for {symbol}")

    df["trade_date"] = df["trade_date"].apply(lambda d: d.isoformat() if hasattr(d, "isoformat") else d)
    return df.to_dict("records")


@app.get("/prices/{symbol}/range", response_model=list[PriceRow])
def get_prices_range(
    symbol: str,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
):
    """Return price history for a symbol within a date range."""
    df = read_sql_df("""
        SELECT trade_date, symbol, open, high, low, close, prev_close,
               total_traded_qty, total_traded_value_lakh, total_trades, series
        FROM fact_eod_price
        WHERE symbol = :symbol
          AND trade_date >= :from_date
          AND trade_date <= :to_date
        ORDER BY trade_date
    """, params={"symbol": symbol.upper(), "from_date": from_date, "to_date": to_date})

    df["trade_date"] = df["trade_date"].apply(lambda d: d.isoformat() if hasattr(d, "isoformat") else d)
    return df.to_dict("records")


@app.get("/market-overview")
def get_market_overview(calc_date: Optional[str] = Query(None)):
    """Return aggregated stats for the market overview page."""
    
    # Defaults to max date if not specified
    date_filter = "s.calc_date = :calc_date" if calc_date else "s.calc_date = (SELECT MAX(calc_date) FROM mart_stock_signals)"
    
    # 1. Sector Breadth Aggregates — restrict to current Nifty 50 constituents
    df = read_sql_df(f"""
        SELECT
            d.sector,
            COUNT(s.symbol) as num_stocks,
            SUM(CASE WHEN s.return_1d > 0 THEN 1 ELSE 0 END) as advancing,
            SUM(CASE WHEN s.return_1d < 0 THEN 1 ELSE 0 END) as declining,
            AVG(s.return_1d) as avg_return_1d,
            AVG(s.return_1m) as avg_return_1m,
            AVG(s.iss_score) as avg_iss
        FROM mart_stock_signals s
        JOIN dim_stock d ON s.symbol = d.symbol
        WHERE {date_filter}
          AND d.nifty50_member = TRUE
        GROUP BY d.sector
    """, params={"calc_date": calc_date} if calc_date else {})

    # 2. Raw Signal Rows (for treemap rendering directly on client)
    raw = read_sql_df(f"""
        SELECT s.symbol, d.company_name, d.sector, s.return_1d, s.return_1m, s.return_1y, s.iss_score
        FROM mart_stock_signals s
        JOIN dim_stock d ON s.symbol = d.symbol
        WHERE {date_filter}
          AND d.nifty50_member = TRUE
    """, params={"calc_date": calc_date} if calc_date else {})
    
    return {
        "sector_breadth": df.to_dict("records") if not df.empty else [],
        "components": raw.to_dict("records") if not raw.empty else []
    }


@app.get("/movers")
def get_movers(calc_date: Optional[str] = Query(None)):
    """Return top gainers, losers, and full vol array for scatter plots."""
    date_filter = "s.calc_date = :calc_date" if calc_date else "s.calc_date = (SELECT MAX(calc_date) FROM mart_stock_signals)"
    
    # Extract Movers Logic — restrict to current Nifty 50 constituents
    df = read_sql_df(f"""
        SELECT s.symbol, d.company_name, d.sector, p.close,
               s.return_1d, s.return_1m, s.vol_ratio_1d,
               s.signal_category, s.iss_score
        FROM mart_stock_signals s
        JOIN dim_stock d ON s.symbol = d.symbol
        LEFT JOIN fact_eod_price p ON s.symbol = p.symbol AND s.calc_date = p.trade_date
        WHERE {date_filter}
          AND d.nifty50_member = TRUE
    """, params={"calc_date": calc_date} if calc_date else {})
    
    if df.empty:
        return []
        
    df = df.fillna(0) # clean nans
    # Top 10 Gainers / Losers calculated explicitly by Backend
    gainers = df.nlargest(10, 'return_1d').to_dict('records')
    losers = df.nsmallest(10, 'return_1d').to_dict('records')
    all_data = df.to_dict("records")
    
    return {
        "gainers": gainers,
        "losers": losers,
        "all_data": all_data
    }


@app.get("/events")
def get_events(
    symbol: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    min_significance: int = Query(1),
):
    """List corporate events with optional filters (reads fact_corporate_event)."""
    conditions = ["1=1"]
    params: dict = {}
    if symbol:
        conditions.append("symbol = :ev_symbol")
        params["ev_symbol"] = symbol.upper()
    if from_date:
        conditions.append("event_date >= :ev_from_date")
        params["ev_from_date"] = from_date
    if to_date:
        conditions.append("event_date <= :ev_to_date")
        params["ev_to_date"] = to_date
    if event_type:
        conditions.append(
            "(LOWER(event_type) = LOWER(:ev_event_type) "
            "OR UPPER(COALESCE(raw_announcement_text, '')) LIKE UPPER(:ev_type_like) "
            "OR UPPER(COALESCE(event_summary, '')) LIKE UPPER(:ev_type_like))"
        )
        params["ev_event_type"] = event_type.strip()
        params["ev_type_like"] = f"%{event_type.strip()}%"
    if min_significance > 1:
        conditions.append("significance_score >= :ev_min_sig")
        params["ev_min_sig"] = min_significance

    where = " AND ".join(conditions)
    df = read_sql_df(f"""
        SELECT symbol, event_date, event_type,
               significance_score AS significance,
               categorization_method,
               event_summary AS description,
               raw_announcement_text,
               (event_date > CURRENT_DATE) AS is_upcoming
        FROM fact_corporate_event
        WHERE {where}
        ORDER BY event_date DESC LIMIT 500
    """, params=params)
    df["event_date"] = df["event_date"].apply(lambda d: d.isoformat() if hasattr(d, "isoformat") else d)
    return _sanitize_api_records(df.to_dict("records"))


@app.get("/actions")
def get_actions(
    symbol: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
):
    """List corporate actions (dividends, splits, bonuses) from fact_corporate_action."""
    conditions = ["1=1"]
    params: dict = {}
    if symbol:
        conditions.append("symbol = :ca_symbol")
        params["ca_symbol"] = symbol.upper()
    if from_date:
        conditions.append("ex_date >= :ca_from_date")
        params["ca_from_date"] = from_date
    if to_date:
        conditions.append("ex_date <= :ca_to_date")
        params["ca_to_date"] = to_date
    if event_type:
        conditions.append("LOWER(action_type) = LOWER(:ca_action_type)")
        params["ca_action_type"] = event_type.strip()

    where = " AND ".join(conditions)
    df = read_sql_df(f"""
        SELECT symbol,
               purpose_text AS purpose,
               action_type AS event_type,
               ex_date, record_date,
               CAST(NULL AS INTEGER) AS significance,
               dividend_amount_per_share AS amount,
               ratio_numerator AS ratio_num,
               ratio_denominator AS ratio_den
        FROM fact_corporate_action
        WHERE {where}
        ORDER BY ex_date DESC LIMIT 500
    """, params=params)
    for col in ["ex_date", "record_date"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda d: d.isoformat() if hasattr(d, "isoformat") else d)
    return _sanitize_api_records(df.to_dict("records"))
