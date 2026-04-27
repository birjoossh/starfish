"""Phase F dashboard helpers: Drawdown Scanner, Momentum Monitor, Volume Anomaly.

Uses `mart_stock_signals` (+ joins) as the data source. Tag heuristics follow
PROJECT_STATUS / DESIGN.md intent; full Moneycontrol fields are out of scope.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.database import read_sql_df


def load_signals_for_phase_f(calc_date: str) -> pd.DataFrame:
    """Load one calc_date slice with all columns needed for Views 3–5."""
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
    c1, c2, c3 = st.columns([2, 2, 3])
    with c1:
        threshold = st.slider(
            "Min drawdown from 52W high (%)",
            min_value=-50,
            max_value=-10,
            value=-20,
            step=1,
            help="Show names at or below this level (more negative = deeper drawdown).",
        )
    with c2:
        sectors = sorted(df["sector"].dropna().unique().tolist())
        pick = st.multiselect("Sectors", sectors, default=sectors)

    dff = df[df["sector"].isin(pick)].copy()

    with c3:
        deep_preview = dff[dff["drawdown_from_52w_high_pct"] <= float(threshold)]
        st.metric("Names ≤ threshold", f"{len(deep_preview)}")
        if not dff.empty:
            st.metric("Avg drawdown (all filtered)", f"{dff['drawdown_from_52w_high_pct'].mean():.1f}%")

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
        use_container_width=True,
        height=min(520, 40 + len(show) * 36),
        hide_index=True,
        column_config={
            "3M %": st.column_config.NumberColumn(format="%+.1f%%"),
            "1Y %": st.column_config.NumberColumn(format="%+.1f%%"),
            "DD vs 52W high %": st.column_config.NumberColumn(format="%.1f%%"),
            "Dist from 52W low %": st.column_config.NumberColumn(format="%.1f%%"),
            "ISS": st.column_config.NumberColumn(format="%.0f"),
            "Mkt cap (₹Cr)": st.column_config.NumberColumn(format="%.0f"),
            "Close": st.column_config.NumberColumn(format="₹%.2f"),
        },
    )

    st.caption("Tag legend: **Potential Accumulation** = contracting volume / ACC bias · **Falling Knife Risk** = expanding volume or EventDriven · **Needs Event Review** = event flag or mixed setup.")

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
        st.plotly_chart(fig, use_container_width=True)


def render_momentum_tab(df: pd.DataFrame) -> None:
    """View 4: Active momentum, near-breakout radar, RS chart."""
    st.subheader("View 4 · Breakout & Momentum Monitor")

    mom = df[(df["momentum_flag"] == True) | (df["signal_category"] == "Momentum")].copy()
    mom["MOM tier"] = mom["iss_score"].apply(lambda x: momentum_tier_label(float(x)))

    st.markdown("#### Active momentum (MOM flag or Momentum category)")
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
        m_show["return_1d"] *= 100
        m_show["return_3m"] *= 100
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
            use_container_width=True,
            height=min(400, 40 + len(m_show) * 36),
            hide_index=True,
            column_config={
                "1D %": st.column_config.NumberColumn(format="%+.2f%%"),
                "3M %": st.column_config.NumberColumn(format="%+.2f%%"),
                "Vol 1D/20D": st.column_config.NumberColumn(format="%.2fx"),
                "Vol 5D/20D": st.column_config.NumberColumn(format="%.2fx"),
                "DD vs 52W %": st.column_config.NumberColumn(format="%.1f%%"),
                "RS vs Nifty 3M": st.column_config.NumberColumn(format="%+.2f%%"),
                "ISS": st.column_config.NumberColumn(format="%.0f"),
                "Close": st.column_config.NumberColumn(format="₹%.2f"),
            },
        )

    st.markdown("#### Near-breakout radar")
    st.caption("Within ~5% of 52W high, ISS ≥ 50, not yet MOM-flagged.")
    near = df[
        (~df["momentum_flag"])
        & (df["drawdown_from_52w_high_pct"] >= -5.0)
        & (df["iss_score"] >= 50)
    ].sort_values("drawdown_from_52w_high_pct", ascending=False)
    if near.empty:
        st.info("No names match the near-breakout filter.")
    else:
        n_show = near[
            ["symbol", "company_name", "sector", "close", "drawdown_from_52w_high_pct", "vol_ratio_1d", "iss_score"]
        ].copy()
        n_show.columns = ["Symbol", "Company", "Sector", "Close", "DD vs 52W %", "Vol 1D/20D", "ISS"]
        st.dataframe(n_show, use_container_width=True, hide_index=True, height=min(320, 40 + len(n_show) * 36))

    st.markdown("#### RS vs Nifty (3M) — top 15")
    top = df.nlargest(15, "rs_vs_nifty_3m").copy()
    if not top.empty:
        top["rs_pct"] = top["rs_vs_nifty_3m"].astype(float) * 100.0
        fig = px.bar(
            top.sort_values("rs_pct"),
            x="rs_pct",
            y="symbol",
            orientation="h",
            color="rs_pct",
            color_continuous_scale="RdYlGn",
            height=420,
        )
        fig.add_vline(x=0, line_dash="dash", line_color="gray")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", yaxis_title="", xaxis_title="RS vs Nifty 3M (%)")
        st.plotly_chart(fig, use_container_width=True)


def render_volume_tab(df: pd.DataFrame, calc_date: str) -> None:
    """View 5: Volume anomaly buckets + contraction + optional mart."""
    st.subheader("View 5 · Volume Anomaly Monitor")

    mart = load_volume_anomaly_mart(calc_date)
    if not mart.empty:
        st.markdown("#### From `mart_volume_anomaly`")
        st.dataframe(mart, use_container_width=True, height=min(400, 40 + len(mart) * 36), hide_index=True)

    st.markdown("#### From same-day volume ratios (`vol_ratio_1d`)")
    st.caption("Buckets vs 20D average: >20% ≈ 1.2×, >50% ≈ 1.5×, >100% ≈ 2.0×. Contraction: 1D vol ≤ 0.85× and contracting 3M trend.")

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
                sub["return_1d"] *= 100
                sub.columns = ["Symbol", "Vol×", "1D %", "ISS"]
                st.dataframe(sub, hide_index=True, height=min(260, 36 * (len(sub) + 1)), use_container_width=True)
