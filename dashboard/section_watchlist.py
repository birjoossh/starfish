"""§02 Watchlist · Auto-curated + Pinned — single-page consolidated layout.

Layout (per design lock):
    Row 1: 4 category tabs (Contrarian / Momentum / Event-Driven / Volume-Confirmed)
    Row 2: Watchlist table (9 cols) + sticky ISS Gauge sidebar (3 cols)

Categories filter the same `mart_stock_signals` slice locally — mirrors the
logic in ``api/routers/watchlist.py::get_category_items`` but avoids an HTTP
hop so the section also works under :mod:`streamlit.testing.v1.AppTest`.

Backend gap: ISS factor decomposition (Price Momentum / Volume Quality /
Drawdown-Recovery / Corporate Event / Relative Strength sub-scores) is not
yet computed — see TODO-122 and Phase 2 ISS scoring task in the spec. The
gauge surfaces this with a "ISS pipeline pending" pill rather than fabricated
numbers.
"""
from __future__ import annotations

import datetime as dt
import math
from html import escape
from typing import Optional

import pandas as pd
import streamlit as st

from dashboard.primitives import pill
from dashboard.watchlist import load_watchlist


# ----------------------------- Categories -------------------------------- #


CATEGORIES: tuple[str, ...] = (
    "Contrarian Opportunities",
    "Momentum Leaders",
    "Event-Driven Candidates",
    "Volume-Confirmed Movers",
)


def _filter_category(signals_df: pd.DataFrame, category: str, min_iss: float = 50) -> pd.DataFrame:
    """Apply the category-specific filter to a signals slice.

    Mirrors the logic in ``api/routers/watchlist.py::get_category_items`` so the
    UI doesn't require an HTTP round-trip. Returns the rows that match the
    category along with a ``key_reason`` column for the table.
    """
    if signals_df.empty:
        return signals_df

    cat = category.lower()
    df = signals_df.copy()

    # Ensure cols exist; fill missing with safe defaults so filters don't crash
    for col in ("drawdown_from_52w_high_pct", "vol_ratio_1d", "iss_score",
                "rs_vs_nifty_3m", "momentum_flag", "event_flag",
                "accumulation_flag", "return_1d", "return_1m"):
        if col not in df.columns:
            df[col] = 0

    if cat == "contrarian opportunities":
        mask = (
            (df["drawdown_from_52w_high_pct"] <= -20)
            & (df["vol_ratio_1d"] <= 0.85)
            & (df["iss_score"] >= min_iss)
        )
        out = df[mask].copy()
        out["key_reason"] = out.apply(
            lambda r: f"Deep DD ({r['drawdown_from_52w_high_pct']:.0f}%) · Vol contraction ({r['vol_ratio_1d']:.2f}x)",
            axis=1,
        )
        out["primary_signal"] = "Accumulation"
        out["signal_kind"] = "info"
    elif cat == "momentum leaders":
        mask = (
            (df["iss_score"] >= max(min_iss, 70))
            & (df["rs_vs_nifty_3m"] > 0)
            & (df["momentum_flag"].astype(bool))
        )
        out = df[mask].copy()
        out["key_reason"] = "Strong momentum · ISS ≥ 70 · RS > 0 · momentum flag set"
        out["primary_signal"] = "Momentum"
        out["signal_kind"] = "pos"
    elif cat == "event-driven candidates":
        mask = (df["event_flag"].astype(bool)) & (df["iss_score"] >= min_iss)
        out = df[mask].copy()
        out["key_reason"] = "Recent qualifying corporate event · monitor follow-through"
        out["primary_signal"] = "Event-Driven"
        out["signal_kind"] = "evt"
    elif cat == "volume-confirmed movers":
        mask = (df["vol_ratio_1d"] > 2.0) & (df["return_1d"] > 0)
        out = df[mask].copy()
        out["key_reason"] = out.apply(
            lambda r: f"Vol {r['vol_ratio_1d']:.2f}x with {r['return_1d']*100:+.1f}% gain",
            axis=1,
        )
        out["primary_signal"] = "Volume-Confirmed"
        out["signal_kind"] = "pos"
    else:
        out = df.iloc[0:0].copy()
        out["key_reason"] = []
        out["primary_signal"] = []
        out["signal_kind"] = []

    return out


# --------------------------- Mini-gauge SVG ------------------------------ #


