# Session Summary — Dashboard Consolidation (single-page rewrite)

**Active branch:** `feature/dashboard-consolidation` (NOT pushed; do not push without user permission).
**Status as of 2026-05-11:** Phase 0 + Phase 1 of 10 complete. Phase 2 (Watchlist + ISS Gauge) is next.
**Visual contract:** `design/mock_consolidated.html` (locked).
**Implementation plan:** `docs/dashboard_consolidation_plan.md` (locked).

---

## How to resume in a fresh session

1. Read this file first.
2. Read `~/.claude/projects/-Users-birjoossh-brij-work-starfish/memory/dashboard_consolidation_progress.md` for current phase status table.
3. Read `docs/dashboard_consolidation_plan.md` §6 (Phase 2 task breakdown).
4. Confirm on the right branch: `git status` should show `feature/dashboard-consolidation`.
5. Start Task #14 (Phase 2 · §02 Watchlist + sticky ISS Gauge sidebar).

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
| **2 · §02 Watchlist + ISS Gauge** | **NEXT** | plan §6 |
| 3 · §03 Trend Workbench (NEW) | pending | biggest piece; new `/trend` endpoint + `services/trend_stats.py` + Plotly subplot |
| 4–8 · §04–§08 refactor | pending | reuse phase_f/phase_g; restyle to tokens; wire drill-in to §03 |
| 9 · Polish | pending | scrubber, keybindings, `use_container_width` migration, responsive, smoke test |

---

## Phase 2 — what to build next (per plan §6)

| Task | Spec |
|---|---|
| 2.1 | 4 category tabs: Contrarian / Momentum / Event-Driven / Volume-Confirmed |
| 2.2 | Watchlist table — columns: pin, symbol, company·sector, mcap, ISS bar (use `dashboard.primitives.iss_bar`), primary signal pill (`pill(label, kind)`), key reason text, last event, days on list |
| 2.3 | Sticky ISS Gauge sidebar (right 3/12) — Plotly Indicator gauge + 5 horizontal `factor_bar()` calls (Price Mom, Vol Quality, Drawdown/Recovery, Corp Event, Rel Strength). Sticky via CSS class `.sticky-sidebar` already in tokens.py. |
| 2.4 | CSV export button → `nifty50_watchlist_YYYYMMDD.csv` (FastAPI `/watchlist/export` already exists per `api/routers/watchlist.py:570`) |
| 2.5 | Pin persistence — YAML for now (existing `dashboard/watchlist.py`); SQLite migration is stretch |

**Backend gap to note in UI:** ISS scoring function not yet computed (TODOS Phase 2 deviation #3) → factor bars show "—" with a `pill("ISS pipeline pending", "warn")` until TODO-122 + ISS function land.

**Existing helpers to reuse:**
- `dashboard.watchlist.load_watchlist()` → `set[str]` of pinned symbols
- FastAPI `/watchlist/categories/<category>` (api/routers/watchlist.py:452) returns pre-built per-tab lists
- FastAPI `/watchlist/export` (api/routers/watchlist.py:570) emits the CSV stream
- Existing `dashboard/phase_g.py::render_watchlist_builder` has the old (pre-consolidation) implementation to mine for query patterns

**File to create:** `dashboard/section_watchlist.py` (avoid clashing with existing `dashboard/watchlist.py` which is the YAML loader). Module should export `render_watchlist_section(calc_date, signals_df)` and slot into `dashboard/app.py::_render_section_02_watchlist`.

---

## Previous session work (pre-consolidation, still in repo)

The earlier widget-info + percent-conversion work landed on `feature/dashboard-widget-info` and was merged into history before this consolidation effort started. Key takeaways still relevant:

- `dashboard/widget_info.py` is the 57-widget tooltip registry — every section in the new layout should still call `tooltip(key)` for column-help text and `render_info(key)` where the mock shows a "ℹ️ About" expander.
- Ratio-vs-percent: returns are stored as ratios in mart tables; ALWAYS multiply by 100 before display.
- See git log for `713574d`, `14434f2`, `c625a75`, `08f0410` for details.
