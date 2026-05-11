"""Shared Primary Scanner Pipeline rendering — drill-down helpers.

§01 (treemap + sector breadth) and §04–§07 share the same drill-down
table format. All consumers should import :func:`render_scanner_drilldown`
from this module to keep columns and formatting consistent.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from dashboard.widget_info import tooltip


SCANNER_DISPLAY_COLS: list[str] = [
    "Symbol", "Company", "Sector", "Close",
    "Ret 1D", "Ret 1M", "Ret 3M",
    "Vol 20D", "Avg Vol 20D",
    "% from 52W High", "% from 52W Low",
    "ISS", "Signal", "Momentum", "Accum",
    "Watch",
]


def build_scanner_display_df(
    signals_df: pd.DataFrame, watchlist: list[str]
) -> pd.DataFrame:
    """Project the Primary Scanner Pipeline columns onto a display-ready frame."""
    if signals_df.empty:
        return pd.DataFrame(columns=SCANNER_DISPLAY_COLS)

    display_df = signals_df[[
        "symbol", "company_name", "sector", "close",
        "return_1d", "return_1m", "return_3m",
        "vol_ratio_1d", "avg_volume_20d",
        "drawdown_from_52w_high_pct", "distance_from_52w_low_pct",
        "iss_score", "signal_category", "momentum_flag", "accumulation_flag",
    ]].copy()

    for ratio_col in ("return_1d", "return_1m", "return_3m"):
        display_df[ratio_col] = display_df[ratio_col].astype(float) * 100

    display_df["momentum_flag"] = display_df["momentum_flag"].apply(
        lambda x: "MOM" if x else ""
    )
    display_df["accumulation_flag"] = display_df["accumulation_flag"].apply(
        lambda x: "ACC" if x else ""
    )
    watchlist_set = set(watchlist or [])
    display_df["watch"] = display_df["symbol"].apply(
        lambda s: "★" if s in watchlist_set else ""
    )

    display_df.columns = SCANNER_DISPLAY_COLS
    return display_df


def scanner_column_config() -> dict:
    """Shared ``column_config`` for any scanner-derived dataframe."""
    return {
        "Sector": st.column_config.TextColumn("Sector", width="medium"),
        "Company": st.column_config.TextColumn("Company", width="medium"),
        "Ret 1D": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("return_1d")),
        "Ret 1M": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("return_1m")),
        "Ret 3M": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("return_3m")),
        "Close": st.column_config.NumberColumn(format="₹%.2f"),
        "Vol 20D": st.column_config.NumberColumn(format="%.2fx", help=tooltip("vol_ratio_1d")),
        "Avg Vol 20D": st.column_config.NumberColumn(help=tooltip("avg_volume_20d")),
        "% from 52W High": st.column_config.NumberColumn(format="%.2f%%", help=tooltip("drawdown_pct")),
        "% from 52W Low": st.column_config.NumberColumn(format="%.2f%%", help=tooltip("distance_from_low")),
        "ISS": st.column_config.NumberColumn(format="%.2f", help=tooltip("iss_score")),
        "Signal": st.column_config.TextColumn("Signal", help=tooltip("signal_category")),
        "Momentum": st.column_config.TextColumn("Momentum", help=tooltip("momentum_flag")),
        "Accum": st.column_config.TextColumn("Accum", help=tooltip("accumulation_flag")),
    }


def render_scanner_drilldown(
    signals_df: pd.DataFrame,
    watchlist: list[str],
    *,
    title: str,
    key: str,
    sector: str | None = None,
    symbols: list[str] | None = None,
) -> None:
    """Render scanner-pipeline rows filtered to a sector or list of symbols."""
    if signals_df.empty:
        return
    subset = signals_df
    if sector is not None:
        subset = subset[subset["sector"] == sector]
    if symbols is not None:
        subset = subset[subset["symbol"].isin(symbols)]
    if subset.empty:
        st.info(f"No scanner rows found for {title}.")
        return
    display_df = build_scanner_display_df(subset, watchlist)
    st.markdown(
        f'<div class="kicker" style="margin-top:8px">{escape(title)} · {len(display_df)} '
        f'name{"s" if len(display_df) != 1 else ""}</div>',
        unsafe_allow_html=True,
    )
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=min(420, 60 + len(display_df) * 36),
        key=key,
        column_config=scanner_column_config(),
    )


__all__ = [
    "SCANNER_DISPLAY_COLS",
    "build_scanner_display_df",
    "scanner_column_config",
    "render_scanner_drilldown",
]
