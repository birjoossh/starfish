"""Purpose string parser for NSE corporate action descriptions.

Extracts structured data (type, amount, ratio) from free-text NSE purpose strings.

Examples:
    "DIVIDEND - RS 12.50 PER SHARE"           → dividend, 12.5
    "BONUS 1:2"                                → bonus, ratio 1:2
    "STOCK SPLIT FROM RS 10 TO RS 2"          → split, ratio 1:5
    "RIGHTS 3:7 @ RS 450"                     → rights
    "BUY BACK OF SHARES"                       → buyback
    "INTERIM DIVIDEND - RS 5 PER SHARE"       → dividend, 5.0
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Event types ─────────────────────────────────────────────────────────────
EVENT_DIVIDEND = "DIVIDEND"
EVENT_BONUS    = "BONUS"
EVENT_SPLIT    = "SPLIT"
EVENT_RIGHTS   = "RIGHTS"
EVENT_BUYBACK  = "BUYBACK"
EVENT_AGM      = "AGM"
EVENT_EGM      = "EGM"
EVENT_RESULTS  = "RESULTS"
EVENT_OTHER    = "OTHER"


@dataclass
class ParsedPurpose:
    event_type: str
    amount: Optional[float] = None      # dividend amount in ₹
    ratio_num: Optional[int] = None     # bonus/split/rights numerator
    ratio_den: Optional[int] = None     # bonus/split/rights denominator
    raw_text: str = ""


# ─── Regex patterns ─────────────────────────────────────────────────────────
_DIVIDEND_RE = re.compile(
    r"(?:INTERIM\s+|FINAL\s+|SPECIAL\s+)?DIVIDEND"
    r"(?:.*?RS\.?\s*(\d+(?:\.\d+)?))?",
    re.IGNORECASE,
)
_BONUS_RE = re.compile(
    r"BONUS\s+(\d+)\s*[:/]\s*(\d+)",
    re.IGNORECASE,
)
_SPLIT_RE = re.compile(
    r"SPLIT|SUB.?DIVISION",
    re.IGNORECASE,
)
_SPLIT_RATIO_RE = re.compile(
    r"RS\.?\s*(\d+(?:\.\d+)?)\s+TO\s+RS\.?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_RIGHTS_RE = re.compile(
    r"RIGHTS\s+(\d+)\s*[:/]\s*(\d+)",
    re.IGNORECASE,
)
_BUYBACK_RE = re.compile(r"BUY\s*BACK|BUYBACK", re.IGNORECASE)
_AGM_RE     = re.compile(r"\bAGM\b",             re.IGNORECASE)
_EGM_RE     = re.compile(r"\bEGM\b",             re.IGNORECASE)
_RESULTS_RE = re.compile(r"\bRESULTS?\b",        re.IGNORECASE)


def parse_purpose(purpose: str) -> ParsedPurpose:
    """Parse a free-text NSE corporate action purpose string.

    Args:
        purpose: Raw NSE purpose string e.g. "DIVIDEND - RS 12.50 PER SHARE"

    Returns:
        ParsedPurpose with event_type, optional amount, optional ratio.
    """
    text = purpose.strip().upper()

    # ── Dividend ──────────────────────────────────────────────────────────
    m = _DIVIDEND_RE.search(text)
    if m:
        amount = float(m.group(1)) if m.group(1) else None
        return ParsedPurpose(EVENT_DIVIDEND, amount=amount, raw_text=purpose)

    # ── Bonus ─────────────────────────────────────────────────────────────
    m = _BONUS_RE.search(text)
    if m:
        return ParsedPurpose(
            EVENT_BONUS,
            ratio_num=int(m.group(1)),
            ratio_den=int(m.group(2)),
            raw_text=purpose,
        )

    # ── Stock split (with ratio from face value change) ───────────────────
    if _SPLIT_RE.search(text):
        ratio_m = _SPLIT_RATIO_RE.search(text)
        if ratio_m:
            old_fv = float(ratio_m.group(1))
            new_fv = float(ratio_m.group(2))
            if new_fv > 0:
                # e.g. RS 10 TO RS 2 → ratio 5:1 (multiplier)
                ratio_num = int(old_fv / new_fv)
                return ParsedPurpose(EVENT_SPLIT, ratio_num=ratio_num, ratio_den=1, raw_text=purpose)
        return ParsedPurpose(EVENT_SPLIT, raw_text=purpose)

    # ── Rights ────────────────────────────────────────────────────────────
    m = _RIGHTS_RE.search(text)
    if m:
        return ParsedPurpose(
            EVENT_RIGHTS,
            ratio_num=int(m.group(1)),
            ratio_den=int(m.group(2)),
            raw_text=purpose,
        )

    # ── Buyback ───────────────────────────────────────────────────────────
    if _BUYBACK_RE.search(text):
        return ParsedPurpose(EVENT_BUYBACK, raw_text=purpose)

    # ── AGM / EGM ─────────────────────────────────────────────────────────
    if _AGM_RE.search(text):
        return ParsedPurpose(EVENT_AGM, raw_text=purpose)
    if _EGM_RE.search(text):
        return ParsedPurpose(EVENT_EGM, raw_text=purpose)

    # ── Results announcement ──────────────────────────────────────────────
    if _RESULTS_RE.search(text):
        return ParsedPurpose(EVENT_RESULTS, raw_text=purpose)

    return ParsedPurpose(EVENT_OTHER, raw_text=purpose)


def event_significance(parsed: ParsedPurpose) -> int:
    """Score the significance of a corporate event on a 1–5 scale.

    Used for EVT signal classification — events with significance >= 3
    contribute to Factor 5 and can trigger the EVT signal category.

    Scale:
        5 — Bonus, split, buyback (structural/major)
        4 — Dividend > ₹10 or rights issue
        3 — Dividend ₹1–₹10, results
        2 — Dividend < ₹1, AGM/EGM
        1 — Other / unclassified
    """
    t = parsed.event_type

    if t in (EVENT_BONUS, EVENT_SPLIT, EVENT_BUYBACK):
        return 5

    if t == EVENT_RIGHTS:
        return 4

    if t == EVENT_DIVIDEND:
        if parsed.amount is None:
            return 3
        if parsed.amount >= 10:
            return 4
        if parsed.amount >= 1:
            return 3
        return 2

    if t == EVENT_RESULTS:
        return 3

    if t in (EVENT_AGM, EVENT_EGM):
        return 2

    return 1
