"""Phase I: Mobile Layout + Deployment Hardening.

Mobile-responsive dashboard views and containerization support.
"""

import streamlit as st
import pandas as pd
from typing import Optional


def detect_mobile() -> bool:
    """Detect if user is on mobile device."""
    return st.session_state.get("is_mobile", False)


def render_mobile_header():
    """Mobile-optimized header with collapsible controls."""
    st.markdown("""
        <style>
        .mobile-header {
            padding: 0.5rem;
            background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 0.5rem;
            margin-bottom: 1rem;
        }
        .mobile-title {
            font-size: 1.5rem;
            font-weight: bold;
            color: #00d4aa;
            text-align: center;
        }
        .touch-target {
            min-height: 44px;
            min-width: 44px;
            padding: 12px;
        }
        @media (max-width: 768px) {
            .stMetric {
                padding: 0.5rem;
            }
            div[data-testid="stMetricValue"] > div {
                font-size: 1.2rem !important;
            }
            div[data-testid="stMetricLabel"] > div {
                font-size: 0.8rem !important;
            }
            .stDataFrame {
                font-size: 0.85rem;
            }
        }
        </style>
        <div class="mobile-header">
            <div class="mobile-title">Nifty 50 Starfish</div>
        </div>
    """, unsafe_allow_html=True)


def render_kpi_cards_mobile(signals_df: pd.DataFrame):
    """Mobile-friendly KPI cards in horizontal scroll."""
    if signals_df.empty:
        return

    latest = signals_df.iloc[-1] if len(signals_df) > 0 else None
    if latest is None:
        return

    # Calculate KPIs
    top_iss = signals_df.nlargest(1, "iss_score").iloc[0]
    gainers = signals_df[signals_df["return_1d"] > 0]
    losers = signals_df[signals_df["return_1d"] < 0]

    # Mobile: Use horizontal scrolling container
    st.markdown('<div style="display: flex; overflow-x: auto; gap: 1rem; padding: 0.5rem 0;">', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Top ISS", top_iss["symbol"], f"{top_iss['iss_score']:.0f}")
    with col2:
        avg_iss = signals_df["iss_score"].mean()
        st.metric("Avg ISS", f"{avg_iss:.0f}")
    with col3:
        st.metric("Gainers", len(gainers), f"{len(gainers)/50*100:.0f}%")
    with col4:
        st.metric("Losers", len(losers), f"-{len(losers)/50*100:.0f}%")

    st.markdown('</div>', unsafe_allow_html=True)


def render_signals_table_mobile(signals_df: pd.DataFrame, n: int = 20):
    """Mobile-optimized signals table with larger touch targets."""
    if signals_df.empty:
        st.warning("No data available")
        return

    # Get top N by ISS
    df = signals_df.nlargest(n, "iss_score").copy()

    # Format columns for mobile
    display_cols = ["symbol", "iss_score", "return_1d", "return_1m", "drawdown_from_52w_high_pct"]
    available_cols = [c for c in display_cols if c in df.columns]

    if "return_1d" in available_cols:
        df["return_1d"] = df["return_1d"].apply(lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "N/A")
    if "return_1m" in available_cols:
        df["return_1m"] = df["return_1m"].apply(lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "N/A")
    if "drawdown_from_52w_high_pct" in available_cols:
        df["drawdown_from_52w_high_pct"] = df["drawdown_from_52w_high_pct"].apply(
            lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A"
        )
    if "iss_score" in available_cols:
        df["iss_score"] = df["iss_score"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "N/A")

    # Rename columns for display
    rename_map = {
        "symbol": "Symbol",
        "iss_score": "ISS",
        "return_1d": "1D%",
        "return_1m": "1M%",
        "drawdown_from_52w_high_pct": "DD%",
    }
    df = df.rename(columns=rename_map)

    # Mobile: Use st.dataframe with column config
    st.dataframe(
        df[list(rename_map.values())],
        use_container_width=True,
        hide_index=True,
    )


def render_sidebar_mobile():
    """Mobile-optimized sidebar with collapsible sections."""
    with st.sidebar:
        st.markdown("### Controls")

        # Date selector
        from config.database import read_sql_df
        dates = read_sql_df("SELECT DISTINCT calc_date FROM mart_stock_signals ORDER BY calc_date DESC")
        if not dates.empty:
            selected = st.selectbox(
                "Date",
                dates["calc_date"].tolist(),
                format_func=lambda x: str(x),
            )
            return selected
    return None


def render_view_mobile(calc_date: Optional[str] = None):
    """Mobile-optimized main view.

    Args:
        calc_date: Optional date string to load data for
    """
    render_mobile_header()

    # Load data
    from dashboard.phase_f import load_signals_for_phase_f
    from config.database import read_sql_df

    # Get available dates
    dates_df = read_sql_df("SELECT DISTINCT calc_date FROM mart_stock_signals ORDER BY calc_date DESC")

    if dates_df.empty:
        st.warning("No data available. Run backfill first.")
        return

    available_dates = dates_df["calc_date"].tolist()

    # Date selector
    if calc_date is None:
        calc_date = available_dates[0]
    else:
        # Validate date exists
        if calc_date not in available_dates:
            calc_date = available_dates[0]

    selected_date = st.selectbox(
        "Select Date",
        available_dates,
        index=available_dates.index(calc_date),
        format_func=lambda x: str(x),
    )

    # Load signals for selected date
    signals_df = load_signals_for_phase_f(selected_date)

    # KPI cards
    render_kpi_cards_mobile(signals_df)

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["Top ISS", "Gainers", "Losers", "All"])

    with tab1:
        render_signals_table_mobile(signals_df, 20)

    with tab2:
        gainers_df = signals_df[signals_df["return_1d"] > 0].nlargest(20, "return_1d")
        render_signals_table_mobile(gainers_df, 20)

    with tab3:
        losers_df = signals_df[signals_df["return_1d"] < 0].nsmallest(20, "return_1d")
        render_signals_table_mobile(losers_df, 20)

    with tab4:
        render_signals_table_mobile(signals_df, 50)


