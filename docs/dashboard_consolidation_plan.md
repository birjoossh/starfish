# Dashboard Consolidation — Implementation Plan

**Status:** Design locked · 2026-05-11
**Visual source of truth:** `design/mock_consolidated.html`
**Target stack:** Streamlit (port into existing `dashboard/` modules)
**Production migration target:** React + TS (deferred; mock kept as 1:1 visual contract)

---

## 1. Design contract (locked)

### Sections

| # | Section | Mode |
|---|---|---|
| §01 | Market Overview | always open (hero) |
| §02 | Watchlist · Auto-curated + Pinned | always open (hero) |
| §03 | Trend Workbench · Multi-Day Analysis | always open (NEW) |
| §04 | Movers & Extremes | collapsible · default open |
| §05 | Drawdown Scanner | collapsible · default open |
| §06 | Breakout & Momentum Monitor | collapsible · default open |
| §07 | Volume Anomaly Monitor | collapsible · default open |
| §08 | Corporate Events Tracker | collapsible · default open |

### Visual tokens

- **Type:** Instrument Serif (display) · Geist (body) · JetBrains Mono (data, tabular nums)
- **Color:** ink-black `#0A0A0B` base · parchment `#F4F4F0` text · saffron `#F4A340` accent · pos `#4ADE80` · neg `#F87171` · warn `#FBBF24` · info `#60A5FA` · evt `#A78BFA`
- **Surfaces:** 1px hairline panels (`#26262C`) — no chunky cards · subtle SVG noise overlay · tricolor thread (saffron→white→green) under brand band
- **Density:** 13px base · tabular numbers everywhere · row hover `#1C1C20`
- **Pills:** thin-outlined, semantic color · small caps · monospace
- **Tags:** square 1px border, monospace 10px, used for filter chips

### Component primitives

| Primitive | Implementation |
|---|---|
| `panel` / `sub` | bordered surface, two depths |
| `pill` (pos/neg/warn/info/acc/evt) | semantic outlined chip |
| `tag` | filter chip / period selector |
| `iss-bar` | horizontal track + numeric label |
| `bar` | inline progress bar (used in ISS factor breakdown, Top-15 momentum) |
| `tm-cell` | treemap cell with sym + return |
| `vh-cell` | volume heatmap cell |
| `gauge` / `mini-gauge` | conic-gradient arc (Plotly Indicator in app) |
| `donut` | conic-gradient (Plotly pie in app) |
| `spark` | inline SVG line (Plotly mini-chart in app) |
| `sec-num` + `kicker` + `sec-rule` | section header trio |

---

## 2. Architecture

### Structure

```
dashboard/
├── app.py                  ← single-page entry, layout shell
├── tokens.py               ← NEW · injects global CSS (vars, fonts, primitives)
├── primitives.py           ← NEW · render_panel, render_pill, render_iss_bar, …
├── overview.py             ← NEW · §01 Market Overview
├── watchlist.py            ← UPDATE · §02 Watchlist + ISS gauge sidebar
├── trend.py                ← NEW · §03 Trend Workbench
├── phase_f.py              ← REFACTOR · §04 Movers, §05 Drawdown, §06 Momentum, §07 Volume
├── phase_g.py              ← REFACTOR · §08 Corporate Events
├── phase_i.py              ← keep (advanced metrics)
└── widget_info.py          ← keep (tooltip glossary)
```

### State (st.session_state)

| Key | Owner | Purpose |
|---|---|---|
| `calc_date` | top selector | Single-date snapshot for §01–§02, §04–§08 |
| `trend.subject` | §03 + drill clicks | Symbol or sector currently focused in Workbench |
| `trend.mode` | §03 | "stock" / "sector" / "compare" |
| `trend.period` | §03 | 1M / 3M / 6M / 1Y / 3Y / YTD / Custom |
| `trend.overlays` | §03 | dict of bool flags |
| `watchlist.tab` | §02 | active category tab |
| `watchlist.selected` | §02 | symbol whose ISS gauge renders |
| `watchlist.pins` | §02 + persistence | user-pinned symbols |

### API surface needed

