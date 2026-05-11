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
from dashboard.section_drawdown import render_drawdown_section
from dashboard.section_momentum import render_momentum_section
from dashboard.section_movers import render_movers_section
from dashboard.section_trend import render_trend_section
from dashboard.section_volume import render_volume_section
from dashboard.section_watchlist import render_watchlist_section
from dashboard.tokens import inject_global_styles

# §08 still wraps phase_g pending TODO-119/120 (corp event ingestion).
from dashboard.phase_g import render_events_tracker  # noqa: E402


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


def _render_section_02_watchlist(
    calc_date: str,
    signals_df: pd.DataFrame,
) -> None:
    render_section_header(
        "02", "Watchlist · Auto-curated + Pinned", hint="always open"
    )
    render_watchlist_section(calc_date, signals_df)


def _render_section_03_trend(
    calc_date: str, signals_df: pd.DataFrame
) -> None:
    render_section_header(
        "03",
        "Trend Workbench · Multi-Day Analysis",
        hint="always open · price · volume · ISS over time",
    )
    render_trend_section(calc_date, signals_df)


def _render_section_04_movers(
    calc_date: str, signals_df: pd.DataFrame
) -> None:
    render_section_header("04", "Movers & Extremes")
    render_movers_section(calc_date, signals_df)


def _render_section_05_drawdown(
    calc_date: str, signals_df: pd.DataFrame
) -> None:
    render_section_header("05", "Drawdown Scanner")
    render_drawdown_section(calc_date, signals_df)


def _render_section_06_momentum(
    calc_date: str, signals_df: pd.DataFrame
) -> None:
    render_section_header("06", "Breakout & Momentum Monitor")
    render_momentum_section(calc_date, signals_df)


def _render_section_07_volume(
    calc_date: str, signals_df: pd.DataFrame
) -> None:
    render_section_header("07", "Volume Anomaly Monitor")
    render_volume_section(calc_date, signals_df)


def _render_section_08_events(calc_date: str) -> None:
    render_section_header(
        "08", "Corporate Events Tracker",
        hint="data: fact_corporate_event · TODO-119/120",
    )
    try:
        render_events_tracker()
    except Exception as e:
        _placeholder(
            f"§08 Events Tracker unavailable: {type(e).__name__}. "
            "Likely blocked on TODO-119/120 (events table not yet seeded)."
        )


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


def _shift_calc_date(delta: int, options: list[str]) -> None:
    """Callback for the ◀ / ▶ scrubber buttons. Mutates ``st.session_state.calc_date``."""
    cur = st.session_state.get("calc_date", options[0])
    if cur not in options:
        st.session_state["calc_date"] = options[0]
        return
    idx = options.index(cur)
    new_idx = max(0, min(len(options) - 1, idx + delta))
    st.session_state["calc_date"] = options[new_idx]


def _resolve_selected_date(dates: list[str]) -> tuple[str, list[str]]:
    """Read or initialize ``st.session_state.calc_date`` against the slider options.

    Returns ``(selected_date, slider_options)`` where ``slider_options`` is the
    oldest→newest ordering needed by ``st.select_slider``.
    """
    slider_options = list(reversed(dates))
    if (
        "calc_date" not in st.session_state
        or st.session_state["calc_date"] not in slider_options
    ):
        st.session_state["calc_date"] = slider_options[-1]  # most recent
    return str(st.session_state["calc_date"]), slider_options


