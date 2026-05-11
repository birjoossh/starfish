"""Reusable HTML render primitives for the consolidated Nifty 50 dashboard.

Helpers emit small chunks of HTML that match the locked design tokens defined
in :mod:`dashboard.tokens`. Every section (§01–§08) should consume primitives
from this module rather than inlining HTML, so that visual changes propagate
in one place.

All functions return a string (callers wrap with ``st.markdown(..., unsafe_allow_html=True)``)
or render directly via ``st.markdown`` when the helper is named ``render_*``.
"""
from __future__ import annotations

from html import escape
from typing import Literal, Optional

import streamlit as st


PillKind = Literal["pos", "neg", "warn", "info", "acc", "evt", "mute"]


# ----------------------------- Section header ----------------------------- #


def render_section_header(
    number: str,
    title: str,
    hint: Optional[str] = None,
    *,
    right: Optional[str] = None,
) -> None:
    """Render the editorial section header trio.

    Layout: ``§ NN`` (italic serif accent) · TITLE (small-caps kicker) · 1px
    rule filling remaining space · optional hint on the right.

    Args:
        number: Two-digit section number string, e.g. ``"01"``.
        title: Short section name in title case; rendered as the kicker.
        hint: Optional muted hint on the far right (e.g. ``"always open"``).
        right: Optional **trusted, unescaped** HTML chunk that displaces
            ``hint`` if supplied. Reserved for future controls (sort toggles,
            badges). Callers MUST sanitize any dynamic content themselves;
            the helper does not call :func:`html.escape` on this value so it
            can carry markup. Never pass user-supplied strings here.
    """
    right_chunk = right or (
        f'<span class="kicker tx3">{escape(hint)}</span>' if hint else ""
    )
    st.markdown(
        f"""
<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:10px;">
  <span class="sec-num">§ {escape(number)}</span>
  <span class="kicker">{escape(title)}</span>
  <span class="sec-rule"></span>
  {right_chunk}
</div>
""",
        unsafe_allow_html=True,
    )


# ----------------------------- Pills & tags ------------------------------ #


_PILL_CLASS = {
    "pos": "pill fill-pos pos",
    "neg": "pill fill-neg neg",
    "warn": "pill fill-warn warn",
    "info": "pill fill-info info",
    "acc": "pill fill-acc acc",
    "evt": "pill fill-evt evt",
    "mute": "pill tx2",
}


def pill(label: str, kind: PillKind = "mute") -> str:
    """Return an HTML pill span. Use inside other ``st.markdown`` blocks."""
    cls = _PILL_CLASS.get(kind, _PILL_CLASS["mute"])
    return f'<span class="{cls}">{escape(label)}</span>'


def tag(label: str, *, active: bool = False) -> str:
    """Return an HTML filter-chip tag span."""
    cls = "tag active" if active else "tag"
    return f'<span class="{cls}">{escape(label)}</span>'


def gold_badge(label: str = "Triple Conf") -> str:
    """Return the gold "Triple Confirmation" badge HTML."""
    return f'<span class="badge-gold">{escape(label)}</span>'


# ------------------------------- ISS bar --------------------------------- #


def iss_bar(score: float, *, width: int = 64) -> str:
    """Return an inline ISS bar (track + fill + numeric).

    Color follows the standard tier thresholds (0–39 red, 40–59 amber,
    60–79 green, 80–100 deep green).

    Args:
        score: ISS score 0–100.
        width: Track width in px (kept small for table cells).
    """
    s = max(0.0, min(100.0, float(score)))
    if s < 40:
        color = "var(--neg)"
        text_class = "neg"
    elif s < 60:
        color = "var(--warn)"
        text_class = "warn"
    elif s < 80:
        color = "var(--pos)"
        text_class = "pos"
    else:
        color = "#2DD881"
        text_class = "pos"
    return (
        f'<span class="iss-bar">'
        f'<span class="iss-track" style="width:{int(width)}px">'
        f'<span class="iss-fill" style="width:{s:.0f}%;background:{color}"></span>'
        f"</span>"
        f'<span class="mono {text_class}">{s:.0f}</span>'
        f"</span>"
    )


# ------------------------- Inline factor / progress ---------------------- #


def factor_bar(value: float, *, color: str = "var(--pos)") -> str:
    """Return an inline thin progress bar used in the ISS factor breakdown."""
    v = max(0.0, min(100.0, float(value)))
    return f'<div class="bar"><i style="width:{v:.1f}%;background:{color}"></i></div>'


# ---------------------------- Tricolor thread ---------------------------- #


def tricolor_thread() -> None:
    """Render the thin saffron→white→green thread under the brand band."""
    st.markdown('<div class="tricolor"></div>', unsafe_allow_html=True)


