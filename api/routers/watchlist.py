"""Watchlist API Router.

Endpoints for managing user watchlists with persistent storage.
Supports pinning, annotations, and multiple users.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from config.database import read_sql_df

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


# ============================================================
# Request/Response Models
# ============================================================

class WatchlistItem(BaseModel):
    watchlist_id: int
    symbol: str
    company_name: str
    sector: str
    added_date: str
    reason: Optional[str] = None
    pinned: bool
    created_at: str


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]
    total_count: int
    pinned_count: int


class AddWatchlistRequest(BaseModel):
    symbol: str
    reason: Optional[str] = None
    pinned: bool = False


class UpdateWatchlistRequest(BaseModel):
    reason: Optional[str] = None
    pinned: Optional[bool] = None


class WatchlistCategoryItem(BaseModel):
    symbol: str
    company_name: str
    sector: str
    signal_category: str
    iss_score: float
    return_1d: float
    return_1m: float
    vol_ratio_1d: float
    drawdown_from_52w_high_pct: float
    key_reason: str


class WatchlistCategoryResponse(BaseModel):
    category_name: str
    items: list[WatchlistCategoryItem]
    count: int


# ============================================================
# Helper Functions
# ============================================================

def _sanitize_watchlist_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Clean watchlist records for JSON serialization."""
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


def _get_user_id() -> int:
    """Get default user ID (MVP: single user support)."""
    # TODO: Replace with actual user authentication
    return 1  # Default user for MVP


def _get_or_create_user(username: str = "default", email: str = "user@starfish.local") -> int:
    """Get existing user or create new one."""
    # Check if user exists
    existing = read_sql_df("""
        SELECT user_id FROM watchlist_users WHERE username = :username
    """, params={"username": username})

    if not existing.empty:
        return int(existing.iloc[0]["user_id"])

    # Create new user
    read_sql_df("""
        INSERT INTO watchlist_users (username, email)
        VALUES (:username, :email)
        RETURNING user_id
    """, params={"username": username, "email": email})

    # Fetch the new ID
    new_user = read_sql_df("""
        SELECT user_id FROM watchlist_users WHERE username = :username
    """, params={"username": username})
    return int(new_user.iloc[0]["user_id"])


# ============================================================
# Endpoints
# ============================================================

@router.get("", response_model=WatchlistResponse)
async def get_user_watchlist(
    user_id: int = Query(1, description="User ID (default: 1 for MVP)"),
):
    """Get user's watchlist with full stock details."""
    df = read_sql_df("""
        SELECT w.watchlist_id, w.symbol, d.company_name, d.sector,
               w.added_date, w.reason, w.pinned, w.created_at
        FROM user_watchlist w
        JOIN dim_stock d ON w.symbol = d.symbol
        WHERE w.user_id = :user_id
        ORDER BY w.pinned DESC, w.added_date DESC
    """, params={"user_id": user_id})

    if df.empty:
        return WatchlistResponse(items=[], total_count=0, pinned_count=0)

    df["added_date"] = df["added_date"].apply(lambda d: d.isoformat() if hasattr(d, "isoformat") else d)
    df["created_at"] = df["created_at"].apply(lambda d: d.isoformat() if hasattr(d, "isoformat") else d)

    items = [
        WatchlistItem(
            watchlist_id=int(row["watchlist_id"]),
            symbol=row["symbol"],
            company_name=row["company_name"],
            sector=row["sector"],
            added_date=row["added_date"],
            reason=row["reason"],
            pinned=bool(row["pinned"]),
            created_at=row["created_at"],
        )
        for _, row in df.iterrows()
    ]

    return WatchlistResponse(
        items=items,
        total_count=len(items),
        pinned_count=int(df["pinned"].sum()),
    )


