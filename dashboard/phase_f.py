"""Phase F dashboard helpers: Drawdown Scanner, Momentum Monitor, Volume Anomaly.

Uses `mart_stock_signals` (+ joins) as the data source. Tag heuristics follow
PROJECT_STATUS / DESIGN.md intent; full Moneycontrol fields are out of scope.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.database import read_sql_df
from dashboard.widget_info import render_info, tooltip


def load_signals_for_phase_f(calc_date: str) -> pd.DataFrame:
    """Load one calc_date slice with all columns needed for Views 3–5.

    Scoped to current Nifty 50 constituents via ``dim_stock.nifty50_member``.
    """
    return read_sql_df(
        """
        SELECT s.calc_date, s.symbol, d.company_name, d.sector, d.market_cap_cr,
               p.close, s.return_1d, s.return_1m, s.return_3m, s.return_1y,
               s.vol_ratio_1d, s.vol_ratio_5d, s.vol_ratio_20d,
               s.avg_volume_20d, s.volume_trend_3m,
               s.drawdown_from_52w_high_pct, s.distance_from_52w_low_pct,
               s.signal_category, s.momentum_flag, s.accumulation_flag, s.event_flag,
               s.iss_score, s.rs_vs_nifty_3m, s.rs_vs_nifty_1y,
               s.last_event_type, s.days_since_last_event
        FROM mart_stock_signals s
        JOIN dim_stock d ON s.symbol = d.symbol
        LEFT JOIN fact_eod_price p ON s.symbol = p.symbol AND s.calc_date = p.trade_date
        WHERE s.calc_date = :calc_date
          AND d.nifty50_member = TRUE
        ORDER BY s.drawdown_from_52w_high_pct ASC, s.symbol
        """,
        params={"calc_date": calc_date},
    )


def drawdown_signal_tag(row: pd.Series, threshold_pct: float) -> str:
    """Classify drawdown row into Phase F tag (View 3).

    `drawdown_from_52w_high_pct` is stored as percent (e.g. -25 = 25% below 52W high).
    """
    dd = float(row["drawdown_from_52w_high_pct"])
    if dd > threshold_pct:  # threshold_pct is negative, e.g. -20
        return ""

    vt = str(row.get("volume_trend_3m") or "Mixed")
    sc = str(row.get("signal_category") or "Neutral")
    evt = bool(row.get("event_flag"))

    # Falling knife: rising volume during drawdown, or hot tape while not de-risking vol
    if vt == "Expanding":
        return "Falling Knife Risk"
    if sc == "EventDriven" and vt != "Contracting":
        return "Falling Knife Risk"

    if evt or sc == "EventDriven":
        return "Needs Event Review"

    if vt == "Contracting" or bool(row.get("accumulation_flag")):
        return "Potential Accumulation"

    return "Needs Event Review"


def momentum_tier_label(iss: float) -> str:
    """Mirror analytics.signal_classifier.assign_momentum_tier for UI."""
    if iss >= 80:
        return "Strong"
    if iss >= 65:
        return "Confirmed"
    if iss >= 50:
        return "Watch"
    return ""


def load_volume_anomaly_mart(calc_date: str) -> pd.DataFrame:
    """Return mart_volume_anomaly rows when populated; may be empty."""
    try:
        return read_sql_df(
            """
            SELECT v.symbol, d.company_name, d.sector, v.volume_ratio, v.spike_level,
                   v.price_chg_on_spike_day, v.delivery_pct, v.anomaly_direction,
                   v.nearest_event_within_5d, v.nearest_event_type
            FROM mart_volume_anomaly v
            JOIN dim_stock d ON d.symbol = v.symbol
            WHERE v.calc_date = :calc_date
            ORDER BY v.volume_ratio DESC
            """,
            params={"calc_date": calc_date},
        )
    except Exception:
        return pd.DataFrame()


def render_drawdown_tab(df: pd.DataFrame) -> None:
    """View 3: Drawdown scanner + tags + scatter."""
    st.subheader("View 3 · Drawdown Scanner")
    render_info("drawdown_scanner")
    c1, c2, c3 = st.columns([2, 2, 3])
    with c1:
        threshold = st.slider(
            "Min drawdown from 52W high (%)",
            min_value=-50,
            max_value=-10,
            value=-20,
            step=1,
            help=tooltip("drawdown_threshold"),
        )
    with c2:
        sectors = sorted(df["sector"].dropna().unique().tolist())
        pick = st.multiselect("Sectors", sectors, default=sectors)

    dff = df[df["sector"].isin(pick)].copy()

    with c3:
        deep_preview = dff[dff["drawdown_from_52w_high_pct"] <= float(threshold)]
        st.metric("Names ≤ threshold", f"{len(deep_preview)}", help=tooltip("drawdown_count"))
        if not dff.empty:
            st.metric(
                "Avg drawdown (all filtered)",
                f"{dff['drawdown_from_52w_high_pct'].mean():+.2f}%",
                help=tooltip("drawdown_avg"),
            )

    deep = dff[dff["drawdown_from_52w_high_pct"] <= float(threshold)].copy()
    if deep.empty:
        st.info("No stocks meet the drawdown threshold for the selected filters.")
        return

    deep["Tag"] = deep.apply(lambda r: drawdown_signal_tag(r, float(threshold)), axis=1)
    scan = deep
    show = scan[
        [
            "symbol",
            "company_name",
            "sector",
            "market_cap_cr",
            "close",
            "return_3m",
            "return_1y",
            "drawdown_from_52w_high_pct",
            "distance_from_52w_low_pct",
            "volume_trend_3m",
            "signal_category",
            "iss_score",
            "Tag",
        ]
    ].copy()
    show["return_3m"] = show["return_3m"].fillna(0) * 100
    show["return_1y"] = show["return_1y"].fillna(0) * 100
    show.columns = [
        "Symbol",
        "Company",
        "Sector",
        "Mkt cap (₹Cr)",
        "Close",
        "3M %",
        "1Y %",
        "DD vs 52W high %",
        "Dist from 52W low %",
        "Vol trend 3M",
        "Signal",
        "ISS",
        "Tag",
    ]

    st.dataframe(
        show,
        width='stretch',
        height=min(520, 40 + len(show) * 36),
        hide_index=True,
        column_config={
            "3M %": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("return_3m")),
            "1Y %": st.column_config.NumberColumn(format="%+.2f%%"),
            "DD vs 52W high %": st.column_config.NumberColumn(format="%.2f%%", help=tooltip("drawdown_pct")),
            "Dist from 52W low %": st.column_config.NumberColumn(format="%.2f%%", help=tooltip("distance_from_low")),
            "ISS": st.column_config.NumberColumn(format="%.2f", help=tooltip("iss_score")),
            "Mkt cap (₹Cr)": st.column_config.NumberColumn(format="%.2f"),
            "Close": st.column_config.NumberColumn(format="₹%.2f"),
            "Vol trend 3M": st.column_config.TextColumn("Vol trend 3M", help=tooltip("volume_trend_3m")),
            "Signal": st.column_config.TextColumn("Signal", help=tooltip("signal_category")),
            "Tag": st.column_config.TextColumn("Tag", help=tooltip("drawdown_tag")),
        },
    )

    st.caption("Tag legend: **Potential Accumulation** = contracting volume / ACC bias · **Falling Knife Risk** = expanding volume or EventDriven · **Needs Event Review** = event flag or mixed setup.")
    render_info("drawdown_tag", label="Drawdown Tag — full rules")

    if len(scan) >= 3:
        fig = px.scatter(
            scan,
            x="distance_from_52w_low_pct",
            y="drawdown_from_52w_high_pct",
            color="signal_category",
            hover_name="symbol",
            size="iss_score",
            height=360,
            labels={
                "distance_from_52w_low_pct": "Distance from 52W low %",
                "drawdown_from_52w_high_pct": "Drawdown from 52W high %",
            },
        )
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, width='stretch')


def render_momentum_tab(df: pd.DataFrame) -> None:
    """View 4: Active momentum, near-breakout radar, RS chart."""
    st.subheader("View 4 · Breakout & Momentum Monitor")

    st.markdown("#### Active momentum (MOM flag or Momentum category)")
    render_info("momentum_active")
    mom_iss_floor = st.slider(
        "Min ISS score (also include any name above this)",
        min_value=0,
        max_value=100,
        value=50,
        step=1,
        key="momentum_active_iss",
        help=(
            "Default keeps flag/category-based momentum names. Lower this to also include "
            "names whose ISS reaches the chosen floor — useful when running on a short-history "
            "dataset where the MOM flag rarely fires."
        ),
    )
    mom = df[
        (df["momentum_flag"] == True)
        | (df["signal_category"] == "Momentum")
        | (df["iss_score"] >= mom_iss_floor)
    ].copy()
    mom["MOM tier"] = mom["iss_score"].apply(lambda x: momentum_tier_label(float(x)))
    if mom.empty:
        st.info("No momentum-flagged names on this date.")
    else:
        m_show = mom[
            [
                "symbol",
                "company_name",
                "sector",
                "close",
                "return_1d",
                "return_3m",
                "vol_ratio_1d",
                "vol_ratio_5d",
                "drawdown_from_52w_high_pct",
                "rs_vs_nifty_3m",
                "iss_score",
                "MOM tier",
            ]
        ].copy()
        m_show["return_1d"] = m_show["return_1d"].astype(float) * 100
        m_show["return_3m"] = m_show["return_3m"].astype(float) * 100
        m_show["rs_vs_nifty_3m"] = m_show["rs_vs_nifty_3m"].astype(float) * 100
        m_show.columns = [
            "Symbol",
            "Company",
            "Sector",
            "Close",
            "1D %",
            "3M %",
            "Vol 1D/20D",
            "Vol 5D/20D",
            "DD vs 52W %",
            "RS vs Nifty 3M",
            "ISS",
            "MOM tier",
        ]
        st.dataframe(
            m_show,
            width='stretch',
            height=min(400, 40 + len(m_show) * 36),
            hide_index=True,
            column_config={
                "1D %": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("return_1d")),
                "3M %": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("return_3m")),
                "Vol 1D/20D": st.column_config.NumberColumn(format="%.2fx", help=tooltip("vol_ratio_1d")),
                "Vol 5D/20D": st.column_config.NumberColumn(format="%.2fx", help=tooltip("vol_ratio_5d")),
                "DD vs 52W %": st.column_config.NumberColumn(format="%.2f%%", help=tooltip("drawdown_pct")),
                "RS vs Nifty 3M": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("rs_vs_nifty_3m")),
                "ISS": st.column_config.NumberColumn(format="%.2f", help=tooltip("iss_score")),
                "Close": st.column_config.NumberColumn(format="₹%.2f"),
                "MOM tier": st.column_config.TextColumn("MOM tier", help=tooltip("momentum_tier")),
            },
        )

    st.markdown("#### Near-breakout radar")
    render_info("breakout_radar")
    near_c1, near_c2 = st.columns(2)
    with near_c1:
        near_pct = st.slider(
            "Distance from 52W high (%)",
            min_value=1.0,
            max_value=25.0,
            value=5.0,
            step=0.5,
            key="near_breakout_pct",
            help="Stocks whose close is within this percent of their 52W high.",
        )
    with near_c2:
        iss_floor = st.slider(
            "Min ISS score",
            min_value=0,
            max_value=100,
            value=50,
            step=1,
            key="near_breakout_iss",
            help="Lower this when running against a short-history dataset where ISS scores cap below 50.",
        )
    st.caption(
        f"Within ~{near_pct:g}% of 52W high, ISS ≥ {iss_floor}, not yet MOM-flagged."
    )
    near = df[
        (~df["momentum_flag"])
        & (df["drawdown_from_52w_high_pct"] >= -near_pct)
        & (df["iss_score"] >= iss_floor)
    ].sort_values("drawdown_from_52w_high_pct", ascending=False)
    if near.empty:
        st.info("No names match the near-breakout filter.")
    else:
        n_show = near[
            ["symbol", "company_name", "sector", "close", "drawdown_from_52w_high_pct", "vol_ratio_1d", "iss_score"]
        ].copy()
        n_show.columns = ["Symbol", "Company", "Sector", "Close", "DD vs 52W %", "Vol 1D/20D", "ISS"]
        st.dataframe(
            n_show,
            width='stretch',
            hide_index=True,
            height=min(320, 40 + len(n_show) * 36),
            column_config={
                "DD vs 52W %": st.column_config.NumberColumn(format="%.2f%%", help=tooltip("drawdown_pct")),
                "Vol 1D/20D": st.column_config.NumberColumn(format="%.2fx", help=tooltip("vol_ratio_1d")),
                "ISS": st.column_config.NumberColumn(format="%.2f", help=tooltip("iss_score")),
                "Close": st.column_config.NumberColumn(format="₹%.2f"),
            },
        )

    st.markdown("#### RS vs Nifty (3M)")
    render_info("rs_chart_top15")
    rs_top_n = st.slider(
        "Top N by RS vs Nifty (3M)",
        min_value=5,
        max_value=50,
        value=15,
        step=1,
        key="rs_chart_top_n",
        help="How many leading names (by 3M relative strength vs Nifty) to chart.",
    )
    top = df.nlargest(rs_top_n, "rs_vs_nifty_3m").copy()
    if not top.empty:
        top["rs_pct"] = top["rs_vs_nifty_3m"].astype(float) * 100.0
        fig = px.bar(
            top.sort_values("rs_pct"),
            x="rs_pct",
            y="symbol",
            orientation="h",
            color="rs_pct",
            color_continuous_scale="RdYlGn",
            height=max(280, 28 * rs_top_n),
        )
        fig.add_vline(x=0, line_dash="dash", line_color="gray")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", yaxis_title="", xaxis_title="RS vs Nifty 3M (%)")
        st.plotly_chart(fig, width='stretch')


def render_volume_tab(df: pd.DataFrame, calc_date: str) -> None:
    """View 5: Volume anomaly buckets + contraction + optional mart."""
    st.subheader("View 5 · Volume Anomaly Monitor")
    render_info("volume_anomaly_view")

    mart = load_volume_anomaly_mart(calc_date)
    if not mart.empty:
        st.markdown("#### From `mart_volume_anomaly`")
        render_info("volume_anomaly_mart")
        st.dataframe(
            mart,
            width='stretch',
            height=min(400, 40 + len(mart) * 36),
            hide_index=True,
            column_config={
                "volume_ratio": st.column_config.NumberColumn(help=tooltip("vol_ratio_1d")),
                "spike_level": st.column_config.TextColumn(help=tooltip("spike_level")),
                "delivery_pct": st.column_config.NumberColumn(help=tooltip("delivery_pct")),
            },
        )

    st.markdown("#### From same-day volume ratios (`vol_ratio_1d`)")
    st.caption("Buckets vs 20D average: >20% ≈ 1.2×, >50% ≈ 1.5×, >100% ≈ 2.0×. Contraction: 1D vol ≤ 0.85× and contracting 3M trend.")
    render_info("volume_anomaly_buckets")

    base = df.copy()
    vr = base["vol_ratio_1d"]
    b100 = base[vr >= 2.0]
    b50 = base[(vr >= 1.5) & (vr < 2.0)]
    b20 = base[(vr >= 1.2) & (vr < 1.5)]
    contr = base[(base["vol_ratio_1d"] <= 0.85) & (base["volume_trend_3m"] == "Contracting")]

    cols = st.columns(4)
    for col, title, part in zip(
        cols,
        [">100% vs 20D avg", ">50% (not >100%)", ">20% (not >50%)", "Contraction"],
        [b100, b50, b20, contr],
    ):
        with col:
            st.markdown(f"**{title}** · _{len(part)}_")
            if part.empty:
                st.caption("—")
            else:
                sub = part[["symbol", "vol_ratio_1d", "return_1d", "iss_score"]].copy()
                sub["return_1d"] = sub["return_1d"].astype(float) * 100
                sub.columns = ["Symbol", "Vol 20D", "1D %", "ISS"]
                st.dataframe(
                    sub,
                    hide_index=True,
                    height=min(260, 36 * (len(sub) + 1)),
                    width='stretch',
                    column_config={
                        "Vol 20D": st.column_config.NumberColumn(format="%.2fx", help=tooltip("vol_ratio_1d")),
                        "1D %": st.column_config.NumberColumn(format="%+.2f%%", help=tooltip("return_1d")),
                        "ISS": st.column_config.NumberColumn(format="%.2f", help=tooltip("iss_score")),
                    },
                )
