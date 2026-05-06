"""Per-widget information registry for the Nifty 50 dashboard.

This module is the single source of truth for the inline help text and
"deep dive" explanations attached to every metric, table, and chart on
the Streamlit dashboard.

Two helpers are exposed:

* :func:`tooltip` — a short multi-line string suitable for the ``help=``
  parameter on Streamlit primitives (``st.metric``, ``st.column_config.*``).
  Combines a one-line plain-language description with the underlying
  formula so the user can see both in the native hover bubble.
* :func:`render_info` — renders an ``st.expander`` containing a longer
  markdown explanation: the intuition for an investor user (Rahul,
  Sanjana, or Vikram), notable edge cases, and a citation back to the
  canonical specification document.

Every entry is anchored to either:

* ``docs/nifty50_dashboard_full_spec.md`` (Sections 4, 5, 6) — the
  product / data-dictionary / signal-rules specification, or
* the current implementation in ``analytics/iss_scorer.py`` and
  ``analytics/signal_classifier.py`` where the prototype intentionally
  diverges from the spec.

When the implementation diverges from the spec the deep-dive text says so
explicitly so an investor reading the dashboard understands what they are
looking at today versus the eventual target behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import streamlit as st


__all__ = [
    "WidgetInfo",
    "WIDGETS",
    "tooltip",
    "render_info",
]


@dataclass(frozen=True)
class WidgetInfo:
    """Static metadata describing a single dashboard widget or column.

    Attributes:
        title: Human-readable name shown in the deep-dive expander header.
        short: One-line plain-language description (<= 120 chars). Used
            as the first line of the hover tooltip.
        formula: One- or two-line math / pseudocode statement of how the
            value is computed. Shown on the second line of the tooltip.
        deep_dive: Markdown body for the expander. Should include
            intuition, edge cases, and a spec or code reference.
    """

    title: str
    short: str
    formula: str
    deep_dive: str


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

WIDGETS: dict[str, WidgetInfo] = {
    # ------------------------------------------------------------------
    # View 1 — Market Overview (header KPI strip + sector / heatmap)
    # ------------------------------------------------------------------
    "overall_breadth": WidgetInfo(
        title="Overall Breadth",
        short="How many Nifty 50 stocks closed up vs down today.",
        formula="advancing = count(return_1d > 0); declining = count(return_1d < 0)",
        deep_dive=(
            "**What it tells you.** Breadth answers a simple question: was today's "
            "move broad or narrow? When 35+ stocks advance, the index move is "
            "supported by the whole market. When only a handful do, the headline "
            "index can rise on the back of two or three large names while most "
            "stocks are actually weak.\n\n"
            "**Edge cases.** A stock with `return_1d == 0` is counted as "
            "unchanged, not advancing. The count is restricted to current Nifty 50 "
            "members.\n\n"
            "**Reference.** Spec §4 View 1, Widget 1.3 (Advancing vs Declining)."
        ),
    ),
    "average_iss": WidgetInfo(
        title="Average ISS",
        short="Mean Investment Signal Score across all 50 constituents (0-100).",
        formula="avg_iss = mean(iss_score) over Nifty 50 members on calc_date",
        deep_dive=(
            "**What it tells you.** A single-number snapshot of how attractive "
            "the index *as a basket* looks today on the seven-factor ISS framework "
            "(price, RS vs Nifty, drawdown, volume, events, trend stability, "
            "breakout alignment). Readings consistently above ~60 indicate a "
            "broadly constructive tape; readings below ~40 indicate the average "
            "stock is failing several factors simultaneously.\n\n"
            "**Edge cases.** ISS is bounded to [0, 100] in code; missing inputs "
            "default to a neutral sub-score (see `analytics/iss_scorer.py`). The "
            "average is equal-weighted across constituents — it is *not* market-"
            "cap weighted.\n\n"
            "**Reference.** Spec §6.1 (ISS factor weights); "
            "`analytics/iss_scorer.py::compute_iss`."
        ),
    ),
    "avg_1d_return": WidgetInfo(
        title="Average 1-Day Return",
        short="Equal-weighted mean of today's percentage returns across the 50 names.",
        formula="avg_1d = mean(return_1d) * 100 (%)",
        deep_dive=(
            "**What it tells you.** This is a breadth-weighted view of the day. "
            "Compare it to the headline Nifty 50 index move — if the index is up "
            "+0.8% but the equal-weighted average is only +0.1%, the rally was "
            "concentrated in a few large names (a Breadth Divergence signal in "
            "spec terminology).\n\n"
            "**Reference.** Spec §4 View 1, Widget 1.4 (Average Constituent "
            "Return Cards)."
        ),
    ),
    "top_sector": WidgetInfo(
        title="Top Sector",
        short="Sector with the highest equal-weighted average 1-day return today.",
        formula="argmax over sectors of mean(return_1d) within sector",
        deep_dive=(
            "**What it tells you.** Quick read on rotation. A different sector "
            "topping the leaderboard most days is a healthy, rotational tape; "
            "the same defensive sector leading repeatedly often signals risk-off "
            "behaviour.\n\n"
            "**Edge cases.** Sector membership comes from `dim_stock.sector`. "
            "Sectors with only one or two constituents can swing the leaderboard "
            "on a single name's move.\n\n"
            "**Reference.** Spec §4 View 1, Widget 1.2 (Sector Breadth Table)."
        ),
    ),
    "market_structure": WidgetInfo(
        title="Market Structure",
        short="Heuristic regime label for the current tape (e.g. Mean Reverting / Trending).",
        formula="Classifier on recent breadth, dispersion and trend stability",
        deep_dive=(
            "**What it tells you.** A coarse, qualitative regime tag intended to "
            "set expectation for which playbook is working: trend-following or "
            "mean-reversion. In the current build this is a placeholder; future "
            "phases will derive it from realised vol, breadth oscillators and "
            "trend stability.\n\n"
            "**Reference.** Roadmap item — exact rule to be specified before "
            "Phase H release."
        ),
    ),
    "morning_digest": WidgetInfo(
        title="Morning Digest",
        short="Top three stocks ranked by ISS for a one-glance pre-market briefing.",
        formula="signals.nlargest(3, 'iss_score')",
        deep_dive=(
            "**What it tells you.** The three names where the seven-factor ISS "
            "stack is most aligned today. Hover reveals 1D return, volume "
            "multiple, signal category, and current drawdown from 52-week high.\n\n"
            "**How to use it.** Treat as the start of analysis, not the end — a "
            "high ISS only means the model thinks the setup is interesting, not "
            "that you should buy. Cross-check the underlying signal category "
            "(ACC vs MOM vs EVT) before acting.\n\n"
            "**Reference.** Spec §6.1 (ISS); §6.2 (signal categories)."
        ),
    ),
    "sector_rotation_heatmap": WidgetInfo(
        title="Sector Rotation & Breadth Heatmap",
        short="Visual breakdown of advancers vs decliners and per-stock 1-day return inside each sector.",
        formula="Donut: counts of advancing/declining; Treemap: cell size = ISS, color = return_1d",
        deep_dive=(
            "**What it tells you.** Two complementary views of today's tape:\n\n"
            "* **Donut** — share of the 50 names that are up vs down today.\n"
            "* **Treemap** — cell size encodes ISS (signal strength), cell colour "
            "encodes today's return (red-yellow-green diverging scale centered on "
            "zero). Look for *large green cells* (high-conviction names that are "
            "also working today) and *large red cells* (high-conviction names that "
            "are breaking down).\n\n"
            "**Reference.** Spec §4 View 1, Widget 1.3 and Widget 1.6 "
            "(Performance Heatmap)."
        ),
    ),
    "sector_aggregation": WidgetInfo(
        title="Sector Aggregation",
        short="Per-sector averages of 1D / 1M return and ISS, plus advancer / decliner counts.",
        formula="group by sector; avg(return_*); avg(iss_score); count(advancing/declining)",
        deep_dive=(
            "**What it tells you.** Where capital is rotating *to* and *from*. "
            "Persistent leadership at both 1D and 1M horizons is a stronger "
            "signal than a one-day pop.\n\n"
            "**Reference.** Spec §4 View 1, Widget 1.2."
        ),
    ),
    "watchlist_signals": WidgetInfo(
        title="Watchlist Signals",
        short="Live screener row for every symbol you have pinned to your watchlist.",
        formula="signals where symbol IN user_watchlist; show close, return_1d, vol_ratio_1d, iss_score, signal_category",
        deep_dive=(
            "**What it tells you.** Fast cross-check of your tracked names. The "
            "**Signal** column is one of `Accumulation`, `Momentum`, "
            "`EventDriven`, or `Neutral` — see the Signal column tooltip for "
            "rule details.\n\n"
            "**Reference.** Spec §4 View 7 (Watchlist Builder)."
        ),
    ),
    "movers_gainers": WidgetInfo(
        title="Movers — Gainers",
        short="Top advancers today with sector context, volume confirmation, and ISS.",
        formula="ORDER BY return_1d DESC LIMIT N (server-side via /movers endpoint)",
        deep_dive=(
            "**What it tells you.** Today's leadership. Pair the return with the "
            "**Vol** column: a +3% move on 2x volume is structurally different "
            "from the same move on 0.6x volume — the former has institutional "
            "fingerprints, the latter is thin air.\n\n"
            "**Reference.** Spec §4 View 2, Widget 2.2 (Top 10 Gainers)."
        ),
    ),
    "movers_losers": WidgetInfo(
        title="Extremes — Losers",
        short="Steepest declines today with sector context and volume.",
        formula="ORDER BY return_1d ASC LIMIT N (server-side via /movers endpoint)",
        deep_dive=(
            "**What it tells you.** Today's pain trades. A red day on heavy "
            "volume is distribution; on light volume it is often noise. The "
            "Drawdown Scanner tab classifies these further into Accumulation / "
            "Falling Knife / Event Review.\n\n"
            "**Reference.** Spec §4 View 2, Widget 2.3 (Top 10 Losers)."
        ),
    ),
    "primary_scanner": WidgetInfo(
        title="Primary Scanner Pipeline Data",
        short="Full 50-row screener: price, returns, volume, drawdown, ISS, and signal flags.",
        formula="SELECT * FROM mart_stock_signals JOIN dim_stock WHERE calc_date = :date",
        deep_dive=(
            "**What it tells you.** This is the canonical mart powering every "
            "view on the dashboard. Every column maps directly to a row in the "
            "data dictionary (`docs/nifty50_dashboard_full_spec.md` §5 Table 7 "
            "`mart_stock_signals`). Use the type-ahead filter for sector or "
            "symbol regex search.\n\n"
            "**Reference.** Spec §5 Table 7 (`mart_stock_signals`)."
        ),
    ),
    # ------------------------------------------------------------------
    # Master screener column dictionary
    # ------------------------------------------------------------------
    "return_1d": WidgetInfo(
        title="1-Day Return (%)",
        short="Today's percentage price change vs prior close.",
        formula="(close - prev_close) / prev_close * 100",
        deep_dive=(
            "**Reference.** Spec §5 Table 7 — `return_1d` (DECIMAL(8,4)). "
            "Computed by the EOD batch from `fact_eod_price.close` and "
            "`fact_eod_price.prev_close`."
        ),
    ),
    "return_1m": WidgetInfo(
        title="1-Month Return (%)",
        short="Approx. 1-month return — change vs close 21 trading days ago.",
        formula="(close_today - close_21d_ago) / close_21d_ago * 100",
        deep_dive=(
            "**Why 21 days.** ~21 trading sessions ≈ one calendar month. Stored "
            "in `mart_stock_signals.return_1m`.\n\n"
            "**Reference.** Spec §5 Table 7 — `return_1m`."
        ),
    ),
    "return_3m": WidgetInfo(
        title="3-Month Return (%)",
        short="Approx. 3-month return — change vs close 63 trading days ago.",
        formula="(close_today - close_63d_ago) / close_63d_ago * 100",
        deep_dive=(
            "**Why this matters.** 3M return is the spine of momentum signals "
            "(Factor 1 of the ISS, weight 15) and a hard gate on the MOM rule "
            "(`return_3m > +15%` is one of the qualifying conditions).\n\n"
            "**Reference.** Spec §5 Table 7 — `return_3m`; §6.1 Factor 1; "
            "§6.2 MOM_RULE."
        ),
    ),
    "vol_ratio_1d": WidgetInfo(
        title="Vol 1D / 20D",
        short="Today's traded quantity as a multiple of the 20-day average.",
        formula="vol_ratio_1d = volume_today / avg_volume_20d",
        deep_dive=(
            "**How to read it.** 1.0x is exactly average. Spec thresholds:\n\n"
            "* **>= 1.2x** — mild expansion\n"
            "* **>= 1.5x** — moderate\n"
            "* **>= 2.0x** — high (potential breakout / distribution)\n"
            "* **>= 3.0x** — extreme (often event-driven, see VA-5 rule)\n"
            "* **<= 0.85x** with contracting 3M trend — drying up, possible "
            "breakout setup (VA-4)\n\n"
            "**Reference.** Spec §5 Table 7 — `vol_ratio_1d`; §5 Table 8 "
            "`spike_level` thresholds; §6.3 Volume Anomaly Rules."
        ),
    ),
    "avg_volume_20d": WidgetInfo(
        title="20-Day Average Volume",
        short="Rolling mean of total traded quantity over the last 20 sessions.",
        formula="avg_volume_20d = mean(total_traded_qty over prior 20 trading days)",
        deep_dive=(
            "**Why it's the denominator.** Used to normalise both intraday "
            "spikes (`vol_ratio_1d`) and the 5-day moving picture "
            "(`vol_ratio_5d`). 20 sessions ≈ one calendar month of activity.\n\n"
            "**Reference.** Spec §5 Table 7 — `avg_volume_20d`."
        ),
    ),
    "drawdown_pct": WidgetInfo(
        title="% from 52-Week High",
        short="How far below the prior 52-week peak the current close sits (negative number).",
        formula="(close - wk52_high) / wk52_high * 100",
        deep_dive=(
            "**How to read it.** Always non-positive. -22.5 means 22.5% below "
            "the rolling 52-week peak. This is the key field for the Drawdown "
            "Scanner (View 3) and one of the seven ISS factors.\n\n"
            "**Reference.** Spec §5 Table 3 (`fact_52wk.pct_from_high`); "
            "§5 Table 7 (`drawdown_from_52w_high_pct`); §6.1 Factor 3."
        ),
    ),
    "distance_from_low": WidgetInfo(
        title="% from 52-Week Low",
        short="How far above the prior 52-week trough the current close sits (positive number).",
        formula="(close - wk52_low) / wk52_low * 100",
        deep_dive=(
            "**How to read it.** Always non-negative. 35.0 means the close is "
            "35% above the rolling 52-week low. Used in ISS Factor 7 "
            "(Accumulation / Breakout Alignment).\n\n"
            "**Reference.** Spec §5 Table 7 — `distance_from_52w_low_pct`; "
            "§6.1 Factor 7."
        ),
    ),
    "iss_score": WidgetInfo(
        title="ISS — Investment Signal Score (0-100)",
        short="Composite of 7 factors covering momentum, drawdown, volume, events, and trend.",
        formula="ISS = F1(price 25) + F2(RS 20) + F3(drawdown 15) + F4(volume 15) + F5(event 10) + F6(stability 10) + F7(alignment 5)",
        deep_dive=(
            "**Composition (max points in brackets).**\n\n"
            "* **F1 — Price Performance [25].** 3M return [15] + 1Y return [10].\n"
            "* **F2 — Relative Strength vs Nifty 50 [20].** RS_3M [12] + RS_1Y [8].\n"
            "* **F3 — Drawdown from 52W High [15].** Mode-aware: in Momentum "
            "mode lower drawdown scores higher; in Accumulation mode (3M < -10% "
            "and 1Y < -20%) deeper drawdown scores higher.\n"
            "* **F4 — Volume Confirmation [15].** Rewards rising price on rising "
            "volume; penalises falling price on rising volume (distribution).\n"
            "* **F5 — Corporate Event Presence [10].** Significance score 5 = 10 "
            "pts; tapered down to 0 for no event in 20 days. Negative event of "
            "significance >= 4 inside 10 days deducts 5 from total.\n"
            "* **F6 — Trend Stability [10].** Direction consistency over the "
            "last 20 sessions, penalised for >2% intraday reversals.\n"
            "* **F7 — Accumulation / Breakout Alignment [5].** Price near 52W "
            "low with expanding volume, or within 3% of the 52W high.\n\n"
            "**Important — implementation vs spec.** The current "
            "`analytics/iss_scorer.py` uses simplified bucket thresholds "
            "(see code) and clips to [0, 100]. Future revisions will tighten "
            "these to match the spec tables exactly.\n\n"
            "**Reference.** Spec §6.1 (Factors 1-7); "
            "`analytics/iss_scorer.py::compute_iss`."
        ),
    ),
    "signal_category": WidgetInfo(
        title="Signal Category",
        short="Primary classification — one of Accumulation / Momentum / EventDriven / Neutral.",
        formula="See ACC / MOM / EVT rules in spec §6.2 (priority: EVT > ACC > MOM > Neutral)",
        deep_dive=(
            "**ACC (Accumulation Candidate).** `return_1y < -20%` AND "
            "`return_3m < -10%` AND drawdown < -25% AND volume not "
            "expanding AND no recent regulatory / rating event AND ISS >= 35. "
            "Filters out 'falling knives' where volume is contracting alongside "
            "an accelerating decline.\n\n"
            "**MOM (Momentum Candidate).** (`return_3m > +15%` OR "
            "`return_1y > +30%`) AND volume expansion AND `rs_vs_nifty_3m > +5%` "
            "AND no major adverse event AND ISS >= 60. Strength tier comes from "
            "ISS: 85+ Strong, 70-84 Confirmed, 60-69 Watch.\n\n"
            "**EVT (Event-Driven).** Significant corporate event in past 20 "
            "days *or* upcoming inside 10 days, with material price reaction. "
            "Co-exists with ACC / MOM (e.g. `MOM+EVT`).\n\n"
            "**Neutral.** None of the above triggered.\n\n"
            "**Reference.** Spec §6.2; "
            "`analytics/signal_classifier.py::classify_signal`."
        ),
    ),
    "momentum_flag": WidgetInfo(
        title="MOM flag",
        short="True if the stock passes all Momentum Candidate gates today.",
        formula="MOM_RULE per spec §6.2: returns + volume expansion + RS_3M > 5% + ISS >= 60",
        deep_dive=(
            "**Reference.** Spec §6.2 (MOM_RULE). The flag is computed during "
            "the EOD signal pass and persisted in `mart_stock_signals.momentum_flag`."
        ),
    ),
    "accumulation_flag": WidgetInfo(
        title="ACC flag",
        short="True if the stock passes all Accumulation Candidate gates today.",
        formula="ACC_RULE per spec §6.2: deep drawdown + volume not expanding + ISS >= 35",
        deep_dive=(
            "**Reference.** Spec §6.2 (ACC_RULE) and the Falling Knife "
            "exclusion sub-rule. Stored in `mart_stock_signals.accumulation_flag`."
        ),
    ),
    # ------------------------------------------------------------------
    # View 3 — Drawdown Scanner (phase_f.py)
    # ------------------------------------------------------------------
    "drawdown_scanner": WidgetInfo(
        title="View 3 — Drawdown Scanner",
        short="Surfaces names trading materially below their 52-week peak and tags the setup.",
        formula="Filter mart_stock_signals where drawdown_from_52w_high_pct <= threshold",
        deep_dive=(
            "**What it does.** Implements Spec View 3. The filter slider lets you "
            "raise or lower the drawdown threshold (default -20%); each "
            "qualifying stock gets a `Tag` derived from its volume trend, "
            "signal category, and event flags.\n\n"
            "**Reference.** Spec §4 View 3 (Drawdown Scanner)."
        ),
    ),
    "drawdown_threshold": WidgetInfo(
        title="Drawdown threshold",
        short="Show only stocks at or below this drawdown vs their 52-week high.",
        formula="filter: drawdown_from_52w_high_pct <= threshold (more negative = deeper)",
        deep_dive=(
            "**Tip.** Default -20% mirrors the Spec definition of a 'deep "
            "drawdown' (>= 20% off peak). Slide further (more negative) to focus "
            "on bombed-out names; slide closer to zero to widen the universe.\n\n"
            "**Reference.** Spec §4 View 3, Widget 3.1."
        ),
    ),
    "drawdown_count": WidgetInfo(
        title="Names <= threshold",
        short="Count of filtered stocks whose drawdown is at or below the threshold.",
        formula="count(rows where drawdown_from_52w_high_pct <= threshold)",
        deep_dive=(
            "Used as a quick gauge of how broad the pain is at the chosen "
            "threshold. A reading of 5+ at -20% inside Nifty 50 is meaningful — "
            "the index is supposed to be the highest-quality liquid universe."
        ),
    ),
    "drawdown_avg": WidgetInfo(
        title="Avg drawdown (filtered)",
        short="Average drawdown across all sector-filtered names (not just those past the threshold).",
        formula="mean(drawdown_from_52w_high_pct) over current sector filter",
        deep_dive=(
            "**Why filtered, not threshold-filtered.** The metric uses the "
            "*sector-filter* universe rather than only the threshold-passing "
            "rows so it stays meaningful when the threshold is tightened — "
            "otherwise the average would always converge near the threshold."
        ),
    ),
    "drawdown_tag": WidgetInfo(
        title="Tag — drawdown classification",
        short="Potential Accumulation / Falling Knife Risk / Needs Event Review based on volume + events.",
        formula="See dashboard.phase_f.drawdown_signal_tag",
        deep_dive=(
            "**Tag rules (priority order).**\n\n"
            "1. **Falling Knife Risk** — volume_trend_3m == 'Expanding', or "
            "signal_category == 'EventDriven' with non-contracting volume. "
            "Money is leaving the building.\n"
            "2. **Needs Event Review** — event_flag is True or signal_category "
            "is EventDriven. The setup is news-driven; check the event before "
            "acting.\n"
            "3. **Potential Accumulation** — volume_trend_3m == 'Contracting' "
            "or `accumulation_flag` is True. Selling appears to be exhausting.\n"
            "4. Fallback — Needs Event Review.\n\n"
            "**Reference.** Spec §4 View 3, Widget 3.2 (Signal Tag Logic); "
            "`dashboard/phase_f.py::drawdown_signal_tag`."
        ),
    ),
    "volume_trend_3m": WidgetInfo(
        title="Volume Trend (3M)",
        short="Direction of volume over the last ~63 sessions: Expanding / Contracting / Mixed.",
        formula="Linear regression on 63-day daily volume; sign of slope, with R^2 >= 0.3 threshold",
        deep_dive=(
            "**How to read it.** Spec §5 Table 7:\n\n"
            "* **Expanding** — slope positive AND R^2 >= 0.3. Money flowing in.\n"
            "* **Contracting** — slope negative AND R^2 >= 0.3. Activity drying "
            "up.\n"
            "* **Mixed** — R^2 < 0.3. No discernible direction.\n\n"
            "**Why it matters for drawdowns.** Drawdown + Contracting often "
            "marks selling exhaustion (accumulation candidate). Drawdown + "
            "Expanding is distribution (falling knife)."
        ),
    ),
    # ------------------------------------------------------------------
    # View 4 — Breakout & Momentum (phase_f.py)
    # ------------------------------------------------------------------
    "momentum_active": WidgetInfo(
        title="Active momentum",
        short="Stocks with momentum_flag = True or signal_category = Momentum.",
        formula="filter: momentum_flag OR signal_category == 'Momentum'",
        deep_dive=(
            "**What you see.** Names that already cleared the full MOM gate "
            "(returns + volume + RS + ISS >= 60) plus any classified as "
            "Momentum by the rule engine. The MOM tier column converts the ISS "
            "into a strength label.\n\n"
            "**Reference.** Spec §6.2 (MOM_RULE)."
        ),
    ),
    "breakout_radar": WidgetInfo(
        title="Near-breakout radar",
        short="Stocks within ~5% of their 52-week high with ISS >= 50 but no MOM flag yet.",
        formula="not momentum_flag AND drawdown_from_52w_high_pct >= -5% AND iss_score >= 50",
        deep_dive=(
            "**What you see.** Names approaching a breakout but not yet "
            "qualifying as full Momentum candidates. Useful as a watchlist for "
            "Sanjana (tactical trader) — the moment volume confirms, several "
            "of these usually cross into MOM.\n\n"
            "**Reference.** Spec §4 View 4 (Breakout / Momentum Monitor); "
            "spec §6.2 MOM_RULE for the qualifying gates."
        ),
    ),
    "momentum_tier": WidgetInfo(
        title="MOM tier",
        short="Strength label derived from ISS — Strong / Confirmed / Watch.",
        formula="ISS >= 80 -> Strong; 65-79 -> Confirmed; 50-64 -> Watch; else blank",
        deep_dive=(
            "**Tiers and intent.**\n\n"
            "* **Strong** (ISS >= 80) — position size with confidence.\n"
            "* **Confirmed** (65-79) — qualifies but not a leader.\n"
            "* **Watch** (50-64) — early — let it prove itself.\n\n"
            "**Note.** The dashboard uses 80 / 65 / 50 cutoffs "
            "(`dashboard/phase_f.momentum_tier_label`). The spec specifies "
            "85 / 70 / 60 for Strong / Confirmed / Watch — the production "
            "thresholds will be tightened to match before Phase 6.\n\n"
            "**Reference.** Spec §6.2 Momentum Strength Tiers; "
            "`analytics/signal_classifier.py::assign_momentum_tier`."
        ),
    ),
    "rs_vs_nifty_3m": WidgetInfo(
        title="RS vs Nifty (3M)",
        short="3-month relative strength — alpha vs the Nifty 50 index, in percentage points.",
        formula="rs_vs_nifty_3m = return_3m - nifty50_return_3m",
        deep_dive=(
            "**How to read it.** Positive = outperforming the index; negative = "
            "underperforming. The MOM gate requires `rs_vs_nifty_3m > +5%` "
            "(meaningful outperformance, not just being in a rising tide).\n\n"
            "**Reference.** Spec §5 Table 7 — `rs_vs_nifty_3m`; §6.1 Factor 2; "
            "§6.2 MOM_RULE."
        ),
    ),
    "rs_chart_top15": WidgetInfo(
        title="RS vs Nifty (3M) — top 15",
        short="Bar chart of the 15 strongest 3-month relative-strength names.",
        formula="ORDER BY rs_vs_nifty_3m DESC LIMIT 15; bar = rs_pct (%)",
        deep_dive=(
            "Color encodes the same value redundantly with bar length to make "
            "scanning fast. Cross-check the bar leaders against the Active "
            "Momentum table — names in both lists are the highest-conviction "
            "trend candidates."
        ),
    ),
    "vol_ratio_5d": WidgetInfo(
        title="Vol 5D / 20D",
        short="Rolling 5-day average volume as a multiple of the 20-day average.",
        formula="mean(volume last 5d) / avg_volume_20d",
        deep_dive=(
            "**Why this exists alongside vol_ratio_1d.** Single-day spikes can "
            "be one-off block deals or expiry quirks. The 5D/20D ratio confirms "
            "*sustained* expansion — a better signal of changing institutional "
            "interest. The MOM gate accepts either ratio above 1.3.\n\n"
            "**Reference.** Spec §5 Table 7 — `vol_ratio_5d`; §6.2 MOM_RULE."
        ),
    ),
    # ------------------------------------------------------------------
    # View 5 — Volume Anomaly (phase_f.py)
    # ------------------------------------------------------------------
    "volume_anomaly_view": WidgetInfo(
        title="View 5 — Volume Anomaly Monitor",
        short="Identifies unusual volume — spikes and contractions — as a leading indicator.",
        formula="Buckets vs 20D avg: 1.2x / 1.5x / 2.0x; contraction <= 0.85x with 3M trend Contracting",
        deep_dive=(
            "**Why volume matters.** Volume spikes often precede announcements; "
            "high-volume declines suggest distribution by large holders; "
            "high-volume recoveries suggest re-accumulation. Persistent volume "
            "contraction on a falling stock can mark exhaustion. Delivery "
            "percentage (where available) separates speculative intraday "
            "surges (low delivery) from genuine institutional positioning "
            "(high delivery).\n\n"
            "**Reference.** Spec §4 View 5; §6.3 Volume Anomaly Rules."
        ),
    ),
    "volume_anomaly_mart": WidgetInfo(
        title="mart_volume_anomaly",
        short="Curated daily mart of volume anomalies with delivery %, spike level, and event proximity.",
        formula="SELECT FROM mart_volume_anomaly WHERE calc_date = :calc_date ORDER BY volume_ratio DESC",
        deep_dive=(
            "**Columns of note.**\n\n"
            "* **volume_ratio** — same definition as `vol_ratio_1d`.\n"
            "* **spike_level** — Normal / Mild / Moderate / High / Extreme "
            "(<1.2 / 1.2-1.5 / 1.5-2.0 / 2.0-3.0 / >3.0).\n"
            "* **delivery_pct** — fraction of traded quantity that settled "
            "(NULL on T+0; populated T+1).\n"
            "* **anomaly_direction** — Up / Down based on price change on "
            "spike day.\n"
            "* **nearest_event_within_5d** — corporate event within +/- 5 "
            "trading days, if any.\n\n"
            "**Reference.** Spec §5 Table 8 (`mart_volume_anomaly`)."
        ),
    ),
    "volume_anomaly_buckets": WidgetInfo(
        title="Same-day volume buckets",
        short="Splits today's tape into >100% / >50% / >20% above-average and contraction buckets.",
        formula=">100%: vr>=2.0; >50%: 1.5<=vr<2.0; >20%: 1.2<=vr<1.5; Contraction: vr<=0.85 AND trend=Contracting",
        deep_dive=(
            "**Why thresholds matter.** Spec §5 Table 8 spike levels:\n\n"
            "* `Mild` 1.2-1.5x — early-warning.\n"
            "* `Moderate` 1.5-2.0x — meaningful.\n"
            "* `High` 2.0-3.0x — institutional or news.\n"
            "* `Extreme` >3.0x — usually event-driven; pause and verify "
            "(Volume Anomaly Rule VA-5).\n\n"
            "**Contraction.** A drying-up tape (<=0.85x with 3M trend "
            "contracting) is the breakout setup precursor (Rule VA-4)."
        ),
    ),
    "delivery_pct": WidgetInfo(
        title="Delivery %",
        short="Share of today's volume that actually settled (delivered) vs squared off intraday.",
        formula="delivery_pct = delivery_qty / total_traded_qty * 100",
        deep_dive=(
            "**How to read it.** Spec Volume Anomaly rules:\n\n"
            "* `vol_ratio > 1.5` AND `delivery_pct > 60` -> "
            "*Institutional Accumulation Likely* (positive).\n"
            "* `vol_ratio > 1.5` AND `delivery_pct < 25` -> *Speculative "
            "Activity* (intraday driven, not accumulation).\n\n"
            "**Edge case.** NSE publishes the delivery file with a one-day lag, "
            "so this column is `NULL` on T+0 and back-filled on T+1.\n\n"
            "**Reference.** Spec §5 Table 2 (`delivery_pct`); §6.3 rules VA-6, "
            "VA-7."
        ),
    ),
    "spike_level": WidgetInfo(
        title="Spike level",
        short="Bucketed volume-ratio label — Normal / Mild / Moderate / High / Extreme.",
        formula="<1.2 Normal · 1.2-1.5 Mild · 1.5-2.0 Moderate · 2.0-3.0 High · >3.0 Extreme",
        deep_dive=(
            "**Reference.** Spec §5 Table 8 — `spike_level` enum thresholds."
        ),
    ),
    # ------------------------------------------------------------------
    # View 6 — Corporate Events Tracker (phase_g.py)
    # ------------------------------------------------------------------
    "events_view": WidgetInfo(
        title="View 6 — Corporate Events Tracker",
        short="Unified, chronological feed of material corporate events for Nifty 50 names.",
        formula="SELECT FROM fact_corporate_event JOIN dim_stock filtered by date range, type, significance",
        deep_dive=(
            "**Sources.** Earnings, leadership change, M&A, large orders, "
            "pledging change, rating change, regulatory action, and other "
            "categorised filings. Event type is assigned by the NLP / rule "
            "categoriser (`categorization_method` records which path was "
            "used).\n\n"
            "**Reference.** Spec §4 View 6; §5 Table 6 (`fact_corporate_event`)."
        ),
    ),
    "events_total": WidgetInfo(
        title="Total Events",
        short="Number of events matching the current filter (date range + type + min significance).",
        formula="count(events where filters apply)",
        deep_dive="Resets when filters change. Spec §4 View 6, Widget 6.1.",
    ),
    "events_upcoming": WidgetInfo(
        title="Upcoming Events",
        short="Events with event_date strictly in the future relative to today.",
        formula="count(events where event_date > CURRENT_DATE)",
        deep_dive=(
            "**Why it matters.** Upcoming high-significance events feed the "
            "EVT classification — see spec §6.2 EVT_RULE upcoming branch "
            "(`upcoming_event_date <= calc_date + 10 days` with significance "
            ">= 3)."
        ),
    ),
    "events_recent": WidgetInfo(
        title="Recent Events (Past)",
        short="Events with event_date already in the past inside the selected window.",
        formula="count(events where event_date <= CURRENT_DATE within window)",
        deep_dive=(
            "Pair this with the price-impact columns (1D / 5D / 20D) on the "
            "expanded event card to assess how the market actually reacted."
        ),
    ),
    "events_high_sig": WidgetInfo(
        title="High-Significance Events (>= 4)",
        short="Events rated 4 (High Impact) or 5 (Transformative) on the 1-5 significance scale.",
        formula="count(events where significance >= 4)",
        deep_dive=(
            "**Significance scale (Spec §4 View 6, Widget 6.2).**\n\n"
            "1 — Routine (small dividend, general filing)\n"
            "2 — Notable (earnings report, leadership change)\n"
            "3 — Significant (large order > 5% of revenue, rating up/downgrade)\n"
            "4 — High Impact (merger announcement, large buyback, regulatory "
            "notice)\n"
            "5 — Transformative (merger completion, delisting, major regulatory "
            "penalty)\n\n"
            "Events at >= 4 auto-flag `follow_up_required = TRUE`."
        ),
    ),
    "events_significance": WidgetInfo(
        title="Event Significance (1-5)",
        short="Importance rating from 1 (Routine) to 5 (Transformative).",
        formula="Rule-engine or NLP-assigned, stored in fact_corporate_event.significance_score",
        deep_dive=(
            "**Auto-promote rules (Spec §4 View 6, Widget 6.2 Follow-up Logic).** "
            "Significance ≥ 4, OR Regulatory Action / Leadership Change / "
            "Pledging Change > 5% / |1D price reaction| > 5% all trigger "
            "`follow_up_required = TRUE` automatically.\n\n"
            "**Reference.** Spec §5 Table 6 `significance_score`."
        ),
    ),
    "events_timeline": WidgetInfo(
        title="Events Timeline",
        short="Chronological grouping of all matching events with significance badge and 1D price reaction.",
        formula="GROUP BY event_date ORDER BY event_date DESC, significance DESC",
        deep_dive=(
            "**Reference.** Spec §4 View 6, Widget 6.2 (Corporate Events "
            "Timeline Table)."
        ),
    ),
    "events_price_impact": WidgetInfo(
        title="Price Reaction (1D / 5D / 20D)",
        short="Cumulative % price change from the event day across three windows.",
        formula="(close_t+N - close_event_day) / close_event_day * 100",
        deep_dive=(
            "**How to read it.** 1D captures the immediate reaction; 5D shows "
            "whether the move stuck; 20D tests structural significance. A 1D "
            "pop that fully reverses by 20D is a fade; a 1D move that extends "
            "by 20D is the start of a trend.\n\n"
            "**Reference.** Spec §5 Table 6 (`price_chg_1d`, `price_chg_5d`, "
            "`price_chg_20d`)."
        ),
    ),
    # ------------------------------------------------------------------
    # View 7 — Watchlist Builder (phase_g.py)
    # ------------------------------------------------------------------
    "watchlist_builder": WidgetInfo(
        title="View 7 — Watchlist Builder",
        short="Auto-curated, rules-based watchlist split into four signal-driven categories.",
        formula="See per-tab category logic (spec §4 Widget 7.1)",
        deep_dive=(
            "**Reference.** Spec §4 View 7. Items are auto-populated by the "
            "watchlist builder service; user pin / unpin and notes are layered "
            "on top."
        ),
    ),
    "watchlist_contrarian": WidgetInfo(
        title="Contrarian Opportunities",
        short="Drawdown >20%, signal = Accumulation, ISS >= 40 — beaten-down quality.",
        formula="drawdown < -20% AND signal_tag = 'ACC' AND iss_score >= 40",
        deep_dive=(
            "**Persona fit.** Rahul (long-only fundamental). Look for companies "
            "where the price has corrected materially but the underlying "
            "business is intact and volume is no longer accelerating to the "
            "downside.\n\n"
            "**Reference.** Spec §4 View 7, Widget 7.1 (Contrarian Opportunities)."
        ),
    ),
    "watchlist_momentum": WidgetInfo(
        title="Momentum Leaders",
        short="3M return >20%, momentum tag = Volume-Confirmed or Event-Driven, ISS >= 50.",
        formula="return_3m > 20% AND momentum_tag IN ('Volume-Confirmed','Event-Driven') AND iss_score >= 50",
        deep_dive=(
            "**Persona fit.** Sanjana (tactical trader). Already-working trends "
            "with volume backing. Beware: momentum lists can crowd at major "
            "tops — check the MOM tier and the RS vs Nifty 3M chart for "
            "deterioration before sizing up.\n\n"
            "**Reference.** Spec §4 View 7, Widget 7.1 (Momentum Leaders)."
        ),
    ),
    "watchlist_event": WidgetInfo(
        title="Event-Driven Candidates",
        short="Significance >=3 event in past 30d or upcoming 14d, follow-up required, ISS >= 35.",
        formula="event_window AND follow_up_required = TRUE AND iss_score >= 35",
        deep_dive=(
            "**Persona fit.** Vikram (risk officer) — these are the names where "
            "*something happened*; the price implication may not be in the "
            "tape yet. Use the price-impact columns to gauge market reaction.\n\n"
            "**Reference.** Spec §4 View 7, Widget 7.1 (Event-Driven Candidates)."
        ),
    ),
    "watchlist_volume": WidgetInfo(
        title="Volume-Confirmed Movers",
        short="Volume Ratio >1.5x in last 5 sessions, positive return on spike day, ISS >= 40.",
        formula="vol_ratio_1d > 1.5 (within last 5d) AND price_chg_on_spike > 0 AND iss_score >= 40",
        deep_dive=(
            "**Why this list.** A move on heavy volume is materially different "
            "from a quiet drift. This category surfaces exactly that — moves "
            "that have institutional fingerprints.\n\n"
            "**Reference.** Spec §4 View 7, Widget 7.1 (Volume-Confirmed Movers)."
        ),
    ),
    "watchlist_iss_badge": WidgetInfo(
        title="ISS Score badge tiers (in tab tables)",
        short="Color-coded ISS bands — red 0-39, amber 40-59, green 60-79, deep green 80-100.",
        formula="0-39 red · 40-59 amber · 60-79 green · 80-100 deep green",
        deep_dive=(
            "**Reference.** Spec §4 View 7, Widget 7.2 (ISS Score badge "
            "colour scheme). The bands are deliberately wider than the "
            "Momentum tier cutoffs (which are 60 / 65 / 80 in the prototype) "
            "because the badge spans all signal categories, not just MOM."
        ),
    ),
    # ------------------------------------------------------------------
    # Phase I — Mobile + desktop KPI cards (reuse top_iss/avg_iss/etc.)
    # ------------------------------------------------------------------
    "kpi_top_iss": WidgetInfo(
        title="Top ISS",
        short="Stock with the highest Investment Signal Score on the selected date.",
        formula="argmax(iss_score) over all filtered rows",
        deep_dive=(
            "**How to use it.** A pointer to the single most-aligned setup on "
            "the day. Always cross-check the underlying signal category "
            "before acting (a high ISS with EVT can mean a name in flux, not "
            "a clean buy).\n\n"
            "**Reference.** Spec §6.1 (ISS factors)."
        ),
    ),
    "kpi_gainers": WidgetInfo(
        title="Gainers (count + share)",
        short="How many stocks closed positive today, and what share of the universe that is.",
        formula="count(return_1d > 0); share = count / 50 * 100",
        deep_dive=(
            "Same definition as `Overall Breadth` but framed as a percentage "
            "of the 50-name universe for quick mental anchoring (e.g. '32 / 50 "
            "= 64% advancing')."
        ),
    ),
    "kpi_losers": WidgetInfo(
        title="Losers (count + share)",
        short="How many stocks closed negative today, and what share of the universe that is.",
        formula="count(return_1d < 0); share = count / 50 * 100",
        deep_dive=(
            "Mirror of the Gainers KPI; useful for at-a-glance breadth on "
            "down days."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def tooltip(key: str) -> str:
    """Return a multi-line ``help=`` string for a widget key.

    Combines the short description and the formula into a single tooltip
    string suitable for any Streamlit primitive that accepts ``help=``
    (``st.metric``, ``st.column_config.NumberColumn``, ``st.checkbox``,
    etc.). Streamlit renders the string in a hover bubble with line
    breaks preserved.

    Args:
        key: One of the entries in :data:`WIDGETS`.

    Returns:
        A string of the form ``"{short}\\n\\nFormula: {formula}"`` if the
        key is registered; a generic fallback otherwise so callers are
        never broken by a typo.
    """
    info = WIDGETS.get(key)
    if info is None:
        return "No description available for this widget."
    return f"{info.short}\n\nFormula: {info.formula}"


def render_info(key: str, label: Optional[str] = None) -> None:
    """Render a deep-dive ``st.expander`` for the given widget key.

    Safe to call with an unknown key — emits a small ``st.caption`` rather
    than raising, so a typo never breaks the page.

    Args:
        key: One of the entries in :data:`WIDGETS`.
        label: Optional override for the expander header. If omitted the
            registered ``title`` is used.
    """
    info = WIDGETS.get(key)
    if info is None:
        st.caption(f"No info available for `{key}`.")
        return

    header_title = label or info.title
    with st.expander(f"ℹ️ About: {header_title}", expanded=False):
        st.markdown(f"**{info.short}**")
        st.markdown(f"_Formula:_ `{info.formula}`")
        st.markdown(info.deep_dive)
