"""Keyword classifier for NSE corporate announcements.

Maps free-text announcement / subject / body strings into the
`fact_corporate_event.event_type` enum and a 1–5 significance score, as
specified in §M3.4 of the dashboard spec.

Spec event types (mirrors the DB CHECK constraint):

    Earnings          — quarterly results, profit warnings
    Leadership_Change — CEO/MD/CFO resignation, appointment
    M&A               — merger, acquisition, demerger, takeover
    Large_Order       — order win, large contract
    Pledging_Change   — promoter pledge / release
    Rating_Change     — credit-rating action by ICRA/CRISIL/S&P/Moody's
    Regulatory        — SEBI / RBI / court actions, notices
    Other             — fallback

The classifier is purely lexical (no ML); spec §M3.4 reserves NLP for Phase 6.
Each rule scans the lowercased input for a phrase from a keyword list.
First match wins, in the order declared by ``CATEGORIES`` below — that
ordering is signal-priority (a "CEO resignation" string contains both
"resignation" → Leadership and "ceo" → Leadership, but if it also
mentioned "rating downgrade" we'd want Rating_Change to win; bound by the
ordering).

Public surface:

* :func:`classify_event` — single-row classification.
* :func:`event_significance_for` — significance score derived from
  ``(event_type, raw_text)``.
* :func:`is_negative_event` — boolean negative-event flag.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ─── Event types (must mirror the DB CHECK constraint) ───────────────────────

EVENT_EARNINGS    = "Earnings"
EVENT_LEADERSHIP  = "Leadership_Change"
EVENT_MA          = "M&A"
EVENT_LARGE_ORDER = "Large_Order"
EVENT_PLEDGING    = "Pledging_Change"
EVENT_RATING      = "Rating_Change"
EVENT_REGULATORY  = "Regulatory"
EVENT_OTHER       = "Other"


# ─── Keyword catalogues (kept inline; spec calls for a YAML in Phase 6) ──────

_KEYWORDS = {
    EVENT_RATING: [
        # rating action verbs
        "credit rating", "rating action", "rating change",
        "rating downgrade", "rating upgrade", "rating affirmed",
        "credit watch", "creditwatch", "outlook revised",
        "outlook revision", "outlook revised to negative",
        "negative watch", "positive watch",
        # rating agencies
        "icra", "crisil", "care ratings", "moody", "s&p global", "fitch",
        "india ratings",
    ],
    EVENT_PLEDGING: [
        "pledge", "pledging", "pledged shares", "release of pledge",
        "encumbrance", "invocation of pledge",
    ],
    EVENT_LEADERSHIP: [
        # role + action keywords. Role alone is too generic; pair with an
        # action verb in the matcher below to avoid false positives like
        # "CFO addresses analyst day".
    ],
    EVENT_MA: [
        "merger", "demerger", "amalgamation", "acquisition",
        "scheme of arrangement", "takeover", "open offer",
        "joint venture", "slump sale",
    ],
    EVENT_LARGE_ORDER: [
        "order win", "order received", "letter of award",
        "loa from", "contract win", "contract awarded",
        "bagged order", "large order", "purchase order",
    ],
    EVENT_REGULATORY: [
        "sebi", "rbi action", "enforcement", "show cause notice",
        "scn from", "show-cause", "tribunal order",
        "supreme court", "high court order", "nclt",
        "penalty imposed", "adjudication order", "settlement order",
    ],
    EVENT_EARNINGS: [
        "quarterly results", "q1 result", "q2 result", "q3 result",
        "q4 result", "fy result", "earnings release",
        "audited financial results", "unaudited financial results",
        "board meeting to consider results",
        "profit warning", "profit and loss", "revenue guidance",
        "eps revision",
    ],
}


# Leadership rule: role keyword (CEO/MD/CFO/Director) + action verb
# (resign / step down / appoint / quit / departure). This avoids the
# "CFO speaks at conference" false-positive.
_LEADERSHIP_ROLE_RE = re.compile(
    r"\b(ceo|md|managing director|cfo|coo|cto|whole[- ]time director|"
    r"company secretary|chairman|chairperson|chief executive|chief financial)\b",
    re.IGNORECASE,
)
_LEADERSHIP_ACTION_RE = re.compile(
    r"\b(resign\w*|stepping down|step down|appointed|appointment|"
    r"cessation|quit|removal|removed|departure|"
    r"reappoint\w*|re-appoint\w*)\b",
    re.IGNORECASE,
)


# Category priority — first hit wins. Rating + Regulatory + Pledging ahead
# of Earnings because announcements often bundle rating actions inside a
# results-day filing.
CATEGORIES = (
    EVENT_RATING,
    EVENT_REGULATORY,
    EVENT_PLEDGING,
    EVENT_LEADERSHIP,
    EVENT_MA,
    EVENT_LARGE_ORDER,
    EVENT_EARNINGS,
)


# ─── Significance heuristics (spec §M3.4) ────────────────────────────────────

_NEGATIVE_RATING_RE = re.compile(
    r"\b(downgrade|negative watch|outlook revised to negative|"
    r"creditwatch negative|negative outlook|rating cut)\b",
    re.IGNORECASE,
)
_NEGATIVE_LEADERSHIP_RE = re.compile(
    r"\b(resign\w*|stepping down|quit|removal|abrupt)\b",
    re.IGNORECASE,
)
_NEGATIVE_REGULATORY_RE = re.compile(
    r"\b(enforcement|show cause|penalty|adjudication|suspended|"
    r"contravention|violation)\b",
    re.IGNORECASE,
)
_BIG_DEAL_RE = re.compile(
    r"\b(acqui[sz]ition|merger|demerger|takeover|open offer)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClassifiedEvent:
    """Output of :func:`classify_event`."""

    event_type: str
    significance: int
    is_negative: bool


def _contains_any(haystack: str, needles: list[str]) -> bool:
    hay = haystack.lower()
    return any(needle.lower() in hay for needle in needles)


def _detect_type(text: str) -> str:
    """Return the first matching ``event_type`` per the CATEGORIES order."""
    for cat in CATEGORIES:
        if cat == EVENT_LEADERSHIP:
            if _LEADERSHIP_ROLE_RE.search(text) and _LEADERSHIP_ACTION_RE.search(text):
                return EVENT_LEADERSHIP
            continue
        if _contains_any(text, _KEYWORDS.get(cat, [])):
            return cat
    return EVENT_OTHER


def _detect_significance(event_type: str, text: str) -> int:
    """Map (event_type, raw_text) → 1..5 significance.

    Uses the heuristics from spec §M3.4. When the raw text doesn't carry a
    strong signal (e.g. "Routine board meeting notice") this drops to 2.
    """
    lowered = text.lower()

    if event_type == EVENT_RATING:
        if _NEGATIVE_RATING_RE.search(lowered):
            return 4
        if "upgrade" in lowered or "positive watch" in lowered:
            return 3
        if "outlook" in lowered:
            return 3
        return 2

    if event_type == EVENT_REGULATORY:
        if _NEGATIVE_REGULATORY_RE.search(lowered):
            return 5
        if "court" in lowered or "tribunal" in lowered or "nclt" in lowered:
            return 4
        return 2

    if event_type == EVENT_PLEDGING:
        if "release" in lowered or "invocation" in lowered:
            return 3
        return 4  # default pledge disclosure — caller can downgrade if ratio is tiny

    if event_type == EVENT_LEADERSHIP:
        if re.search(r"\b(ceo|md|managing director|chairman|chairperson)\b", lowered):
            if _NEGATIVE_LEADERSHIP_RE.search(lowered):
                return 5
            return 3
        if re.search(r"\b(cfo|coo|cto)\b", lowered):
            return 3
        return 2

    if event_type == EVENT_MA:
        if _BIG_DEAL_RE.search(lowered):
            return 5 if any(k in lowered for k in ("acquisition", "merger", "demerger")) else 4
        return 3

    if event_type == EVENT_LARGE_ORDER:
        if re.search(r"\b(large|mega|substantial)\b", lowered):
            return 4
        return 3

    if event_type == EVENT_EARNINGS:
        if re.search(r"\b(beat|miss|surprise|profit warning|extraordinary)\b", lowered):
            return 4
        if "guidance" in lowered:
            return 3
        return 2  # routine quarterly results

    # EVENT_OTHER
    if "agm" in lowered or "egm" in lowered:
        return 1
    return 1


def is_negative_event(event_type: str, text: str) -> bool:
    """Negative-event predicate per spec §M3.4."""
    lowered = text.lower()
    if event_type == EVENT_RATING and _NEGATIVE_RATING_RE.search(lowered):
        return True
    if event_type == EVENT_REGULATORY and _NEGATIVE_REGULATORY_RE.search(lowered):
        return True
    if event_type == EVENT_LEADERSHIP and _NEGATIVE_LEADERSHIP_RE.search(lowered):
        return True
    if event_type == EVENT_PLEDGING and "pledge" in lowered and "release" not in lowered:
        return True
    if event_type == EVENT_EARNINGS and re.search(r"\b(miss|profit warning|warning|loss)\b", lowered):
        return True
    return False


def classify_event(text: Optional[str]) -> ClassifiedEvent:
    """Classify a free-text NSE announcement.

    Args:
        text: Concatenation of subject + body / category + description.
            ``None`` / empty falls back to ``EVENT_OTHER`` at significance 1.

    Returns:
        :class:`ClassifiedEvent` with type, 1–5 significance, and the
        negative-event flag.
    """
    if not text or not text.strip():
        return ClassifiedEvent(EVENT_OTHER, 1, False)

    event_type = _detect_type(text)
    sig = _detect_significance(event_type, text)
    neg = is_negative_event(event_type, text)
    return ClassifiedEvent(event_type, sig, neg)


def event_significance_for(event_type: str, text: str) -> int:
    """Public wrapper around :func:`_detect_significance`."""
    return _detect_significance(event_type, text)
