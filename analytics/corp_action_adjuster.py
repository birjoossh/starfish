"""Corporate-action price adjustment.

Back-adjusts historical close/prev_close for splits and bonuses so that
returns and 52-week metrics computed across an ex-date are economically
meaningful (i.e. not contaminated by a 5x or 10x mechanical price drop).

Convention: prices on dates *strictly before* `ex_date` are divided by the
cumulative product of all subsequent ex-date factors. Prices on or after
`ex_date` are left unchanged. This produces a back-adjusted series whose
most recent value equals the raw most recent value.

Supported actions (from `fact_corporate_action`):
- Bonus a:b — multiplier = (a+b)/b, sourced from ratio_numerator/denominator.
- Split — multiplier = old_face_value / new_face_value, parsed from
  purpose_text (e.g. "From Rs 2/- Per Share To Re 1/- Per Share").

Dividends, rights and buybacks are intentionally ignored: the spec requires
mechanical adjustment only, and a TERP-style rights adjustment is out of scope.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Iterable

import pandas as pd
from sqlalchemy import text

from config.database import get_engine

logger = logging.getLogger(__name__)


_SPLIT_FROM_TO_RE = re.compile(
    r"from\s+(?:rs\.?|re\.?)\s*([\d.]+).*?to\s+(?:rs\.?|re\.?)\s*([\d.]+)",
    re.IGNORECASE,
)


def _parse_split_factor(purpose_text: str | None) -> float | None:
    """Parse 'From Rs X To Re Y' (case-insensitive) → X/Y.

    Returns None if the text doesn't match or yields a non-positive ratio.
    """
    if not purpose_text:
        return None
    m = _SPLIT_FROM_TO_RE.search(purpose_text)
    if not m:
        return None
    try:
        old_fv = float(m.group(1))
        new_fv = float(m.group(2))
    except ValueError:
        return None
    if old_fv <= 0 or new_fv <= 0 or old_fv == new_fv:
        return None
    return old_fv / new_fv


def _bonus_factor(num: float | None, den: float | None) -> float | None:
    """Bonus a:b → (a+b)/b. Returns None if inputs invalid."""
    if num is None or den is None:
        return None
    try:
        a = float(num)
        b = float(den)
    except (TypeError, ValueError):
        return None
    if b <= 0 or a < 0:
        return None
    return (a + b) / b


def load_corp_actions(symbols: Iterable[str] | None = None) -> pd.DataFrame:
    """Load Bonus/Split actions from fact_corporate_action and resolve a per-row factor.

    Returns DataFrame with columns: symbol, ex_date, factor.
    Multiple actions on the same (symbol, ex_date) are kept as separate rows;
    callers should multiply them together when applying.
    """
    engine = get_engine()
    query = text(
        """
        SELECT symbol, action_type, ex_date,
               ratio_numerator, ratio_denominator, purpose_text
        FROM fact_corporate_action
        WHERE action_type IN ('Bonus', 'Split')
        ORDER BY symbol, ex_date
        """
    )
    df = pd.read_sql_query(query, engine)
    if symbols is not None:
        df = df[df["symbol"].isin(set(symbols))].copy()
    if df.empty:
        return pd.DataFrame(columns=["symbol", "ex_date", "factor"])

    factors: list[float | None] = []
    for _, row in df.iterrows():
        if row["action_type"] == "Bonus":
            factors.append(_bonus_factor(row["ratio_numerator"], row["ratio_denominator"]))
        else:  # Split
            factors.append(_parse_split_factor(row["purpose_text"]))
    df["factor"] = factors

    skipped = df[df["factor"].isna()]
    if not skipped.empty:
        for _, r in skipped.iterrows():
            logger.warning(
                "Skipping unparseable corp action: %s %s %s — %r",
                r["symbol"], r["action_type"], r["ex_date"], r["purpose_text"],
            )
    df = df.dropna(subset=["factor"])
    return df[["symbol", "ex_date", "factor"]].reset_index(drop=True)


def adjust_prices(prices: pd.DataFrame, actions: pd.DataFrame | None = None) -> pd.DataFrame:
    """Back-adjust close and prev_close for splits and bonuses.

    Args:
        prices: DataFrame with at least columns trade_date, symbol, close.
                prev_close is adjusted if present.
        actions: DataFrame with columns symbol, ex_date, factor.
                 If None, loads from DB for the symbols in `prices`.

    Returns:
        Copy of `prices` with `close` (and `prev_close` if present) overwritten
        by adjusted values. Rows for symbols with no actions are returned
        unchanged.
    """
    if prices.empty:
        return prices.copy()

    if actions is None:
        actions = load_corp_actions(prices["symbol"].unique())

    out = prices.copy()
    if actions.empty:
        return out

    actions = actions.copy()
    actions["ex_date"] = pd.to_datetime(actions["ex_date"]).dt.date

    out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.date

    intraday_cols = [c for c in ("open", "high", "low", "close") if c in out.columns]
    has_prev = "prev_close" in out.columns
    affected_symbols = set(actions["symbol"].unique())
    for sym in affected_symbols:
        sym_actions = actions[actions["symbol"] == sym].sort_values("ex_date")
        sym_idx = out.index[out["symbol"] == sym]
        if len(sym_idx) == 0:
            continue
        sym_dates = out.loc[sym_idx, "trade_date"]

        # Intraday OHLC for a row D divides by product of factors with ex_date > D.
        # prev_close represents the previous trading day's close, so it is
        # back-adjusted whenever the previous day was strictly before ex_date,
        # equivalently (trade_date <= ex_date).
        intraday_factor = pd.Series(1.0, index=sym_idx)
        prev_factor = pd.Series(1.0, index=sym_idx)
        for _, a in sym_actions.iterrows():
            ex = a["ex_date"]
            factor = float(a["factor"])
            intraday_factor.loc[sym_idx[sym_dates < ex]] *= factor
            if has_prev:
                prev_factor.loc[sym_idx[sym_dates <= ex]] *= factor

        for col in intraday_cols:
            out.loc[sym_idx, col] = (
                out.loc[sym_idx, col].astype(float) / intraday_factor
            ).round(4)
        if has_prev:
            out.loc[sym_idx, "prev_close"] = (
                out.loc[sym_idx, "prev_close"].astype(float) / prev_factor
            ).round(4)

    return out