@router.post("", response_model=WatchlistItem)
async def add_to_watchlist(
    request: AddWatchlistRequest,
    user_id: int = Query(1, description="User ID"),
):
    """Add a symbol to the watchlist.

    If the symbol is already on the watchlist, returns the existing entry.
    """
    # Validate symbol exists
    stock_df = read_sql_df("""
        SELECT symbol, company_name, sector
        FROM dim_stock
        WHERE symbol = :symbol
    """, params={"symbol": request.symbol.upper()})

    if stock_df.empty:
        raise HTTPException(status_code=404, detail=f"Symbol {request.symbol} not found")

    stock = stock_df.iloc[0]

    # Check if already in watchlist
    existing = read_sql_df("""
        SELECT watchlist_id, symbol, company_name, sector, added_date, reason, pinned, created_at
        FROM user_watchlist
        WHERE user_id = :user_id AND symbol = :symbol
    """, params={"user_id": user_id, "symbol": request.symbol.upper()})

    if not existing.empty:
        existing_row = existing.iloc[0]
        return WatchlistItem(
            watchlist_id=int(existing_row["watchlist_id"]),
            symbol=existing_row["symbol"],
            company_name=existing_row["company_name"],
            sector=existing_row["sector"],
            added_date=existing_row["added_date"].isoformat() if hasattr(existing_row["added_date"], "isoformat") else existing_row["added_date"],
            reason=existing_row["reason"],
            pinned=bool(existing_row["pinned"]),
            created_at=existing_row["created_at"].isoformat() if hasattr(existing_row["created_at"], "isoformat") else existing_row["created_at"],
        )

    # Insert new entry
    watchlist_id = read_sql_df("""
        INSERT INTO user_watchlist (user_id, symbol, reason, pinned)
        VALUES (:user_id, :symbol, :reason, :pinned)
        RETURNING watchlist_id
    """, params={
        "user_id": user_id,
        "symbol": request.symbol.upper(),
        "reason": request.reason,
        "pinned": request.pinned,
    })

    return WatchlistItem(
        watchlist_id=int(watchlist_id.iloc[0]["watchlist_id"]),
        symbol=request.symbol.upper(),
        company_name=stock["company_name"],
        sector=stock["sector"],
        added_date=date.today().isoformat(),
        reason=request.reason,
        pinned=request.pinned,
        created_at=date.today().isoformat(),
    )


@router.delete("/{symbol}")
async def remove_from_watchlist(
    symbol: str,
    user_id: int = Query(1, description="User ID"),
):
    """Remove a symbol from the watchlist."""
    result = read_sql_df("""
        DELETE FROM user_watchlist
        WHERE user_id = :user_id AND symbol = :symbol
    """, params={"user_id": user_id, "symbol": symbol.upper()})

    return {"message": f"Removed {symbol.upper()} from watchlist"}


@router.patch("/{symbol}")
async def update_watchlist_item(
    symbol: str,
    request: UpdateWatchlistRequest,
    user_id: int = Query(1, description="User ID"),
):
    """Update watchlist item (reason, pin status)."""
    updates = []
    params: dict = {"user_id": user_id, "symbol": symbol.upper()}

    if request.reason is not None:
        updates.append("reason = :reason")
        params["reason"] = request.reason
    if request.pinned is not None:
        updates.append("pinned = :pinned")
        params["pinned"] = request.pinned

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    query = f"""
        UPDATE user_watchlist
        SET {', '.join(updates)}
        WHERE user_id = :user_id AND symbol = :symbol
        RETURNING watchlist_id, reason, pinned
    """

    result = read_sql_df(query, params=params)

    if result.empty:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found in watchlist")

    row = result.iloc[0]
    return {
        "message": "Updated successfully",
        "watchlist_id": int(row["watchlist_id"]),
        "reason": row["reason"],
        "pinned": bool(row["pinned"]),
    }


@router.post("/{symbol}/pin")
async def toggle_pin(
    symbol: str,
    pinned: bool = True,
    user_id: int = Query(1, description="User ID"),
):
    """Pin or unpin a watchlist item."""
    result = read_sql_df("""
        UPDATE user_watchlist
        SET pinned = :pinned
        WHERE user_id = :user_id AND symbol = :symbol
        RETURNING watchlist_id
    """, params={"user_id": user_id, "symbol": symbol.upper(), "pinned": pinned})

    if result.empty:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found in watchlist")

    return {"message": f"{'Pinned' if pinned else 'Unpinned'} {symbol.upper()}", "watchlist_id": int(result.iloc[0]["watchlist_id"])}


