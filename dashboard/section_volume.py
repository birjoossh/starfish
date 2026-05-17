"""§07 Volume Anomaly Monitor.

Layout (per design lock):
    Row 1: 3 spike sub-tables (1.2× · 1.5× · 2×) + Contraction sub-table
    Row 2: 50-cell vol-ratio heatmap (sorted descending by vol_ratio_1d)
    Row 3: Education collapsible

Spike-band logic (per spec §6.4):
    A · 1.20× ≤ vol/20D avg < 1.50×
    B · 1.50× ≤ vol/20D avg < 2.00×
    C · vol/20D avg ≥ 2.00×

"Unexplained Spike" pill (warn): vol_ratio_1d ≥ 3.0 AND days_since_last_event
either NULL or > 5.

Row click on any spike table sends ``trend_subject`` to §03 Trend Workbench.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.section_trend import request_trend_focus

from dashboard.widget_info import tooltip


# ------------------------------ Public API ------------------------------- #


def render_volume_section(calc_date: str, signals_df: pd.DataFrame) -> None:
    """Render §07 Volume Anomaly Monitor."""
    if signals_df.empty:
        _empty("No signal data for selected date.")
        return

    df = signals_df.copy()
    df["unexplained"] = (
        (df["vol_ratio_1d"].astype(float) >= 3.0)
        & (
            df.get("days_since_last_event", pd.Series(dtype=float)).isna()
            | (df.get("days_since_last_event", pd.Series(dtype=float)) > 5)
        )
    )
    vr = df["vol_ratio_1d"].astype(float)
    b2x = df[vr >= 2.0].copy()
    b15 = df[(vr >= 1.5) & (vr < 2.0)].copy()
    b12 = df[(vr >= 1.2) & (vr < 1.5)].copy()
    contr = df[
        (vr <= 0.85)
        & (df["volume_trend_3m"] == "Contracting")
    ].copy()

    _render_kpi_strip(b2x, b15, b12, contr)

    cols = st.columns(4, gap="small")
    for col, badge, label, part, slot in zip(
        cols,
        ["C", "B", "A", "—"],
        [">2.0×", "1.5×–2.0×", "1.2×–1.5×", "Contraction (≤0.85×)"],
        [b2x, b15, b12, contr],
        ["vol_c", "vol_b", "vol_a", "vol_contr"],
    ):
        with col:
            _render_spike_table(part, badge=badge, label=label, slot_key=slot)

    _render_heatmap(df)

    with st.expander("§ 07.5 · Volume anomaly · reading guide", expanded=False):
        _render_education()


# ------------------------------ KPI strip -------------------------------- #


def _render_kpi_strip(
    b2x: pd.DataFrame, b15: pd.DataFrame, b12: pd.DataFrame, contr: pd.DataFrame
) -> None:
    unexp = int(b2x["unexplained"].sum()) if "unexplained" in b2x.columns else 0
    cards = [
        ("Class C · >2.0×", f"{len(b2x)}", "neg", "potential climax / news"),
        ("Class B · 1.5–2.0×", f"{len(b15)}", "warn", "confirmed interest"),
        ("Class A · 1.2–1.5×", f"{len(b12)}", "info", "elevated turnover"),
        ("Unexplained spikes", f"{unexp}", "acc",
         "≥3.0× and no event in ±5d window"),
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
    if len(contr):
        st.markdown(
            f'<div class="mono" style="font-size:10px;color:var(--tx3);padding:2px 4px 6px">'
            f'· {len(contr)} names contracting (vol ≤ 0.85× and 3M vol-trend = Contracting)'
            f'</div>',
            unsafe_allow_html=True,
        )


# --------------------------- Spike sub-tables ---------------------------- #


def _render_spike_table(
    df: pd.DataFrame, *, badge: str, label: str, slot_key: str
) -> None:
    st.markdown(
        f'<div class="panel" style="padding:10px 12px;margin-bottom:-1px;border-bottom:0">'
        f'  <div style="display:flex;align-items:baseline;gap:8px">'
        f'    <span class="badge-gold">{escape(badge)}</span>'
        f'    <span class="serif" style="font-size:14px">{escape(label)}</span>'
        f'    <span class="kicker" style="margin-left:auto">{len(df)}</span>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if df.empty:
        st.markdown(
            '<div class="sub" style="padding:14px;text-align:center;color:var(--tx3);'
            "font-family:'JetBrains Mono',monospace;font-size:11px\">no rows</div>",
            unsafe_allow_html=True,
        )
        return

    sub = df[["symbol", "vol_ratio_1d", "return_1d", "iss_score"]].copy()
    sub["return_1d"] = sub["return_1d"].astype(float) * 100
    sub["⚠"] = df["unexplained"].map({True: "·", False: ""}).reset_index(drop=True)
    sub = sub.reset_index(drop=True)
    sub.columns = ["Symbol", "Vol 20D", "Ret 1D", "ISS", "⚠"]

    event = st.dataframe(
        sub,
        width="stretch",
        hide_index=True,
        height=min(280, 60 + len(sub) * 32),
        key=f"{slot_key}_df",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Vol 20D": st.column_config.NumberColumn(format="%.2fx", help=tooltip("vol_ratio_1d")),
            "Ret 1D": st.column_config.NumberColumn(format="%+.2f%%"),
            "ISS": st.column_config.NumberColumn(format="%.0f"),
            "⚠": st.column_config.TextColumn(
                "⚠", help="Unexplained spike: ratio ≥ 3.0× and no event within ±5d",
            ),
        },
    )
    rows = (event or {}).get("selection", {}).get("rows") or []
    if rows:
        idx = rows[0]
        if 0 <= idx < len(sub):
            symbol = str(sub.iloc[idx]["Symbol"])
            request_trend_focus(symbol, "stock", source=slot_key)
            st.markdown(
                f'<div class="mono" style="font-size:10px;color:var(--acc);padding:6px 4px">'
                f"↻ {escape(symbol)} → §03</div>",
                unsafe_allow_html=True,
            )


# ----------------------- 50-cell vol-ratio heatmap ----------------------- #


def _render_heatmap(df: pd.DataFrame) -> None:
    """Plot a 5×10 heatmap of the top-50 vol-ratio names with symbol labels."""
    top = df.dropna(subset=["vol_ratio_1d"]).nlargest(50, "vol_ratio_1d").reset_index(drop=True)
    if top.empty:
        return
    rows, cols = 5, 10
    z = [[0.0] * cols for _ in range(rows)]
    text = [[""] * cols for _ in range(rows)]
    hover = [[""] * cols for _ in range(rows)]
    for i, row in top.iterrows():
        r, c = divmod(i, cols)
        if r >= rows:
            break
        vr = float(row.get("vol_ratio_1d") or 0)
        z[r][c] = vr
        text[r][c] = (
            f"<span style='font-family:JetBrains Mono'>"
            f"{escape(str(row.get('symbol') or '')):s}"
            f"<br>{vr:.2f}x</span>"
        )
        hover[r][c] = (
            f"{row.get('symbol')} · vol_ratio {vr:.2f}× · "
            f"ret {float(row.get('return_1d') or 0) * 100:+.2f}%"
        )

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            colorscale=[
                [0.0, "#1C1C20"],
                [0.30, "#26262C"],
                [0.55, "#5A3A1A"],
                [0.80, "#C2761C"],
                [1.0, "#F4A340"],
            ],
            zmin=0, zmax=max(2.0, float(top["vol_ratio_1d"].max())),
            showscale=False,
            text=text, texttemplate="%{text}",
            hovertext=hover, hoverinfo="text",
            xgap=2, ygap=2,
        )
    )
    fig.update_layout(
        height=240,
        margin=dict(l=14, r=14, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono", color="#F4F4F0", size=9),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, autorange="reversed")
    st.markdown(
        '<div class="kicker" style="margin-top:14px;padding:4px">'
        '7.3 · Top 50 by vol-ratio · brighter = higher anomaly · hover for detail'
        '</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, width="stretch", key="vol_heatmap")


# --------------------------- Education panel ----------------------------- #


def _render_education() -> None:
    st.markdown(
        """
<div class="mono" style="font-size:11px;color:var(--tx2);line-height:1.6">
<strong class="acc">How to read this section.</strong><br><br>
The volume ratio compares today's traded volume to the 20-day average. Above
1.2× signals elevated participation; above 2.0× usually pairs with news or
event-driven flow.<br><br>
<strong>Class A (1.2–1.5×)</strong> — early interest. Look for confirmation by 5D vol ratio rising.<br>
<strong>Class B (1.5–2.0×)</strong> — confirmed conviction. Pair with momentum or breakout signal.<br>
<strong>Class C (&gt;2.0×)</strong> — climax-style move. Often retraces unless event-supported.<br><br>
The <span class="acc">⚠</span> column flags unexplained spikes: 3.0×+ volume with
no corporate event in a ±5-day window. These deserve manual review — possibly
information leak or out-of-cycle institutional action.<br><br>
<strong>Contraction</strong> (vol ≤ 0.85× and 3M trend = Contracting) often
precedes basing/accumulation phases. Cross-reference with §05.
</div>
""",
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


__all__ = ["render_volume_section"]
