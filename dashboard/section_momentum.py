"""§06 Breakout & Momentum Monitor.

Layout (per design lock):
    Row 1: Filter bar (Min ISS · Near-breakout %)
    Row 2: 3 KPI cards (Momentum names · Near-breakout · Triple-confirm)
    Row 3: Momentum table with 4-tier quality tag + Triple Conf badge · row click drill into §03
    Row 4: Top-15 RS-vs-Nifty horizontal bar chart

Quality-tag taxonomy (per spec §6.2):
    * Volume-Confirmed — momentum_flag AND vol_ratio_1d ≥ 1.5
    * Event-Driven Pop — event_flag in last 5 sessions
    * Thin Volume      — momentum_flag AND vol_ratio_1d < 1.0
    * Squeeze Risk     — drawdown_from_52w_high_pct ≤ -10 AND vol_ratio_1d ≥ 2.0

Triple Confirmation badge: ISS ≥ 65 AND vol_ratio_1d ≥ 1.5 AND
distance from 52WH ≤ 2%.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.widget_info import tooltip


# ----------------------------- Tag taxonomy ------------------------------ #


def _quality_tag(row: pd.Series) -> str:
    """Classify a momentum candidate into one of four tags or empty."""
    vr = float(row.get("vol_ratio_1d") or 0)
    iss = float(row.get("iss_score") or 0)
    mom = bool(row.get("momentum_flag"))
    evt = bool(row.get("event_flag"))
    dd = float(row.get("drawdown_from_52w_high_pct") or 0)
    if mom and vr >= 1.5:
        return "Volume-Confirmed"
    if evt:
        return "Event-Driven Pop"
    if mom and vr < 1.0:
        return "Thin Volume"
    if dd <= -10 and vr >= 2.0:
        return "Squeeze Risk"
    if iss >= 65 and vr >= 1.2:
        return "Building"
    return ""


def _is_triple_confirm(row: pd.Series) -> bool:
    """Triple Confirmation: ISS ≥ 65 · vol-confirmed · near 52WH."""
    iss = float(row.get("iss_score") or 0)
    vr = float(row.get("vol_ratio_1d") or 0)
    dd = float(row.get("drawdown_from_52w_high_pct") or 0)
    return iss >= 65 and vr >= 1.5 and dd >= -2.0


_TAG_COLORS = {
    "Volume-Confirmed": "#4ADE80",
    "Event-Driven Pop": "#A78BFA",
    "Thin Volume": "#FBBF24",
    "Squeeze Risk": "#F87171",
    "Building": "#60A5FA",
}


# ----------------------------- Public API -------------------------------- #


def render_momentum_section(calc_date: str, signals_df: pd.DataFrame) -> None:
    """Render §06 Breakout & Momentum Monitor."""
    if signals_df.empty:
        _empty("No signal data for selected date.")
        return

    iss_floor, near_pct = _render_filter_bar()
    df = signals_df.copy()
    df["Tag"] = df.apply(_quality_tag, axis=1)
    df["triple"] = df.apply(_is_triple_confirm, axis=1)

    mom = df[
        (df["momentum_flag"] == True)
        | (df["signal_category"] == "Momentum")
        | (df["iss_score"] >= iss_floor)
    ].copy()
    near = df[
        (~df["momentum_flag"])
        & (df["drawdown_from_52w_high_pct"] >= -near_pct)
        & (df["iss_score"] >= iss_floor)
    ].copy()

    _render_kpi_strip(mom, near, df)

    if mom.empty:
        _empty("No momentum-flagged names — try lowering Min ISS.")
    else:
        _render_momentum_table(mom)

    _render_top_rs_chart(df)


# ----------------------------- Filter bar -------------------------------- #


def _render_filter_bar() -> tuple[int, float]:
    st.markdown(
        '<div class="panel" style="padding:10px 14px;margin-bottom:8px">',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2, gap="small")
    with c1:
        st.markdown(
            '<div class="kicker" style="margin-bottom:2px">Min ISS score</div>',
            unsafe_allow_html=True,
        )
        iss_floor = st.slider(
            "iss floor", min_value=0, max_value=100, value=50, step=1,
            label_visibility="collapsed", key="mom_iss",
            help="Lower this on short-history datasets where ISS rarely exceeds 50.",
        )
    with c2:
        st.markdown(
            '<div class="kicker" style="margin-bottom:2px">Near-breakout · distance from 52W high (%)</div>',
            unsafe_allow_html=True,
        )
        near_pct = st.slider(
            "near pct", min_value=1.0, max_value=25.0, value=5.0, step=0.5,
            label_visibility="collapsed", key="mom_near_pct",
        )
    st.markdown("</div>", unsafe_allow_html=True)
    return int(iss_floor), float(near_pct)


# ------------------------------ KPI strip -------------------------------- #


def _render_kpi_strip(
    mom: pd.DataFrame, near: pd.DataFrame, df: pd.DataFrame
) -> None:
    triple = int(df["triple"].sum())
    vol_conf = int((df["Tag"] == "Volume-Confirmed").sum())
    cards = [
        ("Momentum names", f"{len(mom)}", "acc",
         "MOM-flagged or ISS ≥ floor"),
        ("Near 52W high", f"{len(near)}", "info",
         "within filter % of high · not yet MOM-flagged"),
        ("Volume-Confirmed", f"{vol_conf}", "pos",
         "MOM + vol_ratio_1d ≥ 1.5"),
        ("Triple Confirmation", f"{triple}", "warn",
         "ISS ≥ 65 · vol-confirmed · near 52WH"),
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


# -------------------------- Momentum table ------------------------------- #


def _render_momentum_table(mom: pd.DataFrame) -> None:
    show = mom[
        [
            "symbol", "company_name", "sector", "close",
            "return_1d", "return_3m",
            "vol_ratio_1d", "vol_ratio_5d",
            "drawdown_from_52w_high_pct",
            "rs_vs_nifty_3m", "iss_score", "Tag", "triple",
        ]
    ].copy()
    show["return_1d"] = show["return_1d"].astype(float) * 100
    show["return_3m"] = show["return_3m"].astype(float) * 100
    show["rs_vs_nifty_3m"] = show["rs_vs_nifty_3m"].astype(float) * 100
    show["triple"] = show["triple"].map({True: "★", False: ""})

    show.columns = [
        "Symbol", "Company", "Sector", "Close",
        "Ret 1D", "Ret 3M",
        "Vol 1D/20D", "Vol 5D/20D",
        "DD vs 52WH",
        "RS Nifty 3M", "ISS", "Tag", "Triple",
    ]

    event = st.dataframe(
        show,
        width="stretch",
        hide_index=True,
        height=min(440, 60 + len(show) * 36),
        key="mom_table",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Sector": st.column_config.TextColumn("Sector", width="medium"),
            "Company": st.column_config.TextColumn("Company", width="medium"),
            "Close": st.column_config.NumberColumn(format="₹%.2f"),
            "Ret 1D": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("return_1d")),
            "Ret 3M": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("return_3m")),
            "Vol 1D/20D": st.column_config.NumberColumn(format="%.2fx", help=tooltip("vol_ratio_1d")),
            "Vol 5D/20D": st.column_config.NumberColumn(format="%.2fx", help=tooltip("vol_ratio_5d")),
            "DD vs 52WH": st.column_config.NumberColumn(format="%.2f%%", help=tooltip("drawdown_pct")),
            "RS Nifty 3M": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("rs_vs_nifty_3m")),
            "ISS": st.column_config.NumberColumn(format="%.0f", help=tooltip("iss_score")),
            "Tag": st.column_config.TextColumn("Tag", help="Quality classification (see legend)"),
            "Triple": st.column_config.TextColumn("Triple", help="ISS ≥ 65 + vol-confirmed + near 52WH"),
        },
    )
    rows = (event or {}).get("selection", {}).get("rows") or []
    if rows:
        idx = rows[0]
        if 0 <= idx < len(show):
            symbol = str(show.iloc[idx]["Symbol"])
            st.session_state["trend_subject"] = symbol
            st.session_state["trend_kind"] = "stock"
            st.markdown(
                f'<div class="mono" style="font-size:10px;color:var(--acc);padding:6px 4px">'
                f"↻ {escape(symbol)} sent to §03 Trend Workbench · scroll up to view</div>",
                unsafe_allow_html=True,
            )

    legend_pills = " ".join(
        f'<span class="pill" style="color:{color}">{escape(label)}</span>'
        for label, color in _TAG_COLORS.items()
    )
    st.markdown(
        f'<div class="mono" style="font-size:10px;color:var(--tx3);padding:6px 4px;display:flex;gap:6px;flex-wrap:wrap">'
        f'<span>Tag legend ·</span> {legend_pills}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ------------------------ Top-N RS bar chart ----------------------------- #


def _render_top_rs_chart(df: pd.DataFrame) -> None:
    top_n = 15
    top = df.dropna(subset=["rs_vs_nifty_3m"]).nlargest(top_n, "rs_vs_nifty_3m").copy()
    if top.empty:
        return
    top["rs_pct"] = top["rs_vs_nifty_3m"].astype(float) * 100
    top = top.sort_values("rs_pct")
    colors = [_TAG_COLORS.get(t, "#60A5FA") for t in top["Tag"]]

    fig = go.Figure(
        data=go.Bar(
            x=top["rs_pct"], y=top["symbol"],
            orientation="h",
            marker=dict(color=colors, line=dict(width=0)),
            hovertemplate="%{y} · %{x:+.2f}% RS<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_dash="dot", line_color="#26262C", line_width=1)
    fig.update_layout(
        height=max(280, 24 * len(top)),
        margin=dict(l=14, r=14, t=18, b=14),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono", color="#F4F4F0", size=10),
        showlegend=False,
        xaxis=dict(
            title="RS vs Nifty 3M · %", showgrid=True, gridcolor="#26262C",
            gridwidth=0.5, color="#57575E", linecolor="#26262C", zeroline=False,
        ),
        yaxis=dict(
            title="", showgrid=False, color="#F4F4F0", linecolor="#26262C",
        ),
        hoverlabel=dict(
            bgcolor="#0A0A0B", bordercolor="#3A3A42",
            font=dict(color="#F4F4F0", family="JetBrains Mono", size=11),
        ),
    )
    st.markdown(
        '<div class="kicker" style="margin-top:14px;padding:4px">6.4 · Top 15 by RS vs Nifty · color = quality tag</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, width="stretch", key="mom_top_rs_chart")


# ------------------------------- Helpers --------------------------------- #


def _empty(message: str) -> None:
    st.markdown(
        f'<div class="panel" style="padding:32px;text-align:center;color:var(--tx3);'
        f"font-family:'JetBrains Mono',monospace;font-size:12px\">"
        f"{escape(message)}</div>",
        unsafe_allow_html=True,
    )


__all__ = ["render_momentum_section"]
