"""§02 Watchlist · Auto-curated + Pinned — single-page consolidated layout.

Layout (per design lock):
    Row 1: 4 category tabs (Contrarian / Momentum / Event-Driven / Volume-Confirmed)
    Row 2: Watchlist table (9 cols) + sticky ISS Gauge sidebar (3 cols)

Filters mirror the spec gates in ``api/routers/watchlist.py`` but adapt to
the live signal distribution: the spec's `iss_score >= 50` gate filters
every Nifty 50 name out while ISS scoring is still warming up (current max
36 across the universe), and `momentum_flag` / `rs_vs_nifty_3m` are sparse
upstream. Each category therefore runs an ideal-gate first; when zero names
qualify it falls back to a relaxed query with a visible "ISS gate relaxed"
pill so the user knows the surfaced rows are best-available rather than
spec-quality.

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


# ----------------------------- Thresholds -------------------------------- #
#
# Default gate values per category. Stored in session_state under
# ``wl_thresh__<category>__<param>`` so each widget owns one slot and
# ``_filter_category`` reads the live values without prop-drilling.

DEFAULT_THRESHOLDS: dict[str, dict[str, float]] = {
    "Contrarian Opportunities": {
        "ideal_dd_pct_max": -20.0,
        "ideal_vol_ratio_max": 0.85,
        "ideal_iss_min": 50.0,
        "relaxed_dd_pct_max": -10.0,
        "relaxed_vol_ratio_max": 1.0,
    },
    "Momentum Leaders": {
        "ideal_iss_min": 70.0,
        "ideal_rs_3m_min": 0.0,
        "relaxed_iss_min": 0.0,
        "relaxed_rs_1m_min": 0.0,
        "relaxed_ret_1m_min": 0.0,
    },
    "Event-Driven Candidates": {
        "ideal_iss_min": 50.0,
    },
    "Volume-Confirmed Movers": {
        "vol_ratio_min": 2.0,
        "return_1d_min": 0.0,
    },
}


def _threshold_key(category: str, param: str) -> str:
    return f"wl_thresh__{category}__{param}"


def _get_threshold(category: str, param: str) -> float:
    """Return the active value for ``(category, param)``, defaults if unset."""
    key = _threshold_key(category, param)
    return float(st.session_state.get(key, DEFAULT_THRESHOLDS[category][param]))


def _reset_thresholds(category: str) -> None:
    """Restore every threshold for ``category`` to its spec default.

    Used as the popover's *Reset to defaults* callback. Writing into
    ``session_state`` before the widget instantiates on the next rerun
    propagates the change into the input controls.
    """
    for k, v in DEFAULT_THRESHOLDS[category].items():
        st.session_state[_threshold_key(category, k)] = v


def _format_threshold_summary(category: str) -> str:
    """Build a one-line human-readable summary of the active thresholds."""
    if category == "Contrarian Opportunities":
        return (
            f"ideal · DD ≤ {_get_threshold(category, 'ideal_dd_pct_max'):.0f}% · "
            f"vol ≤ {_get_threshold(category, 'ideal_vol_ratio_max'):.2f}x · "
            f"ISS ≥ {_get_threshold(category, 'ideal_iss_min'):.0f}  →  "
            f"relaxed · DD ≤ {_get_threshold(category, 'relaxed_dd_pct_max'):.0f}% · "
            f"vol ≤ {_get_threshold(category, 'relaxed_vol_ratio_max'):.2f}x"
        )
    if category == "Momentum Leaders":
        return (
            f"ideal · ISS ≥ {_get_threshold(category, 'ideal_iss_min'):.0f} · "
            f"rs_3m > {_get_threshold(category, 'ideal_rs_3m_min'):.0f} · "
            f"momentum_flag  →  relaxed · "
            f"rs_1m > {_get_threshold(category, 'relaxed_rs_1m_min'):.0f} · "
            f"ret_1m > {_get_threshold(category, 'relaxed_ret_1m_min'):.0f} · "
            f"ISS > {_get_threshold(category, 'relaxed_iss_min'):.0f}"
        )
    if category == "Event-Driven Candidates":
        return (
            f"ideal · event_flag · ISS ≥ {_get_threshold(category, 'ideal_iss_min'):.0f}"
            f"  →  relaxed · event_flag OR signal_category = EventDriven"
        )
    if category == "Volume-Confirmed Movers":
        return (
            f"vol > {_get_threshold(category, 'vol_ratio_min'):.2f}x · "
            f"return_1d > {_get_threshold(category, 'return_1d_min'):.1f}%"
        )
    return ""


def _ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Make every filter column safe to read; fill missing with 0."""
    for col in (
        "drawdown_from_52w_high_pct", "vol_ratio_1d", "iss_score",
        "rs_vs_nifty_1m", "rs_vs_nifty_3m", "momentum_flag", "event_flag",
        "accumulation_flag", "return_1d", "return_1m", "signal_category",
    ):
        if col not in df.columns:
            df[col] = 0
    return df


