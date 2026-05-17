"""§04 Movers & Extremes — best / worst performers + return × volume scatter.

Layout (per design lock):
    Row 1: Filter bar (period · mcap tier · sector · Nifty50 toggle)
    Row 2: Top-10 Gainers (6 cols) + Top-10 Losers (6 cols)
    Row 3: Return × Volume scatter with quadrant lines

Drill-in: row click in either table sets ``st.session_state.trend_subject``
+ ``trend_kind='stock'`` so the user is teleported into §03.
"""
from __future__ import annotations

from html import escape
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from dashboard.section_trend import request_trend_focus


API_URL = "http://localhost:8000"

PERIODS: tuple[str, ...] = ("1D", "1M", "3M", "1Y")


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_movers(calc_date: str) -> dict[str, Any]:
    """GET /movers for the calc date. Returns empty dict on failure.

    The /movers endpoint occasionally returns ``[]`` (a list) for dates with
    no signal data — we coerce to the canonical dict shape so the renderer
    can rely on ``data.get(...)``.
    """
    try:
        resp = requests.get(
            f"{API_URL}/movers", params={"calc_date": calc_date}, timeout=5
        )
        if resp.status_code == 200:
            payload = resp.json()
            if isinstance(payload, dict):
                return payload
    except Exception:
        pass
    return {"gainers": [], "losers": [], "all_data": []}


# ----------------------------- Public API -------------------------------- #


def render_movers_section(calc_date: str, signals_df: pd.DataFrame) -> None:
    """Render §04 Movers & Extremes."""
    with st.spinner("Loading movers…"):
        data = _fetch_movers(calc_date)
    gainers = pd.DataFrame(data.get("gainers") or [])
    losers = pd.DataFrame(data.get("losers") or [])
    all_df = pd.DataFrame(data.get("all_data") or [])

    if gainers.empty and losers.empty:
        st.markdown(
            '<div class="panel" style="padding:32px;text-align:center;color:var(--tx3);'
            "font-family:'JetBrains Mono',monospace;font-size:12px\">"
            "No movers data for selected date.</div>",
            unsafe_allow_html=True,
        )
        return

    _render_filter_bar()
    col_g, col_l = st.columns(2, gap="small")
    with col_g:
        _render_movers_table(gainers, kind="gainers", slot_key="movers_g")
    with col_l:
        _render_movers_table(losers, kind="losers", slot_key="movers_l")

    if not all_df.empty:
        _render_scatter(all_df)


# ----------------------------- Filter bar -------------------------------- #


def _render_filter_bar() -> None:
    st.markdown(
        f"""
<div class="panel" style="padding:8px 14px;margin-bottom:8px">
  <div class="mono" style="font-size:11px;color:var(--tx2);display:flex;flex-wrap:wrap;gap:6px;align-items:center">
    <span class="kicker">Period</span>
    <span class="tag active">1D</span>
    <span class="tag">1M</span>
    <span class="tag">3M</span>
    <span class="tag">1Y</span>
    <span class="kicker" style="margin-left:12px">Mcap</span>
    <span class="tag">All</span>
    <span class="tag">5K Cr</span>
    <span class="tag">20K Cr</span>
    <span class="tag">1L Cr</span>
    <span class="kicker" style="margin-left:12px">Universe</span>
    <span class="tag active">Nifty 50</span>
    <span style="margin-left:auto;color:var(--tx3);font-size:10px">filter controls deferred to Phase 9</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# --------------------------- Movers tables ------------------------------- #


def _render_movers_table(df: pd.DataFrame, *, kind: str, slot_key: str) -> None:
    """Render a Top-10 gainers or losers table with row-click drill into §03."""
    title = "Top 10 Gainers" if kind == "gainers" else "Top 10 Losers"
    sign_pill = (
        '<span class="pill fill-pos pos">▲ session</span>'
        if kind == "gainers"
        else '<span class="pill fill-neg neg">▼ session</span>'
    )
    st.markdown(
        f"""
<div class="panel" style="padding:12px 16px;margin-bottom:-1px;border-bottom:0">
  <div style="display:flex;align-items:baseline;justify-content:space-between">
    <div class="serif" style="font-size:20px;line-height:1.2">{escape(title)} <span class="tx3" style="font-size:13px;font-family:'JetBrains Mono',monospace">· 1D</span></div>
    {sign_pill}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    if df.empty:
        st.markdown(
            '<div class="sub" style="padding:18px;text-align:center;color:var(--tx3);'
            "font-family:'JetBrains Mono',monospace;font-size:11px\">no rows</div>",
            unsafe_allow_html=True,
        )
        return

    display = df.copy()
    # API returns return_1d as ratio; convert to percent
    if "return_1d" in display.columns:
        display["return_1d"] = display["return_1d"].astype(float) * 100
    # Project to display schema
    cols_keep = ["symbol", "company_name", "sector", "close",
                 "return_1d", "vol_ratio_1d", "iss_score", "signal_category"]
    keep = [c for c in cols_keep if c in display.columns]
    display = display[keep].copy()
    display.columns = ["Symbol", "Company", "Sector", "Close",
                       "Ret 1D", "Vol 20D", "ISS", "Signal"][: len(keep)]

    event = st.dataframe(
        display,
        width='stretch',
        hide_index=True,
        height=min(440, 60 + len(display) * 36),
        key=f"{slot_key}_df",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Sector": st.column_config.TextColumn("Sector", width="medium"),
            "Company": st.column_config.TextColumn("Company", width="medium"),
            "Close": st.column_config.NumberColumn(format="₹%.2f"),
            "Ret 1D": st.column_config.NumberColumn(format="%+.2f%%"),
            "Vol 20D": st.column_config.NumberColumn(format="%.2fx"),
            "ISS": st.column_config.NumberColumn(format="%.0f"),
            "Signal": st.column_config.TextColumn("Signal"),
        },
    )
    rows = (event or {}).get("selection", {}).get("rows") or []
    if rows:
        idx = rows[0]
        if 0 <= idx < len(display):
            symbol = str(display.iloc[idx]["Symbol"])
            request_trend_focus(symbol, "stock", source=slot_key)
            st.markdown(
                f'<div class="mono" style="font-size:10px;color:var(--acc);padding:6px 4px">'
                f"↻ {escape(symbol)} sent to §03 Trend Workbench · scroll up to view</div>",
                unsafe_allow_html=True,
            )


