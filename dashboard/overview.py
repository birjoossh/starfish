"""§01 Market Overview — single-screen daily briefing.

Layout (per design lock):
    Row 1: 5 KPI cards (Index · 52W bracket · Avg constituent · Vol gauge · Breadth donut)
    Row 2: Sector Breadth table (5 cols) + Performance Heatmap (7 cols)
    Row 3: Optional drill-in (Primary Scanner subset) when a sector or treemap cell is clicked

Backend gaps surfaced as muted "pending" panels (TODO-106 NSE index prices)
rather than blocking the rest of the section. Real data is rendered for
everything that exists in ``mart_stock_signals``.
"""
from __future__ import annotations

import math
from html import escape
from typing import Any, Optional

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from dashboard.primitives import pill
from dashboard.scanner import render_scanner_drilldown


API_URL = "http://localhost:8000"


# ----------------------------- Data accessors ---------------------------- #


@st.cache_data(ttl=60)
def fetch_market_overview(calc_date: str) -> dict[str, Any]:
    """Fetch ``/market-overview`` for ``calc_date``. Returns empty dict on failure."""
    try:
        resp = requests.get(
            f"{API_URL}/market-overview",
            params={"calc_date": calc_date},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"sector_breadth": [], "components": []}


# ------------------------------ Public API ------------------------------- #


def render_overview(
    calc_date: str,
    signals_df: pd.DataFrame,
    watchlist: list[str],
) -> None:
    """Render §01 Market Overview.

    Args:
        calc_date: ISO date string driving all queries.
        signals_df: Pre-loaded mart_stock_signals slice for drill-downs.
        watchlist: List of pinned symbols (drives the ★ column in drill).
    """
    data = fetch_market_overview(calc_date)
    sector_df = pd.DataFrame(data.get("sector_breadth", []))
    components = pd.DataFrame(data.get("components", []))

    if components.empty:
        st.markdown(
            '<div class="panel" style="padding:32px;text-align:center;'
            "color:var(--tx3);font-family:'JetBrains Mono',monospace;"
            'font-size:12px">No signal data for selected date.</div>',
            unsafe_allow_html=True,
        )
        return

    _render_kpi_strip(sector_df, components)
    st.write("")  # spacing

    col_breadth, col_heatmap = st.columns([5, 7], gap="small")
    with col_breadth:
        selected_sector = _render_sector_breadth_panel(sector_df)
    with col_heatmap:
        treemap_label = _render_treemap_panel(components)

    if (selected_sector or treemap_label) and not signals_df.empty:
        _render_drill(signals_df, watchlist, selected_sector, treemap_label)


# ----------------------------- KPI strip --------------------------------- #


def _render_kpi_strip(sector_df: pd.DataFrame, components: pd.DataFrame) -> None:
    """5 KPI cards. Cards 1, 2, 4 are placeholders pending TODO-106 (index prices)."""
    avg_1d = float(components["return_1d"].mean() * 100) if not components.empty else 0.0
    avg_1m = float(components["return_1m"].mean() * 100) if not components.empty else 0.0
    avg_iss = float(components["iss_score"].mean()) if not components.empty else 0.0

    adv = int(sector_df["advancing"].sum()) if not sector_df.empty else 0
    dec = int(sector_df["declining"].sum()) if not sector_df.empty else 0
    n_total = (
        int(sector_df["num_stocks"].sum()) if not sector_df.empty else len(components)
    )
    unch = max(0, n_total - adv - dec)

    cols = st.columns(5, gap="small")

    with cols[0]:
        _pending_kpi(
            "Nifty 50 Index",
            "—",
            "TODO-106 · NSE index prices ingestion pending",
        )
    with cols[1]:
        _pending_kpi(
            "52-Week Bracket",
            "—",
            "index 52W data pending · TODO-106",
        )
    with cols[2]:
        _avg_constituent_kpi(avg_1d, avg_1m, avg_iss)
    with cols[3]:
        _pending_kpi(
            "Realized Vol · 20D",
            "—",
            "vol gauge needs index series · TODO-106",
        )
    with cols[4]:
        _breadth_donut_kpi(adv, dec, unch)


