"""Phase G dashboard helpers: Corporate Events Tracker + Watchlist Builder.

Implements View 6 (Events Tracker) and View 7 (Watchlist Builder) as
described in the Nifty 50 Dashboard Specification.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from config.database import read_sql_df
from dashboard.widget_info import render_info, tooltip

API_URL = "http://localhost:8000/api/v1"


# ============================================================
# Data Loading Functions
# ============================================================

@st.cache_data(ttl=60)
def load_all_events(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    event_type: Optional[str] = None,
    min_significance: int = 1,
) -> pd.DataFrame:
    """Load events with optional filters (cached)."""
    params = {
        "from_date": from_date or (date.today() - timedelta(days=90)).isoformat(),
        "to_date": to_date or date.today().isoformat(),
        "min_significance": min_significance,
    }
    if event_type:
        params["event_type"] = event_type

    try:
        response = requests.get(f"{API_URL}/events/timeline", params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            events = []
            for entry in data.get("timeline", []):
                for event in entry.get("events", []):
                    events.append(event)
            return pd.DataFrame(events)
    except Exception:
        pass

    # Fallback to direct DB query
    return _load_events_from_db(from_date, to_date, event_type, min_significance)


def _load_events_from_db(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    event_type: Optional[str] = None,
    min_significance: int = 1,
) -> pd.DataFrame:
    """Load events directly from database."""
    conditions = ["d.nifty50_member = TRUE"]
    params: dict = {}

    if from_date:
        conditions.append("e.event_date >= :from_date")
        params["from_date"] = from_date
    if to_date:
        conditions.append("e.event_date <= :to_date")
        params["to_date"] = to_date
    if event_type:
        conditions.append("LOWER(e.event_type) = LOWER(:event_type)")
        params["event_type"] = event_type
    conditions.append("e.significance_score >= :min_sig")
    params["min_sig"] = min_significance

    where = " AND ".join(conditions)

    df = read_sql_df(f"""
        SELECT e.event_id, e.symbol, e.event_date, e.event_type,
               e.significance_score AS significance,
               e.categorization_method,
               e.event_summary AS description,
               e.raw_announcement_text,
               e.price_chg_1d, e.price_chg_5d, e.price_chg_20d,
               e.follow_up_required,
               d.company_name, d.sector,
               (e.event_date > CURRENT_DATE) AS is_upcoming
        FROM fact_corporate_event e
        JOIN dim_stock d ON e.symbol = d.symbol
        WHERE {where}
        ORDER BY e.event_date DESC, e.significance_score DESC
    """, params=params)

    if not df.empty:
        df["event_date"] = df["event_date"].apply(
            lambda d: d.isoformat() if hasattr(d, "isoformat") else d
        )
    return df


@st.cache_data(ttl=60)
def load_watchlist(user_id: int = 1) -> pd.DataFrame:
    """Load user watchlist with stock details (cached)."""
    try:
        response = requests.get(f"{API_URL}/watchlist", params={"user_id": user_id}, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame(data.get("items", []))
    except Exception:
        pass

    # Fallback to direct DB query
    df = read_sql_df("""
        SELECT w.watchlist_id, w.symbol, d.company_name, d.sector,
               w.added_date, w.reason, w.pinned, w.created_at
        FROM user_watchlist w
        JOIN dim_stock d ON w.symbol = d.symbol
        WHERE w.user_id = :user_id
        ORDER BY w.pinned DESC, w.added_date DESC
    """, params={"user_id": user_id})

    if not df.empty:
        df["added_date"] = df["added_date"].apply(
            lambda d: d.isoformat() if hasattr(d, "isoformat") else d
        )
        df["created_at"] = df["created_at"].apply(
            lambda d: d.isoformat() if hasattr(d, "isoformat") else d
        )
    return df


@st.cache_data(ttl=60)
def load_category_suggestions() -> list[dict[str, Any]]:
    """Load watchlist category suggestions (auto-populated)."""
    try:
        response = requests.get(f"{API_URL}/watchlist/categories", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []


# ============================================================
# View 6: Corporate Events Tracker
# ============================================================

def render_events_tracker() -> None:
    """View 6: Corporate Events Tracker.

    Provides a unified, chronological feed of all material corporate events
    for Nifty 50 companies, with pre- and post-event price context.
    """
    st.subheader("View 6 · Corporate Events Tracker")
    render_info("events_view")

    # Row 1: Filters
    c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
    with c1:
        from_date = st.date_input(
            "From Date",
            value=date.today() - timedelta(days=30),
            label_visibility="collapsed",
        )
    with c2:
        to_date = st.date_input(
            "To Date",
            value=date.today() + timedelta(days=60),
            label_visibility="collapsed",
        )
    with c3:
        event_types = ["All", "Earnings", "Leadership_Change", "M&A", "Large_Order",
                       "Pledging_Change", "Rating_Change", "Regulatory", "Other"]
        selected_type = st.selectbox(
            "Event Type",
            event_types,
            index=0,
            label_visibility="collapsed",
        )
    with c4:
        min_sig = st.slider(
            "Min Significance",
            1, 5, 2,
            label_visibility="collapsed",
            help=tooltip("events_significance"),
        )

    # Load events
    event_type_filter = None if selected_type == "All" else selected_type
    events_df = load_all_events(
        from_date.isoformat(),
        to_date.isoformat(),
        event_type_filter,
        min_sig,
    )

    if events_df.empty:
        st.info("No events found for the selected filters.")
        return

    # Summary cards
    upcoming = events_df[events_df["is_upcoming"] == True].shape[0]  # noqa: E712
    recent = events_df[events_df["is_upcoming"] == False].shape[0]  # noqa: E712
    high_sig = events_df[events_df["significance"] >= 4].shape[0]

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Events", len(events_df), help=tooltip("events_total"))
    s2.metric("Upcoming", upcoming, help=tooltip("events_upcoming"))
    s3.metric("Recent (Past 30d)", recent, help=tooltip("events_recent"))
    s4.metric("High Significance (>=4)", high_sig, help=tooltip("events_high_sig"))

    # Timeline view
    st.markdown("#### Timeline")
    render_info("events_timeline")
    _render_events_timeline(events_df)


def _render_events_timeline(events_df: pd.DataFrame) -> None:
    """Render events grouped by date."""
    # Group by date
    events_df = events_df.copy()
    events_df["event_date"] = pd.to_datetime(events_df["event_date"])

    for date_str, group in events_df.groupby(events_df["event_date"].dt.date):
        group = group.sort_values("significance", ascending=False)

        st.markdown(f"##### {date_str.strftime('%A, %B %d, %Y')}")

        # Create columns for each event
        for _, event in group.iterrows():
            col1, col2, col3 = st.columns([3, 2, 1])

            with col1:
                badge_color = _get_significance_color(event["significance"])
                st.markdown(
                    f"<span style='background-color: {badge_color}; "
                    f"color: white; padding: 4px 12px; border-radius: 4px; "
                    f"font-weight: bold;'>{event['event_type']}</span>",
                    unsafe_allow_html=True,
                )
                st.write(f"**{event['symbol']}** - {event.get('company_name', '')}")
                if event.get("description"):
                    st.caption(event["description"])

            with col2:
                st.write(f"**Significance**: {event['significance']}/5")
                if pd.notna(event.get("price_chg_1d")):
                    chg_1d = float(event["price_chg_1d"])
                    color = "green" if chg_1d >= 0 else "red"
                    st.caption(
                        f"<span style='color: {color};'>1D: {chg_1d:+.1f}%</span>",
                        unsafe_allow_html=True,
                    )
                if event.get("is_upcoming"):
                    st.caption("Upcoming Event")

            with col3:
                # Expand button
                if st.button("Details", key=f"detail_{event['event_id']}"):
                    _show_event_details(event)

        st.markdown("---")


def _show_event_details(event: pd.Series | dict) -> None:
    """Show event details in an expander."""
    with st.expander(f"Details: {event['symbol']} - {event['event_type']}", expanded=True):
        d1, d2 = st.columns(2)

        with d1:
            st.write(f"**Symbol**: {event['symbol']}")
            st.write(f"**Event Type**: {event['event_type']}")
            st.write(f"**Event Date**: {event['event_date']}")
            st.write(f"**Significance**: {event['significance']}/5")
            st.write(f"**Categorization**: {event.get('categorization_method', 'N/A')}")

        with d2:
            st.write(f"**Description**: {event.get('description', 'N/A')}")
            if event.get("raw_announcement_text"):
                st.write(f"**Announcement**: {event['raw_announcement_text'][:500]}...")

        # Price impact
        if pd.notna(event.get("price_chg_1d")) or pd.notna(event.get("price_chg_5d")) or pd.notna(event.get("price_chg_20d")):
            st.write("**Price Impact**")
            render_info("events_price_impact")
            p1, p2, p3 = st.columns(3)
            if pd.notna(event.get("price_chg_1d")):
                chg = float(event["price_chg_1d"])
                color = "green" if chg >= 0 else "red"
                p1.markdown(f"<span style='color: {color};'>1-day: {chg:+.1f}%</span>", unsafe_allow_html=True)
            if pd.notna(event.get("price_chg_5d")):
                chg = float(event["price_chg_5d"])
                color = "green" if chg >= 0 else "red"
                p2.markdown(f"<span style='color: {color};'>5-day: {chg:+.1f}%</span>", unsafe_allow_html=True)
            if pd.notna(event.get("price_chg_20d")):
                chg = float(event["price_chg_20d"])
                color = "green" if chg >= 0 else "red"
                p3.markdown(f"<span style='color: {color};'>20-day: {chg:+.1f}%</span>", unsafe_allow_html=True)

        if event.get("follow_up_required"):
            st.warning("⚠️ Follow-up required")


def _get_significance_color(significance: int) -> str:
    """Get background color for significance badge."""
    colors = {
        1: "#6b7280",  # Grey
        2: "#f59e0b",  # Amber
        3: "#3b82f6",  # Blue
        4: "#ef4444",  # Red
        5: "#dc2626",  # Dark Red
    }
    return colors.get(significance, "#6b7280")


# ============================================================
# View 7: Watchlist Builder
# ============================================================

def render_watchlist_builder() -> None:
    """View 7: Watchlist Builder.

    Auto-generates a curated, rules-based watchlist of actionable Nifty 50
    candidates, classified by signal type, with a transparent composite
    scoring system.
    """
    st.subheader("View 7 · Watchlist Builder")
    render_info("watchlist_builder")

    # Load suggestions
    suggestions = load_category_suggestions()

    if not suggestions:
        st.info("No watchlist candidates available yet. Run signal computation first.")
        return

    # Tab navigation (Row 1)
    tabs = st.tabs([
        "Contrarian Opportunities",
        "Momentum Leaders",
        "Event-Driven Candidates",
        "Volume-Confirmed Movers",
    ])

    # Per-tab info keys (positional, mirrors the tabs list above).
    _category_info_keys = (
        "watchlist_contrarian",
        "watchlist_momentum",
        "watchlist_event",
        "watchlist_volume",
    )

    # Display each category (Row 2)
    for i, (tab, suggestion) in enumerate(zip(tabs, suggestions)):
        with tab:
            category_name = suggestion.get("category_name", f"Category {i+1}")
            items = suggestion.get("items", [])

            st.markdown(f"#### {category_name}")
            st.caption(f"Showing {len(items)} candidates")
            if i < len(_category_info_keys):
                render_info(_category_info_keys[i])

            if not items:
                st.info("No candidates match this category's criteria.")
                continue

            # Display items table
            _render_watchlist_items(items, category_name)


def _render_watchlist_items(items: list[dict], category_name: str) -> None:
    """Render watchlist items in a table."""
    if not items:
        return

    # Prepare display dataframe
    display_data = []
    for item in items:
        display_data.append({
            "Symbol": item.get("symbol", ""),
            "Company": item.get("company_name", ""),
            "Sector": item.get("sector", ""),
            "Signal": item.get("signal_category", ""),
            "ISS": item.get("iss_score", 0),
            "1D %": item.get("return_1d", 0),
            "1M %": item.get("return_1m", 0),
            "Vol Ratio": item.get("vol_ratio_1d", 0),
            "DD %": item.get("drawdown_from_52w_high_pct", 0),
            "Key Reason": item.get("key_reason", ""),
        })

    df = pd.DataFrame(display_data)

    # Color formatting helper
    def format_cell(val, col: str):
        if col == "Signal":
            colors = {"ACC": "#10b981", "MOM": "#3b82f6", "EVT": "#f59e0b"}
            return f"color: {colors.get(val, '#000')}; font-weight: bold;"
        elif col == "1D %":
            return "color: #10b981;" if val > 0 else "color: #ef4444;" if val < 0 else "color: #6b7280;"
        elif col == "ISS":
            if val >= 80:
                return "background-color: #10b981; color: white;"
            elif val >= 60:
                return "background-color: #3b82f6; color: white;"
            elif val >= 40:
                return "background-color: #f59e0b; color: white;"
            return "background-color: #ef4444; color: white;"
        return ""

    # Display table with formatting
    st.dataframe(
        df,
        use_container_width=True,
        height=min(500, 40 + len(df) * 36),
        hide_index=True,
        column_config={
            "Symbol": st.column_config.TextColumn("Symbol", width="medium"),
            "Company": st.column_config.TextColumn("Company", width="large"),
            "Sector": st.column_config.TextColumn("Sector", width="medium"),
            "Signal": st.column_config.TextColumn("Signal", width="small", help=tooltip("signal_category")),
            "ISS": st.column_config.NumberColumn("ISS", format="%.0f", help=tooltip("iss_score")),
            "1D %": st.column_config.NumberColumn("1D %", format="%.1f%%", help=tooltip("return_1d")),
            "1M %": st.column_config.NumberColumn("1M %", format="%.1f%%", help=tooltip("return_1m")),
            "Vol Ratio": st.column_config.NumberColumn("Vol Ratio", format="%.1fx", help=tooltip("vol_ratio_1d")),
            "DD %": st.column_config.NumberColumn("DD %", format="%.1f%%", help=tooltip("drawdown_pct")),
        },
    )
    st.caption(
        "ISS badge tiers: 0–39 red · 40–59 amber · 60–79 green · 80–100 deep green."
    )
    render_info("watchlist_iss_badge")


# ============================================================
# Utility Functions
# ============================================================

def get_watchlist_stats() -> dict[str, Any]:
    """Get overall watchlist statistics."""
    try:
        response = requests.get(f"{API_URL}/watchlist", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {"total_count": 0, "pinned_count": 0}