def _filter_category(
    signals_df: pd.DataFrame,
    category: str,
) -> tuple[pd.DataFrame, str]:
    """Apply category filters with a fallback when the ideal gate is empty.

    Threshold values come from ``st.session_state`` (seeded by
    :data:`DEFAULT_THRESHOLDS`) so the popover controls in
    :func:`_render_threshold_controls` flow straight into the filter on the
    next rerun without any prop-drilling.

    Returns ``(rows, gate_label)`` where ``gate_label`` records the filter
    that produced the rows so the panel header can disclose whether the
    surfaced names cleared the spec gate or a relaxed one.
    """
    if signals_df.empty:
        return signals_df, "ideal"

    cat = category.lower()
    df = _ensure_cols(signals_df.copy())

    if cat == "contrarian opportunities":
        ideal = df[
            (df["drawdown_from_52w_high_pct"] <= _get_threshold(category, "ideal_dd_pct_max"))
            & (df["vol_ratio_1d"] <= _get_threshold(category, "ideal_vol_ratio_max"))
            & (df["iss_score"] >= _get_threshold(category, "ideal_iss_min"))
        ]
        if not ideal.empty:
            out = ideal.copy()
            gate = "ideal"
        else:
            out = df[
                (df["drawdown_from_52w_high_pct"] <= _get_threshold(category, "relaxed_dd_pct_max"))
                & (df["vol_ratio_1d"] <= _get_threshold(category, "relaxed_vol_ratio_max"))
            ].copy()
            gate = "relaxed"
        out["key_reason"] = out.apply(
            lambda r: (
                f"DD {r['drawdown_from_52w_high_pct']:.0f}% off 52WH · "
                f"vol {r['vol_ratio_1d']:.2f}x (contraction)"
            ),
            axis=1,
        )
        out["primary_signal"] = "Accumulation"
        out["signal_kind"] = "info"

    elif cat == "momentum leaders":
        ideal = df[
            (df["iss_score"] >= _get_threshold(category, "ideal_iss_min"))
            & (df["rs_vs_nifty_3m"] > _get_threshold(category, "ideal_rs_3m_min"))
            & (df["momentum_flag"].astype(bool))
        ]
        if not ideal.empty:
            out = ideal.copy()
            gate = "ideal"
        else:
            # rs_vs_nifty_3m is sparse (TODO-127); fall back to 1M RS which
            # is populated, and use signal_category + rising trend as proxies.
            out = df[
                (df["rs_vs_nifty_1m"] > _get_threshold(category, "relaxed_rs_1m_min"))
                & (df["return_1m"] > _get_threshold(category, "relaxed_ret_1m_min"))
                & (df["iss_score"] > _get_threshold(category, "relaxed_iss_min"))
            ].copy()
            gate = "relaxed"
        out["key_reason"] = out.apply(
            lambda r: (
                f"1M RS {float(r['rs_vs_nifty_1m']) * 100:+.1f}pp · "
                f"1M ret {float(r['return_1m']) * 100:+.1f}%"
            ),
            axis=1,
        )
        out["primary_signal"] = "Momentum"
        out["signal_kind"] = "pos"

    elif cat == "event-driven candidates":
        ideal = df[
            (df["event_flag"].astype(bool))
            & (df["iss_score"] >= _get_threshold(category, "ideal_iss_min"))
        ]
        if not ideal.empty:
            out = ideal.copy()
            gate = "ideal"
        else:
            out = df[
                df["event_flag"].astype(bool)
                | (df["signal_category"] == "EventDriven")
            ].copy()
            gate = "relaxed"
        out["key_reason"] = "Recent qualifying corporate event · monitor follow-through"
        out["primary_signal"] = "Event-Driven"
        out["signal_kind"] = "evt"

    elif cat == "volume-confirmed movers":
        out = df[
            (df["vol_ratio_1d"] > _get_threshold(category, "vol_ratio_min"))
            & (df["return_1d"] * 100 > _get_threshold(category, "return_1d_min"))
        ].copy()
        gate = "ideal"
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
        gate = "ideal"

    return out, gate


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


