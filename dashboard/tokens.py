"""Global visual tokens for the consolidated Nifty 50 dashboard.

Single source of truth for typography, color, and primitive CSS classes
ported from ``design/mock_consolidated.html``. Call :func:`inject_global_styles`
exactly once at the top of ``app.py`` (after ``st.set_page_config``).

Design lock: 2026-05-11. Do not introduce new colors, fonts, or chunky-card
styles. See ``docs/dashboard_consolidation_plan.md`` §1 for the locked
contract.
"""
from __future__ import annotations

import streamlit as st


_GLOBAL_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">

<style>
:root{
  --bg:#0A0A0B; --elev:#131316; --elev2:#1C1C20;
  --bd:#26262C; --bd2:#3A3A42;
  --tx:#F4F4F0; --tx2:#8B8B92; --tx3:#57575E;
  --acc:#F4A340;
  --pos:#4ADE80; --neg:#F87171; --warn:#FBBF24; --info:#60A5FA; --evt:#A78BFA;
}

/* ===== Base ===== */
html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
  color: var(--tx);
  font-family: 'Geist', sans-serif;
  font-size: 13px;
  -webkit-font-smoothing: antialiased;
}
[data-testid="stAppViewContainer"] {
  background-image:
    radial-gradient(1100px circle at 18% -12%, rgba(244,163,64,.05), transparent 55%),
    radial-gradient(900px circle at 92% 110%, rgba(96,165,250,.035), transparent 55%) !important;
}
[data-testid="stHeader"] { background: transparent !important; }
/* Streamlit toolbar intentionally left visible during development;
   hide via Streamlit's deploy config in production. */

/* Grain overlay */
[data-testid="stAppViewContainer"]::before {
  content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 100;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.5'/%3E%3C/svg%3E");
  opacity: .025; mix-blend-mode: overlay;
}

/* Tighten Streamlit's default padding */
.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; max-width: 1800px !important; }

/* ===== Typography utility classes ===== */
.serif { font-family: 'Instrument Serif', serif; }
.mono, .num {
  font-family: 'JetBrains Mono', monospace;
  font-variant-numeric: tabular-nums;
}
.tx2 { color: var(--tx2); }
.tx3 { color: var(--tx3); }
.pos { color: var(--pos); }
.neg { color: var(--neg); }
.acc { color: var(--acc); }
.warn { color: var(--warn); }
.info { color: var(--info); }
.evt { color: var(--evt); }

/* ===== Surfaces ===== */
.panel {
  background: var(--elev);
  border: 1px solid var(--bd);
  border-radius: 2px;
}
.sub {
  background: var(--elev2);
  border: 1px solid var(--bd);
}
.hl { border-color: var(--bd); }

/* ===== Tricolor brand thread ===== */
.tricolor {
  height: 1px;
  background: linear-gradient(90deg,
    transparent 0%, #FF9933 22%, #FFFFFF 50%, #138808 78%, transparent 100%);
  opacity: .45;
}

/* ===== Section header trio ===== */
.sec-num {
  font-family: 'Instrument Serif', serif;
  font-style: italic;
  color: var(--acc);
  font-size: 18px;
  line-height: 1;
}
.sec-rule { height: 1px; background: var(--bd); flex: 1; }
.kicker {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--tx3);
}

/* ===== Pills ===== */
.pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 1px 7px; border: 1px solid currentColor; border-radius: 999px;
  font-family: 'JetBrains Mono', monospace; font-size: 9.5px; line-height: 1.5;
  text-transform: uppercase; letter-spacing: .06em;
}
.pill.fill-pos  { background: rgba(74,222,128,.10); }
.pill.fill-neg  { background: rgba(248,113,113,.10); }
.pill.fill-warn { background: rgba(251,191,36,.10); }
.pill.fill-info { background: rgba(96,165,250,.10); }
.pill.fill-acc  { background: rgba(244,163,64,.10); }
.pill.fill-evt  { background: rgba(167,139,250,.10); }

/* ===== Tags (filter chips) ===== */
.tag {
  display: inline-block; padding: 1px 6px;
  border: 1px solid var(--bd2); border-radius: 2px;
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  color: var(--tx2);
}
.tag.active {
  background: var(--acc); color: var(--bg); border-color: var(--acc);
}

