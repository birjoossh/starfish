"""Nifty 50 Terminal — consolidated single-page dashboard.

Design lock: 2026-05-11. Visual source of truth: ``design/mock_consolidated.html``.
Implementation plan: ``docs/dashboard_consolidation_plan.md``.

Layout (top → bottom):

    Sticky status bar
    Brand header + tricolor thread
    Date selector + Morning Digest
    ─────────────────────────────
    §01 Market Overview      [always open]
    §02 Watchlist            [always open]
    §03 Trend Workbench      [always open]   NEW
    §04 Movers & Extremes    [collapsible]
    §05 Drawdown Scanner     [collapsible]
    §06 Breakout/Momentum    [collapsible]
    §07 Volume Anomaly       [collapsible]
    §08 Corporate Events     [collapsible]
    ─────────────────────────────
    Footer

Phase 0 ships the empty shell; per-section content lands in Phases 1–8.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from dashboard.overview import render_morning_digest, render_overview
from dashboard.primitives import (
    render_brand_header,
    render_footer,
    render_section_header,
    render_topbar,
)
from dashboard.tokens import inject_global_styles


API_URL = "http://localhost:8000"


# ----------------------------- Data accessors ---------------------------- #


@st.cache_data(ttl=60)
def _get_available_dates() -> list[str]:
    """Return calc_dates that have signal data, newest first.

    Falls back to today's date if the DB is unreachable so the shell still
    renders without a backend.
    """
    try:
        from config.database import read_sql_df

        df = read_sql_df(
            "SELECT DISTINCT calc_date FROM mart_stock_signals "
            "ORDER BY calc_date DESC"
        )
        if not df.empty:
            return [str(d) for d in df["calc_date"].tolist()]
    except Exception:
        pass
    return [dt.date.today().isoformat()]


@st.cache_data(ttl=60)
def _load_signals(calc_date: str) -> pd.DataFrame:
    """Load the full mart_stock_signals slice for the calc date.

    Centralized loader so every section that consumes signals (§01–§07) sees
    the same frame. Returns empty DataFrame on failure.
    """
    try:
        from dashboard.phase_f import load_signals_for_phase_f

        return load_signals_for_phase_f(calc_date)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60)
def _load_watchlist() -> list[str]:
    """Load pinned watchlist symbols. Returns empty list on failure."""
    try:
        from dashboard.watchlist import load_watchlist

        return sorted(load_watchlist())
    except Exception:
        return []


# ----------------------------- Section stubs ----------------------------- #
#
# Each ``_render_section_NN`` function is the single entry point for that
# section. Phase 0 leaves them as styled placeholders; Phases 1–8 replace the
# body. Keep signatures stable.


def _render_section_01_market_overview(
    calc_date: str,
    signals_df: pd.DataFrame,
    watchlist: list[str],
) -> None:
    render_section_header("01", "Market Overview", hint="always open")
    render_overview(calc_date, signals_df, watchlist)


def _render_section_02_watchlist(calc_date: str) -> None:
    render_section_header("02", "Watchlist · Auto-curated + Pinned", hint="always open")
    _placeholder("§02 Watchlist — Phase 2 will land here.")


def _render_section_03_trend(calc_date: str) -> None:
    render_section_header(
        "03",
        "Trend Workbench · Multi-Day Analysis",
        hint="always open · price · volume · ISS over time",
    )
    _placeholder("§03 Trend Workbench — Phase 3 will land here (NEW).")


def _render_section_04_movers(calc_date: str) -> None:
    render_section_header("04", "Movers & Extremes")
    _placeholder("§04 Movers & Extremes — Phase 4 will land here.")


def _render_section_05_drawdown(calc_date: str) -> None:
    render_section_header("05", "Drawdown Scanner")
    _placeholder("§05 Drawdown Scanner — Phase 5 will land here.")


def _render_section_06_momentum(calc_date: str) -> None:
    render_section_header("06", "Breakout & Momentum Monitor")
    _placeholder("§06 Breakout & Momentum — Phase 6 will land here.")


def _render_section_07_volume(calc_date: str) -> None:
    render_section_header("07", "Volume Anomaly Monitor")
    _placeholder("§07 Volume Anomaly — Phase 7 will land here.")


def _render_section_08_events(calc_date: str) -> None:
    render_section_header("08", "Corporate Events Tracker")
    _placeholder("§08 Corporate Events — Phase 8 will land here.")


def _placeholder(message: str) -> None:
    """Render a hairline panel with a muted "coming soon" message."""
    st.markdown(
        f"""
<div class="panel" style="padding:32px 24px;display:flex;align-items:center;justify-content:center;color:var(--tx3);font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.06em">
  {message}
</div>
""",
        unsafe_allow_html=True,
    )


# ------------------------------ Header strip ----------------------------- #


def _render_date_picker(dates: list[str], signals_df: pd.DataFrame) -> str:
    """Render the calc-date selector + Morning Digest. Returns selected date."""
    col_date, col_digest = st.columns([2, 7])
    with col_date:
        st.markdown(
            '<div class="kicker" style="margin-bottom:4px">Calc Date</div>',
            unsafe_allow_html=True,
        )
        selected = st.selectbox(
            "Calc Date",
            dates,
            index=0,
            label_visibility="collapsed",
            key="calc_date",
        )
    with col_digest:
        render_morning_digest(signals_df)
    return str(selected)


# ----------------------------- Entry point ------------------------------- #
#
# Keyboard shortcuts (Alt+A expand-all / Alt+C collapse-all) are deferred to
# Phase 9 — they cannot be implemented via ``components.v1.html`` because that
# runs in a sandboxed iframe and cannot mutate parent-document expanders. The
# correct path is a Streamlit custom component or a header button row.


def main() -> None:
    """Streamlit entry point."""
    st.set_page_config(
        page_title="Starfish · Nifty 50 Terminal",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_global_styles()

    dates = _get_available_dates()
    today_label = dt.date.today().strftime("%a %d %b %Y").upper()
    render_topbar(
        nse_status="CLOSED",
        nse_live=False,
        date_label=today_label,
        last_load=dates[0] if dates else "—",
        user="rahul@starfish",
        universe="NIFTY 50",
        latency_ms=42,
    )

    render_brand_header()

    # Pre-load signals once at the date pick so every section sees the same
    # frame. selectbox writes to st.session_state.calc_date; we read it back
    # from the function return so the very first render uses dates[0].
    initial_date = dates[0] if dates else dt.date.today().isoformat()
    signals_df = _load_signals(initial_date)
    watchlist = _load_watchlist()

    selected_date = _render_date_picker(dates, signals_df)

    # If the user changed the date, re-load signals for the new date.
    if selected_date != initial_date:
        signals_df = _load_signals(selected_date)

    # ----- Hero sections (always rendered) -----
    _render_section_01_market_overview(selected_date, signals_df, watchlist)
    _render_section_02_watchlist(selected_date)
    _render_section_03_trend(selected_date)

    # ----- Collapsible scanner sections -----
    for header, hint, fn in [
        ("04 · Movers & Extremes", "10 G · 10 L", _render_section_04_movers),
        ("05 · Drawdown Scanner", "≥ 20%", _render_section_05_drawdown),
        ("06 · Breakout & Momentum Monitor", "3M > 20%", _render_section_06_momentum),
        ("07 · Volume Anomaly Monitor", "3 tiers", _render_section_07_volume),
        ("08 · Corporate Events Tracker", "last 7d · next 7d", _render_section_08_events),
    ]:
        with st.expander(f"§ {header}   ·   {hint}", expanded=True):
            fn(selected_date)

    render_footer()


if __name__ == "__main__":
    main()
