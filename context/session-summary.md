# Session Summary — Dashboard Widget Info + Data Layer Fixes

Branch: `feature/dashboard-widget-info` (pushed to `origin`, not yet merged to `main`).

## Completed Work

### 1. Per-widget info on every dashboard (`713574d`)
- New `dashboard/widget_info.py` — single registry of 57 widgets with `title`, `short` (≤120-char hover), `formula`, and `deep_dive` (markdown body that traces to the spec section it was derived from).
- Helpers: `tooltip(key)` returns a multi-line string for Streamlit's `help=` parameter; `render_info(key)` emits a `st.expander("ℹ️ About: …")` containing the deep-dive. Unknown keys fail soft with "No description available".
- Wired into `dashboard/app.py`, `dashboard/phase_f.py`, `dashboard/phase_g.py`, `dashboard/phase_i.py` via Streamlit primitives only:
  - `st.metric(..., help=tooltip(key))` for hover descriptions
  - `st.column_config.NumberColumn(..., help=tooltip(key))` for dataframe column headers
  - `render_info(key)` placed beneath section headers
- Honest annotations baked in where code diverges from spec (e.g. `momentum_tier` flags 80/65/50 vs spec 85/70/60; `iss_score` lists all seven factor weights).

### 2. Ratio → percent conversion + Vol window labels + aggregation windows (`14434f2`)
- Several mart columns are stored as **ratios** (`returns_engine.py`, `rs_engine.py`) but were being rendered with `%+.2f%%` which is just printf "two decimals + literal `%`" — so 0.0616 printed as `+0.06%` instead of `+6.16%`. Multiplied by 100 before display in:
  - `app.py` Sector Aggregation, Watchlist Signals, Mover Gainers / Losers, Primary Scanner
  - `phase_f.py` Momentum table (`rs_vs_nifty_3m`)
- Already-correct paths verified and left alone: `phase_g.py` watchlist categories (server-side `* 100` in `api/routers/watchlist.py`), `phase_i.py` mobile/desktop, app.py morning digest.
- Volume column labels now name the comparison window: `Vol` → `Vol 20D` everywhere `vol_ratio_1d` is shown; `Avg Vol` → `Avg Vol 20D`. Already-descriptive labels (`Vol 1D/20D`, `Vol 5D/20D`) left as-is.
- Every aggregated widget's deep-dive now leads with an explicit "**Aggregation window**" line naming the period and weighting (equal- vs cap-weighted).

### 3. wk52_loader percent fix + uniform 2-decimal precision (`c625a75`)
- `ingestion/framework/loaders/wk52_loader.py:227` stored `pct_from_high` and `pct_from_low` as **ratios** while the older `analytics/compute_52wk.py`, the spec, the slider (-50..-10), the alert engine (`< -20`), the watchlist contrarian filter, and the dashboard formatter all assume **percent**. Loader now multiplies by 100 and rounds to 4 decimals.
- All dashboard formatters standardized to **2 decimals**: every `%.0f`, `%+.1f%%`, `%.1f%%`, `%.1fx` → `%.2f`, `%+.2f%%`, `%.2f%%`, `%.2fx`. Inline f-strings (digest hover, mobile/desktop KPIs, event price impact) too.
- `widget_info.py` deep-dives for `return_1d/1m/3m`, `vol_ratio_1d`, `drawdown_pct`, `distance_from_low`, and `rs_vs_nifty_3m` now lead with an explicit **Storage unit** callout naming whether the column is stored as ratio or percent and noting the dashboard's display conversion.