def _mini_gauge_svg(score: float, *, size: int = 130) -> str:
    """Render the ISS mini-gauge as inline SVG (half-arc, 4 zones).

    Inline-SVG so the gauge ships inside one ``st.markdown`` call — Plotly
    chart-in-markdown doesn't nest cleanly inside ``.panel`` borders.
    """
    s = max(0.0, min(100.0, float(score)))
    w = size
    h = size * 0.62
    cx, cy = w / 2, h
    r_outer = w / 2 - 4
    r_inner = r_outer - 12

    # 4 zones: 0-40 red, 40-60 amber, 60-80 green, 80-100 deep green.
    zones = [
        (0, 40, "#F87171"),
        (40, 60, "#FBBF24"),
        (60, 80, "#4ADE80"),
        (80, 100, "#2DD881"),
    ]

    def arc_path(start_pct: float, end_pct: float, color: str) -> str:
        # 0% = 180° (left), 100% = 0° (right). Half-circle.
        a1 = math.pi - start_pct / 100 * math.pi
        a2 = math.pi - end_pct / 100 * math.pi
        x1, y1 = cx + r_outer * math.cos(a1), cy - r_outer * math.sin(a1)
        x2, y2 = cx + r_outer * math.cos(a2), cy - r_outer * math.sin(a2)
        xi1, yi1 = cx + r_inner * math.cos(a2), cy - r_inner * math.sin(a2)
        xi2, yi2 = cx + r_inner * math.cos(a1), cy - r_inner * math.sin(a1)
        return (
            f'<path d="M {x1:.2f} {y1:.2f} '
            f"A {r_outer:.2f} {r_outer:.2f} 0 0 1 {x2:.2f} {y2:.2f} "
            f"L {xi1:.2f} {yi1:.2f} "
            f"A {r_inner:.2f} {r_inner:.2f} 0 0 0 {xi2:.2f} {yi2:.2f} "
            f'Z" fill="{color}"/>'
        )

    arcs = "".join(arc_path(a, b, c) for a, b, c in zones)

    # Needle
    needle_angle = math.pi - s / 100 * math.pi
    nx = cx + (r_outer - 4) * math.cos(needle_angle)
    ny = cy - (r_outer - 4) * math.sin(needle_angle)

    # Score color matches the zone
    if s < 40:
        score_color = "#F87171"
    elif s < 60:
        score_color = "#FBBF24"
    elif s < 80:
        score_color = "#4ADE80"
    else:
        score_color = "#2DD881"

    return f"""
<svg viewBox="0 0 {w} {h + 22}" width="{w}" height="{h + 22}" style="display:block;margin:0 auto">
  {arcs}
  <line x1="{cx:.2f}" y1="{cy:.2f}" x2="{nx:.2f}" y2="{ny:.2f}" stroke="#F4F4F0" stroke-width="2" stroke-linecap="round"/>
  <circle cx="{cx:.2f}" cy="{cy:.2f}" r="4" fill="#F4F4F0"/>
  <text x="{cx:.2f}" y="{cy - 16:.2f}" text-anchor="middle"
        font-family="Instrument Serif" font-size="28" fill="{score_color}">{s:.0f}</text>
  <text x="{cx:.2f}" y="{h + 16:.2f}" text-anchor="middle"
        font-family="JetBrains Mono" font-size="9" fill="#57575E" letter-spacing="2px">COMPOSITE</text>
</svg>
"""


# ------------------------- Sidebar — ISS gauge --------------------------- #


