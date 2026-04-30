# Phases G, H, I - Tech Implementation Plan

**Date:** 2026-04-18  
**Project:** Starfish · Nifty 50 Investment Monitoring Dashboard  
**Status:** Pre-implementation planning

---

## Executive Summary

This document outlines the technical implementation plan for **Phases G, H, and I** of the Starfish dashboard, building upon the completed Phases A-F.

| Phase | Focus | Duration Est. | Key Deliverables |
|-------|-------|---------------|------------------|
| **G** | Views 6-7: Events Tracker + Watchlist Builder | 1-2 weeks | Event timeline view, persistent watchlist |
| **H** | Alert Rules + EOD Scheduler | 1-2 weeks | 14 alert rules, batch scheduler |
| **I** | Backfill + Hardening | 1-2 weeks | 5-year backfill, mobile layout, notifications |

---

## Phase G: View 6 (Events Tracker) + View 7 (Watchlist Builder)

### Current State
- Phase E populated `fact_corporate_event` and `fact_corporate_action`
- `dashboard/watchlist.py` loads from YAML (read-only, no persistence)
- View 6 and View 7 are deferred in PROJECT_STATUS.md

### Specification Requirements

#### View 6: Corporate Events Tracker (Spec §8.3)
> **Purpose:** Provide a unified, chronological feed of all material corporate events for Nifty 50 companies, with pre- and post-event price context built in.

**Layout (Spec §4):**
- Row 1: Event timeline (upcoming, recent, filtered by type)
- Row 2: Event details modal with price impact context

**API Endpoints Required:**
- `GET /events` - Already exists (lists events with filters)
- `GET /events/{symbol}` - Symbol-specific events
- `GET /events/upcoming` - Future events only
- `GET /events/filtered` - Type + date range filters

**Schema (from `fact_corporate_event`):**
```sql
CREATE TABLE fact_corporate_event (
    event_id               BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol                 VARCHAR(20)   NOT NULL,
    event_date             DATE          NOT NULL,
    event_type             VARCHAR(50)   NOT NULL CHECK (event_type IN ('Earnings', 'Leadership_Change', 'M&A', 'Large_Order', 'Pledging_Change', 'Rating_Change', 'Regulatory', 'Other')),
    event_summary          VARCHAR(500)  NOT NULL,
    raw_announcement_text  TEXT,
    categorization_method  VARCHAR(20)   NOT NULL CHECK (categorization_method IN ('Manual', 'Rule', 'NLP')),
    significance_score     INTEGER       NOT NULL CHECK (significance_score BETWEEN 1 AND 5),
    price_chg_1d           DECIMAL(8,4),
    price_chg_5d           DECIMAL(8,4),
    price_chg_20d          DECIMAL(8,4),
    volume_spike_flag      BOOLEAN       NOT NULL DEFAULT FALSE,
    follow_up_required     BOOLEAN       NOT NULL DEFAULT FALSE
);
```

#### View 7: Watchlist Builder (Spec §4, §10.4)
> **Purpose:** Auto-generate a curated, rules-based watchlist of actionable Nifty 50 candidates, classified by signal type, with a transparent composite scoring system.

**Layout (Spec §4.7):**
- Row 1: Four section tabs:
  - **Contrarian Opportunities** - Deep drawdown + volume contraction + ISS > 50
  - **Momentum Leaders** - ISS > 70 + RS > 0 + momentum_flag = TRUE
  - **Event-Driven Candidates** - event_flag = TRUE + upcoming event within 10 days
  - **Volume-Confirmed Movers** - vol_ratio_1d > 2.0 + return_1d > 0
- Row 2: Watchlist table (75%) + ISS Score Gauge panel (25%)
- Row 3: Export and pin controls

