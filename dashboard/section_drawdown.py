"""§05 Drawdown Scanner — names trading well below their 52W high.

Layout (per design lock):
    Row 1: Filter bar (threshold · sector multiselect)
    Row 2: 3 KPI cards (count 3M < −20% · count 1Y < −20% · avg DD)
    Row 3: Drawdown table with Tag pill column · row-click drill into §03

Tag classification reuses :func:`dashboard.phase_f.drawdown_signal_tag` so the
logic stays in one place.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from dashboard.phase_f import drawdown_signal_tag
from dashboard.section_trend import request_trend_focus
from dashboard.widget_info import tooltip


def render_drawdown_section(calc_date: str, signals_df: pd.DataFrame) -> None:
    """Render §05 Drawdown Scanner."""
    if signals_df.empty:
        _empty("No signal data for selected date.")
        return

    threshold, sectors = _render_filter_bar(signals_df)
    dff = signals_df[signals_df["sector"].isin(sectors)].copy()
    deep = dff[dff["drawdown_from_52w_high_pct"] <= float(threshold)].copy()

    _render_kpi_strip(dff, threshold)

    if deep.empty:
        _empty("No names meet the drawdown threshold for the selected filters.")
        return

    deep["Tag"] = deep.apply(lambda r: drawdown_signal_tag(r, float(threshold)), axis=1)
    _render_drawdown_table(deep)


# ----------------------------- Filter bar -------------------------------- #


def _render_filter_bar(df: pd.DataFrame) -> tuple[int, list[str]]:
    st.markdown(
        '<div class="panel" style="padding:10px 14px;margin-bottom:8px">',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([2, 5], gap="small")
    with c1:
        st.markdown(
            '<div class="kicker" style="margin-bottom:2px">Min drawdown from 52W high (%)</div>',
            unsafe_allow_html=True,
        )
        threshold = st.slider(
            "drawdown threshold",
            min_value=-50, max_value=-10, value=-20, step=1,
            label_visibility="collapsed",
            key="dd_threshold",
            help=tooltip("drawdown_threshold"),
        )
    with c2:
        st.markdown(
            '<div class="kicker" style="margin-bottom:2px">Sectors</div>',
            unsafe_allow_html=True,
        )
        sectors_all = sorted(df["sector"].dropna().unique().tolist())
        sectors = st.multiselect(
            "sectors",
            options=sectors_all, default=sectors_all,
            label_visibility="collapsed",
            key="dd_sectors",
        )
    st.markdown("</div>", unsafe_allow_html=True)
    return int(threshold), sectors


# ------------------------------ KPI strip -------------------------------- #


def _render_kpi_strip(df: pd.DataFrame, threshold: float) -> None:
    """3 cards: count 3M<-20%, count 1Y<-20%, avg DD across filtered universe."""
    n_3m_dd = int((df["return_3m"].astype(float) * 100 <= -20).sum())
    n_1y_dd = int((df["return_1y"].astype(float) * 100 <= -20).sum())
    avg_dd = float(df["drawdown_from_52w_high_pct"].mean()) if not df.empty else 0.0
    n_thr = int((df["drawdown_from_52w_high_pct"] <= float(threshold)).sum())

    cards = [
        ("Threshold names", f"{n_thr}", "acc", f"≤ {threshold}% from 52WH"),
        ("3M return ≤ −20%", f"{n_3m_dd}", "neg", "rolling 3-month basis"),
        ("1Y return ≤ −20%", f"{n_1y_dd}", "neg", "rolling 1-year basis"),
        ("Avg DD (filtered)", f"{avg_dd:+.2f}%", "warn" if avg_dd <= -10 else "tx2",
         "mean drawdown across filtered names"),
    ]
    html = ['<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-bottom:8px">']
    for label, value, cls, sub in cards:
        html.append(
            f'<div class="panel" style="padding:12px 14px">'
            f'  <div class="kicker">{escape(label)}</div>'
            f'  <div class="serif {cls}" style="font-size:24px;line-height:1.1;margin-top:2px">{value}</div>'
            f'  <div class="mono" style="font-size:10px;color:var(--tx3);margin-top:4px">{escape(sub)}</div>'
            f'</div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


# ------------------------------ Drawdown table --------------------------- #


def _render_drawdown_table(deep: pd.DataFrame) -> None:
    show = deep[
        [
            "symbol", "company_name", "sector", "market_cap_cr", "close",
            "return_3m", "return_1y",
            "drawdown_from_52w_high_pct", "distance_from_52w_low_pct",
            "volume_trend_3m", "signal_category", "iss_score", "Tag",
        ]
    ].copy()
    show["return_3m"] = show["return_3m"].fillna(0).astype(float) * 100
    show["return_1y"] = show["return_1y"].fillna(0).astype(float) * 100
    show.columns = [
        "Symbol", "Company", "Sector", "Mcap ₹Cr", "Close",
        "Ret 3M", "Ret 1Y",
        "DD vs 52WH", "Dist 52WL", "Vol trend 3M",
        "Signal", "ISS", "Tag",
    ]

    event = st.dataframe(
        show,
        width="stretch",
        hide_index=True,
        height=min(540, 60 + len(show) * 36),
        key="dd_table",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Sector": st.column_config.TextColumn("Sector", width="medium"),
            "Company": st.column_config.TextColumn("Company", width="medium"),
            "Mcap ₹Cr": st.column_config.NumberColumn(format="%.0f"),
            "Close": st.column_config.NumberColumn(format="₹%.2f"),
            "Ret 3M": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("return_3m")),
            "Ret 1Y": st.column_config.NumberColumn(format="%+.2f%%"),
            "DD vs 52WH": st.column_config.NumberColumn(format="%.2f%%", help=tooltip("drawdown_pct")),
            "Dist 52WL": st.column_config.NumberColumn(format="%.2f%%", help=tooltip("distance_from_low")),
            "ISS": st.column_config.NumberColumn(format="%.0f", help=tooltip("iss_score")),
            "Vol trend 3M": st.column_config.TextColumn("Vol trend 3M", help=tooltip("volume_trend_3m")),
            "Signal": st.column_config.TextColumn("Signal", help=tooltip("signal_category")),
            "Tag": st.column_config.TextColumn("Tag", help=tooltip("drawdown_tag")),
        },
    )
    rows = (event or {}).get("selection", {}).get("rows") or []
    if rows:
        idx = rows[0]
        if 0 <= idx < len(show):
            symbol = str(show.iloc[idx]["Symbol"])
            request_trend_focus(symbol, "stock", source="drawdown")
            st.markdown(
                f'<div class="mono" style="font-size:10px;color:var(--acc);padding:6px 4px">'
                f"↻ {escape(symbol)} sent to §03 Trend Workbench · scroll up to view</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="mono" style="font-size:10px;color:var(--tx3);padding:6px 4px">'
        'Tag legend · <span class="pos">Potential Accumulation</span> = contracting volume / ACC bias · '
        '<span class="neg">Falling Knife Risk</span> = expanding volume or EventDriven · '
        '<span class="warn">Needs Event Review</span> = event flag or mixed setup.'
        '</div>',
        unsafe_allow_html=True,
    )


# ------------------------------- Helpers --------------------------------- #


def _empty(message: str) -> None:
    st.markdown(
        f'<div class="panel" style="padding:32px;text-align:center;color:var(--tx3);'
        f"font-family:'JetBrains Mono',monospace;font-size:12px\">"
        f"{escape(message)}</div>",
        unsafe_allow_html=True,
    )


__all__ = ["render_drawdown_section"]
