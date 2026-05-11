# Session Summary — Dashboard Consolidation (single-page rewrite)

**Active branch:** `feature/dashboard-consolidation` (pushed to `origin` 2026-05-11; do not force-push).
**Status as of 2026-05-11:** Phases 0, 1, 2 of 10 complete. Phase 3 (Trend Workbench — biggest piece) is next.
**Visual contract:** `design/mock_consolidated.html` (locked).
**Implementation plan:** `docs/dashboard_consolidation_plan.md` (locked).

---

## How to resume in a fresh session

1. Read this file first.
2. Read `~/.claude/projects/-Users-birjoossh-brij-work-starfish/memory/dashboard_consolidation_progress.md` for current phase status table.
3. Read `docs/dashboard_consolidation_plan.md` §6 (Phase 2 task breakdown).
4. Confirm on the right branch: `git status` should show `feature/dashboard-consolidation`.
5. Start Task #15 (Phase 3 · §03 Trend Workbench — backend endpoint + period stats).

After each phase: `python -m py_compile dashboard/*.py` → `python3 .claude/skills/python-linter/scripts/python_linter.py dashboard/` → `AppTest.from_file('dashboard/app.py').run()` check for exceptions → review pass → update this file → update memory `dashboard_consolidation_progress.md` → commit.

---

## What was built

### Locked visual contract — `design/mock_consolidated.html`
1879-line static HTML+Tailwind mock with all 8 sections (§01–§08), realistic Nifty 50 dummy data, ink-black + saffron + serif aesthetic, hairline panels, treemap, calendar heatmap, etc. The Trend Workbench (§03, NEW) was added in response to "I can only see one date at a time — let me dig deeper into trends per stock/sector". This is the visual source of truth. Tokens (color, typography, spacing, primitives) come from here.

### Locked implementation plan — `docs/dashboard_consolidation_plan.md`
350+ lines. 10 phases, ~14.5 eng-days. Streamlit-first (React deferred). Includes per-phase task tables with acceptance criteria, Plotly mappings for every chart type, backend dependency map linking TODO-### entries to the UI elements they unblock, risks, and out-of-scope items.

### Phase 0 — Foundation (commit `376dea1`)
- **`dashboard/tokens.py`** — `inject_global_styles()` emits CSS variables, Google font imports (Instrument Serif, Geist, JetBrains Mono), and primitive classes (`.panel`, `.pill`, `.tag`, `.iss-bar`, `.sec-num`, `.kicker`, `.bar`, `.dot`, `.tricolor`, etc.) ported verbatim from the mock.
- **`dashboard/primitives.py`** — 10 reusable render helpers: `render_section_header(num, kicker, hint, right)`, `render_topbar(...)`, `render_brand_header(...)`, `render_footer()`, `tricolor_thread()`, `pill(label, kind)`, `tag(label, active)`, `gold_badge(...)`, `iss_bar(score)`, `factor_bar(value, color)`. All string inputs run through `html.escape`. `render_section_header`'s `right` param is intentionally unescaped — documented in its docstring.
- **`dashboard/app.py`** — Refactored from tabs to single-page. Sticky topbar → brand header + tricolor → calc-date picker → §01–§08 sections (§01–§03 always open; §04–§08 in `st.expander(expanded=True)`) → footer.

**Phase 0 review found & fixed:**
1. Alt+A/Alt+C keybinding JS via `components.v1.html` runs in a sandboxed iframe — cannot mutate parent expanders. Removed; deferred to Phase 9.
2. `render_section_header(right=)` docs now clearly state "trusted, unescaped — never pass user-supplied strings".
3. Removed `[data-testid="stToolbar"] {display:none}` (interfered with dev toolbar).

### Phase 1 — §01 Market Overview (commit `cd294a7`)
- **`dashboard/scanner.py`** — Shared Primary Scanner Pipeline:
  `SCANNER_DISPLAY_COLS`, `build_scanner_display_df(signals_df, watchlist)`, `scanner_column_config()`, `render_scanner_drilldown(signals_df, watchlist, *, title, key, sector=None, symbols=None)`. Used by §01 treemap/sector clicks; §04–§07 will use the same helper.
- **`dashboard/overview.py`** —
  - `fetch_market_overview(calc_date)` → cached GET `/market-overview` (60s TTL).
  - `render_overview(calc_date, signals_df, watchlist)` — main §01 renderer.
  - `render_morning_digest(signals_df, n=3)` — top-N ISS picks for header strip.
  - 5-card KPI strip: cards #1 (Nifty Index), #2 (52W bracket), #4 (Vol gauge) render as muted placeholders pending TODO-106 (NSE index prices). Cards #3 (Avg Constituent) and #5 (Breadth donut) compute from real signals.
  - Inline-SVG donut (`_donut_svg`) — three arc paths, single `st.markdown` call so `.panel` border wraps cleanly. Plotly chart-inside-markdown does NOT nest; learned the hard way.
  - Sector breadth table (5/12 cols, row-click drill) + Performance treemap (7/12 cols, cell-click drill). Drill dispatcher calls `render_scanner_drilldown` below the row.
- **`dashboard/app.py`** — Added `_load_signals(calc_date)` and `_load_watchlist()` caches; wired into §01.

**Phase 1 review found & fixed:**
1. Breadth-donut card had `st.markdown('<div panel>')` → `st.plotly_chart(...)` → `st.markdown('</div>')` — three separate Streamlit containers, the `<div>` never wrapped the chart. Replaced Plotly donut with inline SVG arc rendering.
2. Unescaped DB strings (symbol, sector) in HTML markdown interpolations → wrapped in `html.escape()` in morning_digest and scanner.render_scanner_drilldown.
3. Cosmetic `.replace('x', 'x', 1)` no-op removed from `render_morning_digest`.