def _pending_kpi(label: str, value: str, hint: str) -> None:
    """Render a muted placeholder KPI card."""
    st.markdown(
        f"""
<div class="panel" style="padding:14px;height:140px;display:flex;flex-direction:column;justify-content:space-between">
  <div>
    <div class="kicker">{label}</div>
    <div class="serif" style="font-size:32px;line-height:1;margin-top:6px;color:var(--tx3)">{value}</div>
  </div>
  <div class="mono" style="font-size:10px;color:var(--tx3)">{hint}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _avg_constituent_kpi(avg_1d: float, avg_1m: float, avg_iss: float) -> None:
    """Real KPI — equal-weighted average of constituent returns + ISS."""
    cls_1d = "pos" if avg_1d > 0 else "neg" if avg_1d < 0 else "tx2"
    cls_1m = "pos" if avg_1m > 0 else "neg" if avg_1m < 0 else "tx2"
    divergence_pill = pill("Breadth Divergence", "warn") if avg_1m < 0 and avg_1d > 0 else ""
    st.markdown(
        f"""
<div class="panel" style="padding:14px;height:140px;display:flex;flex-direction:column;justify-content:space-between">
  <div>
    <div class="kicker">Avg Constituent · 1D</div>
    <div class="mono {cls_1d}" style="font-size:28px;line-height:1;margin-top:6px">{avg_1d:+.2f}%</div>
  </div>
  <div>
    <div class="mono" style="font-size:11px;color:var(--tx2);margin-bottom:4px">
      1M&nbsp;<span class="{cls_1m}">{avg_1m:+.2f}%</span>
      &nbsp;·&nbsp;ISS avg&nbsp;<span class="acc">{avg_iss:.0f}</span>
    </div>
    {divergence_pill}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _donut_svg(adv: int, dec: int, unch: int, *, size: int = 86) -> str:
    """Render a 3-segment donut as inline SVG.

    Inline SVG keeps the entire card inside one ``st.markdown`` call, so the
    surrounding ``.panel`` border wraps correctly (Plotly charts render in
    their own Streamlit container and break HTML nesting).
    """
    total = max(1, adv + dec + unch)
    radius = size / 2 - 2
    cx = cy = size / 2
    inner = radius * 0.62
    segments = [
        (adv, "#4ADE80"),
        (dec, "#F87171"),
        (unch, "#57575E"),
    ]
    paths: list[str] = []
    angle_start = -math.pi / 2  # 12 o'clock
    for value, color in segments:
        if value <= 0:
            continue
        frac = value / total
        angle_end = angle_start + frac * 2 * math.pi
        large_arc = 1 if frac > 0.5 else 0
        x1, y1 = cx + radius * math.cos(angle_start), cy + radius * math.sin(angle_start)
        x2, y2 = cx + radius * math.cos(angle_end), cy + radius * math.sin(angle_end)
        xi1, yi1 = cx + inner * math.cos(angle_end), cy + inner * math.sin(angle_end)
        xi2, yi2 = cx + inner * math.cos(angle_start), cy + inner * math.sin(angle_start)
        if frac >= 0.999:
            # full circle — render as a ring via two half arcs
            mx, my = cx - radius, cy
            mix, miy = cx - inner, cy
            paths.append(
                f'<path d="M {cx} {cy - radius} A {radius} {radius} 0 1 1 {mx} {my} '
                f"A {radius} {radius} 0 1 1 {cx} {cy - radius} "
                f"L {cx} {cy - inner} A {inner} {inner} 0 1 0 {mix} {miy} "
                f'A {inner} {inner} 0 1 0 {cx} {cy - inner} Z" fill="{color}"/>'
            )
        else:
            paths.append(
                f'<path d="M {x1:.2f} {y1:.2f} '
                f"A {radius} {radius} 0 {large_arc} 1 {x2:.2f} {y2:.2f} "
                f"L {xi1:.2f} {yi1:.2f} "
                f"A {inner} {inner} 0 {large_arc} 0 {xi2:.2f} {yi2:.2f} "
                f'Z" fill="{color}"/>'
            )
        angle_start = angle_end
    arcs = "\n".join(paths)
    return f"""
<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" style="display:block;margin:0 auto">
  {arcs}
</svg>
"""


def _breadth_donut_kpi(adv: int, dec: int, unch: int) -> None:
    """Real KPI — advancing/declining/unchanged donut (inline SVG)."""
    donut = _donut_svg(adv, dec, unch, size=86)
    st.markdown(
        f"""
<div class="panel" style="padding:10px 12px;height:140px;display:flex;align-items:center;gap:10px">
  <div>{donut}</div>
  <div style="flex:1">
    <div class="kicker" style="margin-bottom:4px">Breadth · 1D</div>
    <div class="mono" style="font-size:11px;line-height:1.6">
      <div style="display:flex;align-items:center;gap:6px"><span style="display:inline-block;width:8px;height:8px;background:var(--pos)"></span> <b class="pos">{adv}</b> advancing</div>
      <div style="display:flex;align-items:center;gap:6px"><span style="display:inline-block;width:8px;height:8px;background:var(--neg)"></span> <b class="neg">{dec}</b> declining</div>
      <div style="display:flex;align-items:center;gap:6px"><span style="display:inline-block;width:8px;height:8px;background:var(--tx3)"></span> <span class="tx2">{unch}</span> unchanged</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ------------------------ Sector breadth panel --------------------------- #


def _render_sector_breadth_panel(sector_df: pd.DataFrame) -> Optional[str]:
    """Render the sector breadth table. Returns the selected sector or None."""
    if sector_df.empty:
        st.markdown(
            '<div class="panel" style="padding:32px;text-align:center;color:var(--tx3)">'
            "No sector data.</div>",
            unsafe_allow_html=True,
        )
        return None

    display = sector_df.copy().sort_values("avg_return_1d", ascending=False).reset_index(drop=True)
    for col in ("avg_return_1d", "avg_return_1m"):
        if col in display.columns:
            display[col] = display[col].astype(float) * 100

    n_sectors = len(display)
    n_stocks = int(display.get("num_stocks", pd.Series([0])).sum())

    st.markdown(
        f"""
<div class="panel" style="padding:12px 16px;margin-bottom:-1px;border-bottom:0">
  <div class="kicker">1.2 · Sector Breadth</div>
  <div class="serif" style="font-size:18px;line-height:1.2;margin-top:2px">
    {n_sectors} sectors · {n_stocks} names · ↻ click a row to drill
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    event = st.dataframe(
        display,
        use_container_width=True,
        height=380,
        key="overview_sector_breadth",
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        column_config={
            "sector": st.column_config.TextColumn("Sector", width="medium"),
            "num_stocks": st.column_config.NumberColumn("N"),
            "advancing": st.column_config.NumberColumn("Adv"),
            "declining": st.column_config.NumberColumn("Dec"),
            "avg_return_1d": st.column_config.NumberColumn("Avg 1D", format="%+.2f%%"),
            "avg_return_1m": st.column_config.NumberColumn("Avg 1M", format="%+.2f%%"),
            "avg_iss": st.column_config.NumberColumn("Avg ISS", format="%.0f"),
        },
    )
    rows = (event or {}).get("selection", {}).get("rows") or []
    if rows:
        idx = rows[0]
        if 0 <= idx < len(display):
            return str(display.iloc[idx]["sector"])
    return None


# --------------------------- Performance heatmap ------------------------- #


def _render_treemap_panel(components: pd.DataFrame) -> Optional[str]:
    """Render the performance treemap. Returns clicked label (symbol or sector)."""
    if components.empty:
        return None

    df = components.copy()
    df["return_px"] = df["return_1d"].astype(float) * 100

    # ISS score is the "weight" proxy until market_cap_cr is hydrated (TODO-102).
    fig = px.treemap(
        df,
        path=[px.Constant("Nifty 50"), "sector", "symbol"],
        values="iss_score",
        color="return_px",
        color_continuous_scale=[
            (0.00, "#5A1A1F"),
            (0.20, "#9A2D2D"),
            (0.45, "#3D3D40"),
            (0.55, "#3D3D40"),
            (0.75, "#33874A"),
            (1.00, "#3FA85C"),
        ],
        color_continuous_midpoint=0,
        hover_data={"return_1m": ":+.2%", "iss_score": ":.0f"},
    )
    fig.update_layout(
        height=380,
        margin=dict(l=0, r=0, t=4, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        font_family="JetBrains Mono",
        font_color="#F4F4F0",
        coloraxis_colorbar=dict(
            thickness=8,
            len=0.55,
            x=1.02,
            tickfont=dict(size=9, color="#57575E"),
            title=dict(text="1D %", font=dict(size=9, color="#57575E")),
        ),
    )
    fig.update_traces(
        textfont=dict(family="Geist", size=11, color="#FFFFFF"),
        marker=dict(line=dict(color="#0A0A0B", width=1)),
    )

    st.markdown(
        """
<div class="panel" style="padding:12px 16px;margin-bottom:-1px;border-bottom:0">
  <div class="kicker">1.6 · Performance Heatmap · 1D · ↻ click cell to drill</div>
  <div class="serif" style="font-size:18px;line-height:1.2;margin-top:2px">
    Color = today's return · size = ISS score (mcap pending TODO-102)
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        key="overview_treemap",
        on_select="rerun",
    )
    picks = (event or {}).get("selection", {}).get("points") or []
    if picks:
        last = picks[-1]
        label = last.get("label")
        if label:
            return str(label)
    return None


# ------------------------------- Drill-in -------------------------------- #


def _render_drill(
    signals_df: pd.DataFrame,
    watchlist: list[str],
    sector: Optional[str],
    treemap_label: Optional[str],
) -> None:
    """Dispatch click events to the shared scanner drill-down helper."""
    if treemap_label and treemap_label in set(signals_df["symbol"]):
        render_scanner_drilldown(
            signals_df,
            watchlist,
            title=f"{treemap_label} (treemap)",
            key="overview_drill_symbol",
            symbols=[treemap_label],
        )
    elif treemap_label and treemap_label in set(signals_df["sector"]):
        render_scanner_drilldown(
            signals_df,
            watchlist,
            title=f"Sector: {treemap_label} (treemap)",
            key="overview_drill_sector_tm",
            sector=treemap_label,
        )
    elif sector:
        render_scanner_drilldown(
            signals_df,
            watchlist,
            title=f"Sector: {sector}",
            key="overview_drill_sector_row",
            sector=sector,
        )


def render_morning_digest(signals_df: pd.DataFrame, n: int = 3) -> None:
    """Render the Morning Digest strip — top-N by ISS score.

    Designed for the brand-header row, above §01.

    Args:
        signals_df: Pre-loaded mart_stock_signals slice for the calc date.
        n: Number of picks to show (default 3, matches mock).
    """
    if signals_df.empty or "iss_score" not in signals_df.columns:
        st.markdown(
            '<div class="kicker" style="margin-bottom:4px">☀ Morning Digest</div>'
            '<div class="panel" style="padding:10px 14px;color:var(--tx3);'
            "font-family:'JetBrains Mono',monospace;font-size:11px\">"
            "no signal data for this date</div>",
            unsafe_allow_html=True,
        )
        return

    digest = signals_df.nlargest(n, "iss_score")
    cards_html: list[str] = []
    for i, (_, row) in enumerate(digest.iterrows()):
        ret_1d = float(row.get("return_1d", 0)) * 100
        iss = float(row.get("iss_score", 0))
        signal = escape(str(row.get("signal_category", "—")))
        symbol = escape(str(row.get("symbol", "")))
        ret_cls = "pos" if ret_1d > 0 else "neg" if ret_1d < 0 else "tx2"
        iss_cls = "pos" if iss >= 60 else "warn" if iss >= 40 else "neg"
        border = "none" if i == 0 else "1px solid var(--bd)"
        cards_html.append(
            f"""
<div style="padding:0 14px;border-left:{border}">
  <div class="serif" style="font-size:20px;line-height:1.05">{symbol}</div>
  <div class="mono" style="font-size:11px;color:var(--tx2);margin-top:2px">
    ISS&nbsp;<span class="{iss_cls}">{iss:.0f}</span>
    &nbsp;·&nbsp;<span class="{ret_cls}">{ret_1d:+.2f}%</span>
    &nbsp;·&nbsp;<span class="tx3">{signal}</span>
  </div>
</div>
"""
        )
    cards = "".join(cards_html)
    st.markdown(
        f"""
<div class="kicker" style="margin-bottom:4px">☀ Morning Digest · Top {n} by ISS</div>
<div class="panel" style="padding:10px 4px;display:flex;align-items:stretch;gap:0">
  {cards}
</div>
""",
        unsafe_allow_html=True,
    )


__all__ = ["render_overview", "render_morning_digest", "fetch_market_overview"]