| Endpoint | Used by | Status |
|---|---|---|
| `GET /market-overview?calc_date=` | §01 | exists |
| `GET /movers?calc_date=` | §04 | exists |
| `GET /signals?calc_date=` | §02, §05–§07 | partial (mart_stock_signals) |
| `GET /trend?subject=&kind=stock\|sector&period=` | §03 | **NEW · build in Phase 3** |
| `GET /events?range_from=&range_to=` | §08 | **NEW · blocked on TODO-119/120** |
| `GET /volume-anomaly?calc_date=` | §07 | **NEW · blocked on TODO-123** |

### Plotly mappings (mock → real)

| Mock element | Plotly approach |
|---|---|
| KPI sparkline | `go.Scatter` mode=`lines`, no axes, height ~32px |
| Treemap with size + color | `px.treemap` (already used) — switch values to `market_cap_cr` once `dim_stock` hydrated |
| Breadth donut | `go.Pie` with `hole=0.65` |
| Vol gauge | `go.Indicator` mode=`gauge+number` |
| Mini ISS gauge (sidebar) | `go.Indicator` smaller, +5 horizontal bars below |
| Calendar heatmap | `go.Heatmap` 5×52 matrix · custom colorscale · hover with date+return |
| Volume bars under price | `go.Bar` synced x-axis with price subplot |
| Price+RS+SMA overlay | `make_subplots` shared x · stacked price (2/3) + volume (1/3) |
| Event markers on price | `add_vline` + `add_annotation` per event |
| Crosshair tooltip | Plotly default hover; styled via `hoverlabel` |
| Vol-ratio 50-cell heatmap | `go.Heatmap` 5×10 · symbol labels in `text` |
| Top-15 momentum bars | `go.Bar` orientation=`h` · color per quality tag |

---

## 3. Phasing

Each phase has acceptance criteria. Do not start phase N+1 until phase N's tests pass.

| Phase | Focus | Est. days |
|---|---|---|
| 0 | Design tokens · layout shell · primitive helpers | 1.5 |
| 1 | §01 Market Overview (port + extend) | 2 |
| 2 | §02 Watchlist + ISS Gauge sidebar | 1.5 |
| 3 | §03 Trend Workbench (NEW) — biggest piece | 4 |
| 4 | §04 Movers & Extremes | 1 |
| 5 | §05 Drawdown Scanner | 1 |
| 6 | §06 Breakout & Momentum Monitor | 1 |
| 7 | §07 Volume Anomaly Monitor | 1.5 |
| 8 | §08 Corporate Events Tracker | 1 (blocked on TODO-119/120 ingestion) |
| 9 | Cross-cutting polish: status bar · date scrubber · tricolor · keybindings | 1 |

**Total:** ~14.5 engineering days · single-stream

---

## 4. Phase 0 — Design tokens + layout shell

**Goal:** Visual-token foundation everything else builds on.

| Task | Description | Acceptance |
|---|---|---|
| **0.1** Create `dashboard/tokens.py` | Single function `inject_global_styles()` that emits the CSS variables, font imports, and primitive classes from the mock's `<style>` block. Called once at top of `app.py`. | `app.py` after refactor matches mock typography and color exactly |
| **0.2** Create `dashboard/primitives.py` | Helpers: `render_pill(label, kind)`, `render_iss_bar(score)`, `render_section_header(num, kicker, hint)`, `render_panel(content)`, `render_kpi(label, value, delta, sparkline)` | All §01 widgets in Phase 1 use these helpers, not inline HTML |
| **0.3** Refactor `app.py` skeleton | Remove `st.tabs(...)`. Replace with vertical sections via `st.container()` + `st.expander()` for collapsibles. Hero sections (§01–§03) outside expanders. | Empty page renders 8 numbered section headers in correct order |
| **0.4** Top status bar + brand header | NSE status, date, last-load timestamp; brand wordmark with tricolor thread. | Top of page matches mock visually |
| **0.5** Footer with keybindings | Ports the bottom strip + `Alt+A` / `Alt+C` accordion controls (component-mounted JS via `streamlit.components.v1.html`) | Keybindings work; visual matches |
| **0.6** Compile-check + lint | `python -m py_compile dashboard/**/*.py` and python-linter skill | No errors |

**Deliverable:** Empty layout shell that loads, looks correct, contains no widgets.

---

## 5. Phase 1 — §01 Market Overview

**Goal:** Single-screen daily briefing — KPI strip + breadth + heatmap.