def render_view_desktop():
    """Desktop-optimized compact view.

    Shows key metrics and top movers in terminal-style layout.
    """
    from dashboard.phase_f import load_signals_for_phase_f
    from config.database import read_sql_df

    dates_df = read_sql_df("SELECT DISTINCT calc_date FROM mart_stock_signals ORDER BY calc_date DESC")

    if dates_df.empty:
        st.warning("No data available. Run backfill first.")
        return

    available_dates = dates_df["calc_date"].tolist()
    selected_date = st.selectbox("Select Date", available_dates, index=0, format_func=str)

    signals_df = load_signals_for_phase_f(selected_date)

    if signals_df.empty:
        st.warning("No signals data for selected date")
        return

    # Compact header metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        top = signals_df.nlargest(1, "iss_score").iloc[0]
        st.metric("Top ISS", top["symbol"], f"{top['iss_score']:.0f}")
    with col2:
        avg = signals_df["iss_score"].mean()
        st.metric("Avg ISS", f"{avg:.0f}")
    with col3:
        gainers = len(signals_df[signals_df["return_1d"] > 0])
        st.metric("Gainers", gainers, f"{gainers/50*100:.0f}%")
    with col4:
        losers = len(signals_df[signals_df["return_1d"] < 0])
        st.metric("Losers", losers, f"-{losers/50*100:.0f}%")

    # Top movers table
    st.markdown("### Top ISS Scores")
    top_df = signals_df.nlargest(15, "iss_score")[
        ["symbol", "iss_score", "return_1d", "return_1m", "signal_class"]
    ].copy()
    top_df["return_1d"] = top_df["return_1d"].apply(lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "N/A")
    top_df["return_1m"] = top_df["return_1m"].apply(lambda x: f"{x*100:+.1f}%" if pd.notna(x) else "N/A")
    top_df["iss_score"] = top_df["iss_score"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "N/A")
    st.dataframe(top_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "mobile":
        st.set_page_config(layout="wide")
        render_view_mobile()
    else:
        render_view_desktop()