"""Corporate Events API Router.

Endpoints for viewing corporate events with filtering and timeline views.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from config.database import read_sql_df

router = APIRouter(prefix="/events", tags=["corporate-events"])


# ============================================================
# Response Models
# ============================================================

class EventResponse(BaseModel):
    event_id: int
    symbol: str
    event_date: str
    event_type: str
    significance: int
    description: str
    is_upcoming: bool
    price_chg_1d: Optional[float] = None
    price_chg_5d: Optional[float] = None
    price_chg_20d: Optional[float] = None
    categorization_method: str
    raw_announcement_text: Optional[str] = None
    follow_up_required: bool


class TimelineEntry(BaseModel):
    event_date: str
    events: list[EventResponse]


class TimelineResponse(BaseModel):
    timeline: list[TimelineEntry]
    total_count: int


class EventSummary(BaseModel):
    symbol: str
    company_name: str
    sector: str
    total_events: int
    upcoming_events: int
    recent_events: int
    avg_significance: float


# ============================================================
# Helper Functions
# ============================================================

def _sanitize_event_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace NaN/inf numeric placeholders in event records."""
    out: list[dict[str, Any]] = []
    for rec in records:
        row: dict[str, Any] = {}
        for k, v in rec.items():
            if v is None:
                row[k] = None
                continue
            try:
                fv = float(v)
                if fv is not None and (fv != fv or fv == float('inf') or fv == float('-inf')):
                    row[k] = None
                    continue
            except (TypeError, ValueError):
                pass
            row[k] = v
        out.append(row)
    return out


def _build_events_query(
    symbol_filter: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    event_type: Optional[str] = None,
    min_significance: int = 1,
    upcoming_only: bool = False,
) -> tuple[str, dict]:
    """Build events query with optional filters."""
    conditions = ["1=1"]
    params: dict = {}

    if symbol_filter:
        conditions.append("symbol = :ev_symbol")
        params["ev_symbol"] = symbol_filter.upper()

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

    if upcoming_only:
        conditions.append("event_date > CURRENT_DATE")

    conditions.append("symbol IN (SELECT symbol FROM dim_stock WHERE nifty50_member = TRUE)")

    where = " AND ".join(conditions)
    return where, params


# ============================================================
# Endpoints
# ============================================================

