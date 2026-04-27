# Nifty 50 Investment Monitoring Dashboard
# Nifty 50 Investment Monitoring Dashboard

## Project Identity

You are an expert Python/FastAPI/PostgreSQL engineer building a **Nifty 50 Investment Monitoring Dashboard** — a signal-detection and investment decision-support tool for Indian equity markets.

**Specification authority:** `docs/Nifty50_Dashboard_Specification_v1.0.md`
This document is the single source of truth for all product decisions, data models, view definitions, alert rules, and milestone sequencing. Read it before making any architectural or schema decision. Never contradict it without explicit user instruction.

---

## Users & Goals

Three personas drive every design decision:

| Persona | Role | Primary need |
|---|---|---|
| Rahul | Long-only fundamental investor | Identify accumulation zones, drawdown recovery candidates |
| Sanjana | Tactical momentum trader | Breakout alerts, 52-week high proximity, volume confirmation |
| Vikram | Risk officer | Portfolio concentration, drawdown exposure, event risk |

The dashboard must answer their daily questions within a single session, from 7 AM market prep through 9 PM post-close review.

---

## Tech Stack

### Prototype (build first)
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic
- **Database:** PostgreSQL 15+ (schema-first, typed columns, no raw JSON blobs for price data)
- **Data layer:** pandas for transforms, psycopg2/asyncpg for DB access
- **Frontend:** Streamlit (prototype only — keep UI logic in `dashboard/` separate from `api/`)
- **Scheduler:** APScheduler or simple cron for EOD data ingestion

### Production path (do not build yet, but do not foreclose)
- Frontend migrates to React + TypeScript
- Backend stays FastAPI
- Consider dbt for transform layer when data volume justifies it

---

## Repository Layout

```
nifty50-dashboard/
├── GEMINI.md                          ← this file
├── AGENTS.md                          ← cross-tool rules (commit to git)
├── docs/
│   └── Nifty50_Dashboard_Specification_v1.0.md   ← spec (source of truth)
├── api/
│   ├── main.py
│   ├── routers/
│   └── models/
├── dashboard/
│   └── app.py                         ← Streamlit entry point
├── ingestion/
│   ├── bhavcopy.py                    ← NSE EOD parser
│   ├── nifty50_constituents.py
│   └── corporate_actions.py
├── db/
│   ├── migrations/                    ← Alembic migrations
│   └── schemas.sql
├── tests/
│   └── ...
├── .agents/
│   ├── rules/
│   │   ├── data-pipeline.md
│   │   ├── api-design.md
│   │   └── testing.md
│   └── workflows/
│       ├── implement-milestone.md
│       ├── review-schema.md
│       └── run-tests.md
└── requirements.txt
```

---

## Database Schemas

Eight schemas are defined in the spec (§5). Implement exactly these — do not rename or restructure without reading the spec first:

1. `dim_stock` — master stock reference
2. `fact_eod_price` — daily OHLCV from NSE Bhavcopy (`sec_bhavdata_full_YYYYMMDD.csv`)
3. `fact_52wk` — 52-week high/low (`CM_52_wk_High_low_YYYYMMDD.csv`)
4. `dim_nifty50_constituent` — index membership with effective date ranges
5. `fact_corporate_action` — dividends, splits, bonuses, rights
6. `fact_event_calendar` — earnings, AGMs, board meetings
7. `fact_announcement` — NSE filing feed
8. `fact_iss_score` — ISS (Institutional Suitability Score) composite

Always use Alembic for schema changes. Never ALTER tables directly in ad-hoc SQL.

---

## Data Sources

### Primary (build pipelines for these)
- **NSE Bhavcopy EOD:** `sec_bhavdata_full_YYYYMMDD.csv` — daily OHLCV, volume, trades
- **52-week file:** `CM_52_wk_High_low_YYYYMMDD.csv` — 52W high/low reference
- **Nifty 50 constituents:** NSE/Nifty Indices official export — updated at semi-annual reconstitution (March, September)
- **Corporate actions feed:** NSE corporate actions CSV — dividends, splits, bonuses, rights
- **Event calendar:** Board meeting, AGM, earnings dates

### Intraday (secondary, lower priority)
- Vendor API (TrueData / Global Datafeeds style) — intraday OHLCV bars for live-refresh views only

### Validation only (never primary source)
- Moneycontrol, Chittorgarh, Screener, Investing.com — cross-checks only, never ingested into DB

---

## Dashboard Views

Seven views are specified in §4 of the spec. Implement in this order:

1. **Market Overview** — index level, breadth, top 5 gainers/losers (day/week/month/year)
2. **Movers & Extremes** — configurable return-period leaderboard, color-coded by magnitude
3. **Drawdown Scanner** — stocks down 20%+ from 52W high, with recovery trajectory
4. **Breakout Monitor** — stocks within 2% of 52W high with volume confirmation
5. **Volume Anomaly Monitor** — volume vs 20D average, spike detection
6. **Corporate Events Tracker** — upcoming dividends, splits, earnings in calendar view
7. **Watchlist Builder** — user-curated list with signal overlays

