"""§03 Trend Workbench — multi-day price + volume + ISS over time.

Layout (per design lock):
    Row 1: Filter row (mode · subject · period · overlay)
    Row 2: Subject header + main chart panel (9 cols) + stats sidebar (3 cols)
            * Plotly subplot — price (2/3) + volume (1/3)
            * Calendar heatmap below
    Row 3: Sector trend strip (13 mini-tiles)

Drill-in: any row click in §02/§04–§08 sets ``st.session_state.trend_subject``
which feeds this section's subject picker.

Backend gaps (handled gracefully):
    * ``rs_vs_nifty_series`` will be ``None`` until TODO-106 (NSE index
      prices) lands — Workbench hides the overlay + shows a "RS unavailable"
      pill.
    * ``events`` will be ``[]`` until corporate events ingestion (TODO-119/
      120) lands — Workbench renders the chart without markers + shows a
      muted "no events in window" note.
    * ``iss_series`` is constant 0.0 until ISS scoring lands (TODO-122) —
      we render the line but pill the sidebar with "ISS pipeline pending".
"""
from __future__ import annotations

import datetime as dt
from html import escape
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

from dashboard.primitives import pill


API_URL = "http://localhost:8000"

PERIODS: tuple[str, ...] = ("1M", "3M", "6M", "1Y", "3Y", "YTD")
DEFAULT_PERIOD = "6M"


# ----------------------------- Data accessor ----------------------------- #