@router.get("", response_model=list[EventResponse])
async def list_events(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    from_date: Optional[str] = Query(None, description="From date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="To date (YYYY-MM-DD)"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    min_significance: int = Query(1, ge=1, le=5, description="Minimum significance score"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
):
    """List corporate events with optional filters.

    Returns events for Nifty 50 stocks. Event types include:
    - Earnings, Leadership_Change, M&A, Large_Order
    - Pledging_Change, Rating_Change, Regulatory, Other
    """
    where, params = _build_events_query(
        symbol_filter=symbol,
        from_date=from_date,
        to_date=to_date,
        event_type=event_type,
        min_significance=min_significance,
    )

    df = read_sql_df(f"""
        SELECT event_id, symbol, event_date, event_type,
               significance_score AS significance,
               categorization_method,
               event_summary AS description,
               raw_announcement_text,
               price_chg_1d, price_chg_5d, price_chg_20d,
               follow_up_required,
               (event_date > CURRENT_DATE) AS is_upcoming
        FROM fact_corporate_event
        WHERE {where}
        ORDER BY event_date DESC LIMIT :limit
    """, params={**params, "limit": limit})

    df["event_date"] = df["event_date"].apply(lambda d: d.isoformat() if hasattr(d, "isoformat") else d)
    return _sanitize_event_records(df.to_dict("records"))


@router.get("/upcoming", response_model=list[EventResponse])
async def get_upcoming_events(
    days_ahead: int = Query(30, ge=1, le=365, description="Number of days ahead to look"),
    min_significance: int = Query(1, ge=1, le=5),
):
    """Get upcoming events within N days.

    Returns events that are scheduled but not yet occurred,
    ordered by event date ascending (soonest first).
    """
    where, params = _build_events_query(
        min_significance=min_significance,
        upcoming_only=True,
    )
    where = f"{where} AND event_date <= CURRENT_DATE + INTERVAL '{days_ahead} days'"

    df = read_sql_df(f"""
        SELECT event_id, symbol, event_date, event_type,
               significance_score AS significance,
               categorization_method,
               event_summary AS description,
               raw_announcement_text,
               price_chg_1d, price_chg_5d, price_chg_20d,
               follow_up_required,
               TRUE AS is_upcoming
        FROM fact_corporate_event
        WHERE {where}
        ORDER BY event_date ASC
    """, params=params)

    df["event_date"] = df["event_date"].apply(lambda d: d.isoformat() if hasattr(d, "isoformat") else d)
    return _sanitize_event_records(df.to_dict("records"))


@router.get("/timeline", response_model=TimelineResponse)
async def get_event_timeline(
    from_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    min_significance: int = Query(1, ge=1, le=5),
):
    """Return events grouped by date for calendar/timeline view.

    Groups events by date and returns a structured timeline
    suitable for calendar views and event feeds.
    """
    where, params = _build_events_query(
        from_date=from_date,
        to_date=to_date,
        event_type=event_type,
        min_significance=min_significance,
    )

    df = read_sql_df(f"""
        SELECT event_id, symbol, event_date, event_type,
               significance_score AS significance,
               categorization_method,
               event_summary AS description,
               raw_announcement_text,
               price_chg_1d, price_chg_5d, price_chg_20d,
               follow_up_required,
               (event_date > CURRENT_DATE) AS is_upcoming
        FROM fact_corporate_event
        WHERE {where}
        ORDER BY event_date, event_type, significance_score DESC
    """, params=params)

    if df.empty:
        return TimelineResponse(timeline=[], total_count=0)

    df["event_date"] = df["event_date"].apply(lambda d: d.isoformat() if hasattr(d, "isoformat") else d)
    events = _sanitize_event_records(df.to_dict("records"))

    # Group by date
    timeline_dict: dict[str, list[EventResponse]] = {}
    for event in events:
        date_str = event["event_date"]
        if date_str not in timeline_dict:
            timeline_dict[date_str] = []
        timeline_dict[date_str].append(event)

    timeline = [
        TimelineEntry(event_date=date_str, events=sorted(events, key=lambda e: (-e["significance"], e["event_type"])))
        for date_str, events in sorted(timeline_dict.items())
    ]

    return TimelineResponse(timeline=timeline, total_count=len(events))


@router.get("/symbol/{symbol}", response_model=list[EventResponse])
async def get_symbol_events(
    symbol: str,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    min_significance: int = Query(1, ge=1, le=5),
    limit: int = Query(50, ge=1, le=200),
):
    """Get all events for a specific symbol.

    Returns historical and upcoming events for the given symbol,
    sorted by event date descending.
    """
    where, params = _build_events_query(
        symbol_filter=symbol,
        from_date=from_date,
        to_date=to_date,
        min_significance=min_significance,
    )

    df = read_sql_df(f"""
        SELECT event_id, symbol, event_date, event_type,
               significance_score AS significance,
               categorization_method,
               event_summary AS description,
               raw_announcement_text,
               price_chg_1d, price_chg_5d, price_chg_20d,
               follow_up_required,
               (event_date > CURRENT_DATE) AS is_upcoming
        FROM fact_corporate_event
        WHERE {where}
        ORDER BY event_date DESC LIMIT :limit
    """, params={**params, "limit": limit})

    df["event_date"] = df["event_date"].apply(lambda d: d.isoformat() if hasattr(d, "isoformat") else d)
    return _sanitize_event_records(df.to_dict("records"))


@router.get("/summary/{symbol}", response_model=EventSummary)
async def get_symbol_summary(
    symbol: str,
):
    """Get summary of events for a symbol.

    Returns aggregated statistics about the symbol's events
    including total count, upcoming count, and average significance.
    """
    # Check if symbol exists and is Nifty 50
    stock_df = read_sql_df("""
        SELECT symbol, company_name, sector
        FROM dim_stock
        WHERE symbol = :symbol AND nifty50_member = TRUE
    """, params={"symbol": symbol.upper()})

    if stock_df.empty:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found or not a Nifty 50 constituent")

    stock = stock_df.iloc[0].to_dict()

    # Get event counts
    counts_df = read_sql_df("""
        SELECT
            COUNT(*) as total_events,
            SUM(CASE WHEN event_date > CURRENT_DATE THEN 1 ELSE 0 END) as upcoming_events,
            SUM(CASE WHEN event_date > CURRENT_DATE - INTERVAL '30 days' THEN 1 ELSE 0 END) as recent_events,
            AVG(significance_score) as avg_significance
        FROM fact_corporate_event
        WHERE symbol = :symbol
    """, params={"symbol": symbol.upper()})

    counts = counts_df.iloc[0].to_dict()

    return EventSummary(
        symbol=stock["symbol"],
        company_name=stock["company_name"],
        sector=stock["sector"],
        total_events=int(counts["total_events"] or 0),
        upcoming_events=int(counts["upcoming_events"] or 0),
        recent_events=int(counts["recent_events"] or 0),
        avg_significance=float(counts["avg_significance"] or 0),
    )


@router.get("/type/{event_type}", response_model=list[EventResponse])
async def get_events_by_type(
    event_type: str,
    min_significance: int = Query(1, ge=1, le=5),
    limit: int = Query(50, ge=1, le=200),
):
    """Get events filtered by event type.

    Event types:
    - Earnings: Quarterly/annual results
    - Leadership_Change: CEO, board changes
    - M&A: Mergers and acquisitions
    - Large_Order: Block deals
    - Pledging_Change: Promoter pledging
    - Rating_Change: Analyst rating changes
    - Regulatory: Regulatory notices
    - Other: Miscellaneous events
    """
    df = read_sql_df("""
        SELECT event_id, symbol, event_date, event_type,
               significance_score AS significance,
               categorization_method,
               event_summary AS description,
               raw_announcement_text,
               price_chg_1d, price_chg_5d, price_chg_20d,
               follow_up_required,
               (event_date > CURRENT_DATE) AS is_upcoming
        FROM fact_corporate_event
        WHERE LOWER(event_type) = LOWER(:event_type)
          AND significance_score >= :min_sig
          AND symbol IN (SELECT symbol FROM dim_stock WHERE nifty50_member = TRUE)
        ORDER BY event_date DESC LIMIT :limit
    """, params={"event_type": event_type.strip(), "min_sig": min_significance, "limit": limit})

    df["event_date"] = df["event_date"].apply(lambda d: d.isoformat() if hasattr(d, "isoformat") else d)
    return _sanitize_event_records(df.to_dict("records"))