### 4. Nifty 50 scope + dim_stock seed cleanup + 52w lookback bug (`08f0410`)
Three independent root causes were collapsing the Drawdown Scanner, Near-breakout radar, and RS-top-15 chart into a 2 653-row broader-market view with all-zero drawdowns. All fixed:
- **`ingestion/seed_stocks.py`** — `NIFTY50_SEED` had accumulated duplicates plus the broader NSE universe; every real Nifty 50 symbol had a later entry with `sector="N/A"` that won the `ON CONFLICT DO UPDATE`, and the loop hardcoded `nifty50_member=TRUE` for all 6 000+ rows. New helper `_real_nifty50_seed()` filters to entries with a real sector and dedupes by symbol. The seed function now resets `nifty50_member=FALSE` table-wide before re-upserting, so stale flags from prior bloated runs are cleared.
- **`analytics/compute_52wk.py`** — single-date branch used `LIMIT :lookback` on rows, not distinct trading dates. With ~2 650 symbols per date, `LIMIT 252` covered ~1/10 of a single day → `wk52_high == wk52_low == close` → `pct_from_high = 0`. Worked accidentally when universe was 50 stocks. Fixed with `SELECT DISTINCT trade_date` in the subquery.
- **`dashboard/phase_f.py::load_signals_for_phase_f`, `api/main.py` `/market-overview` and `/movers`** — all joined `dim_stock` but never filtered `d.nifty50_member = TRUE`. Added the filter to all three.

After applying the code fixes I re-ran the data pipeline: `seed_stocks` reset 4 166 stale flags and seeded 58 names; `compute_52wk` and `compute_signals` recomputed 2026-04-29 and 2026-05-05.

### Verification (Playwright)
- Drawdown Scanner: 18 real Nifty 50 names ≤ -20%, avg drawdown -17.98%, real sectors in the multiselect (Aerospace & Defence, Automobile, Construction, Financial Services, …).
- Near-breakout radar: correctly **empty** (broad weakness on 2026-05-05 — previously appeared "broken" because zero-drawdown junk was passing the `>= -5%` filter).
- RS vs Nifty (3M) top 15: real Nifty 50 names (JIOFIN, WIPRO, HDFCLIFE, ITC, INFY, HCLTECH, INDIGO, TCS, TRENT, NESTLEIND, HDFCBANK, KOTAKBANK, BAJFINANCE, …).
- Screenshots saved at the repo root: `drawdown_2026-05-05.png` (broken state), `drawdown_final.png`, `momentum_2026-05-05.png` (broken state), `momentum_final.png`, `momentum_rs_2026-05-05.png` (broken state), `rs_final.png`, plus a baseline `momentum_2026-04-27.png`.

## Current State

- Branch `feature/dashboard-widget-info` at `08f0410`, pushed to `origin`.
- **PR not yet opened** (the previous attempt failed because `gh` lacked GitHub credentials at the time). PR template body is staged at `/tmp/pr_body.md` from earlier in the session — the user may have opened the PR via the GitHub UI; not confirmed.
- Local dashboard reachable at `http://localhost:8501` (and API at `http://localhost:8000`) — `bash run.sh` was invoked during the session and not stopped, so the services may still be running.
- DB state after the data-pipeline re-run:
  - `dim_stock`: 6 438 rows total, **58** flagged `nifty50_member = TRUE`, **0** of those with N/A sector.
  - `mart_stock_signals` for 2026-04-29 and 2026-05-05 has been refreshed; drawdown values now span ~ -99% to 0 with only ~130 zeros (legitimate at-the-high cases).
- Memory written: none yet — see "Next Steps" if any are worth saving.

## Open Issues