def _render_date_picker(slider_options: list[str], signals_df: pd.DataFrame) -> None:
    """Render the calc-date scrubber + Morning Digest.

    Implements Phase 9.1 (date scrubber): a ``select_slider`` plus Prev/Next
    buttons. The buttons use ``on_click`` callbacks (Streamlit's supported
    pattern for widget-writes-another-widget) — never inline writes after
    widget creation. ``slider_options`` must be oldest→newest.
    """
    col_scrub, col_digest = st.columns([4, 7])
    with col_scrub:
        st.markdown(
            f'<div class="kicker" style="margin-bottom:4px">Calc Date · scrub the last '
            f'{len(slider_options)} trading days</div>',
            unsafe_allow_html=True,
        )
        c_prev, c_slider, c_next = st.columns([1, 10, 1], gap="small")
        with c_prev:
            st.button(
                "◀", key="calc_date_prev", help="Older trading day",
                on_click=_shift_calc_date, args=(-1, slider_options),
            )
        with c_slider:
            st.select_slider(
                "Calc Date",
                options=slider_options,
                label_visibility="collapsed",
                key="calc_date",
            )
        with c_next:
            st.button(
                "▶", key="calc_date_next", help="Newer trading day",
                on_click=_shift_calc_date, args=(1, slider_options),
            )
    with col_digest:
        render_morning_digest(signals_df)


def _set_expand_all(value: bool) -> None:
    """Callback for the expand/collapse buttons."""
    st.session_state["expand_all"] = value


def _render_expand_controls() -> bool:
    """Render Expand-all / Collapse-all buttons; return the current flag.

    Phase 9.3 — replaces the keybindings-via-iframe-JS anti-pattern caught in
    Phase 0 review. Two buttons mutate ``st.session_state.expand_all`` via
    ``on_click`` callbacks; the collapsibles below construct their
    ``expanded=`` arg from this flag.
    """
    if "expand_all" not in st.session_state:
        st.session_state["expand_all"] = True
    expanded = bool(st.session_state["expand_all"])
    state_label = "all open" if expanded else "all closed"
    c_pad, c_a, c_c = st.columns([8, 1, 1], gap="small")
    with c_pad:
        st.markdown(
            f'<div class="kicker" style="text-align:right;padding-top:8px">{state_label}</div>',
            unsafe_allow_html=True,
        )
    with c_a:
        st.button(
            "Expand all", key="expand_all_btn", help="Open §04–§08",
            on_click=_set_expand_all, args=(True,),
        )
    with c_c:
        st.button(
            "Collapse all", key="collapse_all_btn", help="Close §04–§08",
            on_click=_set_expand_all, args=(False,),
        )
    return expanded


# ----------------------------- Entry point ------------------------------- #
#
# Expand/Collapse controls are rendered via :func:`_render_expand_controls`
# above (Phase 9.3). The keybinding-via-iframe-JS approach attempted in
# Phase 0 cannot mutate parent-document expanders because the component runs
# in a sandboxed iframe; the header button row is the supported alternative.


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

    # Resolve the selected date from session state BEFORE loading signals, so
    # every section (including the Morning Digest below) sees the correct date
    # on first render after a scrubber click.
    selected_date, slider_options = _resolve_selected_date(dates)
    signals_df = _load_signals(selected_date)
    watchlist = _load_watchlist()

    _render_date_picker(slider_options, signals_df)

    # ----- Hero sections (always rendered) -----
    _render_section_01_market_overview(selected_date, signals_df, watchlist)
    _render_section_02_watchlist(selected_date, signals_df)
    _render_section_03_trend(selected_date, signals_df)

    # ----- Collapsible scanner sections -----
    # Expand/Collapse buttons drive the `expanded=` flag on every expander.
    expanded = _render_expand_controls()
    with st.expander("§ 04 · Movers & Extremes   ·   10 G · 10 L", expanded=expanded):
        _render_section_04_movers(selected_date, signals_df)
    with st.expander("§ 05 · Drawdown Scanner   ·   ≥ 20%", expanded=expanded):
        _render_section_05_drawdown(selected_date, signals_df)
    with st.expander("§ 06 · Breakout & Momentum Monitor   ·   3M > 20%", expanded=expanded):
        _render_section_06_momentum(selected_date, signals_df)
    with st.expander("§ 07 · Volume Anomaly Monitor   ·   3 tiers", expanded=expanded):
        _render_section_07_volume(selected_date, signals_df)
    with st.expander("§ 08 · Corporate Events Tracker   ·   last 7d · next 7d", expanded=expanded):
        _render_section_08_events(selected_date)

    render_footer()


if __name__ == "__main__":
    main()