**Watchlist Table (Spec §4.7):**
| Attribute | Detail |
|-----------|--------|
| Symbol, Company, Sector | Basic identity |
| Signal Category | ACC / MOM / EVT / Neutral |
| ISS Score | 0-100, color-coded badge |
| 1D Return % | Day performance |
| 1M Return % | Month performance |
| Volume Ratio | Today vs 20D avg |
| Added Date | First entry into watchlist |
| Added Reason | User-provided annotation |
| Remove button | Manual removal |

### Implementation Tasks

#### G.1: Database Schema Extensions
**File:** `sql/migrations/004_phase_g_watchlist.sql`

```sql
-- Watchlist users table (for multi-user support)
CREATE TABLE IF NOT EXISTS watchlist_users (
    user_id       BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username      VARCHAR(50)   NOT NULL UNIQUE,
    email         VARCHAR(100)  NOT NULL,
    created_at    TIMESTAMP     NOT NULL DEFAULT NOW()
);

-- User watchlist items
CREATE TABLE IF NOT EXISTS user_watchlist (
    watchlist_id  BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       BIGINT        NOT NULL,
    symbol        VARCHAR(20)   NOT NULL,
    added_date    DATE          NOT NULL DEFAULT CURRENT_DATE,
    reason        VARCHAR(255),
    pinned        BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMP     NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES watchlist_users(user_id),
    FOREIGN KEY (symbol) REFERENCES dim_stock(symbol)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_watchlist_unique ON user_watchlist (user_id, symbol);
CREATE INDEX IF NOT EXISTS idx_user_watchlist_user ON user_watchlist (user_id);

-- Alerts table (for Phase H)
CREATE TABLE IF NOT EXISTS alerts (
    alert_id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_name        VARCHAR(20)   NOT NULL CHECK (alert_name LIKE 'A-__'),
    symbol            VARCHAR(20),
    triggered_at      TIMESTAMP     NOT NULL DEFAULT NOW(),
    trigger_value     JSONB         NOT NULL,
    user_ids_to_notify BIGINT[]     NOT NULL DEFAULT '{}',
    delivery_status   VARCHAR(20)   NOT NULL DEFAULT 'Pending' CHECK (delivery_status IN ('Pending', 'Sent', 'Failed')),
    dedup_key         VARCHAR(100),
    severity          VARCHAR(20)   NOT NULL DEFAULT 'Medium' CHECK (severity IN ('Critical', 'High', 'Medium', 'Low'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts (triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_dedup ON alerts (alert_name, symbol, dedup_key);
```

#### G.2: API Endpoints (`api/routers/`)
**Files:** `api/routers/events.py`, `api/routers/watchlist.py`

**events.py**
```python
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/events", tags=["corporate-events"])

class EventResponse(BaseModel):
    event_id: int
    symbol: str
    event_date: str
    event_type: str
    significance: int
    description: str
    is_upcoming: bool
    price_chg_1d: Optional[float]
    price_chg_5d: Optional[float]
    price_chg_20d: Optional[float]

@router.get("", response_model=list[EventResponse])
async def list_events(
    symbol: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    event_type: Optional[str] = None,
    min_significance: int = 1
):
    """List corporate events with filters"""

@router.get("/upcoming", response_model=list[EventResponse])
async def get_upcoming_events(days_ahead: int = 30):
    """Get upcoming events within N days"""

@router.get("/timeline", response_model=dict)
async def get_event_timeline(
    from_date: str,
    to_date: str,
    event_type: Optional[str] = None
):
    """Return events grouped by date for calendar view"""
```

**watchlist.py**
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

class WatchlistItem(BaseModel):
    symbol: str
    added_date: str
    reason: Optional[str]
    pinned: bool

class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]
    total_count: int

@router.get("", response_model=WatchlistResponse)
async def get_user_watchlist(user_id: int = 1):  # Default for MVP
    """Get current user's watchlist"""

@router.post("", response_model=WatchlistItem)
async def add_to_watchlist(symbol: str, reason: Optional[str] = None):
    """Add symbol to watchlist"""