---

## Signal Logic & Alert Rules

14 alert rules are defined in §7 of the spec. Key rules:

- **Breakout signal:** Close ≥ 98% of 52W high AND today's volume ≥ 1.5× 20D avg volume
- **Deep drawdown:** Close ≤ 80% of 52W high (i.e. ≥20% off peak)
- **Volume spike:** Today's volume ≥ 2× 20D avg volume
- **Recovery signal:** Stock up ≥10% from 52W low AND improving for 5+ consecutive days
- **Momentum confirmation:** 1M return > 0 AND 3M return > 0 AND 6M return > 0

Do not invent new signal definitions. Implement exactly what the spec defines.

---

## Engineering Rules

### General
- Python 3.11+ with full type hints on all function signatures
- Docstrings on all public functions and classes (Google style)
- No hardcoded credentials — use environment variables via `python-dotenv`
- All DB queries through SQLAlchemy ORM or explicit parameterised SQL; no string concatenation
- Validate all user inputs before they reach business logic
- Keep routers thin — business logic lives in `services/`, data access in `repositories/`

### Data Pipeline
- Parse NSE CSV files with explicit `dtype` specs — never infer column types
- All date columns stored as `DATE` in PostgreSQL, never as strings
- Price values stored as `NUMERIC(12,2)` — never `FLOAT`
- Volume as `BIGINT`
- Idempotent ingestion: re-running a pipeline for the same date must not create duplicates (use `ON CONFLICT DO UPDATE`)
- Log every ingestion run with row counts to a `fact_ingestion_log` table

### API
- All endpoints return typed Pydantic response models
- Standard error shape: `{"error": "message", "code": "ERROR_CODE", "details": {}}`
- No direct DB access from route handlers — always go through service layer
- Include pagination on all list endpoints (`limit` / `offset`)

### Testing
- pytest for all tests
- Minimum 80% line coverage on new code
- Every signal calculation function must have a unit test with edge cases (empty series, single row, exactly-at-threshold)
- Integration tests for all API endpoints using `httpx.AsyncClient`
- Run tests before marking any task complete: `pytest tests/ -v --tb=short`

#### Integration Test
- After every phase completion, run the integration test suite `integration/scenario[1..n].py`. 
- IF NO INtegration Tests exists:
    - Create Sceanrios: Scan through the code base and the spec to come up with a list of test scenarios and create a scenario test for each udner `integration` directory. 
    - Run the  inetgration tests before starting implementation
    - After implemenation add any new scenarios to the `integration` dirctory

### Git
- Never commit directly to `main`
- Feature branches: `feature/<milestone>-<short-description>`
- Always run tests before committing: `pytest tests/ -v`
- Commit messages: `<type>(<scope>): <description>` (conventional commits)

---

## Milestone Sequencing

The spec defines 6 engineering phases (§9). Always work one milestone at a time:

| Phase | Focus |
|---|---|
| 1 | DB schema + Alembic migrations + seed data loader |
| 2 | NSE Bhavcopy ingestion pipeline |
| 3 | Return & signal calculation layer |
| 4 | FastAPI endpoints for all 7 views |
| 5 | Streamlit dashboard UI |
| 6 | Alert engine + scheduler |

Do not start Phase N+1 until Phase N has passing tests.

---

## Antigravity Agent Guidance

### Use Planning Mode for:
- Any new milestone kickoff
- Schema design decisions
- Refactoring across multiple files
- New signal logic implementation

### Use Fast Mode for:
- Adding a single endpoint
- Writing tests for an existing function
- Fixing a specific bug
- Updating a Pydantic model

### @ context to always include:
- `@docs/Nifty50_Dashboard_Specification_v1.0.md` when starting a new milestone
- `@db/schemas.sql` for any DB-related task
- `@api/models/` when modifying data models

### Workflows (trigger with `/`):
- `/implement-milestone` — kick off a new phase with spec review + plan
- `/review-schema` — review a migration before applying it
- `/run-tests` — run full test suite and summarise failures

### Terminal Allow List (safe to auto-execute):
```
pytest tests/ -v --tb=short
pytest tests/ -v -k
alembic upgrade head
alembic revision --autogenerate
alembic history
git status
git diff
git log --oneline -20
pip list
python -m py_compile
cat requirements.txt
ls -al
```

### Always require review before:
- `alembic downgrade`
- `DROP TABLE` or any destructive SQL
- `git push`
- Any `curl` or external network call during development
- `rm` on any file

---

## Anti-Patterns — Never Do These

- Do not fetch data from Moneycontrol, Screener, or any retail portal as a primary data source
- Do not store prices as `FLOAT` — always `NUMERIC(12,2)`
- Do not put business logic in FastAPI route handlers
- Do not skip migrations — never `Base.metadata.create_all()` in production code
- Do not hardcode ISINs, symbols, or index weights — read from `dim_stock` and `dim_nifty50_constituent`
- Do not add new dashboard views not in the spec without explicit user approval
- Do not rename spec-defined schema tables or columns without user confirmation