| Task | Description | Acceptance |
|---|---|---|
| **1.1** Morning Digest strip | Top 3 ISS picks under brand header. Reuse logic from current `app.py:113-130`. | Renders 3 cards with company, ISS, 1D return, signal |
| **1.2** Calc-date selector | Single-date dropdown. Range scrubber deferred to Phase 9. | Dropdown above §01 with last 250 dates; selection drives `st.session_state.calc_date` |
| **1.3** KPI strip (5 cards) | Index level, 52W bracket, Avg constituent (with breadth divergence pill), Vol gauge, Breadth donut. Use Plotly Indicator for gauge, Plotly Pie for donut. Inline sparkline = small `go.Scatter`. | All 5 cards render with real data; nulls handled gracefully |
| **1.4** Sector Breadth table | 13 rows × 8 cols including ISS bar. Row click → drill into Primary Scanner subset (existing helper `_render_scanner_drilldown`). | Sortable, filterable, click-drill works |
| **1.5** Performance heatmap | Treemap with three tabs: 1D / 1M / 1Y. Cells sized by `market_cap_cr` (fallback to `iss_score`). Color anchored to p5/p95 of return distribution daily. | All 50 stocks render; tab switch redraws |
| **1.6** Heatmap drill | Click cell → drill into Primary Scanner subset. Already wired in current `app.py:297-335`. | Existing behavior preserved |

**Backend gaps logged:** none for §01 — all data exists.

---

## 6. Phase 2 — §02 Watchlist

**Goal:** ISS-driven curation + sticky factor breakdown.

| Task | Description | Acceptance |
|---|---|---|
| **2.1** Four category tabs | Contrarian / Momentum / Event-Driven / Volume-Confirmed. Population logic from spec §7 (View 7). | Tab switch repopulates table from same `signals_df` slice |
| **2.2** Watchlist table | Columns: pin, symbol, company·sector, mcap, ISS bar, primary signal pill, key reason text, last event, days on list. Pin column writes to `watchlist.pins`. | Table renders 8+ rows correctly; pin toggle works |
| **2.3** ISS Gauge sidebar | Plotly mini-Indicator + 5 horizontal factor bars (Price Mom, Vol Quality, Drawdown/Recovery, Corp Event, Rel Strength). Sticky position via injected CSS `position:sticky`. | Sidebar updates on row select; stays visible on scroll |
| **2.4** CSV export | Button at top right of table → `nifty50_watchlist_YYYYMMDD.csv` with metadata row. | Download button produces correct CSV |
| **2.5** Pin persistence | Currently YAML-based. Continue with YAML for now (stretch: SQLite-backed user profile in Phase 9). | Pins survive page reload |