@router.delete("/{symbol}")
async def remove_from_watchlist(symbol: str):
    """Remove symbol from watchlist"""

@router.post("/{symbol}/pin")
async def toggle_pin(symbol: str, pinned: bool = True):
    """Pin/unpin a watchlist item"""
```

#### G.3: Analytics Logic (`analytics/`)
**File:** `analytics/watchlist_builder.py`

```python
def get_contrarian_opportunities(df: pd.DataFrame, min_iss: float = 50) -> pd.DataFrame:
    """Deep drawdown + volume contraction + ISS threshold"""
    # drawdown_from_52w_high_pct <= -20
    # vol_ratio_1d <= 0.85 (contracting)
    # iss_score >= min_iss

def get_momentum_leaders(df: pd.DataFrame, min_iss: float = 70) -> pd.DataFrame:
    """High ISS + positive RS + momentum flag"""
    # iss_score >= min_iss
    # rs_vs_nifty_3m > 0
    # momentum_flag == True

def get_event_driven_candidates(df: pd.DataFrame, days_window: int = 10) -> pd.DataFrame:
    """Event flag + upcoming event window"""
    # event_flag == True
    # days_since_last_event <= days_window
    # significance_score >= 3

def get_volume_movers(df: pd.DataFrame) -> pd.DataFrame:
    """Volume spike + positive return"""
    # vol_ratio_1d > 2.0
    # return_1d > 0
```

#### G.4: Streamlit Views (`dashboard/`)
**File:** `dashboard/phase_g.py`

```python
def render_events_tab():
    """View 6: Corporate Events Timeline"""
    - Event type filter (select multiple)
    - Date range picker
    - Timeline view by month
    - Click-to-expand event details modal
    - Price impact visualization

def render_watchlist_tab():
    """View 7: Watchlist Builder"""
    - Tab navigation (Contrarian / Momentum / Event / Volume)
    - Watchlist table with ISS gauge
    - Pin toggle and reason annotation
    - Export to CSV button
```

### Phase G Prerequisites
- [ ] `fact_corporate_event` table has data (Phase E)
- [ ] `mart_stock_signals` has all required columns
- [ ] API health endpoint returns 200

---

## Phase H: Alert Rules + EOD Scheduler

### Specification Requirements

#### Alert Rules (Spec §8)
| # | Alert Name | Condition | Frequency |
|---|------------|-----------|-----------|
| A-01 | Deep Drawdown | `drawdown_from_52w_high_pct < -20%` | Daily EOD |
| A-02 | ISS Momentum Breakout | `iss_score` crosses above 70 | Daily EOD |
| A-03 | ISS Momentum Breakdown | `iss_score` drops below 40 (was > 60 in 10 days) | Daily EOD |
| A-04 | Extreme Volume Spike | `spike_level = 'Extreme'` (> 3.0x) | Real-time / EOD fallback |
| A-05 | Critical Corporate Event | `significance_score >= 4` | Real-time |
| A-06 | Index Reconstitution | New ``dim_nifty50_constituent`` row | Real-time |
| A-07 | Watchlist Large Move | `ABS(return_1d) >= 5%` for watchlist stocks | Daily EOD |
| A-08 | Market Breadth Stress | < 10 advancing stocks out of 50 | Daily EOD |
| A-09 | Multiple 52-Week Lows | 3+ stocks at new 52W low | Daily EOD |
| A-10 | Accumulation Volume Surge | ACC + vol > 1.5x + return > 0 (first after 10 dry days) | Daily EOD |
| A-11 | Promoter Pledging Change | `event_type = 'Pledging_Change'` | Real-time |
| A-12 | Rating Downgrade | `event_type = 'Rating_Change'` + keywords | Real-time |
| A-13 | Breakout Near 52W High | `pct_below_52w_high` crosses ≤ 1% from > 2% | Daily EOD |
| A-14 | Sustained Volume Dryup | `vol_ratio_1d < 0.4` for 5+ sessions | Daily EOD |

#### Alert Deduplication (Spec §8)
- **A-01, A-02, A-03, A-07:** Once fired, won't re-fire for same (symbol, alert_type) within 5 trading days unless condition resets
- **A-05, A-06, A-11, A-12:** No deduplication (real-time, time-sensitive)

#### Severity Levels
| Severity | Color | Channels |
|----------|-------|----------|
| Critical | Red | Dashboard + Email + SMS |
| High | Orange | Dashboard + Email |
| Medium | Yellow | Dashboard only |
| Low | Grey | Dashboard (silent) |

### Implementation Tasks

#### H.1: Alert Engine (`analytics/`)
**Files:** `analytics/alert_engine.py`, `analytics/dedup_engine.py`

```python
# analytics/alert_engine.py