1. **`rs_vs_nifty_3m` is 0.00 for every Nifty 50 name on 2026-05-05** even though `return_3m` has real values (e.g. ADANIPORTS +9.86%, ADANIENT +10.08%). Most likely cause: the Nifty 50 **index** close prices are missing from `fact_eod_price`, so `analytics/rs_engine.py` falls back to defaults. Need to confirm by querying for the index ticker (the spec says NIFTY 50 is tracked separately, exact symbol used by `rs_engine` not yet verified) and add it to the ingestion path. Not a dashboard bug.
2. **Out-of-order pipeline runs silently corrupt data**. The `wk52_loader` enrichment left-joins `fact_eod_price`; if bhavcopy hasn't been ingested yet for the same `trade_date` when wk52 runs, every `pct_from_high` defaults to `0.0` and the user only finds out via dashboard symptoms. Worth either making the loader fail loudly when the join is empty, or wiring an order check into `run_pipeline`.
3. **Mobile / desktop views in `phase_i.py`** were updated for precision but not re-tested in a small viewport via Playwright.
4. **`20MICRONS` is in the curated seed** with `sector="Materials"` but is not actually a Nifty 50 constituent. Cosmetic, easy to drop from `NIFTY50_SEED`.
5. **`tests/unit/test_framework_loaders.py`** passes (50/50) but does not cover the wk52 percent-vs-ratio invariant or the new `_real_nifty50_seed()` filter — both are good candidates for unit tests on a follow-up.

## Next Steps (in priority order)

1. **Open the PR** for `feature/dashboard-widget-info` if not already — body draft at `/tmp/pr_body.md`. After review, merge to `main`.
2. **Fix the Nifty 50 index ingestion gap** so `rs_vs_nifty_3m` populates: confirm the symbol used by `rs_engine.compute_rs`, add or fix the loader that puts the index close into `fact_eod_price`, then re-run `compute_signals` for the affected dates.
3. **Add a guard in `wk52_loader`** that raises (or marks the day as failed) when the close-price join produces zero rows, so silent zero-fill can't recur.
4. **Drop `20MICRONS` from `NIFTY50_SEED`** unless it is intentionally extended.
5. **Add unit tests** for `_real_nifty50_seed()` (dedup + sector filter) and for `wk52_loader._enrich_pct_columns` (asserting the percent unit).
6. **Optional cosmetic**: ISS scores now show two decimals everywhere per the user's "2 decimals across all values" instruction. If `78.00` reads as noisier than `78`, the user may want to special-case ISS to integer formatting — quick to revert.

## Key Files Touched This Session

| File | Why |
|---|---|
| `dashboard/widget_info.py` (new) | 57-entry registry of tooltips and deep-dives |
| `dashboard/app.py`, `phase_f.py`, `phase_g.py`, `phase_i.py` | Wired widget info, ratio→percent fixes, Vol-window labels, 2-decimal formatters |
| `ingestion/framework/loaders/wk52_loader.py` | Multiply pct_from_high/low by 100 (matches spec) |
| `analytics/compute_52wk.py` | `SELECT DISTINCT trade_date` lookback fix |
| `ingestion/seed_stocks.py` | `_real_nifty50_seed()` + reset stale `nifty50_member` flags |
| `api/main.py` | Add `nifty50_member = TRUE` filter to `/market-overview` and `/movers` |

## Useful Commands From This Session

```bash
# Re-seed dim_stock (resets bad nifty50_member flags + upserts curated 58)
python -m ingestion.seed_stocks

# Recompute 52w + signals for a specific date (no raw CSV required)
python -c "from datetime import date; from analytics.compute_52wk import compute_52wk; \
           compute_52wk(date.fromisoformat('2026-05-05'))"
python -c "from datetime import date; from analytics.compute_signals import compute_signals; \
           compute_signals(date.fromisoformat('2026-05-05'))"

# Restart dashboard + API
bash run.sh --stop && bash run.sh

# Sanity-check stored units in mart_stock_signals
PGPASSWORD=myuser1234 psql -h localhost -p 5433 -U myuser -d nifty50 -c "
SELECT calc_date, COUNT(*),
       MIN(drawdown_from_52w_high_pct), MAX(drawdown_from_52w_high_pct),
       SUM(CASE WHEN drawdown_from_52w_high_pct = 0 THEN 1 ELSE 0 END) AS zero_count
FROM mart_stock_signals GROUP BY calc_date ORDER BY calc_date DESC LIMIT 6;"
```