# ------------------------ Threshold controls UI ------------------------ #


def _render_threshold_controls(category: str) -> None:
    """Popover with number inputs for every adjustable threshold.

    Widgets bind directly to ``st.session_state`` via their ``key=`` arg,
    so changes propagate to ``_filter_category`` on the next rerun without
    needing an explicit submit. A *Reset to defaults* button writes the
    spec values back via :func:`_reset_thresholds` (callback path, fires
    before the script re-runs, so the inputs pick up the new values).
    """
    with st.popover("⚙ Adjust thresholds", use_container_width=False):
        st.markdown(
            f'<div class="kicker">{escape(category)} · gate values</div>',
            unsafe_allow_html=True,
        )

        if category == "Contrarian Opportunities":
            col_i, col_r = st.columns(2)
            with col_i:
                st.markdown('<div class="kicker">Ideal gate</div>', unsafe_allow_html=True)
                st.number_input(
                    "Drawdown ≤ (%)",
                    min_value=-95.0, max_value=0.0, step=1.0,
                    value=_get_threshold(category, "ideal_dd_pct_max"),
                    key=_threshold_key(category, "ideal_dd_pct_max"),
                    help="Stock must be at least this far off its 52-week high.",
                )
                st.number_input(
                    "Vol ratio ≤ (x)",
                    min_value=0.05, max_value=5.0, step=0.05,
                    value=_get_threshold(category, "ideal_vol_ratio_max"),
                    key=_threshold_key(category, "ideal_vol_ratio_max"),
                    help="Today's volume vs 20-day average — contraction signal.",
                )
                st.number_input(
                    "ISS ≥",
                    min_value=0.0, max_value=100.0, step=5.0,
                    value=_get_threshold(category, "ideal_iss_min"),
                    key=_threshold_key(category, "ideal_iss_min"),
                )
            with col_r:
                st.markdown('<div class="kicker">Relaxed fallback</div>', unsafe_allow_html=True)
                st.number_input(
                    "Drawdown ≤ (%)",
                    min_value=-95.0, max_value=0.0, step=1.0,
                    value=_get_threshold(category, "relaxed_dd_pct_max"),
                    key=_threshold_key(category, "relaxed_dd_pct_max"),
                )
                st.number_input(
                    "Vol ratio ≤ (x)",
                    min_value=0.05, max_value=5.0, step=0.05,
                    value=_get_threshold(category, "relaxed_vol_ratio_max"),
                    key=_threshold_key(category, "relaxed_vol_ratio_max"),
                )

        elif category == "Momentum Leaders":
            col_i, col_r = st.columns(2)
            with col_i:
                st.markdown('<div class="kicker">Ideal gate</div>', unsafe_allow_html=True)
                st.number_input(
                    "ISS ≥",
                    min_value=0.0, max_value=100.0, step=5.0,
                    value=_get_threshold(category, "ideal_iss_min"),
                    key=_threshold_key(category, "ideal_iss_min"),
                )
                st.number_input(
                    "rs_3m >",
                    min_value=-1.0, max_value=1.0, step=0.01,
                    value=_get_threshold(category, "ideal_rs_3m_min"),
                    key=_threshold_key(category, "ideal_rs_3m_min"),
                    help="Relative strength vs Nifty over 3 months. "
                         "Note: rs_3m is sparse upstream (TODO-127).",
                )
                st.markdown(
                    '<div class="mono" style="font-size:10px;color:var(--tx3);margin-top:4px">'
                    'momentum_flag is required (boolean, not adjustable).'
                    '</div>',
                    unsafe_allow_html=True,
                )
            with col_r:
                st.markdown('<div class="kicker">Relaxed fallback</div>', unsafe_allow_html=True)
                st.number_input(
                    "ISS >",
                    min_value=0.0, max_value=100.0, step=5.0,
                    value=_get_threshold(category, "relaxed_iss_min"),
                    key=_threshold_key(category, "relaxed_iss_min"),
                )
                st.number_input(
                    "rs_1m >",
                    min_value=-1.0, max_value=1.0, step=0.01,
                    value=_get_threshold(category, "relaxed_rs_1m_min"),
                    key=_threshold_key(category, "relaxed_rs_1m_min"),
                )
                st.number_input(
                    "ret_1m >",
                    min_value=-1.0, max_value=1.0, step=0.01,
                    value=_get_threshold(category, "relaxed_ret_1m_min"),
                    key=_threshold_key(category, "relaxed_ret_1m_min"),
                )

        elif category == "Event-Driven Candidates":
            st.markdown('<div class="kicker">Ideal gate</div>', unsafe_allow_html=True)
            st.number_input(
                "ISS ≥",
                min_value=0.0, max_value=100.0, step=5.0,
                value=_get_threshold(category, "ideal_iss_min"),
                key=_threshold_key(category, "ideal_iss_min"),
            )
            st.markdown(
                '<div class="mono" style="font-size:10px;color:var(--tx3);margin-top:6px;line-height:1.5">'
                'event_flag is required (boolean, not adjustable).<br>'
                'Relaxed fallback = event_flag OR signal_category = EventDriven (no tuning).'
                '</div>',
                unsafe_allow_html=True,
            )

        elif category == "Volume-Confirmed Movers":
            st.number_input(
                "Vol ratio > (x)",
                min_value=0.1, max_value=10.0, step=0.1,
                value=_get_threshold(category, "vol_ratio_min"),
                key=_threshold_key(category, "vol_ratio_min"),
                help="Today's volume vs 20-day average — confirmation signal.",
            )
            st.number_input(
                "return_1d > (%)",
                min_value=-20.0, max_value=20.0, step=0.5,
                value=_get_threshold(category, "return_1d_min"),
                key=_threshold_key(category, "return_1d_min"),
            )

        st.button(
            "Reset to defaults",
            key=f"wl_thresh__reset__{category}",
            on_click=_reset_thresholds,
            args=(category,),
        )


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
    filtered, gate = _filter_category(signals_df, category)
    n = len(filtered)

    # Sort pinned to top, then by ISS descending
    if not filtered.empty:
        filtered = filtered.assign(
            _pin_sort=filtered["symbol"].apply(lambda s: 0 if s in pinned else 1)
        ).sort_values(["_pin_sort", "iss_score"], ascending=[True, False]).drop(columns=["_pin_sort"])

    gate_pill = (
        pill("ISS gate relaxed · scoring distribution still warming up", "warn")
        if gate == "relaxed"
        else ""
    )
    pinned_count = sum(1 for s in filtered.get("symbol", []) if s in pinned)
    pinned_suffix = f" · {pinned_count} pinned" if n else ""
    summary = escape(_format_threshold_summary(category))

    col_hdr, col_ctrl = st.columns([5, 1], gap="small")
    with col_hdr:
        st.markdown(
            f"""
<div style="padding:8px 4px 4px 4px">
  <div class="kicker">7.1 · {escape(category)}</div>
  <div class="serif" style="font-size:18px;line-height:1.2">{n} name{'s' if n != 1 else ''}{pinned_suffix}</div>
  <div class="mono" style="font-size:10.5px;color:var(--tx3);margin-top:6px;line-height:1.5">
    <span class="tx2" style="letter-spacing:1px">ACTIVE THRESHOLDS · </span>{summary}
  </div>
  <div style="margin-top:6px">{gate_pill}</div>
</div>
""",
            unsafe_allow_html=True,
        )
    with col_ctrl:
        st.markdown(
            '<div class="mono" style="font-size:10px;color:var(--tx3);'
            'padding:8px 0 4px 0;text-align:right">click row → ISS gauge</div>',
            unsafe_allow_html=True,
        )
        _render_threshold_controls(category)

    if filtered.empty:
        st.markdown(
            '<div class="sub" style="padding:24px;text-align:center;color:var(--tx3);'
            "font-family:'JetBrains Mono',monospace;font-size:11px\">"
            "no candidates pass ideal gate or fallback for this date</div>",
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