@router.get("/categories", response_model=list[WatchlistCategoryResponse])
async def get_category_suggestions(
    min_iss: float = Query(50, description="Minimum ISS score threshold"),
):
    """Get auto-populated watchlist categories.

    Returns candidates for each category based on current signal data:
    - Contrarian Opportunities: Deep drawdown + volume contraction
    - Momentum Leaders: High ISS + positive RS
    - Event-Driven Candidates: Event flag + upcoming events
    - Volume-Confirmed Movers: Volume spike + positive return
    """
    # Get latest signal data
    signals_df = read_sql_df("""
        SELECT s.symbol, d.company_name, d.sector, s.signal_category, s.iss_score,
               s.return_1d, s.return_1m, s.vol_ratio_1d,
               s.drawdown_from_52w_high_pct, s.momentum_flag, s.event_flag,
               s.accumulation_flag, s.rs_vs_nifty_3m, s.volume_trend_3m
        FROM mart_stock_signals s
        JOIN dim_stock d ON s.symbol = d.symbol
        WHERE s.calc_date = (SELECT MAX(calc_date) FROM mart_stock_signals)
          AND s.nifty50_member = TRUE
    """)

    if signals_df.empty:
        return []

    categories = []

    # 1. Contrarian Opportunities
    contrarian = signals_df[
        (signals_df["drawdown_from_52w_high_pct"] <= -20) &
        (signals_df["vol_ratio_1d"] <= 0.85) &
        (signals_df["iss_score"] >= min_iss)
    ].copy()
    if not contrarian.empty:
        contrarian["key_reason"] = contrarian.apply(
            lambda r: f"Deep DD ({r['drawdown_from_52w_high_pct']:.0f}%) + Vol contraction ({r['vol_ratio_1d']:.1f}x)",
            axis=1
        )
        categories.append(WatchlistCategoryResponse(
            category_name="Contrarian Opportunities",
            items=[WatchlistCategoryItem(
                symbol=r["symbol"],
                company_name=r["company_name"],
                sector=r["sector"],
                signal_category="ACC",
                iss_score=float(r["iss_score"]),
                return_1d=float(r["return_1d"]) * 100,
                return_1m=float(r["return_1m"]) * 100,
                vol_ratio_1d=float(r["vol_ratio_1d"]),
                drawdown_from_52w_high_pct=float(r["drawdown_from_52w_high_pct"]),
                key_reason=r["key_reason"],
            ) for _, r in contrarian.iterrows()],
            count=len(contrarian),
        ))

    # 2. Momentum Leaders
    momentum = signals_df[
        (signals_df["iss_score"] >= 70) &
        (signals_df["rs_vs_nifty_3m"] > 0) &
        (signals_df["momentum_flag"] == True)
    ].copy()
    if not momentum.empty:
        momentum["key_reason"] = "Strong momentum: ISS > 70 + RS > 0 + Momentum flag"
        categories.append(WatchlistCategoryResponse(
            category_name="Momentum Leaders",
            items=[WatchlistCategoryItem(
                symbol=r["symbol"],
                company_name=r["company_name"],
                sector=r["sector"],
                signal_category="MOM",
                iss_score=float(r["iss_score"]),
                return_1d=float(r["return_1d"]) * 100,
                return_1m=float(r["return_1m"]) * 100,
                vol_ratio_1d=float(r["vol_ratio_1d"]),
                drawdown_from_52w_high_pct=float(r["drawdown_from_52w_high_pct"]),
                key_reason=r["key_reason"],
            ) for _, r in momentum.iterrows()],
            count=len(momentum),
        ))

    # 3. Event-Driven Candidates
    event_driven = signals_df[
        (signals_df["event_flag"] == True) &
        (signals_df["days_since_last_event"] <= 10) &
        (signals_df["iss_score"] >= min_iss)
    ].copy()
    if not event_driven.empty:
        event_driven["key_reason"] = event_driven.apply(
            lambda r: f"Event-driven: {r['days_since_last_event']} days since event",
            axis=1
        )
        categories.append(WatchlistCategoryResponse(
            category_name="Event-Driven Candidates",
            items=[WatchlistCategoryItem(
                symbol=r["symbol"],
                company_name=r["company_name"],
                sector=r["sector"],
                signal_category="EVT",
                iss_score=float(r["iss_score"]),
                return_1d=float(r["return_1d"]) * 100,
                return_1m=float(r["return_1m"]) * 100,
                vol_ratio_1d=float(r["vol_ratio_1d"]),
                drawdown_from_52w_high_pct=float(r["drawdown_from_52w_high_pct"]),
                key_reason=r["key_reason"],
            ) for _, r in event_driven.iterrows()],
            count=len(event_driven),
        ))

    # 4. Volume-Confirmed Movers
    volume_movers = signals_df[
        (signals_df["vol_ratio_1d"] > 2.0) &
        (signals_df["return_1d"] > 0)
    ].copy()
    if not volume_movers.empty:
        volume_movers["key_reason"] = volume_movers.apply(
            lambda r: f"Volume spike: {r['vol_ratio_1d']:.1f}x with {r['return_1d']*100:+.1f}% gain",
            axis=1
        )
        categories.append(WatchlistCategoryResponse(
            category_name="Volume-Confirmed Movers",
            items=[WatchlistCategoryItem(
                symbol=r["symbol"],
                company_name=r["company_name"],
                sector=r["sector"],
                signal_category="MOM",
                iss_score=float(r["iss_score"]),
                return_1d=float(r["return_1d"]) * 100,
                return_1m=float(r["return_1m"]) * 100,
                vol_ratio_1d=float(r["vol_ratio_1d"]),
                drawdown_from_52w_high_pct=float(r["drawdown_from_52w_high_pct"]),
                key_reason=r["key_reason"],
            ) for _, r in volume_movers.iterrows()],
            count=len(volume_movers),
        ))

    return categories