from dataclasses import dataclass
from enum import Enum
from typing import Optional

class AlertSeverity(Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

@dataclass
class AlertCondition:
    alert_name: str
    severity: AlertSeverity
    description: str
    frequency: str  # "realtime" or "daily"
    dedup_days: Optional[int]

class AlertEngine:
    """Evaluates alert conditions against mart_stock_signals"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def evaluate_all_alerts(self, calc_date: date) -> list[dict]:
        """Run all alert conditions for a given date"""
        alerts = []
        
        # A-01: Deep Drawdown
        alerts.extend(self._check_deep_drawdown(calc_date))
        
        # A-02: ISS Momentum Breakout
        alerts.extend(self._check_iss_breakout(calc_date))
        
        # ... more conditions
        
        return alerts
    
    async def fire_alert(self, alert: dict) -> str:
        """Insert alert into database, handle deduplication"""
        # Check deduplication first
        # Insert into alerts table
        # Return alert_id
```

```python
# analytics/dedup_engine.py

from datetime import date
from typing import Optional

class DedupEngine:
    """Alert fatigue deduplication logic"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def should_fire_alert(
        self,
        alert_name: str,
        symbol: Optional[str],
        calc_date: date
    ) -> bool:
        """Check if alert should fire given dedup rules"""
        # For A-01, A-02, A-03, A-07: check 5-day dedup window
        # Return True if alert should fire, False otherwise
    
    async def record_alert_fired(
        self,
        alert_name: str,
        symbol: Optional[str],
        dedup_key: str,
        fired_at: date
    ):
        """Record alert firing for future dedup checks"""
```

#### H.2: Alert Condition Implementations

```python
# analytics/alert_conditions.py

class AlertConditions:
    """Individual alert condition checks"""
    
    async def a01_deep_drawdown(self, calc_date: date) -> list[dict]:
        """A-01: drawdown_from_52w_high_pct < -20%"""
        df = read_sql_df(f"""
            SELECT symbol, drawdown_from_52w_high_pct
            FROM mart_stock_signals
            WHERE calc_date = :calc_date
              AND drawdown_from_52w_high_pct < -20
              AND nifty50_member = TRUE
        """, params={"calc_date": calc_date})
        
        return [{
            "alert_name": "A-01",
            "symbol": row["symbol"],
            "trigger_value": {"drawdown_pct": float(row["drawdown_from_52w_high_pct"])},
            "severity": "Medium",
            "description": f"{row['symbol']} is in deep drawdown ({row['drawdown_from_52w_high_pct']:.1f}% below 52W high)"
        } for _, row in df.iterrows()]
    
    async def a02_iss_breakout(self, calc_date: date) -> list[dict]:
        """A-02: iss_score crosses above 70"""
        # Compare with previous day's iss_score
    
    async def a03_iss_breakdown(self, calc_date: date) -> list[dict]:
        """A-03: iss_score drops below 40 (was > 60 in 10 days)"""
        # Check 10-day window
    
    async def a07_watchlist_move(self, calc_date: date) -> list[dict]:
        """A-07: watchlist stock with ABS(return_1d) >= 5%"""
        # Join with user_watchlist table
    
    async def a08_market_breadth(self, calc_date: date) -> list[dict]:
        """A-08: < 10 advancing stocks out of 50"""
        # Count advancing stocks, fire global alert