/* ===== ISS bar ===== */
.iss-bar { display: inline-flex; align-items: center; gap: 6px; }
.iss-track {
  height: 5px; width: 64px;
  background: var(--elev2); border: 1px solid var(--bd);
  border-radius: 3px; overflow: hidden;
}
.iss-fill { height: 100%; display: block; }

/* ===== Inline progress / factor bars ===== */
.bar {
  position: relative; height: 14px;
  background: var(--elev2); border: 1px solid var(--bd);
  border-radius: 2px; overflow: hidden;
}
.bar i {
  position: absolute; left: 0; top: 0; bottom: 0; display: block;
}

/* ===== Gold "Triple Confirmation" badge ===== */
.badge-gold {
  background: linear-gradient(180deg, #F4A340, #C2761C);
  color: #1A0F02; font-weight: 600;
  padding: 1px 6px; border-radius: 2px;
  font-size: 9.5px; font-family: 'JetBrains Mono', monospace;
  letter-spacing: .05em; text-transform: uppercase;
}

/* ===== Status dot ===== */
.dot {
  display: inline-block; width: 6px; height: 6px;
  border-radius: 50%; background: var(--pos);
}
.dot.live {
  box-shadow: 0 0 0 0 rgba(74,222,128,.55);
  animation: dot-pulse 2s infinite;
}
@keyframes dot-pulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(74,222,128,.5); }
  50%     { box-shadow: 0 0 0 5px rgba(74,222,128,0); }
}

/* ===== Streamlit element overrides ===== */
[data-testid="stMetricValue"] > div {
  white-space: normal !important;
  font-family: 'Instrument Serif', serif !important;
  font-size: 1.85rem !important;
  line-height: 1 !important;
}
[data-testid="stMetricLabel"] > div {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 10px !important;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--tx3) !important;
}
[data-testid="stMetricDelta"] {
  font-family: 'JetBrains Mono', monospace !important;
  font-variant-numeric: tabular-nums;
}

/* DataFrame & dataframes */
[data-testid="stDataFrame"] {
  background: var(--elev);
  border: 1px solid var(--bd);
  border-radius: 2px;
}

/* Expander header */
details summary,
[data-testid="stExpander"] summary {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 11px !important;
  letter-spacing: .12em;
  text-transform: uppercase;
}

/* Selection + scrollbar */
::selection { background: var(--acc); color: var(--bg); }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--bd2); border-radius: 4px; }

/* Sticky helper */
.sticky-top { position: sticky; top: 0; z-index: 50;
  backdrop-filter: blur(8px); background: rgba(10,10,11,.86);
  border-bottom: 1px solid var(--bd);
}
.sticky-sidebar { position: sticky; top: 12px; }

/* Blink for "live" indicators (used sparingly) */
.blink { animation: blink 1.6s infinite; }
@keyframes blink { 50% { opacity: .35; } }

/* ===== Responsive: collapse 9-3 grids + multi-col KPI strips on tablet/below ===== */
@media (max-width: 1024px) {
  .block-container { padding-left: .75rem !important; padding-right: .75rem !important; }
  /* Streamlit horizontal blocks become vertical stacks */
  [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="column"] {
    flex: 1 1 100% !important;
    width: 100% !important;
    min-width: 0 !important;
  }
  /* Sticky sidebar stops sticking — content flows underneath chart on narrow */
  .sticky-sidebar { position: static !important; }
  /* Sector strip / KPI grids: cap minmax to readable single-col */
  div[style*="grid-template-columns:repeat"] {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }
  /* Brand wordmark shrinks */
  h1.serif { font-size: 44px !important; }
  h1.serif span.serif { font-size: 28px !important; margin-left: 8px !important; }
}
@media (max-width: 720px) {
  div[style*="grid-template-columns:repeat"] {
    grid-template-columns: repeat(1, minmax(0, 1fr)) !important;
  }
  h1.serif { font-size: 34px !important; }
}
</style>
"""


def inject_global_styles() -> None:
    """Inject all global CSS variables, fonts, and primitive classes.

    Must be called exactly once, immediately after :func:`st.set_page_config`,
    before any other UI rendering. Idempotent in practice (Streamlit will
    re-emit the same markdown on rerun) but designed to be called once per page
    render.
    """
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


__all__ = ["inject_global_styles"]