# ---------------------------- Status / topbar ---------------------------- #


def render_topbar(
    *,
    nse_status: str = "CLOSED",
    nse_live: bool = False,
    date_label: str = "",
    last_load: str = "",
    user: str = "",
    universe: str = "NIFTY 50",
    latency_ms: int = 42,
) -> None:
    """Render the sticky top status bar.

    Args:
        nse_status: ``"OPEN"`` or ``"CLOSED"``.
        nse_live: If True, the dot pulses (used when status is OPEN).
        date_label: Free-form display date, e.g. ``"SUN 10 MAY 2026"``.
        last_load: Free-form ``"YYYY-MM-DD HH:MM"`` last successful EOD ingest.
        user: User identifier rendered on the right.
        universe: Universe label (defaults to ``"NIFTY 50"``).
        latency_ms: Last query latency in ms; colored green ≤100, amber ≤300, red otherwise.
    """
    dot_cls = "dot live" if nse_live else "dot"
    if nse_status.upper() == "OPEN":
        status_color = "var(--pos)"
    else:
        status_color = "var(--tx2)"
    if latency_ms <= 100:
        lat_color = "var(--pos)"
    elif latency_ms <= 300:
        lat_color = "var(--warn)"
    else:
        lat_color = "var(--neg)"
    st.markdown(
        f"""
<div class="sticky-top">
  <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 28px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--tx2)">
    <div style="display:flex;align-items:center;gap:20px">
      <span style="display:inline-flex;align-items:center;gap:8px">
        <span class="{dot_cls}" style="background:{status_color}"></span>
        <span style="color:{status_color}">NSE · {escape(nse_status)}</span>
      </span>
      <span>{escape(date_label)}</span>
      <span>last EOD load <span class="acc">{escape(last_load)}</span></span>
    </div>
    <div style="display:flex;align-items:center;gap:20px">
      <span><span class="tx3">Universe</span>&nbsp;{escape(universe)}</span>
      <span><span class="tx3">Latency</span>&nbsp;<span style="color:{lat_color}">{int(latency_ms)}ms</span></span>
      <span><span class="tx3">User</span>&nbsp;{escape(user)}</span>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ---------------------------- Footer / keymap ---------------------------- #


def render_footer() -> None:
    """Render the bottom footer with keybinding cheat-sheet and data sources."""
    st.markdown(
        """
<footer style="margin-top:32px;padding:18px 28px;border-top:1px solid var(--bd);font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tx3);display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px">
  <div style="display:flex;align-items:center;gap:16px">
    <span class="serif" style="color:var(--tx2);font-style:normal;font-size:13px">Starfish · Nifty 50 Terminal</span>
    <span>data: <span class="acc">mart_stock_signals</span> · <span class="acc">mart_volume_anomaly</span> · <span class="acc">fact_corporate_event</span></span>
  </div>
  <div style="display:flex;align-items:center;gap:16px">
    <span><span class="tx2">↑↓</span> rows</span>
    <span><span class="tx2">⇧⏎</span> drill</span>
    <span><span class="tx2">/</span> filter</span>
    <span><span class="tx2">e</span> export</span>
    <span><span class="tx2">w</span> watchlist</span>
    <span><span class="tx2">Expand / Collapse all</span> · top-of-§04 buttons</span>
    <span><span class="tx2">?</span> help</span>
  </div>
</footer>
""",
        unsafe_allow_html=True,
    )


# ------------------------------ Brand band ------------------------------- #


def render_brand_header(
    *,
    subtitle: str = "India Equities · Signal Terminal · v1.0",
    big_word: str = "Starfish",
    small_word: str = "Nifty 50",
) -> None:
    """Render the editorial brand wordmark with subtitle + tricolor thread."""
    st.markdown(
        f"""
<div style="padding:20px 0 4px 0">
  <div class="kicker" style="margin-bottom:6px">{escape(subtitle)}</div>
  <h1 class="serif" style="font-size:64px;line-height:.95;letter-spacing:-0.02em;margin:0">
    {escape(big_word)}<span class="acc">.</span><span class="serif" style="font-style:italic;color:var(--tx2);font-size:40px;margin-left:12px">{escape(small_word)}</span>
  </h1>
  <div class="kicker" style="margin-top:8px">A daily briefing · drawdown · momentum · volume · events &nbsp;—&nbsp; on one page</div>
</div>
""",
        unsafe_allow_html=True,
    )
    tricolor_thread()


__all__ = [
    "render_section_header",
    "render_topbar",
    "render_footer",
    "render_brand_header",
    "tricolor_thread",
    "pill",
    "tag",
    "gold_badge",
    "iss_bar",
    "factor_bar",
]