def _render_iss_gauge(selected_row: Optional[pd.Series]) -> None:
    """Render the sticky ISS gauge panel for the currently selected stock.

    Args:
        selected_row: A single row from the watchlist table or ``None`` if the
            user hasn't clicked yet.
    """
    if selected_row is None:
        st.markdown(
            """
<div class="panel" style="padding:14px;min-height:340px">
  <div class="kicker">7.3 · ISS Gauge</div>
  <div class="serif" style="font-size:18px;line-height:1.2;margin-top:4px;color:var(--tx2)">
    select a row →
  </div>
  <div class="mono" style="font-size:11px;color:var(--tx3);margin-top:14px;line-height:1.6">
    Click any watchlist row to surface the ISS composite breakdown for that stock.
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        return

    sym = escape(str(selected_row.get("symbol", "—")))
    iss = float(selected_row.get("iss_score", 0))
    company = escape(str(selected_row.get("company_name", "")))
    sector = escape(str(selected_row.get("sector", "")))
    gauge = _mini_gauge_svg(iss)

    pending_pill = pill("ISS pipeline pending · TODO-122", "warn")
    factor_rows = []
    for label in (
        "Price Momentum",
        "Volume Quality",
        "Drawdown / Recovery",
        "Corporate Event",
        "Relative Strength",
    ):
        factor_rows.append(
            f"""
<div style="margin-bottom:8px">
  <div class="mono" style="font-size:11px;display:flex;justify-content:space-between;margin-bottom:2px">
    <span class="tx2">{label}</span><span class="tx3">—&nbsp;/&nbsp;20</span>
  </div>
  <div class="bar"><i style="width:0;background:var(--tx3)"></i></div>
</div>
"""
        )
    factor_block = "".join(factor_rows)

    st.markdown(
        f"""
<div class="panel sticky-sidebar" style="padding:14px;min-height:340px">
  <div class="kicker">7.3 · ISS Gauge</div>
  <div class="serif" style="font-size:18px;line-height:1.2;margin-top:2px">{sym}
    <span class="tx3" style="font-size:11px;font-family:'JetBrains Mono',monospace">selected</span></div>
  <div class="mono" style="font-size:10px;color:var(--tx3);margin-bottom:4px">{company} · {sector}</div>
  <div style="margin:8px 0">{gauge}</div>
  <div style="margin:10px 0">{pending_pill}</div>
  <div style="margin-top:12px">
    <div class="kicker" style="margin-bottom:6px">Factor breakdown</div>
    {factor_block}
  </div>
  <div class="mono" style="font-size:10px;color:var(--tx3);line-height:1.5;margin-top:10px">
    Composite of 5 factors · weights v1.0.<br>
    Factor decomposition wired when TODO-122 (mart_stock_signals factor cols) + ISS scoring function land.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ----------------------- Table — display projection ---------------------- #


_WATCHLIST_DISPLAY_COLS = [
    "Pin", "Symbol", "Company", "Sector",
    "ISS", "Signal", "Key Reason",
    "Ret 1D", "Ret 1M", "Vol 20D",
    "↘ 52WH",
]


def _build_watchlist_display(df: pd.DataFrame, pinned: set[str]) -> pd.DataFrame:
    """Project the filtered category frame into the display columns."""
    if df.empty:
        return pd.DataFrame(columns=_WATCHLIST_DISPLAY_COLS)

    out = pd.DataFrame()
    out["Pin"] = df["symbol"].apply(lambda s: "★" if s in pinned else "·")
    out["Symbol"] = df["symbol"]
    out["Company"] = df["company_name"]
    out["Sector"] = df["sector"]
    out["ISS"] = df["iss_score"].astype(float)
    out["Signal"] = df["primary_signal"]
    out["Key Reason"] = df["key_reason"]
    out["Ret 1D"] = df["return_1d"].astype(float) * 100
    out["Ret 1M"] = df["return_1m"].astype(float) * 100
    out["Vol 20D"] = df["vol_ratio_1d"].astype(float)
    out["↘ 52WH"] = df["drawdown_from_52w_high_pct"].astype(float)
    return out


def _watchlist_column_config() -> dict:
    return {
        "Pin": st.column_config.TextColumn("", width="small"),
        "Symbol": st.column_config.TextColumn("Symbol", width="small"),
        "Company": st.column_config.TextColumn("Company", width="medium"),
        "Sector": st.column_config.TextColumn("Sector", width="medium"),
        "ISS": st.column_config.NumberColumn("ISS", format="%.0f"),
        "Signal": st.column_config.TextColumn("Signal"),
        "Key Reason": st.column_config.TextColumn("Key Reason", width="large"),
        "Ret 1D": st.column_config.NumberColumn("Ret 1D", format="%+.2f%%"),
        "Ret 1M": st.column_config.NumberColumn("Ret 1M", format="%+.2f%%"),
        "Vol 20D": st.column_config.NumberColumn("Vol 20D", format="%.2fx"),
        "↘ 52WH": st.column_config.NumberColumn("↘ 52WH", format="%.1f%%"),
    }


# ------------------------- CSV export helper ---------------------------- #


def _build_csv(df: pd.DataFrame, category: str, pinned: set[str]) -> bytes:
    """Materialize the current tab to CSV bytes including a metadata header."""
    import io
    import csv

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([f"# Starfish Nifty 50 Watchlist · {category} · "
                f"exported {dt.datetime.now().isoformat(timespec='seconds')}"])
    w.writerow(["Symbol", "Company", "Sector", "ISS", "Signal",
                "Ret 1D %", "Ret 1M %", "Vol 20D x", "↘ 52WH %",
                "Key Reason", "Pinned"])
    for _, r in df.iterrows():
        w.writerow([
            r.get("symbol", ""),
            r.get("company_name", ""),
            r.get("sector", ""),
            f"{float(r.get('iss_score', 0)):.0f}",
            r.get("primary_signal", ""),
            f"{float(r.get('return_1d', 0)) * 100:+.2f}",
            f"{float(r.get('return_1m', 0)) * 100:+.2f}",
            f"{float(r.get('vol_ratio_1d', 0)):.2f}",
            f"{float(r.get('drawdown_from_52w_high_pct', 0)):.1f}",
            r.get("key_reason", ""),
            "Yes" if r.get("symbol") in pinned else "No",
        ])
    return buf.getvalue().encode("utf-8")


# ------------------------------ Public API ------------------------------- #


def render_watchlist_section(
    calc_date: str,
    signals_df: pd.DataFrame,
) -> None:
    """Render §02 — 4 category tabs + watchlist table + sticky ISS gauge.

    Args:
        calc_date: ISO date string driving the underlying signal slice.
        signals_df: Pre-loaded mart_stock_signals frame.
    """
    if signals_df.empty:
        st.markdown(
            '<div class="panel" style="padding:32px;text-align:center;'
            "color:var(--tx3);font-family:'JetBrains Mono',monospace;font-size:12px\">"
            "No signal data for selected date.</div>",
            unsafe_allow_html=True,
        )
        return

    try:
        pinned: set[str] = load_watchlist()
    except Exception:
        pinned = set()

    col_table, col_gauge = st.columns([9, 3], gap="small")

    with col_table:
        tabs = st.tabs([f"{c}" for c in CATEGORIES])
        # Each tab renders independently. We funnel every selection through
        # ``st.session_state.watchlist_selected`` so the gauge reflects the
        # *most recent* row click across tabs — Streamlit re-runs all tabs on
        # every rerun, so we can't infer "which tab is active" by element
        # presence alone. Single session slot avoids stale-selection.
        for i, (tab, category) in enumerate(zip(tabs, CATEGORIES)):
            with tab:
                _render_category_panel(
                    category, signals_df, pinned, slot_key=f"wl_tab_{i}"
                )

        stored = st.session_state.get("watchlist_selected")
        selected_row: Optional[pd.Series] = (
            pd.Series(stored) if isinstance(stored, dict) else None
        )

    with col_gauge:
        _render_iss_gauge(selected_row)


def _render_category_panel(
    category: str,
    signals_df: pd.DataFrame,
    pinned: set[str],
    *,
    slot_key: str,
) -> Optional[pd.Series]:
    """Render one tab: filter chips + table + export button."""
    filtered = _filter_category(signals_df, category)
    n = len(filtered)

    # Sort pinned to top, then by ISS descending
    if not filtered.empty:
        filtered = filtered.assign(
            _pin_sort=filtered["symbol"].apply(lambda s: 0 if s in pinned else 1)
        ).sort_values(["_pin_sort", "iss_score"], ascending=[True, False]).drop(columns=["_pin_sort"])

    st.markdown(
        f"""
<div style="padding:8px 4px 4px 4px;display:flex;align-items:baseline;justify-content:space-between">
  <div>
    <div class="kicker">7.1 · {escape(category)}</div>
    <div class="serif" style="font-size:18px;line-height:1.2">{n} name{'s' if n != 1 else ''}{' · ' + str(sum(1 for s in filtered.get('symbol', []) if s in pinned)) + ' pinned' if n else ''}</div>
  </div>
  <div class="mono" style="font-size:10px;color:var(--tx3)">click row → ISS gauge · pin via watchlist.yaml</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if filtered.empty:
        st.markdown(
            '<div class="sub" style="padding:24px;text-align:center;color:var(--tx3);'
            "font-family:'JetBrains Mono',monospace;font-size:11px\">no candidates for current thresholds</div>",
            unsafe_allow_html=True,
        )
        return None

    display = _build_watchlist_display(filtered, pinned)

    event = st.dataframe(
        display,
        width='stretch',
        hide_index=True,
        height=min(440, 60 + len(display) * 36),
        key=f"{slot_key}_df",
        on_select="rerun",
        selection_mode="single-row",
        column_config=_watchlist_column_config(),
    )

    # CSV export
    csv_bytes = _build_csv(filtered, category, pinned)
    today = dt.date.today().strftime("%Y%m%d")
    safe = category.lower().replace(" ", "_").replace("/", "_")
    st.download_button(
        label="⤓ Export CSV",
        data=csv_bytes,
        file_name=f"nifty50_watchlist_{safe}_{today}.csv",
        mime="text/csv",
        key=f"{slot_key}_csv",
    )

    rows = (event or {}).get("selection", {}).get("rows") or []
    if rows:
        idx = rows[0]
        if 0 <= idx < len(filtered):
            row = filtered.iloc[idx]
            # Persist across tab switches via single session-state slot.
            st.session_state["watchlist_selected"] = {
                "symbol": str(row.get("symbol", "")),
                "company_name": str(row.get("company_name", "")),
                "sector": str(row.get("sector", "")),
                "iss_score": float(row.get("iss_score", 0)),
            }
            return row
    return None


__all__ = ["render_watchlist_section", "CATEGORIES"]