@router.get("/categories/{category_name}", response_model=WatchlistCategoryResponse)
async def get_category_items(
    category_name: str,
    min_iss: float = Query(50),
):
    """Get items for a specific category."""
    # Get latest signal data
    signals_df = read_sql_df("""
        SELECT s.symbol, d.company_name, d.sector, s.signal_category, s.iss_score,
               s.return_1d, s.return_1m, s.vol_ratio_1d,
               s.drawdown_from_52w_high_pct, s.momentum_flag, s.event_flag,
               s.accumulation_flag, s.rs_vs_nifty_3m, s.volume_trend_3m
        FROM mart_stock_signals s
        JOIN dim_stock d ON s.symbol = d.symbol
        WHERE s.calc_date = (SELECT MAX(calc_date) FROM mart_stock_signals)
          AND s.nifty50_member = TRUE
    """)

    if signals_df.empty:
        return WatchlistCategoryResponse(category_name=category_name, items=[], count=0)

    items: list[WatchlistCategoryItem] = []

    if category_name.lower() == "contrarian opportunities":
        df = signals_df[
            (signals_df["drawdown_from_52w_high_pct"] <= -20) &
            (signals_df["vol_ratio_1d"] <= 0.85) &
            (signals_df["iss_score"] >= min_iss)
        ].copy()
        df["key_reason"] = df.apply(
            lambda r: f"Deep DD ({r['drawdown_from_52w_high_pct']:.0f}%) + Vol contraction ({r['vol_ratio_1d']:.1f}x)",
            axis=1
        )
        items = [WatchlistCategoryItem(
            symbol=r["symbol"],
            company_name=r["company_name"],
            sector=r["sector"],
            signal_category="ACC",
            iss_score=float(r["iss_score"]),
            return_1d=float(r["return_1d"]) * 100,
            return_1m=float(r["return_1m"]) * 100,
            vol_ratio_1d=float(r["vol_ratio_1d"]),
            drawdown_from_52w_high_pct=float(r["drawdown_from_52w_high_pct"]),
            key_reason=r["key_reason"],
        ) for _, r in df.iterrows()]

    elif category_name.lower() == "momentum leaders":
        df = signals_df[
            (signals_df["iss_score"] >= 70) &
            (signals_df["rs_vs_nifty_3m"] > 0) &
            (signals_df["momentum_flag"] == True)
        ].copy()
        df["key_reason"] = "Strong momentum: ISS > 70 + RS > 0 + Momentum flag"
        items = [WatchlistCategoryItem(
            symbol=r["symbol"],
            company_name=r["company_name"],
            sector=r["sector"],
            signal_category="MOM",
            iss_score=float(r["iss_score"]),
            return_1d=float(r["return_1d"]) * 100,
            return_1m=float(r["return_1m"]) * 100,
            vol_ratio_1d=float(r["vol_ratio_1d"]),
            drawdown_from_52w_high_pct=float(r["drawdown_from_52w_high_pct"]),
            key_reason=r["key_reason"],
        ) for _, r in df.iterrows()]

    elif category_name.lower() == "event-driven candidates":
        df = signals_df[
            (signals_df["event_flag"] == True) &
            (signals_df["days_since_last_event"] <= 10) &
            (signals_df["iss_score"] >= min_iss)
        ].copy()
        df["key_reason"] = df.apply(
            lambda r: f"Event-driven: {r['days_since_last_event']} days since event",
            axis=1
        )
        items = [WatchlistCategoryItem(
            symbol=r["symbol"],
            company_name=r["company_name"],
            sector=r["sector"],
            signal_category="EVT",
            iss_score=float(r["iss_score"]),
            return_1d=float(r["return_1d"]) * 100,
            return_1m=float(r["return_1m"]) * 100,
            vol_ratio_1d=float(r["vol_ratio_1d"]),
            drawdown_from_52w_high_pct=float(r["drawdown_from_52w_high_pct"]),
            key_reason=r["key_reason"],
        ) for _, r in df.iterrows()]

    elif category_name.lower() == "volume-confirmed movers":
        df = signals_df[
            (signals_df["vol_ratio_1d"] > 2.0) &
            (signals_df["return_1d"] > 0)
        ].copy()
        df["key_reason"] = df.apply(
            lambda r: f"Volume spike: {r['vol_ratio_1d']:.1f}x with {r['return_1d']*100:+.1f}% gain",
            axis=1
        )
        items = [WatchlistCategoryItem(
            symbol=r["symbol"],
            company_name=r["company_name"],
            sector=r["sector"],
            signal_category="MOM",
            iss_score=float(r["iss_score"]),
            return_1d=float(r["return_1d"]) * 100,
            return_1m=float(r["return_1m"]) * 100,
            vol_ratio_1d=float(r["vol_ratio_1d"]),
            drawdown_from_52w_high_pct=float(r["drawdown_from_52w_high_pct"]),
            key_reason=r["key_reason"],
        ) for _, r in df.iterrows()]

    return WatchlistCategoryResponse(
        category_name=category_name,
        items=items,
        count=len(items),
    )


@router.post("/export")
async def export_watchlist(
    user_id: int = Query(1, description="User ID"),
):
    """Export watchlist as CSV-compatible format."""
    items = await get_user_watchlist(user_id=user_id)

    if not items.items:
        return {"message": "Watchlist is empty"}

    import io
    import csv

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Symbol", "Company", "Sector", "Added Date", "Reason", "Pinned"])

    for item in items.items:
        writer.writerow([
            item.symbol,
            item.company_name,
            item.sector,
            item.added_date,
            item.reason or "",
            "Yes" if item.pinned else "No",
        ])

    return {
        "message": "Watchlist exported successfully",
        "csv_data": output.getvalue(),
        "row_count": items.total_count,
    }
