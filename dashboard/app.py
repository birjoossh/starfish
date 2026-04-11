"""Nifty 50 Dashboard — Terminal-Inspired Single Page Layout.

Dense, info-centric UI adhering strictly to DESIGN.md.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import requests
import plotly.express as px

from config.database import read_sql_df
from dashboard.watchlist import load_watchlist

API_URL = "http://localhost:8000"

@st.cache_data(ttl=60)
def get_available_dates() -> list:
    """Get dates with signal data."""
    df = read_sql_df("SELECT DISTINCT calc_date FROM mart_stock_signals ORDER BY calc_date DESC")
    return df["calc_date"].tolist() if not df.empty else []

def get_market_data(selected_date: str):
    try:
        resp = requests.get(f"{API_URL}/market-overview?calc_date={selected_date}", timeout=5)
        return resp.json() if resp.status_code == 200 else {}
    except Exception:
         return {}
         
def get_movers_data(selected_date: str):
    try:
        resp = requests.get(f"{API_URL}/movers?calc_date={selected_date}", timeout=5)
        return resp.json() if resp.status_code == 200 else {}
    except Exception:
         return {}

@st.cache_data(ttl=60)
def load_screener_signals(calc_date: str) -> pd.DataFrame:
    df = read_sql_df("""
        SELECT s.calc_date, s.symbol, d.company_name, d.sector,
               p.close, s.return_1d, s.return_1m, s.return_3m, s.return_1y,
               s.vol_ratio_1d, s.vol_ratio_5d, s.vol_ratio_20d,
               s.avg_volume_20d, s.volume_trend_3m,
               s.drawdown_from_52w_high_pct, s.distance_from_52w_low_pct,
               s.signal_category, s.momentum_flag, s.accumulation_flag,
               s.iss_score
        FROM mart_stock_signals s
        JOIN dim_stock d ON s.symbol = d.symbol
        LEFT JOIN fact_eod_price p ON s.symbol = p.symbol AND s.calc_date = p.trade_date
        WHERE s.calc_date = :calc_date
        ORDER BY s.symbol
    """, params={"calc_date": calc_date})
    return df

def main():
    st.set_page_config(
        page_title="Nifty 50 Terminal",
        page_icon="terminal",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    
    st.markdown("""
        <style>
            /* Force metric values to wrap dynamically on small screens and decrease font to avoid ellipsis */
            div[data-testid="stMetricValue"] > div {
                white-space: normal !important; 
                word-wrap: break-word !important; 
                text-overflow: unset !important;
                overflow: visible !important;
                font-size: 1.5rem !important;
            }
            div[data-testid="stMetricLabel"] > div {
                white-space: normal !important;
                overflow: visible !important;
                font-size: 0.95rem !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    dates = get_available_dates()
    if not dates:
        st.error("No signal data fully ingested yet.")
        return
        
    import base64, os
    def get_base64_of_bin_file(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()

    # Render the full SVG logo as a responsive banner (width proportional to screen)
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "starfish_logo.svg")
    if not os.path.exists(logo_path):
        logo_path = "starfish_logo.svg"

    try:
        svg_b64 = get_base64_of_bin_file(logo_path)
        st.markdown(
            f'<img src="data:image/svg+xml;base64,{svg_b64}" '
            f'style="width:55%; max-width:600px; min-width:260px; display:block; margin-bottom:4px;">',
            unsafe_allow_html=True
        )
    except:
        st.markdown("## 📈 Starfish · Nifty 50 Intelligence")

    # --- Date selector + Morning Digest row ---
    t1, t2 = st.columns([2, 5])
    with t1:
        selected_date = st.selectbox("Date", dates, index=0, label_visibility="collapsed")
    with t2:
        st.caption("☀️ **Morning Digest** — Top 3 by ISS Score")
        signals_df  = load_screener_signals(str(selected_date))
        if not signals_df.empty:
            d_cols = st.columns(3)
            digest = signals_df.nlargest(3, 'iss_score')
            for i, (_, row) in enumerate(digest.iterrows()):
                if i < 3:
                    hover_text = (
                        f"1D Ret: {row['return_1d']*100:+.2f}%  |  "
                        f"Vol: {row['vol_ratio_1d']:.1f}x  |  "
                        f"Signal: {row['signal_category']}  |  "
                        f"{row['drawdown_from_52w_high_pct']:.1f}% from 52W High"
                    )
                    d_cols[i].markdown(
                        f"**{row['symbol']}**<br>"
                        f"<span style='font-size: 0.85em; color: #4ADE80;'>ISS {row['iss_score']:.0f}</span>"
                        f"<span style='font-size: 0.85em; color: gray;'>&nbsp;|&nbsp;{row['return_1d']*100:+.1f}%</span>",
                        unsafe_allow_html=True,
                        help=hover_text
                    )

    st.markdown("---")

    # Fetch Unified Data
    market_data = get_market_data(str(selected_date))
    movers_data = get_movers_data(str(selected_date))
    signals_df  = load_screener_signals(str(selected_date))
    watchlist = load_watchlist()

    # Data extraction
    sector_data = pd.DataFrame(market_data.get("sector_breadth", []))
    components = pd.DataFrame(market_data.get("components", []))
    gainers_data = pd.DataFrame(movers_data.get("gainers", []))
    losers_data = pd.DataFrame(movers_data.get("losers", []))

    # Helper function for text filtering
    def filter_dataframe(df: pd.DataFrame, query: str) -> pd.DataFrame:
        if not query or df.empty: return df
        mask = df.astype(str).apply(lambda col: col.str.contains(query, case=False, na=False))
        return df[mask.any(axis=1)]

    # --- Header: Global Metrics ---
    if not sector_data.empty and not components.empty:
        adv_total = sector_data["advancing"].sum()
        dec_total = sector_data["declining"].sum()
        avg_1d = components["return_1d"].mean() * 100
        
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Overall Breadth", f"{int(adv_total)} Adv", f"{-int(dec_total)} Dec")
        m2.metric("Average ISS", f"{components['iss_score'].mean():.0f}/100")
        m3.metric("Avg 1D Return", f"{avg_1d:+.2f}%")
        top_sector = sector_data.loc[sector_data["avg_return_1d"].idxmax()]["sector"] if not sector_data.empty else "N/A"
        m4.metric("Top Sector", top_sector)
        m5.metric("Market Structure", "Mean Reverting")

    # --- Visualizations Expander (Now immediately below summary) ---
    with st.expander("📊 Nifty 50 Sector Rotation & Breadth Heatmap", expanded=True):
        vc1, vc2 = st.columns([1,2])
        with vc1:
            if 'adv_total' in locals():
                pie_df = pd.DataFrame({
                    "Status": ["Advancing", "Declining"],
                    "Count": [adv_total, dec_total]
                })
                fig = px.pie(pie_df, values='Count', names='Status', hole=.4, color='Status',
                             color_discrete_map={"Advancing": "#00ff00", "Declining": "#ff0000"})
                fig.update_layout(height=400, margin=dict(l=20, r=20, t=30, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
                
        with vc2:
             if not components.empty:
                 components["return_px"] = components["return_1d"] * 100
                 fig2 = px.treemap(components, 
                                   path=[px.Constant("Nifty 50"), 'sector', 'symbol'], 
                                   values='iss_score',
                                   color='return_px',
                                   color_continuous_scale='RdYlGn',
                                   color_continuous_midpoint=0)
                 fig2.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)")
                 st.plotly_chart(fig2, use_container_width=True)

    # --- Row 1: Sector Breadth & Watchlist ---
    st.markdown("---")
    
    # Init session states for filters to allow programmatic tracking
    for k in ["sec_search", "watch_search", "gain_search", "lose_search", "scr_search"]:
        if k not in st.session_state: st.session_state[k] = ""

    c1, c2 = st.columns(2)
    
    with c1:
        st_c1_hdr, st_c1_flt = st.columns([5, 4])
        st_c1_hdr.markdown("### Sector Aggregation")
        st.session_state.sec_search = st_c1_flt.text_input("Filter...", key="ti_sec", value=st.session_state.sec_search, placeholder="Filter sector...", label_visibility="collapsed")
        
        if not sector_data.empty:
            sector_data = sector_data.sort_values(by="avg_return_1d", ascending=False)
            filtered_sector = filter_dataframe(sector_data, st.session_state.sec_search)
            st.dataframe(
                filtered_sector,
                use_container_width=True,
                height=260, # Lock height
                column_config={
                    "sector": st.column_config.TextColumn("Sector", width="medium"),
                    "avg_return_1d": st.column_config.NumberColumn(format="%+.2f%%"),
                    "avg_return_1m": st.column_config.NumberColumn(format="%+.2f%%"),
                    "avg_iss": st.column_config.NumberColumn(format="%.0f"),
                }
            )

    with c2:
        st_c2_hdr, st_c2_flt = st.columns([5, 4])
        st_c2_hdr.markdown("### Watchlist Signals")
        st.session_state.watch_search = st_c2_flt.text_input("Filter...", key="ti_watch", value=st.session_state.watch_search, placeholder="Filter specific tracker...", label_visibility="collapsed")
        
        if watchlist and not signals_df.empty:
            watch_df = signals_df[signals_df["symbol"].isin(watchlist)][[
                "symbol", "close", "return_1d", "vol_ratio_1d", "iss_score", "signal_category"
            ]].copy()
            watch_df.columns = ["Symbol", "Close", "Ret 1D", "Vol", "ISS", "Signal"]
            filtered_watch = filter_dataframe(watch_df, st.session_state.watch_search)
            st.dataframe(
                filtered_watch,
                use_container_width=True,
                height=260,
                column_config={
                    "Symbol": st.column_config.TextColumn("Symbol", width="medium"),
                    "Close": st.column_config.NumberColumn(format="₹%.2f"),
                    "Ret 1D": st.column_config.NumberColumn(format="%+.2f%%"),
                    "Vol": st.column_config.NumberColumn(format="%.2fx"),
                    "ISS": st.column_config.NumberColumn(format="%.0f"),
                }
            )
        else:
            st.info("No items in Watchlist")

    # --- Row 2: Volatility Movers ---
    c3, c4 = st.columns(2)
    disp_cols = ["symbol", "sector", "return_1d", "vol_ratio_1d", "iss_score"]
    
    with c3:
        st_c3_hdr, st_c3_flt = st.columns([5, 4])
        st_c3_hdr.markdown("### 🔥 Mover: Gainers")
        st.session_state.gain_search = st_c3_flt.text_input("Filter...", key="ti_gain", value=st.session_state.gain_search, placeholder="Filter by symbol...", label_visibility="collapsed")
        
        if not gainers_data.empty:
            g_disp = gainers_data[disp_cols].copy()
            g_disp.columns = ["Symbol", "Sector", "Ret 1D", "Vol", "ISS"]
            filtered_gain = filter_dataframe(g_disp, st.session_state.gain_search)
            st.dataframe(filtered_gain, use_container_width=True, hide_index=True, column_config={
                "Sector": st.column_config.TextColumn("Sector", width="medium"),
                "Ret 1D": st.column_config.NumberColumn(format="%+.2f%%"),
                "Vol": st.column_config.NumberColumn(format="%.2fx"),
                "ISS": st.column_config.NumberColumn(format="%.0f"),
            })

    with c4:
        st_c4_hdr, st_c4_flt = st.columns([5, 4])
        st_c4_hdr.markdown("### ❄️ Extremes: Losers")
        st.session_state.lose_search = st_c4_flt.text_input("Filter...", key="ti_lose", value=st.session_state.lose_search, placeholder="Filter by symbol...", label_visibility="collapsed")
        
        if not losers_data.empty:
            l_disp = losers_data[disp_cols].copy()
            l_disp.columns = ["Symbol", "Sector", "Ret 1D", "Vol", "ISS"]
            filtered_lose = filter_dataframe(l_disp, st.session_state.lose_search)
            st.dataframe(filtered_lose, use_container_width=True, hide_index=True, column_config={
                "Sector": st.column_config.TextColumn("Sector", width="medium"),
                "Ret 1D": st.column_config.NumberColumn(format="%+.2f%%"),
                "Vol": st.column_config.NumberColumn(format="%.2fx"),
                "ISS": st.column_config.NumberColumn(format="%.0f"),
            })

    # --- Full Master Screener ---
    st.markdown("---")
    st_s_hdr, st_s_flt = st.columns([8, 4])
    st_s_hdr.markdown("### 📋 Primary Scanner Pipeline Data")
    st.session_state.scr_search = st_s_flt.text_input("Filter...", key="ti_scr", value=st.session_state.scr_search, placeholder="Filter table via Sector, Regex, or Symbol...", label_visibility="collapsed")
    
    if not signals_df.empty:
        display_df = signals_df[[
            "symbol", "company_name", "sector", "close",
            "return_1d", "return_1m", "return_3m",
            "vol_ratio_1d", "avg_volume_20d",
            "drawdown_from_52w_high_pct", "distance_from_52w_low_pct",
            "iss_score", "signal_category", "momentum_flag", "accumulation_flag",
        ]].copy()
    
        display_df["momentum_flag"] = display_df["momentum_flag"].apply(lambda x: "MOM" if x else "")
        display_df["accumulation_flag"] = display_df["accumulation_flag"].apply(lambda x: "ACC" if x else "")
        display_df["watch"] = display_df["symbol"].apply(lambda s: "★" if s in watchlist else "")
    
        display_df.columns = [
            "Symbol", "Company", "Sector", "Close",
            "Ret 1D", "Ret 1M", "Ret 3M",
            "Vol", "Avg Vol",
            "% from 52W High", "% from 52W Low",
            "ISS", "Signal", "Momentum", "Accum",
            "Watch",
        ]
        
        filtered_display = filter_dataframe(display_df, st.session_state.scr_search)
    
        st.dataframe(
            filtered_display,
            use_container_width=True,
            height=600,
            column_config={
                "Sector": st.column_config.TextColumn("Sector", width="medium"),
                "Company": st.column_config.TextColumn("Company", width="medium"),
                "Ret 1D": st.column_config.NumberColumn(format="%+.2f%%"),
                "Ret 1M": st.column_config.NumberColumn(format="%+.2f%%"),
                "Ret 3M": st.column_config.NumberColumn(format="%+.2f%%"),
                "Close": st.column_config.NumberColumn(format="₹%.2f"),
                "Vol": st.column_config.NumberColumn(format="%.2fx"),
                "% from 52W High": st.column_config.NumberColumn(format="%.2f%%"),
                "% from 52W Low": st.column_config.NumberColumn(format="%.2f%%"),
                "ISS": st.column_config.NumberColumn(format="%.0f"),
            },
        )

if __name__ == "__main__":
    main()