### Known deprecation warnings (deferred to Phase 9)
Streamlit 1.56 warns that `use_container_width=True` will be removed after 2025-12-31; should be `width='stretch'`. Existing `phase_f.py`/`phase_g.py`/`phase_i.py` also use the old form. Project-wide change in Phase 9.

---

## Test / verification cadence per phase

```bash
source venv/bin/activate
python -m py_compile dashboard/*.py
python3 .claude/skills/python-linter/scripts/python_linter.py dashboard/
python -c "from streamlit.testing.v1 import AppTest; at = AppTest.from_file('dashboard/app.py', default_timeout=20); at.run(); print(at.exception, at.error)"
```

`AppTest` must report `ElementList()` for both `exception` and `error`. Any non-empty list = regression to fix before commit.

---

## Phase status table (mirror of memory)

| Phase | Status | Notes |
|---|---|---|
| 0 · Tokens + primitives + shell | DONE 2026-05-11, commit `376dea1` | |
| 1 · §01 Market Overview | DONE 2026-05-11, commit `cd294a7` | KPI cards #1/#2/#4 stubbed pending TODO-106 |
| 2 · §02 Watchlist + ISS Gauge | DONE 2026-05-11 | `section_watchlist.py` + inline-SVG mini-gauge + CSV export. Factor breakdown stubbed pending TODO-122. |
| **3 · §03 Trend Workbench (NEW)** | **NEXT** | biggest piece; new `/trend` endpoint + `services/trend_stats.py` + Plotly subplot |
| 4–8 · §04–§08 refactor | pending | reuse phase_f/phase_g; restyle to tokens; wire drill-in to §03 |
| 9 · Polish | pending | scrubber, keybindings, `use_container_width` migration, responsive, smoke test |

---

## Phase 3 — what to build next (per plan §7)

### Backend tasks

| Task | Spec |
|---|---|
| 3.1 | New endpoint `GET /trend?subject=&kind=stock|sector&period=` in `api/main.py` (or `api/routers/trend.py`). Returns `{ price_series, volume_series, sma_50, sma_200, rs_vs_nifty_series, iss_series, events, period_stats }`. Reads `fact_eod_price` + `mart_stock_signals` + `fact_corporate_event` (when populated). |
| 3.2 | New `services/trend_stats.py`: pure-pandas compute of period return, vs-Nifty α, max DD, realized vol (annualized), Sharpe (rf=6%), avg daily vol, avg delivery%, vol expansion days, RS rank vs Nifty 50, % days > SMA50. Unit tests for empty series / single row / threshold edges. |
| 3.3 | Sector aggregation: when `kind=sector`, equal-weight constituent series using `dim_nifty50_constituent` point-in-time membership. |

### Frontend tasks

| Task | Spec |
|---|---|
| 3.4 | Filter row (mode/subject chips/period/overlay toggles). State in `st.session_state.trend.*`. |
| 3.5 | Subject header: symbol · company · sector · ISIN · current price + 1D % + period return + 52W bracket + ISS now/avg. |
| 3.6 | Price chart panel — Plotly `make_subplots` 2/3-1/3: price line + area gradient + Nifty RS dashed + SMA50/200 dotted. `add_vline` per event with annotation. `hovermode='x unified'`. |
| 3.7 | Volume sub-chart — `go.Bar` synced x-axis · color by day return · 20D MA line in saffron. |
| 3.8 | Calendar heatmap — `go.Heatmap` 5 rows (Mon–Fri) × ~52 cols. Custom 7-bucket diverging colorscale. Hover: date · weekday · return %. |
| 3.9 | Stats sidebar — 12-row table from period_stats + inline ISS sparkline. Sticky via `.sticky-sidebar` class already in tokens.py. |
| 3.10 | Events ledger — top-5 by significance in window. |
| 3.11 | Sector trend strip — 13 mini-tiles · 1M sparkline + return per sector. Click tile → flips Workbench to Sector mode. |
| 3.12 | Drill-in wiring: row click in §02/§04–§08 sets `st.session_state.trend_subject` and rerenders §03. |

**Backend gaps to handle gracefully:**
- `iss_score` constant 0.0 → ISS series falls back to a flat line with "ISS pipeline pending" pill (consistent with §02).
- `rs_vs_nifty_*` = 0.0 (TODOS deviation #2) → hide RS overlay + show pill "RS unavailable — index prices pending TODO-106".
- `fact_corporate_event` table empty (TODO-119/120) → no event markers + "no events in window" annotation.

**File to create:** `dashboard/section_trend.py` exporting `render_trend_section(calc_date, signals_df)`. Plus `api/routers/trend.py` for the new endpoint and `services/trend_stats.py` for stats logic.

---

## Previous session work (pre-consolidation, still in repo)

The earlier widget-info + percent-conversion work landed on `feature/dashboard-widget-info` and was merged into history before this consolidation effort started. Key takeaways still relevant:

- `dashboard/widget_info.py` is the 57-widget tooltip registry — every section in the new layout should still call `tooltip(key)` for column-help text and `render_info(key)` where the mock shows a "ℹ️ About" expander.
- Ratio-vs-percent: returns are stored as ratios in mart tables; ALWAYS multiply by 100 before display.
- See git log for `713574d`, `14434f2`, `c625a75`, `08f0410` for details.