```

#### H.3: EOD Scheduler (`scheduler/`)
**File:** `scheduler/eod_scheduler.py`

```python
"""EOD batch scheduling using APScheduler"""

from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from analytics.alert_engine import AlertEngine
from analytics.compute_signals import SignalComputer

class EODScheduler:
    """Manage EOD batch jobs"""
    
    def __init__(self, db_url: str):
        self.scheduler = AsyncIOScheduler()
        self.db_url = db_url
        self.alert_engine = None
    
    def start(self):
        """Start the scheduler"""
        self.alert_engine = AlertEngine(self.db_url)
        
        # Schedule signal computation (6:30 PM IST)
        self.scheduler.add_job(
            self._run_signal_computation,
            CronTrigger(hour=18, minute=30, timezone="Asia/Kolkata"),
            id="signal_computation"
        )
        
        # Schedule alert evaluation (7:00 PM IST)
        self.scheduler.add_job(
            self._run_alert_evaluation,
            CronTrigger(hour=19, minute=0, timezone="Asia/Kolkata"),
            id="alert_evaluation"
        )
        
        self.scheduler.start()
        print("EOD Scheduler started")
    
    async def _run_signal_computation(self):
        """Run daily signal computation"""
        computer = SignalComputer(self.db_url)
        await computer.compute_all_signals()
    
    async def _run_alert_evaluation(self):
        """Run daily alert evaluation"""
        alerts = await self.alert_engine.evaluate_all_alerts(datetime.now().date())
        for alert in alerts:
            await self.alert_engine.fire_alert(alert)
```

#### H.4: Notification Adapters (`alerts/`)
**Directory:** `alerts/notification_adapters/`

```python
# alerts/notification_adapters/base.py
class BaseAdapter:
    """Base notification adapter"""
    async def send(self, alert: dict) -> bool:
        raise NotImplementedError

# alerts/notification_adapters/email_sender.py
class EmailSender(BaseAdapter):
    """Send alerts via SMTP"""
    async def send(self, alert: dict) -> bool:
        # Send email via SMTP
        pass

# alerts/notification_adapters/sms_sender.py
class SMSSender(BaseAdapter):
    """Send alerts via SMS gateway"""
    async def send(self, alert: dict) -> bool:
        # Send SMS via Twilio/AWS SNS
        pass

# alerts/notification_adapters/dashboard_notifier.py
class DashboardNotifier(BaseAdapter):
    """Display alerts in dashboard UI"""
    async def send(self, alert: dict) -> bool:
        # Push to WebSocket or store for UI polling
        pass