# ------------------------- Return × Volume scatter ----------------------- #


def _render_scatter(df: pd.DataFrame) -> None:
    """Quadrant-style scatter: x=return_1d, y=vol_ratio_1d, color=sector."""
    if df.empty or "return_1d" not in df.columns:
        return
    work = df.copy()
    work["return_pct"] = work["return_1d"].astype(float) * 100
    work["vol_ratio_1d"] = work["vol_ratio_1d"].astype(float)
    work["iss_score"] = work["iss_score"].astype(float)
    # marker size by ISS — fallback when mcap_cr missing
    work["size"] = work["iss_score"].clip(lower=20, upper=100)

    fig = go.Figure()
    sectors = sorted(work["sector"].dropna().unique().tolist())
    palette = [
        "#F4A340", "#60A5FA", "#A78BFA", "#4ADE80", "#F87171",
        "#FBBF24", "#2DD881", "#94A3B8", "#22D3EE", "#FB923C",
        "#F472B6", "#A3E635", "#FACC15",
    ]
    for i, sec in enumerate(sectors):
        sub = work[work["sector"] == sec]
        # gold-border outlier rule: return > 0% and vol > 1.5x
        outlier = (sub["return_pct"] > 0) & (sub["vol_ratio_1d"] > 1.5)
        fig.add_trace(
            go.Scatter(
                x=sub["return_pct"], y=sub["vol_ratio_1d"],
                mode="markers+text",
                marker=dict(
                    size=sub["size"] / 5 + 6,
                    color=palette[i % len(palette)],
                    opacity=0.85,
                    line=dict(
                        width=outlier.map({True: 2, False: 0.5}),
                        color=outlier.map({True: "#F4A340", False: "#0A0A0B"}),
                    ),
                ),
                text=sub["symbol"],
                textposition="top center",
                textfont=dict(family="JetBrains Mono", size=9, color="#F4F4F0"),
                name=sec,
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "ret %{x:+.2f}% · vol %{y:.2f}x<extra>" + sec + "</extra>"
                ),
            )
        )

    fig.add_vline(x=0, line_dash="dot", line_color="#26262C", line_width=1)
    fig.add_hline(y=1.0, line_dash="dot", line_color="#26262C", line_width=1)
    fig.add_annotation(text="Volume-Confirmed ▲▲", xref="paper", yref="paper",
                       x=0.99, y=0.99, showarrow=False,
                       font=dict(family="JetBrains Mono", size=9, color="#57575E"),
                       xanchor="right", yanchor="top")
    fig.add_annotation(text="Selling Pressure ▼▲", xref="paper", yref="paper",
                       x=0.01, y=0.99, showarrow=False,
                       font=dict(family="JetBrains Mono", size=9, color="#57575E"),
                       xanchor="left", yanchor="top")
    fig.add_annotation(text="Quiet Drift Down ▼▼", xref="paper", yref="paper",
                       x=0.01, y=0.01, showarrow=False,
                       font=dict(family="JetBrains Mono", size=9, color="#57575E"),
                       xanchor="left", yanchor="bottom")
    fig.add_annotation(text="Quiet Drift Up ▲▼", xref="paper", yref="paper",
                       x=0.99, y=0.01, showarrow=False,
                       font=dict(family="JetBrains Mono", size=9, color="#57575E"),
                       xanchor="right", yanchor="bottom")

    fig.update_layout(
        height=420,
        margin=dict(l=14, r=14, t=18, b=14),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono", color="#F4F4F0", size=10),
        showlegend=True,
        legend=dict(
            font=dict(size=9, color="#8B8B92"),
            bgcolor="rgba(0,0,0,0)", bordercolor="#26262C",
            orientation="h", yanchor="bottom", y=-0.16,
            xanchor="center", x=0.5,
        ),
        hoverlabel=dict(
            bgcolor="#0A0A0B", bordercolor="#3A3A42",
            font=dict(color="#F4F4F0", family="JetBrains Mono", size=11),
        ),
        xaxis=dict(
            title="return 1D · %", showgrid=False,
            color="#57575E", linecolor="#26262C", zeroline=False,
        ),
        yaxis=dict(
            title="vol 20D · x", showgrid=True, gridcolor="#26262C",
            gridwidth=0.5, color="#57575E", linecolor="#26262C",
        ),
    )
    st.markdown(
        '<div class="kicker" style="margin-top:10px;padding:4px">2.4 · Return × Volume · '
        "size = ISS · color = sector · gold border = vol-confirmed gainer</div>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, width='stretch', key="movers_scatter")


__all__ = ["render_movers_section"]
