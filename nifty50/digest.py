"""Morning digest — terminal markdown summary of today's signals.

Prints a structured summary to stdout:
- Top gainers / losers
- Volume spikes
- Stocks near 52-week highs / lows
- Watchlist alerts

Usage:
    python -m nifty50.digest
    python -m nifty50.digest --date 2024-01-17
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

import pandas as pd
from sqlalchemy import text

from config.database import read_sql_df
from dashboard.watchlist import load_watchlist

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_latest_signals(trade_date: date | None = None) -> pd.DataFrame:
    """Load signals for the given date (or latest available)."""
    if trade_date:
        df = read_sql_df("""
            SELECT s.*, d.company_name, d.sector, p.close
            FROM mart_stock_signals s
            JOIN dim_stock d ON s.symbol = d.symbol
            LEFT JOIN fact_eod_price p ON s.symbol = p.symbol AND s.calc_date = p.trade_date
            WHERE s.calc_date = :trade_date
            ORDER BY s.symbol
        """, params={"trade_date": trade_date})
    else:
        df = read_sql_df("""
            SELECT s.*, d.company_name, d.sector, p.close
            FROM mart_stock_signals s
            JOIN dim_stock d ON s.symbol = d.symbol
            LEFT JOIN fact_eod_price p ON s.symbol = p.symbol AND s.calc_date = p.trade_date
            WHERE s.calc_date = (SELECT MAX(calc_date) FROM mart_stock_signals)
            ORDER BY s.symbol
        """)

    return df


def generate_digest(trade_date: date | None = None) -> str:
    """Generate a terminal-friendly digest and return as string.

    Also prints to stdout.
    """
    df = get_latest_signals(trade_date)
    watchlist = load_watchlist()

    if df.empty:
        msg = "No signal data available. Run signal computation first."
        print(msg)
        return msg

    calc_date = df["calc_date"].iloc[0]
    lines = []
    lines.append(f"# Nifty 50 Daily Digest — {calc_date}")
    lines.append("")

    # ---- Top Gainers ----
    top_gainers = df.nlargest(5, "return_1d")
    lines.append("## Top Gainers (1D)")
    for _, row in top_gainers.iterrows():
        flag = " ★" if row["symbol"] in watchlist else ""
        close_str = f"{row['close']:.2f}" if pd.notna(row.get("close")) else "-"
        lines.append(
            f"  {row['symbol']:12s} {row['return_1d']*100:+.2f}%  "
            f"close={close_str:>10s}  "
            f"vol_ratio={row['vol_ratio_1d']:.1f}x{flag}"
        )
    lines.append("")

    # ---- Top Losers ----
    top_losers = df.nsmallest(5, "return_1d")
    lines.append("## Top Losers (1D)")
    for _, row in top_losers.iterrows():
        flag = " ★" if row["symbol"] in watchlist else ""
        lines.append(
            f"  {row['symbol']:12s} {row['return_1d']*100:+.2f}%  "
            f"vol_ratio={row['vol_ratio_1d']:.1f}x{flag}"
        )
    lines.append("")

    # ---- Volume Spikes ----
    volume_spikes = df[df["vol_ratio_1d"] > 1.5].nlargest(5, "vol_ratio_1d")
    if not volume_spikes.empty:
        lines.append("## Volume Spikes (> 1.5x avg)")
        for _, row in volume_spikes.iterrows():
            flag = " ★" if row["symbol"] in watchlist else ""
            lines.append(
                f"  {row['symbol']:12s} {row['vol_ratio_1d']:.2f}x  "
                f"return={row['return_1d']*100:+.2f}%  "
                f"trend={row['volume_trend_3m']}{flag}"
            )
        lines.append("")

    # ---- Near 52-week High ----
    near_high = df.nsmallest(5, "drawdown_from_52w_high_pct")
    lines.append("## Near 52-Week High")
    for _, row in near_high.iterrows():
        flag = " ★" if row["symbol"] in watchlist else ""
        lines.append(
            f"  {row['symbol']:12s} {row['drawdown_from_52w_high_pct']:.2f}% from high{flag}"
        )
    lines.append("")

    # ---- Near 52-week Low ----
    near_low = df.nlargest(5, "distance_from_52w_low_pct")
    lines.append("## Near 52-Week Low")
    for _, row in near_low.iterrows():
        flag = " ★" if row["symbol"] in watchlist else ""
        lines.append(
            f"  {row['symbol']:12s} {row['distance_from_52w_low_pct']:.2f}% from low{flag}"
        )
    lines.append("")

    # ---- Watchlist Summary ----
    if watchlist:
        watchlist_df = df[df["symbol"].isin(watchlist)]
        lines.append(f"## Watchlist ({len(watchlist)} symbols)")
        for _, row in watchlist_df.iterrows():
            lines.append(
                f"  {row['symbol']:12s} "
                f"ret_1d={row['return_1d']*100:+.2f}%  "
                f"ret_1m={row['return_1m']*100:+.2f}%  "
                f"signal={row['signal_category']}"
            )
        lines.append("")

    # ---- Momentum Stocks ----
    momentum = df[df["momentum_flag"] == True]
    if not momentum.empty:
        lines.append("## Momentum (> 5% 1M or > 10% 3M)")
        for _, row in momentum.iterrows():
            flag = " ★" if row["symbol"] in watchlist else ""
            lines.append(
                f"  {row['symbol']:12s} "
                f"ret_1m={row['return_1m']*100:+.2f}%  "
                f"ret_3m={row['return_3m']*100:+.2f}%{flag}"
            )
        lines.append("")

    output = "\n".join(lines)
    print(output)
    return output


def main():
    parser = argparse.ArgumentParser(description="Nifty 50 morning digest")
    parser.add_argument("--date", type=str, help="Date for digest (YYYY-MM-DD)")
    args = parser.parse_args()

    trade_date = date.fromisoformat(args.date) if args.date else None
    generate_digest(trade_date)


if __name__ == "__main__":
    main()