```

### Phase H Prerequisites
- [ ] Phase G watchlist table created
- [ ] `mart_stock_signals` has all signal columns
- [ ] Alert rules tested against sample data

---

## Phase I: Backfill + Hardening

### Specification Requirements

#### I.1: 5-Year Historical Backfill (Spec §10.1)
> Complete 5-year historical backfill of NSE Bhavcopy data

**Scope:**
- Bhavcopy: 5 years of daily OHLCV
- 52-week high/low: Computed from Bhavcopy
- Corporate actions/events: As much historical data available
- Index prices: Nifty 50 index history

**Backfill Order:**
1. `dim_stock` - Current stock list
2. `fact_eod_price` - Bhavcopy data (oldest to newest)
3. `fact_52wk` - Computed from eod_price
4. `fact_corporate_action` - Historical corporate actions
5. `fact_corporate_event` - Historical events
6. `mart_stock_signals` - Recompute all signals

#### I.2: Alembic Migrations
> Database schema migrations for Phase G+H changes

**Files:**
- `db/migrations/versions/004_phase_g_watchlist.py`
- `db/migrations/versions/005_phase_h_alerts.py`
- `db/migrations/versions/006_phase_h_scheduler.py`

#### I.3: Live NSE Scraping (Deferred from Phase E)
> Scrape real-time corporate events from NSE website

**Approach:**
- Scrape NSE corporate actions page: https://www.nseindia.com/market-data/corporate-actions
- Parse HTML table for upcoming events
- Compare with `fact_corporate_event` to detect new events
- Schedule: Every 15 minutes

#### I.4: Mobile Layout (Deferred from Phase F)
> Responsive design for mobile devices

**Requirements (Spec §5.5):**
- Collapsible sidebar
- Stacked card layout instead of table
- Touch-friendly buttons (min 44px tap targets)
- Landscape mode support

#### I.5: Notification Delivery (Deferred from Phase H)
> Email/Slack delivery channels for alerts

**Integration Points:**
- SMTP for email (Gmail/Office 365)
- Slack Webhook for team notifications
- SMS gateway (Twilio) for critical alerts

#### I.6: Deployment Optimisation + Monitoring
> Production-ready deployment configuration

**Tasks:**
- Docker containerization
- Health check endpoint
- Log aggregation (CloudWatch/Sentry)
- Database connection pooling
- CI/CD pipeline

### Implementation Tasks

#### I.1: Backfill Pipeline (`ingestion/backfill/orchestrator.py`)

```python
"""5-year backfill pipeline"""

from datetime import datetime, timedelta
from typing import Optional

class BackfillPipeline:
    """Backfill historical data from NSE archives"""
    
    def __init__(self, db_url: str, start_date: datetime, end_date: datetime):
        self.db_url = db_url
        self.start_date = start_date
        self.end_date = end_date
    
    async def run_all(self):
        """Run complete backfill pipeline"""
        # 1. Backfill Bhavcopy
        await self._backfill_bhavcopy()
        
        # 2. Compute 52-week metrics
        await self._compute_52wk_metrics()
        
        # 3. Load corporate actions (if available)
        await self._load_corporate_actions()
        
        # 4. Load corporate events (if available)
        await self._load_corporate_events()
        
        # 5. Recompute all signals
        await self._recompute_signals()
    
    async def _backfill_bhavcopy(self):
        """Download and ingest Bhavcopy for date range"""
        current = self.start_date
        while current <= self.end_date:
            # Skip market holidays
            if not self._is_market_holiday(current):
                await self._download_and_ingest_day(current)
            current += timedelta(days=1)
```

#### I.2: Live NSE Scraper (`ingestion/nse_scraper.py`)

```python
"""Live scraping of NSE corporate actions"""

import httpx
from bs4 import BeautifulSoup