@st.cache_data(ttl=60, show_spinner=False)
def fetch_trend(subject: str, kind: str, period: str, as_of: str) -> dict[str, Any]:
    """GET /trend with the given params. Returns empty payload on failure."""
    try:
        resp = requests.get(
            f"{API_URL}/trend",
            params={"subject": subject, "kind": kind, "period": period, "as_of": as_of},
            timeout=6,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {
        "subject": subject,
        "kind": kind,
        "period": period,
        "from_date": "",
        "to_date": as_of,
        "price_series": [],
        "volume_series": [],
        "sma_50": [],
        "sma_200": [],
        "rs_vs_nifty_series": None,
        "iss_series": [],
        "events": [],
        "period_stats": {},
        "constituent_count": 0,
        "sector": None,
    }


# ------------------------------ Public API ------------------------------- #


def render_trend_section(calc_date: str, signals_df: pd.DataFrame) -> None:
    """Render §03 Trend Workbench."""
    # ---- Subject resolution: session_state → signals_df default ----
    default_subject = _pick_default_subject(signals_df)
    if "trend_subject" not in st.session_state:
        st.session_state["trend_subject"] = default_subject
    if "trend_kind" not in st.session_state:
        st.session_state["trend_kind"] = "stock"
    if "trend_period" not in st.session_state:
        st.session_state["trend_period"] = DEFAULT_PERIOD

    subject = st.session_state["trend_subject"]
    kind = st.session_state["trend_kind"]
    period = st.session_state["trend_period"]

    _render_filter_row(signals_df)

    # Re-read after filter row (which may have written to session_state)
    subject = st.session_state["trend_subject"]
    kind = st.session_state["trend_kind"]
    period = st.session_state["trend_period"]

    if not subject:
        st.markdown(
            '<div class="panel" style="padding:32px;text-align:center;color:var(--tx3);'
            "font-family:'JetBrains Mono',monospace;font-size:12px\">"
            "No subject selected.</div>",
            unsafe_allow_html=True,
        )
        return

    payload = fetch_trend(subject, kind, period, calc_date)

    col_main, col_side = st.columns([9, 3], gap="small")
    with col_main:
        _render_subject_header(subject, kind, payload, signals_df)
        _render_price_volume_chart(payload)
        _render_calendar_heatmap(payload)
    with col_side:
        _render_stats_sidebar(payload)

    _render_sector_strip(signals_df)


# ----------------------------- Filter row -------------------------------- #


def _on_mode_change() -> None:
    """Reset subject when the user toggles between stock and sector modes.

    Without this, switching modes leaves a stale value in
    ``st.session_state.trend_subject`` (e.g. ``"RELIANCE"`` while options are
    sectors) which makes the selectbox warn about a value-not-in-options.
    """
    st.session_state["trend_subject"] = ""


def _render_filter_row(signals_df: pd.DataFrame) -> None:
    """Render Mode · Subject · Period · (Overlay placeholders)."""
    c_mode, c_subject, c_period = st.columns([2, 4, 4], gap="small")
    with c_mode:
        st.markdown('<div class="kicker" style="margin-bottom:2px">Mode</div>', unsafe_allow_html=True)
        st.radio(
            "Mode",
            options=["stock", "sector"],
            index=0 if st.session_state.get("trend_kind", "stock") == "stock" else 1,
            horizontal=True,
            label_visibility="collapsed",
            key="trend_kind",
            on_change=_on_mode_change,
        )
    with c_subject:
        st.markdown('<div class="kicker" style="margin-bottom:2px">Subject</div>', unsafe_allow_html=True)
        if st.session_state["trend_kind"] == "stock":
            opts = (
                sorted(signals_df["symbol"].unique().tolist())
                if not signals_df.empty
                else [st.session_state.get("trend_subject", "")]
            )
        else:
            opts = (
                sorted(signals_df["sector"].dropna().unique().tolist())
                if not signals_df.empty
                else []
            )
        current = st.session_state.get("trend_subject", opts[0] if opts else "")
        if current not in opts and opts:
            current = opts[0]
        st.selectbox(
            "Subject",
            options=opts,
            index=opts.index(current) if current in opts else 0,
            label_visibility="collapsed",
            key="trend_subject",
        )
    with c_period:
        st.markdown('<div class="kicker" style="margin-bottom:2px">Period</div>', unsafe_allow_html=True)
        st.radio(
            "Period",
            options=PERIODS,
            index=PERIODS.index(st.session_state.get("trend_period", DEFAULT_PERIOD)),
            horizontal=True,
            label_visibility="collapsed",
            key="trend_period",
        )
    st.markdown(
        f"""
<div class="mono" style="font-size:10px;color:var(--tx3);margin-top:6px">
  Overlays · {pill('Events', 'evt')} {pill('52WH/L', 'acc')} {pill('RS · Nifty unavailable', 'warn')} <span class="tag" style="margin-left:6px">SMA 50</span> <span class="tag">SMA 200</span>
  &nbsp;·&nbsp; ↻ click any row in §02–§08 to focus subject here
</div>
""",
        unsafe_allow_html=True,
    )


# --------------------------- Subject header ------------------------------ #


def _render_subject_header(
    subject: str, kind: str, payload: dict[str, Any], signals_df: pd.DataFrame
) -> None:
    """Render the subject info strip above the main chart."""
    info = _signals_row(signals_df, subject) if kind == "stock" else None
    company = escape(str(info["company_name"])) if info is not None else ""
    sector = escape(str(info["sector"])) if info is not None else (
        escape(subject) if kind == "sector" else ""
    )
    close = float(info["close"]) if info is not None and pd.notna(info.get("close")) else None
    ret_1d = float(info["return_1d"]) * 100 if info is not None and pd.notna(info.get("return_1d")) else 0.0

    stats = payload.get("period_stats") or {}
    period = payload.get("period", "—")
    period_return = stats.get("period_return")
    period_pct = f"{period_return * 100:+.2f}%" if period_return is not None else "—"
    pr_cls = (
        "pos" if (period_return or 0) > 0 else "neg" if (period_return or 0) < 0 else "tx2"
    )
    ret_1d_cls = "pos" if ret_1d > 0 else "neg" if ret_1d < 0 else "tx2"

    constituents_pill = (
        pill(f"{payload.get('constituent_count', 0)} constituents", "info")
        if kind == "sector" else ""
    )

    px_line = (
        f'<span class="serif" style="font-size:30px;line-height:1">₹{close:,.2f}</span>'
        f'&nbsp;<span class="mono {ret_1d_cls}" style="font-size:13px">{ret_1d:+.2f}%</span>'
        if close is not None
        else f'<span class="serif" style="font-size:30px;line-height:1;color:var(--tx3)">—</span>'
    )

    st.markdown(
        f"""
<div class="panel" style="padding:14px 16px;margin-top:10px;border-bottom:none">
  <div class="kicker">{escape(subject)} · {company}{(' · ' + sector) if sector else ''} · {kind}</div>
  <div style="display:flex;align-items:baseline;gap:12px;margin-top:4px;flex-wrap:wrap">
    {px_line}
    <div style="border-left:1px solid var(--bd);padding-left:12px">
      <div class="kicker">period · {escape(period)}</div>
      <div class="mono {pr_cls}" style="font-size:14px">{period_pct}</div>
    </div>
    <div style="margin-left:auto">{constituents_pill}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# -------------------------- Price + Volume chart ------------------------- #


def _render_price_volume_chart(payload: dict[str, Any]) -> None:
    """Plotly subplot — price line + SMAs + volume bars (synced x)."""
    price = payload.get("price_series") or []
    volume = payload.get("volume_series") or []
    sma50 = payload.get("sma_50") or []
    sma200 = payload.get("sma_200") or []
    events = payload.get("events") or []

    if not price:
        st.markdown(
            '<div class="panel" style="padding:48px;text-align:center;color:var(--tx3);'
            "font-family:'JetBrains Mono',monospace;font-size:12px;border-top:none\">"
            "no price history in this window</div>",
            unsafe_allow_html=True,
        )
        return

    dates = [p["date"] for p in price]
    closes = [p["close"] for p in price]
    sma50_vals = [s["value"] for s in sma50] if sma50 else [None] * len(dates)
    sma200_vals = [s["value"] for s in sma200] if sma200 else [None] * len(dates)
    vol_values = [v["volume"] for v in volume]
    vol_colors = ["#4ADE80" if v["ret"] >= 0 else "#F87171" for v in volume]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.72, 0.28],
    )
    # --- Price area + line ---
    fig.add_trace(
        go.Scatter(
            x=dates, y=closes, mode="lines",
            line=dict(color="#F4A340", width=1.6),
            fill="tozeroy", fillcolor="rgba(244,163,64,0.10)",
            name="Close", hovertemplate="%{x}<br>₹%{y:,.2f}<extra></extra>",
        ),
        row=1, col=1,
    )
    # SMAs
    if any(v is not None for v in sma50_vals):
        fig.add_trace(
            go.Scatter(
                x=dates, y=sma50_vals, mode="lines",
                line=dict(color="#F4F4F0", width=0.9, dash="dot"),
                name="SMA 50", opacity=0.55,
                hovertemplate="SMA 50 · %{y:,.2f}<extra></extra>",
            ),
            row=1, col=1,
        )
    if any(v is not None for v in sma200_vals):
        fig.add_trace(
            go.Scatter(
                x=dates, y=sma200_vals, mode="lines",
                line=dict(color="#60A5FA", width=0.9, dash="dot"),
                name="SMA 200", opacity=0.55,
                hovertemplate="SMA 200 · %{y:,.2f}<extra></extra>",
            ),
            row=1, col=1,
        )
    # --- Event vlines (only when events are present) ---
    for ev in events:
        ev_date = ev.get("date")
        ev_type = ev.get("type", "Event")
        if not ev_date:
            continue
        fig.add_vline(
            x=ev_date, line_dash="dash",
            line_color="#A78BFA", line_width=0.8, opacity=0.6,
            annotation_text=ev_type, annotation_position="top",
            annotation_font=dict(size=9, color="#A78BFA"),
        )
    # --- Volume bars ---
    fig.add_trace(
        go.Bar(
            x=dates, y=vol_values,
            marker=dict(color=vol_colors, line=dict(width=0)),
            name="Volume", opacity=0.85,
            hovertemplate="%{x}<br>vol %{y:,.0f}<extra></extra>",
        ),
        row=2, col=1,
    )

    # Styling
    fig.update_layout(
        height=420,
        margin=dict(l=12, r=12, t=14, b=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono", color="#F4F4F0", size=10),
        showlegend=False,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#0A0A0B", bordercolor="#3A3A42",
            font=dict(color="#F4F4F0", family="JetBrains Mono", size=11),
        ),
    )
    fig.update_xaxes(
        showgrid=False, color="#57575E", linecolor="#26262C",
        rangeslider=dict(visible=False),
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="#26262C", gridwidth=0.5,
        color="#57575E", linecolor="#26262C",
        row=1, col=1,
    )
    fig.update_yaxes(
        showgrid=False, color="#57575E", linecolor="#26262C",
        row=2, col=1,
    )

    # NOTE: Plotly charts render in their own Streamlit container; wrapping
    # them in a `<div class="panel">` opened via st.markdown does NOT nest
    # (each st.markdown is a separate element). We render the chart bare and
    # add the events annotation as a separate markdown element below.
    st.plotly_chart(fig, use_container_width=True, key="trend_main_chart")
    if not events:
        st.markdown(
            '<div class="mono" style="font-size:10px;color:var(--tx3);'
            'padding:2px 4px 0 4px">'
            "no corporate events in this window · TODO-119/120 not yet seeded"
            "</div>",
            unsafe_allow_html=True,
        )


# ----------------------- Calendar heatmap (1Y) --------------------------- #


def _render_calendar_heatmap(payload: dict[str, Any]) -> None:
    """5 × ~52 cell daily-return heatmap (Mon–Fri rows)."""
    vol_series = payload.get("volume_series") or []
    if not vol_series:
        return
    df = pd.DataFrame(vol_series)
    df["date"] = pd.to_datetime(df["date"])
    df["weekday"] = df["date"].dt.weekday  # 0=Mon..6=Sun
    df = df[df["weekday"] < 5]  # trading-week only
    if df.empty:
        return
    df["week"] = ((df["date"] - df["date"].min()).dt.days // 7).astype(int)

    # Pivot: rows=weekday, cols=week, values=ret
    pivot = df.pivot_table(
        index="weekday", columns="week", values="ret", aggfunc="mean"
    ).reindex(index=range(5))
    z = pivot.values * 100  # to percent
    # pandas 2.2+ removed DataFrame.applymap; use .map (with na_action) instead.
    text = pivot.map(
        lambda r: f"{r * 100:+.2f}%" if pd.notna(r) else ""
    ).values

    # 7-bucket diverging colorscale anchored at p5/p95 of subject distribution
    vals_flat = z[~pd.isna(z)]
    if len(vals_flat) == 0:
        return
    p5, p95 = float(pd.Series(vals_flat).quantile(0.05)), float(
        pd.Series(vals_flat).quantile(0.95)
    )
    bound = max(abs(p5), abs(p95), 1.0)

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            colorscale=[
                [0.0, "#5A1A1F"],
                [0.15, "#7A2228"],
                [0.35, "#9A2D2D"],
                [0.50, "#2C2C30"],
                [0.65, "#2A6739"],
                [0.85, "#33874A"],
                [1.0, "#3FA85C"],
            ],
            zmin=-bound, zmax=bound, zmid=0,
            showscale=False,
            hoverinfo="text",
            text=text,
            xgap=2, ygap=2,
        )
    )
    fig.update_layout(
        height=130,
        margin=dict(l=14, r=14, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono", color="#57575E", size=9),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(
        tickmode="array",
        tickvals=[0, 1, 2, 3, 4],
        ticktext=["Mon", "Tue", "Wed", "Thu", "Fri"],
        autorange="reversed",
        showgrid=False, color="#57575E",
    )
    st.markdown(
        f"""
<div class="kicker" style="display:flex;justify-content:space-between;padding:8px 4px 0 4px">
  <span>Daily Return Calendar · {len(df)} trading days</span>
  <span class="tx3">color anchored to p5/p95 of subject (±{bound:.1f}%)</span>
</div>
""",
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, use_container_width=True, key="trend_cal_heatmap")


# ----------------------------- Stats sidebar ----------------------------- #


def _render_stats_sidebar(payload: dict[str, Any]) -> None:
    """Render the period_stats table + RS-unavailable pill + ISS sparkline."""
    stats = payload.get("period_stats") or {}
    pr = stats.get("period_return")
    vs = stats.get("vs_nifty_pp")
    mdd = stats.get("max_drawdown")
    rv = stats.get("realized_vol")
    sh = stats.get("sharpe")
    avg_vol = stats.get("avg_daily_vol")
    delivery = stats.get("avg_delivery_pct")
    veds = stats.get("vol_expansion_days") or 0
    pct_above = stats.get("pct_days_above_sma50") or 0
    iss_now = stats.get("iss_now")
    iss_avg = stats.get("iss_period_avg")

    def _fmt_pct(v: Optional[float]) -> str:
        if v is None:
            return "—"
        return f"{v * 100:+.2f}%"

    def _fmt_pp(v: Optional[float]) -> str:
        if v is None:
            return "—"
        return f"{v:+.2f} pp"

    def _cls(v: Optional[float]) -> str:
        if v is None or v == 0:
            return "tx2"
        return "pos" if v > 0 else "neg"

    rs_pill = pill("RS · Nifty unavailable · TODO-106", "warn")
    iss_pill = pill("ISS pipeline pending · TODO-122", "warn") if (iss_now in (None, 0.0)) else ""

    iss_block = ""
    iss_series = payload.get("iss_series") or []
    if iss_series:
        # Mini sparkline as inline SVG
        vals = [pt["value"] for pt in iss_series]
        if vals and max(vals) > min(vals):
            pts: list[str] = []
            lo, hi = min(vals), max(vals)
            for i, v in enumerate(vals):
                x = i * (60 / max(1, len(vals) - 1))
                y = 12 - (v - lo) / max(1e-9, hi - lo) * 10
                pts.append(f"{x:.1f},{y:.1f}")
            iss_block = (
                f'<svg viewBox="0 0 60 14" width="60" height="14" '
                f'style="display:inline-block;vertical-align:middle">'
                f'<polyline points="{" ".join(pts)}" fill="none" '
                f'stroke="#4ADE80" stroke-width="1.25"/></svg>'
            )

    rows = [
        ("Return", _fmt_pct(pr), _cls(pr)),
        ("vs Nifty (α)", _fmt_pp(vs), _cls(vs)),
        ("Max drawdown", _fmt_pct(mdd), "neg" if (mdd or 0) < 0 else "tx2"),
        ("Realized vol (ann.)", f"{(rv or 0) * 100:.1f}%", "tx2"),
        ("Sharpe (rf=6%)", f"{sh or 0:.2f}", _cls(sh)),
        ("Avg daily vol", f"{(avg_vol or 0):,.0f}", "tx2"),
        ("Avg delivery %", f"{delivery:.1f}%" if delivery is not None else "—", "tx2"),
        ("Vol expansion days", f"{veds}", "warn" if veds > 10 else "tx2"),
        ("% days &gt; SMA 50", f"{pct_above * 100:.0f}%", _cls(pct_above - 0.5)),
        ("ISS now / avg",
         f"{iss_now:.0f} / {iss_avg:.0f}" if iss_now is not None and iss_avg is not None else "— / —",
         "tx2"),
        ("ISS trend", iss_block or "—", "tx2"),
    ]
    table_html = "".join(
        f"<tr><td style='padding:6px 10px;border-bottom:1px solid var(--bd);color:var(--tx2);font-family:Geist;font-size:11px'>{label}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid var(--bd);text-align:right;font-family:JetBrains Mono;font-size:11px' class='{cls}'>{val}</td></tr>"
        for label, val, cls in rows
    )

    st.markdown(
        f"""
<div class="panel sticky-sidebar" style="padding:14px;min-height:420px">
  <div class="kicker">Period stats · {escape(str(payload.get('period', '—')))} · vs Nifty 50</div>
  <div class="serif" style="font-size:18px;line-height:1.2;margin-top:2px">{escape(str(payload.get('subject', '—')))}</div>
  <table style="width:100%;border-collapse:collapse;margin-top:8px">
    {table_html}
  </table>
  <div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:6px">
    {rs_pill} {iss_pill}
  </div>
  <div class="mono" style="font-size:10px;color:var(--tx3);margin-top:12px;line-height:1.5">
    Source · <span class="acc">fact_eod_price</span> + <span class="acc">mart_stock_signals</span>.<br>
    Events / RS pending TODO-106, TODO-119/120, TODO-122.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# --------------------------- Sector trend strip -------------------------- #


def _render_sector_strip(signals_df: pd.DataFrame) -> None:
    """13-tile sector strip — click flips Workbench to Sector mode."""
    if signals_df.empty or "sector" not in signals_df.columns:
        return
    grp = (
        signals_df.groupby("sector")
        .agg(avg_1m=("return_1m", "mean"), n=("symbol", "count"))
        .reset_index()
    )
    grp["avg_1m_pct"] = grp["avg_1m"].astype(float) * 100
    grp = grp.sort_values("avg_1m_pct", ascending=False).reset_index(drop=True)

    tiles: list[str] = []
    for _, row in grp.iterrows():
        sector = escape(str(row["sector"]))
        ret = float(row["avg_1m_pct"])
        cls = "pos" if ret > 0 else "neg" if ret < 0 else "tx2"
        tiles.append(
            f"""
<div class="sub" style="padding:8px 10px">
  <div class="kicker" style="margin-bottom:2px">{sector}</div>
  <div class="mono {cls}" style="font-size:13px">{ret:+.2f}%</div>
  <div class="mono" style="font-size:9px;color:var(--tx3)">{int(row['n'])} stocks · 1M avg</div>
</div>
"""
        )
    st.markdown(
        f"""
<div class="panel" style="padding:12px 14px;margin-top:10px">
  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px">
    <div>
      <div class="kicker">Quick sector trends · 1M avg return</div>
      <div class="serif" style="font-size:14px">Informational · switch Mode → Sector above to drill</div>
    </div>
    <span class="tag mono">{len(grp)} sectors</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat({min(13, max(1, len(grp)))},minmax(0,1fr));gap:6px">
    {"".join(tiles)}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ----------------------------- Misc helpers ------------------------------ #


def _pick_default_subject(signals_df: pd.DataFrame) -> str:
    """Default subject: top-ISS symbol; falls back to RELIANCE."""
    if signals_df.empty:
        return "RELIANCE"
    if "iss_score" in signals_df.columns:
        try:
            return str(signals_df.nlargest(1, "iss_score").iloc[0]["symbol"])
        except Exception:
            pass
    return str(signals_df.iloc[0]["symbol"])


def _signals_row(signals_df: pd.DataFrame, symbol: str) -> Optional[pd.Series]:
    if signals_df.empty:
        return None
    sub = signals_df[signals_df["symbol"] == symbol]
    if sub.empty:
        return None
    return sub.iloc[0]


__all__ = ["render_trend_section", "fetch_trend"]