**Backend gaps logged:**
- ISS scoring not yet computed (TODOS Phase 2 deviation #3) → factor bars stub at "—" with "ISS pipeline not yet wired" pill until TODO-122 + ISS function land.
- Signal categories use wrong labels (TODOS deviation #1) → fix before §02 ships.

---

## 7. Phase 3 — §03 Trend Workbench (NEW)

**Goal:** Multi-day price + volume + ISS over time, per stock or sector.

### Backend

| Task | Description | Acceptance |
|---|---|---|
| **3.1** New endpoint `GET /trend` | Params: `subject` (symbol or sector slug), `kind` (stock\|sector), `period` (1M\|3M\|6M\|1Y\|3Y\|YTD\|custom + from/to). Returns `{ price_series, volume_series, sma_50, sma_200, rs_vs_nifty_series, iss_series, events, period_stats }`. Backed by `fact_eod_price` + `mart_stock_signals` + `fact_corporate_event`. | curl returns valid JSON for `subject=RELIANCE&period=6M` |
| **3.2** Period stats computation | `services/trend_stats.py`: period return, vs-Nifty α, max DD, realized vol, Sharpe (rf=6%), avg vol, avg delivery%, vol expansion days, RS rank, % days > SMA50, ISS now/avg. Pure pandas. | Unit tests cover empty series, single row, threshold edges |
| **3.3** Sector aggregation | When `kind=sector`, equal-weight constituent series · membership from `dim_nifty50_constituent` (point-in-time). | Returns aggregated daily series + sector-level stats |

### Frontend

| Task | Description | Acceptance |
|---|---|---|
| **3.4** Filter row | Mode toggle, subject chips with add/remove, period selector, overlay toggles (Events / 52WH-L / RS / SMA50 / SMA200). All write to `st.session_state.trend.*`. | Changing any filter reruns the chart |
| **3.5** Subject header | Symbol · company · sector · ISIN · current price + 1D % + period return + 52W bracket + ISS today/avg. | Mirrors mock left/right alignment |
| **3.6** Price chart panel | Plotly subplot 2/3-1/3: price line + area gradient + Nifty RS dashed + SMA50/200 dotted. `add_vline` per event with annotation. Crosshair via Plotly `hovermode='x unified'`. | Renders 6M of RELIANCE with all overlays |
| **3.7** Volume sub-chart | `go.Bar` synced x-axis · color by day return · 20D MA line in saffron · spike highlight outline. | Bars align with price ticks |
| **3.8** Calendar heatmap | `go.Heatmap` 5 rows (Mon–Fri) × ~52 cols. Custom 7-bucket diverging colorscale (red→neutral→green). Hover: date · weekday · return %. | 252-cell matrix renders; hover works |
| **3.9** Stats sidebar | 12-row dense table from `period_stats`. ISS trend mini-spark via `go.Scatter`. | All values populated; sticky position |
| **3.10** Events ledger | List of in-window events with date pill + type pill + reaction %. | Top-5 by significance |
| **3.11** Sector trend strip | 13 mini-tiles below main panel · 1M sparkline + return. Click tile → flips Workbench to Sector mode with that sector. | Click sets `trend.mode='sector'`, `trend.subject=` |
| **3.12** Drill-in wiring | Add row click handlers in §02, §04, §05, §06, §07, §08 tables that set `trend.subject` and scroll to §03. | Click any row → §03 re-renders for that symbol |

**Backend gaps logged:**
- `iss_score` not computed → ISS series falls back to constant ISS bar with "Not yet computed" annotation
- `rs_vs_nifty_*` = 0.0 (TODOS deviation #2) → RS overlay shown only when nifty_index_prices populated (TODO-106). Otherwise hide overlay + show pill "RS unavailable — index prices pending".
- Corporate events table empty (TODO-119) → events overlay degrades to "no events in window"

---

## 8. Phase 4 — §04 Movers & Extremes

| Task | Description |
|---|---|
| **4.1** Filter bar (Period · Mcap tier · Sector · Nifty50 toggle) writing to `st.session_state.movers.*` |
| **4.2** Top-10 gainers + losers tables (existing `get_movers_data`, restyled to mock columns) |
| **4.3** Return × Volume scatter — Plotly · quadrant lines · sector color · marker size = mcap · gold border on top-right outliers |
| **4.4** Row click → set `trend.subject` (Phase 3.12 dependency) |

---

## 9. Phase 5 — §05 Drawdown Scanner

| Task | Description |
|---|---|
| **5.1** Filter bar (Threshold · Period · Sector · Mcap) |
| **5.2** 3 KPI cards: # 3M < −20% · # 1Y < −20% · Avg DD from 52WH |
| **5.3** Drawdown table with signal tags. Tag logic per spec §6.2: Accumulation · Falling Knife · Needs Event Review |
| **5.4** 1Y sparkline column via inline mini Plotly per row OR HTML+SVG for performance |
| **5.5** Reuse current `phase_f.render_drawdown_tab` as the basis; restyle to new tokens |

---

## 10. Phase 6 — §06 Breakout & Momentum Monitor

| Task | Description |
|---|---|
| **6.1** Filter bar (Period · Threshold · Volume Confirmation · Min ISS) |
| **6.2** Momentum table with 4-tier quality tag (Volume-Confirmed · Event-Driven Pop · Thin Volume · Squeeze Risk) + Triple Confirmation badge |
| **6.3** Top-15 horizontal bar chart, color per quality tag |
| **6.4** Reuse `phase_f.render_momentum_tab` as the basis; align tag categories with spec §6.2 |

---

## 11. Phase 7 — §07 Volume Anomaly Monitor

| Task | Description |
|---|---|
| **7.1** 3 spike sub-tables (1.2× / 1.5× / 2×) with badges A/B/C |
| **7.2** Volume Contraction sub-table |
| **7.3** 50-cell vol-ratio heatmap (Plotly Heatmap 5×10 with symbol labels) |
| **7.4** Education sidebar (collapsible, 4 paragraph block) |
| **7.5** "Unexplained Spike" badge logic: ratio > 3× AND no event within ±5d |

**Backend gap:** `mart_volume_anomaly` empty (TODO-123). Build view materialization function `services/volume_anomaly.py` as part of this phase.

---

## 12. Phase 8 — §08 Corporate Events Tracker

| Task | Description |
|---|---|
| **8.1** Filter bar (Date range · Event type · Symbol search · Significance ≥ N · Follow-up flag) |
| **8.2** Events table with type pill, summary, +1D/+5D/+20D reaction columns, 1–5 star significance, follow-up checkbox |
| **8.3** Inline 20-day pre/post sparkline column with vertical event marker |
| **8.4** Row tinting: blue for upcoming · red stripe for regulatory · purple stripe for M&A/large-order |

**Blocking dependencies (TODOS):**
- TODO-116 `fact_corporate_action` table populated
- TODO-119 `fact_corporate_event` table populated
- TODO-117 purpose_parser implemented
- TODO-120 keyword classifier
Until these land, §08 renders an empty-state panel with the data-source breadcrumb.

---

## 13. Phase 9 — Cross-cutting polish

| Task | Description |
|---|---|
| **9.1** Date range scrubber in top bar — slider through last 250 trading days |
| **9.2** "Compare to" delta selector (Δ vs 1D / 1W / 1M) — adds Δ columns where useful |
| **9.3** Keyboard nav: `↑↓` row · `⇧↩` drill · `/` filter · `e` export · `w` watchlist · `?` help · `Alt+A/C` accordions |
| **9.4** Responsive breakpoints: tablet (≥1024px) collapses 9-3 grids to stacked |
| **9.5** Loading skeletons for slow queries (Trend Workbench charts) |
| **9.6** Integration smoke test (`integration/scenario_consolidated_dashboard.py`) — Streamlit boots, all 8 sections present, no traceback for empty-data states |

---

## 14. Backend dependency map

| TODOS-### | UI element blocked | Phase that surfaces it |
|---|---|---|
| TODO-103 (delivery data) | Volume anomaly delivery% column · ISS Factor 2 | 7 |
| TODO-106 (Nifty index prices) | RS overlay (Trend Workbench) · ISS Factor 2 | 3, 6 |
| TODO-111 (constituents) | Point-in-time membership for sector aggregation | 3 |
| TODO-116 / TODO-119 (corp action/event tables) | Events ledger · §08 entire view | 3, 8 |
| TODO-122 (mart_stock_signals all cols) | ISS gauge · all signal pills | 1, 2, 5, 6 |
| TODO-123 (mart_volume_anomaly) | §07 spike sub-tables · 50-cell heatmap | 7 |
| ISS scoring function (Phase 2 spec) | ISS bars everywhere · gauge breakdown | 2 |
| Signal classification per spec §6.2 | Pill labels (Accumulation / Momentum / EventDriven / Neutral) | 1, 2, 5, 6 |

UI degrades gracefully where backend is missing — no UI work waits on backend in any phase, but section is "feature-complete" only when both UI and data land.

---

## 15. Acceptance gate per phase

Run before declaring a phase done:

```
source venv/bin/activate
python -m py_compile dashboard/*.py
pytest tests/ -v --tb=short
streamlit run dashboard/app.py
```

Visual diff: open mock + live app side-by-side, confirm density, color, type, and component placement match.

Run integration test: `pytest integration/scenario_consolidated_dashboard.py -v`

---

## 16. Risks

| Risk | Mitigation |
|---|---|
| Streamlit `position:sticky` for ISS sidebar may not behave inside flex grids | Fall back to repeating the gauge above the table on scroll, or use `st.sidebar` (loses two-column layout) |
| 252-cell heatmap re-render on every filter change is slow | Cache via `@st.cache_data(ttl=60)` keyed on `(symbol, period)` |
| Plotly hover tooltip cannot match the mock's custom tooltip box exactly | Use Plotly's `hoverlabel` + `hovertemplate`; document the visual delta |
| Drill-in row click in `st.dataframe` requires `on_select="rerun"` — works for single row but multi-section coordination is fragile | Centralize via `st.session_state.trend.subject` and a small dispatch layer |
| Custom font loading (Instrument Serif, Geist, JetBrains Mono) over CDN may flash unstyled content | Preload via `<link rel="preload">` in injected CSS |

---

## 17. Out of scope

- Real-time intraday refresh (Streamlit + EOD only, per spec §13)
- Mobile breakpoint design
- Internationalization
- User accounts / auth
- Alerting (Phase 5 of overall product roadmap, separate plan)
- React migration (deferred; mock kept as 1:1 contract for future port)