class NSEScraper:
    """Scrape NSE website for corporate events"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Starfish-Dashboard/1.0 (+https://github.com/yourorg/starfish)"
            },
            timeout=30.0
        )
    
    async def scrape_upcoming_events(self) -> list[dict]:
        """Scrape upcoming corporate events from NSE"""
        url = "https://www.nseindia.com/market-data/corporate-actions"
        
        resp = await self.client.get(url)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Parse table rows
        events = []
        for row in soup.select("table tbody tr"):
            cells = row.select("td")
            if len(cells) >= 6:
                events.append({
                    "symbol": cells[0].text.strip(),
                    "event_date": cells[1].text.strip(),
                    "event_type": self._categorize_event(cells[2].text),
                    "event_summary": cells[3].text,
                    "board_meeting_date": cells[4].text,
                })
        
        return events
    
    async def sync_to_db(self) -> int:
        """Sync scraped events to fact_corporate_event"""
        events = await self.scrape_upcoming_events()
        inserted = 0
        
        for event in events:
            # Check for duplicates
            existing = await self._check_duplicate(event)
            if not existing:
                await self._insert_event(event)
                inserted += 1
        
        return inserted
```

#### I.3: Mobile UI (`dashboard/phase_i.py`)

```python
"""Mobile-responsive dashboard views"""

import streamlit as st

def render_mobile_view(signals_df):
    """Mobile-first card layout"""
    st.set_page_config(layout="wide")
    
    # Header
    st.markdown("# 📈 Starfish")
    
    # Date selector
    selected_date = st.date_input("Date", value=signals_df["calc_date"].max())
    
    # Summary cards (horizontal scroll)
    st.markdown("### Summary")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Top ISS", top_iss_symbol, top_iss_score)
    with col2:
        st.metric("Gainers", num_gainers, f"{avg_gain:+.1f}%")
    # ...
    
    # signals list as cards
    for _, row in signals_df.nlargest(20, "iss_score").iterrows():
        render_signal_card(row)
```

### Phase I Prerequisites
- [ ] All previous phases deployed
- [ ] NSE archive access (historical CSVs)
- [ ] Deployment infrastructure ready

---

## Technical Dependencies

### New Python Packages
```txt
# Phase G: Watchlist + Events
fastapi[all]          # For websockets if needed

# Phase H: Alerts + Scheduler
apscheduler           # EOD job scheduling
python-dotenv         # Environment config

# Phase I: Backfill + Scraping
httpx                 # Async HTTP client
beautifulsoup4        # HTML parsing
```

### Database Changes Summary

| Table | Action | Purpose |
|-------|--------|---------|
| `watchlist_users` | CREATE | User management for watchlists |
| `user_watchlist` | CREATE | User-curated stock lists |
| `alerts` | CREATE | Alert tracking and deduplication |

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| NSE rate limiting on scrapers | High | Add exponential backoff, rate limit tracking |
| Alert fatigue (too many alerts) | Medium | Strict deduplication, user preference controls |
| Mobile layout breaks existing views | Low | Test on actual devices, use progressive enhancement |

---

## Testing Strategy

### Unit Tests
- `tests/test_alert_engine.py` - Alert condition checks
- `tests/test_watchlist_builder.py` - Watchlist filtering logic
- `tests/test_backfill_pipeline.py` - Backfill data integrity

### Integration Tests
- `integration/test_phase_g_events.py` - Events view end-to-end
- `integration/test_phase_h_alerts.py` - Alert firing workflow
- `integration/test_phase_i_backfill.py` - Full backfill pipeline

---

## Deliverables Checklist

### Phase G
- [ ] `sql/migrations/004_phase_g_watchlist.sql` created
- [ ] `api/routers/events.py` implemented
- [ ] `api/routers/watchlist.py` implemented
- [ ] `analytics/watchlist_builder.py` created
- [ ] `dashboard/phase_g.py` implemented
- [ ] Tests passing: `pytest tests/ -v -k phase_g`

### Phase H
- [ ] `analytics/alert_engine.py` created
- [ ] `analytics/dedup_engine.py` created
- [ ] `analytics/alert_conditions.py` with all 14 rules
- [ ] `scheduler/eod_scheduler.py` implemented
- [ ] `alerts/notification_adapters/` created
- [ ] Tests passing: `pytest tests/ -v -k phase_h`

### Phase I
- [ ] `ingestion/backfill/orchestrator.py` implemented
- [ ] `ingestion/nse_scraper.py` implemented
- [ ] `dashboard/phase_i.py` (mobile layout)
- [ ] Alembic migrations for Phase G/H
- [ ] Dockerfile for deployment
- [ ] Tests passing: `pytest tests/ -v -k phase_i`

---

## Next Steps

1. **Review this plan** with the team
2. **Create feature branch:** `feature/phase-g-watchlist-events`
3. **Implement Phase G** first (depends on Phase E data)
4. **Create integration test** for Events Tracker
5. **Review with Phase E data** before moving to Phase H

---

*Document version: 1.0*  
*Last updated: 2026-04-18*
