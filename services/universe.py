"""Point-in-time Nifty 50 membership queries.

The dashboard universe is the Nifty 50 *as of a calc_date*, not the current
snapshot. Back-testing, the Trend Workbench multi-year view, and signal
suppression for newly-added names all need to ask: "was X in the index on
2023-06-15?" — that question is answered here.

Backed by ``dim_nifty50_constituent``. A symbol is considered a member on
``as_of_date`` iff there is an active membership interval covering that
date — i.e. some row where ``change_type != 'Deletion'``,
``effective_from <= as_of_date``, and ``effective_to`` is either NULL or
``>= as_of_date``. Same-symbol re-entry after deletion (non-overlapping
intervals) and weight-only Rebalance updates are handled naturally by
this rule.

Two surfaces:

* :func:`is_nifty50_member` — single-symbol check.
* :func:`nifty50_members_as_of` — bulk set of all members on a date,
  cheaper than calling the single-symbol form 50 times.

A pure :func:`membership_covers` helper accepts a sequence of intervals
so the rule can be unit-tested without a database.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.database import get_engine


MembershipInterval = tuple[date, Optional[date], str]


def membership_covers(
    intervals: Iterable[MembershipInterval],
    as_of_date: date,
) -> bool:
    """Pure interval-overlap check.

    Args:
        intervals: Iterable of ``(effective_from, effective_to, change_type)``.
            ``effective_to`` may be ``None`` for currently-active membership.
        as_of_date: Date to check.

    Returns:
        True iff some non-Deletion interval covers ``as_of_date``.
    """
    for eff_from, eff_to, change_type in intervals:
        if change_type == "Deletion":
            continue
        if eff_from > as_of_date:
            continue
        if eff_to is not None and eff_to < as_of_date:
            continue
        return True
    return False


def is_nifty50_member(
    symbol: str,
    as_of_date: date,
    *,
    engine: Optional[Engine] = None,
) -> bool:
    """Was ``symbol`` a Nifty 50 constituent on ``as_of_date``?

    Args:
        symbol: NSE trading symbol.
        as_of_date: Date to check membership for.
        engine: Override SQLAlchemy engine (used in tests). Defaults to
            :func:`config.database.get_engine`.
    """
    engine = engine or get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT effective_from, effective_to, change_type
                  FROM dim_nifty50_constituent
                 WHERE symbol = :symbol
                """
            ),
            {"symbol": symbol},
        ).fetchall()
    return membership_covers(
        ((r[0], r[1], r[2]) for r in rows),
        as_of_date,
    )


def nifty50_members_as_of(
    as_of_date: date,
    *,
    engine: Optional[Engine] = None,
) -> set[str]:
    """Return the set of symbols that were Nifty 50 members on ``as_of_date``.

    Bulk variant — single round-trip versus 50× :func:`is_nifty50_member`.
    """
    engine = engine or get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT symbol
                  FROM dim_nifty50_constituent
                 WHERE change_type != 'Deletion'
                   AND effective_from <= :as_of
                   AND (effective_to IS NULL OR effective_to >= :as_of)
                """
            ),
            {"as_of": as_of_date},
        ).fetchall()
    return {r[0] for r in rows}
