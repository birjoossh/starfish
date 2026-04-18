"""Watchlist Builder Module.

Auto-generates rules-based watchlist candidates from mart_stock_signals,
classified by signal type (Contrarian, Momentum, Event-Driven, Volume-Confirmed).
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def get_contrarian_opportunities(
    df: pd.DataFrame,
    min_iss: float = 50.0,
    max_vol_ratio: float = 0.85,
    min_drawdown_pct: float = -20.0,
) -> pd.DataFrame:
    """Get Contrarian Opportunities candidates.

    Criteria:
    - Deep drawdown from 52W high (>= 20%)
    - Volume contraction (vol_ratio_1d <= max_vol_ratio)
    - Minimum ISS score (min_iss)

    Args:
        df: mart_stock_signals DataFrame
        min_iss: Minimum ISS score threshold (default: 50)
        max_vol_ratio: Maximum volume ratio (default: 0.85)
        min_drawdown_pct: Minimum drawdown percentage (default: -20)

    Returns:
        Filtered DataFrame with contrarian candidates
    """
    mask = (
        (df["drawdown_from_52w_high_pct"] <= min_drawdown_pct) &
        (df["vol_ratio_1d"] <= max_vol_ratio) &
        (df["iss_score"] >= min_iss)
    )
    candidates = df[mask].copy()
    return _annotate_candidates(candidates, "Contrarian Opportunities")


def get_momentum_leaders(
    df: pd.DataFrame,
    min_iss: float = 70.0,
    min_rs_3m: float = 0.0,
) -> pd.DataFrame:
    """Get Momentum Leaders candidates.

    Criteria:
    - High ISS score (>= min_iss)
    - Positive relative strength vs Nifty 3M (>= min_rs_3m)
    - Momentum flag = True

    Args:
        df: mart_stock_signals DataFrame
        min_iss: Minimum ISS score threshold (default: 70)
        min_rs_3m: Minimum RS vs Nifty 3M (default: 0)

    Returns:
        Filtered DataFrame with momentum candidates
    """
    mask = (
        (df["iss_score"] >= min_iss) &
        (df["rs_vs_nifty_3m"] > min_rs_3m) &
        (df["momentum_flag"] == True)  # noqa: E712
    )
    candidates = df[mask].copy()
    return _annotate_candidates(candidates, "Momentum Leaders")


def get_event_driven_candidates(
    df: pd.DataFrame,
    days_window: int = 10,
    min_significance: int = 3,
    min_iss: float = 50.0,
) -> pd.DataFrame:
    """Get Event-Driven Candidates.

    Criteria:
    - Event flag = True
    - Days since last event <= days_window
    - ISS score >= min_iss

    Args:
        df: mart_stock_signals DataFrame
        days_window: Maximum days since event (default: 10)
        min_significance: Minimum event significance (default: 3)
        min_iss: Minimum ISS score threshold (default: 50)

    Returns:
        Filtered DataFrame with event-driven candidates
    """
    # Get events data for significance check
    from config.database import read_sql_df

    events_df = read_sql_df("""
        SELECT symbol, event_date, event_type, significance_score
        FROM fact_corporate_event
        WHERE event_date = (SELECT MAX(calc_date) FROM mart_stock_signals)
    """)

    # Join with events to get significance
    mask = (
        (df["event_flag"] == True) &
        (df["days_since_last_event"] <= days_window) &
        (df["iss_score"] >= min_iss)
    )
    candidates = df[mask].copy()

    # Annotate with event details
    if not candidates.empty and not events_df.empty:
        candidates = candidates.merge(
            events_df[["symbol", "significance_score"]],
            on="symbol",
            how="left",
            suffixes=("", "_event"),
        )
        candidates["event_significance"] = candidates.get("significance_score_event", candidates.get("significance_score"))
    else:
        candidates["event_significance"] = None

    return _annotate_candidates(candidates, "Event-Driven Candidates")


def get_volume_movers(
    df: pd.DataFrame,
    min_vol_ratio: float = 2.0,
    min_return_1d: float = 0.0,
) -> pd.DataFrame:
    """Get Volume-Confirmed Movers.

    Criteria:
    - Volume ratio > min_vol_ratio (e.g., > 2.0x)
    - Positive 1-day return (>= min_return_1d)

    Args:
        df: mart_stock_signals DataFrame
        min_vol_ratio: Minimum volume ratio (default: 2.0)
        min_return_1d: Minimum 1-day return (default: 0)

    Returns:
        Filtered DataFrame with volume mover candidates
    """
    mask = (
        (df["vol_ratio_1d"] > min_vol_ratio) &
        (df["return_1d"] >= min_return_1d)
    )
    candidates = df[mask].copy()
    return _annotate_candidates(candidates, "Volume-Confirmed Movers")


def get_all_categories(
    df: pd.DataFrame,
    min_iss: float = 50.0,
) -> dict[str, pd.DataFrame]:
    """Get all watchlist categories.

    Returns a dictionary with category names as keys and
    DataFrames as values.

    Args:
        df: mart_stock_signals DataFrame
        min_iss: Minimum ISS score for filtering

    Returns:
        Dict mapping category names to candidate DataFrames
    """
    return {
        "Contrarian Opportunities": get_contrarian_opportunities(df, min_iss=min_iss),
        "Momentum Leaders": get_momentum_leaders(df, min_iss=min_iss),
        "Event-Driven Candidates": get_event_driven_candidates(df, min_iss=min_iss),
        "Volume-Confirmed Movers": get_volume_movers(df),
    }


def _annotate_candidates(candidates: pd.DataFrame, category: str) -> pd.DataFrame:
    """Add key_reason annotation to candidates."""
    if candidates.empty:
        return candidates

    candidates = candidates.copy()

    if category == "Contrarian Opportunities":
        candidates["key_reason"] = candidates.apply(
            lambda r: f"Deep DD ({r['drawdown_from_52w_high_pct']:.0f}%) + Vol contraction ({r['vol_ratio_1d']:.1f}x)",
            axis=1,
        )
        candidates["signal_category"] = "ACC"
    elif category == "Momentum Leaders":
        candidates["key_reason"] = candidates.apply(
            lambda r: f"Strong MOM: ISS {r['iss_score']:.0f} + RS {r['rs_vs_nifty_3m']:.1f}% + Flag",
            axis=1,
        )
        candidates["signal_category"] = "MOM"
    elif category == "Event-Driven Candidates":
        candidates["key_reason"] = candidates.apply(
            lambda r: f"Event: {r.get('days_since_last_event', 'N/A')} days ago",
            axis=1,
        )
        candidates["signal_category"] = "EVT"
    elif category == "Volume-Confirmed Movers":
        candidates["key_reason"] = candidates.apply(
            lambda r: f"Volume spike: {r['vol_ratio_1d']:.1f}x with {r['return_1d']*100:+.1f}% gain",
            axis=1,
        )
        candidates["signal_category"] = "MOM"
    else:
        candidates["key_reason"] = category

    return candidates


def rank_by_iss(candidates: pd.DataFrame) -> pd.DataFrame:
    """Rank candidates by ISS score descending."""
    if candidates.empty:
        return candidates
    return candidates.sort_values("iss_score", ascending=False)


def filter_by_sectors(
    candidates: pd.DataFrame,
    sectors: list[str],
) -> pd.DataFrame:
    """Filter candidates by sector list."""
    if candidates.empty or not sectors:
        return candidates
    return candidates[candidates["sector"].isin(sectors)]


def get_watchlist_stats(candidates: pd.DataFrame) -> dict[str, Any]:
    """Get summary statistics for a watchlist category."""
    if candidates.empty:
        return {
            "total_count": 0,
            "avg_iss": 0,
            "avg_return_1d": 0,
            "avg_vol_ratio": 0,
            "top_sector": None,
        }

    stats = {
        "total_count": len(candidates),
        "avg_iss": float(candidates["iss_score"].mean()),
        "avg_return_1d": float(candidates["return_1d"].mean() * 100),
        "avg_vol_ratio": float(candidates["vol_ratio_1d"].mean()),
        "top_sector": candidates["sector"].mode().iloc[0] if not candidates["sector"].mode().empty else None,
    }

    # Count by signal category
    if "signal_category" in candidates.columns:
        stats["by_category"] = candidates["signal_category"].value_counts().to_dict()
    else:
        stats["by_category"] = {}

    return stats
