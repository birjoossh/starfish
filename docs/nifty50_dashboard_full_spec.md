# Nifty 50 Investment Monitoring Dashboard
## Complete Product & Engineering Specification

> **Version:** 1.0 — April 2026  
> **Classification:** Internal — Investment Analytics  
> **Scope:** Nifty 50 universe + NSE large-cap (top 100 by market cap)  
> **Target Stack:** Python 3.11 · PostgreSQL · FastAPI · Streamlit / React  
> **Signal Philosophy:** Interpretable rule-based scoring · No black-box ML · Human-readable outputs

---

### Document Structure

| Section | Title |
|---|---|
| 1 | Dashboard Objective |
| 2 | User Personas |
| 3 | Data Inputs Required |
| 4 | Widget-by-Widget Dashboard Design (7 Views) |
| 5 | Table Schemas with Column Definitions (8 Tables) |
| 6 | Signal Rules |
| 7 | Sample Scoring Formula & Output Schema |
| 8 | Recommended Alert Rules |
| 9 | Engineering Design — Phases, Milestones & LLM Prompt Stubs |
| 10 | Sample Output Schema |
| 11 | Example Daily Workflow for an Investor |
| 12 | Nice-to-Have Enhancements (Prioritized Roadmap) |
| 13 | Technology Stack Recommendation |

---

# Nifty 50 Investment Monitoring Dashboard — Specification Document
## Part 1: Objective, Personas, Data Inputs, Widget Design (Sections 1–4)

---

## Section 1: Dashboard Objective

### 1.1 Primary Goal

The dashboard is an **actionable signal detection tool** for medium- to long-term equity investors focused on the Nifty 50 universe. The primary goal is not to display raw price data — it is to surface investment-relevant signals from that data, categorize them by type and urgency, and present them in a form that drives a decision or further investigation within a single daily review session (target: ≤ 20 minutes per session).

**Signal types the dashboard must detect and surface:**

| Signal Class | Description | Typical Holding Horizon |
|---|---|---|
| Sustained Trend | Stock up/down > 20% over 1M, 3M, or 1Y with consistent volume profile | 3M–12M |
| Drawdown & Recovery | Stock at significant discount to 52-week high; recovery pattern beginning | 1M–6M |
| Breakout | Price crosses above 52-week high or recent resistance, with volume confirmation | 1W–3M |
| Abnormal Volume | Volume ratio vs 20-day average > 2× or < 0.5×, with or without price movement | 1D–4W |
| Relative Strength vs Nifty 50 | Stock alpha (stock return minus Nifty 50 return) over 1M, 3M, 1Y | 1M–12M |
| Corporate Event Impact | Price and volume behavior in ±5D and ±20D windows around corporate events | Event-specific |

### 1.2 Secondary Goal

Replace manual, time-consuming workflows currently performed by analysts:

- Daily browsing of NSE portal for bhavcopies, 52-week high/low files, and corporate announcements
- Manual cross-referencing of corporate action calendars with price charts
- Spreadsheet-based tracking of Nifty 50 constituent changes and event schedules
- Ad hoc screening on third-party portals (Moneycontrol, Chittorgarh) to validate signals

The dashboard consolidates all of these into a single structured analytical interface refreshed daily (EOD) with optional intraday refresh for movers.

### 1.3 Design Philosophy

| Principle | Application |
|---|---|
| **Signal > Noise** | Every widget must reduce cognitive load, not increase it. Only display data that informs a decision. |
| **Interpretable Rules** | All scores, tags, and flags are derived from explicit, documented rules (e.g., "Volume Confirmed Trend" = volume ratio > 1.5× AND return > 20%). No black-box ML models. |
| **Human-Readable Scoring** | The Investment Signal Score (ISS) is a 0–100 composite built from labeled sub-components, each visible to the user. |
| **No False Precision** | Forward P/E, dividend yield, and analyst estimates shown only where sourced and labeled, never inferred. |
| **Fail-Safe Display** | If a data input is stale (> 1 business day old), widgets depending on it display a staleness warning rather than silently showing old data. |

---

## Section 2: User Personas

| Attribute | **Persona 1: Rahul Mehra** | **Persona 2: Sanjana Pillai** | **Persona 3: Vikram Rao** |
|---|---|---|---|
| **Role** | Long-Only Fundamental Investor | Active Tactical / Momentum Trader | Portfolio Risk Officer |
| **Firm Type** | Family office / HNI; manages own Nifty 50 portfolio of 15–25 stocks | Proprietary trading desk; takes positional trades in Nifty 50 stocks, 1–8 week horizon | Asset management firm; monitors drawdown limits and event-driven risk across full Nifty 50 exposure |
| **Primary Pain Point** | Cannot efficiently identify which Nifty 50 stocks are at cyclical lows with improving fundamentals without hours of manual research | Misses volume-confirmed momentum entries because he has no systematic volume + price cross-reference for all 50 stocks simultaneously | No centralized view of which holdings have pending board meetings, pending results, or regulatory risks; forced to track events manually in a spreadsheet |
| **Key Daily Questions** | "Which Nifty 50 stocks are down >25% from 52-week highs and have no adverse corporate events? Which have upcoming dividend announcements?" | "Which stocks are breaking out today with abnormal volume? What is the RS vs Nifty 50 over the last month? Has volume been rising during the up-move?" | "Which holdings are in drawdown > 15%? Are any of them approaching a key event (earnings, board meeting) in the next 14 days? Has pledging changed recently?" |
| **Secondary Questions** | "How has the sector breadth changed vs last month? Are my holdings underperforming Nifty 50 on a 1-year basis?" | "Are the top gainers today driven by real delivery volume or is it speculative? Any upcoming events that could be a catalyst or risk?" | "Is Nifty 50 realized volatility rising? Which stocks have had rating downgrades or regulatory actions in the last 30 days?" |
| **Preferred Interaction Mode** | Daily EOD review. Reads tables carefully. Prefers sortable grids with signal tags he can trust. Exports watchlists to CSV for further research. | Intraday refresh. Uses heatmaps and scatter plots for quick visual scanning. Clicks through to movers detail. Uses filters aggressively. | Weekly review with daily alerts for threshold breaches. Prefers structured event timelines and risk flag tables. Wants export-ready data for reporting. |
| **Tolerance for Complexity** | Medium — comfortable with financial metrics, but prefers pre-computed ratios over raw data | High — wants all columns visible, fast filters, no simplification | Low — wants red/amber/green status at a glance; detail available on drill-down |

---

## Section 3: Data Inputs Required

| # | Source Type | Data Source Name | File / API Format | Refresh Frequency | Primary Use in Dashboard | Data Quality Notes |
|---|---|---|---|---|---|---|
| A | NSE Official | EOD Price/Volume Bhavcopy (`sec_bhavdata_full_YYYYMMDD.csv`) | CSV, flat file download from NSE archives or API | Daily, after 18:00 IST (EOD settlement) | OHLC prices, previous close, total traded quantity, total traded value, total number of trades per symbol per day. Feeds all return calculations, volume ratios, heatmaps, and movers tables. | Symbols must be validated against master security list daily. Adjust for bonus/splits using corporate actions feed before computing returns. Watch for settlement holidays — no file on non-trading days. |
| B | NSE Official | 52-Week High/Low (`CM_52_wk_High_low_YYYYMMDD.csv`) | CSV, flat file download from NSE | Daily, after EOD settlement | Compute "Distance from 52W High %" and "Distance from 52W Low %" used in movers tables, drawdown scanner, and breakout monitor. | Cross-check computed rolling 52W high/low (derived from 252-day price history) against this file; if divergence > 2%, flag for review. Do not use NSE file as sole source — it may include intraday extremes vs. close-only series. |
| C | NSE / Index Provider | Nifty 50 Constituents (`nifty50_constituents.csv` or JSON endpoint from NSE Indices) | CSV or JSON; fields: symbol, company name, sector/industry, ISIN, free-float market cap, index weight | Monthly or on reconstitution event | Filter all views to Nifty 50 universe. Market cap and weight fields used for heatmap cell sizing, market cap tier filters, and ISS Score weighting. | Always use official NSE Indices source (not third-party mirrors). On reconstitution effective date, old constituents must be archived, not deleted, to maintain historical signal continuity. |
| D | Internal / Manual | Reconstitution Table (`nifty50_reconstitution_log.csv`) | Internal CSV; fields: symbol, company, ISIN, action (ADD/DELETE), effective_date, review_period (March/September), reason_code | Semi-annual (March and September reviews); manual update within 24h of official NSE announcement | Track which stocks were added/deleted and when. Used to suppress signals for recently added stocks (< 30 days in index), tag newly added stocks, and audit historical watchlist accuracy. | Must be updated manually on reconstitution effective date. Automate alert when effective_date is within 5 business days. Reason codes: MARKET_CAP, LIQUIDITY, SECTOR_REBALANCE, VOLUNTARY_DELISTING, MERGER, OTHER. |
| E | NSE Corporate Filings | Corporate Actions Feed | NSE API or daily download; fields: symbol, ISIN, purpose (enum), ex_date, record_date, face_value, ratio, percentage, announcement_date | Daily pull at 09:00 IST and 18:00 IST | Dividend/bonus/split adjustments for price series. Drives Corporate Events Tracker, event significance scoring, and price reaction computation (+1D/+5D/+20D windows). Also flags upcoming events in volume anomaly context. | Purpose field must be mapped to internal enum: `DIVIDEND`, `BONUS`, `SPLIT`, `RIGHTS`, `BUYBACK`, `OTHER`. Null ex_date records must be quarantined. Dividend amounts must be normalized against face value for comparability. |
| F | NSE / BSE / Vendor | Event Calendar Feed | API or vendor feed (e.g., NSE API `/corporates/event-calendar`); fields: symbol, event_type, event_date, description, board_meeting_purpose | Daily at 09:00 IST; retrospective backfill on first load | Populate Corporate Events Tracker timeline (upcoming 30 days + past 30 days). Drive "Nearest Corporate Event" column in volume anomaly monitor. Feed event significance score computation. | Distinguish between announced dates (confirmed) and estimated dates (from vendor projections). Tag unconfirmed dates visually. Financial result event dates typically announced 7 days prior; board meeting notices 2 days prior under SEBI regulations. |
| G | NSE Corporate Announcements | Corporate Announcements Stream | NSE API (`/corporates/announcements`); fields: symbol, submission_date, category (enum), subject, attachment_url, body_text (first 500 chars) | Every 30 minutes during market hours; EOD full pull | Feed Corporate Events Tracker. Categorize free-text announcements into: `LARGE_ORDER`, `LEADERSHIP_CHANGE`, `PLEDGING_CHANGE`, `MERGER_DEMERGER`, `RATING_CHANGE`, `REGULATORY_NOTICE`, `GENERAL`. Drive event significance scoring and Follow-up Required Flag. | Free-text category field from NSE is inconsistent. Implement keyword-rule classifier (non-ML) to map raw category strings to internal enum. Log all unmapped categories for manual review. Archive raw body_text for audit. |
| H | Intraday Vendor | Real-Time / 15-Min Delayed Intraday OHLCV (e.g., TrueData, Global Datafeeds) | REST API; fields: symbol, timestamp, open, high, low, close, volume; 1-minute or 5-minute bars | Every 5–15 minutes during market hours (09:15–15:30 IST) | Power intraday top gainers/losers refresh in Market Overview and Movers views. Used only for real-time price context; all analytics (returns, volume ratios, signals) remain EOD-based. | This feed is supplementary. If intraday API is unavailable, dashboard gracefully degrades to prior-day EOD data with clear "Intraday data unavailable" banner. Never substitute intraday close for official EOD close. |
| I | Secondary Portals | Moneycontrol / Chittorgarh / Investing.com | Manual URL fetch or structured export; no automated ingestion | On-demand, manual only | Validation of forward P/E estimates, dividend yield, analyst consensus where not available from NSE filings. Not used as primary data source for any computed signal. | Clearly label any data point sourced from secondary portals with a `[Source: MC]` / `[Source: CG]` tag. These fields are informational only and must not feed ISS Score computation. |

---

## Section 4: Widget-by-Widget Dashboard Design

---

### View 1: Market Overview

**Purpose:** Provide a one-screen daily briefing of the Nifty 50 index health and constituent breadth before any drill-down.

**Layout:** Three-row grid.
- Row 1: KPI card strip (5 cards, full width)
- Row 2: Two columns — Sector Breadth Table (left, 55%) + Advancing/Declining Donut + Volatility Gauge (right, 45%)
- Row 3: Nifty 50 Heatmap (full width, 3 tabs)

---

#### Widget 1.1 — Index Snapshot KPI Cards

| Attribute | Detail |
|---|---|
| **Type** | KPI Card strip (5 cards) |
| **Data Fields** | Nifty 50 Level (current close); 1D Change % (vs prior close); 1M Return % (vs 21 trading days ago close); 1Y Return % (vs 252 trading days ago close); 52W High (value + date); 52W Low (value + date) |
| **Filter Controls** | None (index-level, no filtering) |
| **Color Logic** | 1D/1M/1Y change: Green if > 0%, Red if < 0%, Gray if 0%. 52W High card: highlight green if current level is within 1% of 52W high. 52W Low card: highlight red if current level is within 5% of 52W low. |
| **Alert Highlights** | If 1D change > ±2%: card border flashes amber. If Nifty 50 is at new 52W high: card border green with "NEW HIGH" badge. |

---

#### Widget 1.2 — Sector Breadth Table

| Attribute | Detail |
|---|---|
| **Type** | Sortable data table |
| **Data Fields** | Sector Name; # Stocks in Nifty 50 (count); # Advancing Today; # Declining Today; # Unchanged; Avg 1M Return % (equal-weighted); Avg 1Y Return % (equal-weighted) |
| **Filter Controls** | Sort by any column header |
| **Color Logic** | Avg 1M Return: color scale from red (< −5%) to green (> +5%). Avg 1Y Return: same scale, wider range (< −15% to > +20%). # Advancing / # Declining: green / red text. |
| **Alert Highlights** | Sectors where all stocks are declining (# Advancing = 0): row background light red. Sectors where all stocks are advancing: row background light green. |

---

#### Widget 1.3 — Advancing vs. Declining Stocks Chart

| Attribute | Detail |
|---|---|
| **Type** | Donut chart with center count label |
| **Data Fields** | Count of Nifty 50 stocks advancing today; declining today; unchanged today |
| **Filter Controls** | Toggle: Today / 1W / 1M (changes computation window) |
| **Color Logic** | Advancing = green segment; Declining = red segment; Unchanged = gray segment. Center label: "N of 50 advancing" |
| **Alert Highlights** | If > 40 stocks declining: outer ring turns deep red. If > 40 stocks advancing: outer ring turns deep green. |

---

#### Widget 1.4 — Average Constituent Return Cards

| Attribute | Detail |
|---|---|
| **Type** | KPI Card pair |
| **Data Fields** | Avg 1M Return of Nifty 50 constituents (equal-weighted); Avg 1Y Return of Nifty 50 constituents (equal-weighted) |
| **Filter Controls** | None |
| **Color Logic** | Same red/green directional color as Index KPI cards |
| **Alert Highlights** | If avg 1M return diverges from Nifty 50 index 1M return by > 3% (indicating index is skewed by large caps): amber "Breadth Divergence" badge appears |

---

#### Widget 1.5 — Rolling 20-Day Realized Volatility Gauge

| Attribute | Detail |
|---|---|
| **Type** | Arc gauge (speedometer style) |
| **Data Fields** | Nifty 50 index 20-day realized volatility (annualized, computed as: `std(daily log returns over last 20 days) × sqrt(252) × 100`). Display: current value (%), 6M average, 1Y average |
| **Filter Controls** | None |
| **Color Logic** | Gauge zones: 0–12% = green (low vol), 12–20% = amber (moderate), 20%+ = red (elevated). Needle position = current value. |
| **Alert Highlights** | If current > 1.5× the 6M average: "Vol Spike" badge in red. |

---

#### Widget 1.6 — Nifty 50 Performance Heatmap

| Attribute | Detail |
|---|---|
| **Type** | Treemap / heatmap (cell per stock, 3 tabs) |
| **Tabs** | Tab 1: 1-Day Return; Tab 2: 1-Month Return; Tab 3: 1-Year Return |
| **Data Fields** | Each cell: Ticker symbol (top), Return % (bottom center). Cell size proportional to free-float market cap. |
| **Filter Controls** | Tab selector for period; hover tooltip showing Company Name, Sector, Return %, Market Cap |
| **Color Logic** | Diverging color scale: Deep Red (worst) → Light Red → Neutral Gray → Light Green → Deep Green (best). Scale anchored dynamically to p5 and p95 of return distribution each day (prevents outlier from compressing all other colors). |
| **Alert Highlights** | Stocks at 52W high: gold border on cell. Stocks at 52W low: dark border on cell. |

---

### View 2: Movers and Extremes

**Purpose:** Identify the best and worst performers across periods, with volume and relative strength context for entry/exit signal confirmation.

**Layout:**
- Row 1: Filter bar (full width)
- Row 2: Top Gainers Table (left, 50%) + Top Losers Table (right, 50%)
- Row 3: Scatter Plot — Return % vs Volume Change % (full width)

---

#### Widget 2.1 — Filter Bar

| Control | Options |
|---|---|
| Period Toggle | 1D / 1M / 3M / 1Y |
| Market Cap Tier | All / > ₹5,000 Cr / > ₹20,000 Cr / > ₹1 Lakh Cr |
| Sector | Multi-select dropdown |
| Nifty 50 Only | Toggle (default: ON) |

---

#### Widget 2.2 — Top 10 Gainers Table

| Attribute | Detail |
|---|---|
| **Type** | Sortable ranked table |
| **Columns** | Rank; Symbol; Company Name; Sector; Mkt Cap (₹ Cr); Current Price (₹); Change % (for selected period); Volume Change % vs 20-day avg; RS vs Nifty 50 — alpha over selected period; Distance from 52W High %; Distance from 52W Low %; Nifty 50 Member (Y/N) |
| **Filter Controls** | Inherits from Filter Bar (Widget 2.1) |
| **Color Logic** | Change %: green, with intensity scaled to magnitude. Volume Change %: amber if > 50%, deep orange if > 100%. RS vs Nifty 50: green if positive alpha, red if negative alpha. Distance from 52W High: red if > 30% below (despite being a gainer — flag as weak recovery). |
| **Alert Highlights** | If Volume Change % > 100% AND Change % > 5%: "Volume Breakout" badge in orange on row. |

---

#### Widget 2.3 — Top 10 Losers Table

| Attribute | Detail |
|---|---|
| **Type** | Sortable ranked table |
| **Columns** | Same columns as Widget 2.2 |
| **Filter Controls** | Inherits from Filter Bar |
| **Color Logic** | Change %: red. Volume Change %: amber/orange as above. Distance from 52W Low: red if within 5% of 52W low. |
| **Alert Highlights** | If Volume Change % > 100% AND Change % < −5%: "Selling Climax?" badge in red on row. |

---

#### Widget 2.4 — Return vs Volume Scatter Plot

| Attribute | Detail |
|---|---|
| **Type** | Scatter plot |
| **Axes** | X-axis: Return % (for selected period); Y-axis: Volume Change % vs 20-day avg |
| **Data Fields** | Each dot = one stock. Dot size = market cap. Dot color = sector (consistent color palette across dashboard). Dot label = ticker (visible on hover; always shown for top 5 gainers and losers). |
| **Filter Controls** | Inherits from Filter Bar; click on dot to open stock detail sidebar |
| **Color Logic** | Quadrant lines at X=0 and Y=0 divide into 4 zones: Top-right (high return + high volume) = "Volume-Confirmed Move"; Top-left (negative return + high volume) = "Selling Pressure"; Bottom-right (positive return + low volume) = "Quiet Drift Up"; Bottom-left = "Quiet Drift Down" |
| **Alert Highlights** | Stocks in top-right quadrant with Volume Change % > 100%: dot outlined in gold. |

---

### View 3: Drawdown Scanner

**Purpose:** Systematically identify Nifty 50 stocks in significant drawdown, classify them as accumulation candidates, falling knife risks, or stocks needing event review.

**Layout:**
- Row 1: Filter bar
- Row 2: Drawdown Summary KPI cards (3 cards: # stocks down > 20% in 3M, # stocks down > 20% in 1Y, avg drawdown from 52W high across full Nifty 50)
- Row 3: Main drawdown table (full width)

---

#### Widget 3.1 — Drawdown Filter Bar

| Control | Options |
|---|---|
| Drawdown Threshold Slider | Configurable: −10% to −50% (default: −20%) — applies to both 3M and 1Y columns |
| Period | 3M / 1Y / Both (show if either threshold breached) |
| Sector | Multi-select |
| Market Cap | Tier dropdown |

---

#### Widget 3.2 — Drawdown Scanner Table

| Attribute | Detail |
|---|---|
| **Type** | Sortable, filterable data table |
| **Columns** | Symbol; Company Name; Sector; Mkt Cap (₹ Cr); Current Price (₹); 3M Return %; 1Y Return %; Drawdown from 52W High %; Forward P/E (labeled `[MC]` if from Moneycontrol); Dividend Yield % (labeled `[MC]` if secondary source); Volume Trend During Decline (`Rising` / `Falling` / `Mixed` — based on correlation of 20-day rolling volume with price over the decline window); Signal Tag |
| **Signal Tag Logic** | `Potential Accumulation Candidate`: Drawdown > 20%, Volume Trend = Falling (selling exhaustion), no adverse corporate event in last 30 days, no regulatory notice active. `Falling Knife Risk`: Drawdown > 20%, Volume Trend = Rising (distribution), OR adverse corporate event (regulatory action / leadership change / rating downgrade) within last 30 days. `Needs Event Review`: Drawdown > 20%, pending board meeting or results announcement within 14 days, OR recent pledging change, OR M&A announcement. |
| **Color Logic** | Signal Tag: `Potential Accumulation Candidate` = green cell background; `Falling Knife Risk` = red cell background; `Needs Event Review` = amber cell background. 3M/1Y Return: red, darker for larger losses. Drawdown from 52W High: red gradient, darkest at −50%. |
| **Alert Highlights** | If stock is within 3% of 52W Low AND Volume Trend = Rising: append "Near 52W Low — Caution" sub-tag in red. |

---

### View 4: Breakout and Momentum Monitor

**Purpose:** Identify stocks exhibiting strong upward momentum with quality classification to distinguish sustainable trends from noise.

**Layout:**
- Row 1: Filter bar
- Row 2: Breakout table (left, 65%) + Top 15 Momentum Bar Chart (right, 35%)

---

#### Widget 4.1 — Momentum Filter Bar

| Control | Options |
|---|---|
| Period | 1M / 3M / 1Y (return threshold applied to selected period) |
| Return Threshold | > 10% / > 20% / > 30% (default: > 20%) |
| Sector | Multi-select |
| Market Cap | Tier dropdown |
| Volume Confirmation | Toggle: Show only Volume Expansion = Y |

---

#### Widget 4.2 — Breakout / Momentum Table

| Attribute | Detail |
|---|---|
| **Type** | Sortable, filterable data table |
| **Columns** | Symbol; Company Name; Sector; Mkt Cap (₹ Cr); Return % (for selected period); Volume Expansion Flag (Y if avg volume in last 10 days > 1.5× avg volume in prior 30 days); Earnings Surprise Flag (Y if earnings beat announced in last 60 days per event calendar); Positive Corporate Event Flag (Y if large order, dividend declaration, or positive rating change in last 30 days); Momentum Quality Tag |
| **Momentum Quality Tag Logic** | `Volume-Confirmed Trend`: Return > 20% AND Volume Expansion = Y AND no single event accounts for > 50% of the move. `Event-Driven Pop`: Return > 20% AND Positive Corporate Event Flag = Y AND Volume Expansion may or may not be present. `Thin Volume Breakout`: Return > 20% AND Volume Expansion = N (avg volume ratio < 1.0× in last 10 days). `Short Squeeze Risk`: Return > 20% AND Volume spike > 3× in 1–2 days, then volume normalized (likely not sustained). |
| **Color Logic** | Tag color: `Volume-Confirmed Trend` = deep green; `Event-Driven Pop` = blue; `Thin Volume Breakout` = amber; `Short Squeeze Risk` = orange-red. Return %: green gradient. Volume Expansion Flag: green (Y) / gray (N). |
| **Alert Highlights** | Stocks with all three flags = Y (Volume Expansion + Earnings Surprise + Positive Event): "Triple Confirmation" gold badge on row. |

---

#### Widget 4.3 — Top 15 Momentum Bar Chart

| Attribute | Detail |
|---|---|
| **Type** | Horizontal bar chart |
| **Data Fields** | Top 15 stocks ranked by 3M return (or selected period). Each bar shows Return %. Bar color = Momentum Quality Tag color (consistent with table). Ticker labels on Y-axis. |
| **Filter Controls** | Inherits period from filter bar |
| **Color Logic** | Bar color matches tag: green for volume-confirmed, blue for event-driven, amber for thin-volume, orange-red for squeeze risk |
| **Alert Highlights** | Bars exceeding 50% return get a star marker |

---

### View 5: Volume Anomaly Monitor

**Purpose:** Identify unusual volume activity across Nifty 50 stocks as a potential leading indicator of institutional activity, event-driven moves, or liquidity shifts.

**Layout:**
- Row 1: Three sub-tables side by side (Volume Up > 20% / > 50% / > 100%)
- Row 2: Volume Contraction sub-table (left, 55%) + Nifty 50 Volume Ratio Heatmap (right, 45%)
- Row 3: Sidebar explanation widget (full width, collapsible)

---

#### Widget 5.1 — Volume Spike Sub-Tables (3 panels)

| Attribute | Detail |
|---|---|
| **Type** | Three compact data tables with tab/threshold toggle |
| **Panels** | Panel A: Volume Ratio > 1.2× (> 20% above avg); Panel B: Volume Ratio > 1.5×; Panel C: Volume Ratio > 2× |
| **Columns** | Symbol; Company Name; Sector; Mkt Cap (₹ Cr); Today's Volume; 20-Day Avg Volume; Volume Ratio; Delivery % (if available from NSE F&O data or Bhavcopy delivery field); Price Change % on spike day; Nearest Corporate Event (event type + days offset, e.g., "Earnings +3d") |
| **Color Logic** | Volume Ratio: amber (1.2–1.5×), orange (1.5–2×), deep orange/red (> 2×). Price Change %: green/red directional. Nearest Corporate Event: blue if within ±5 days. |
| **Alert Highlights** | Volume Ratio > 3× AND no nearby corporate event: "Unexplained Spike" badge in red — suggests potential undisclosed event or block deal. |

---

#### Widget 5.2 — Volume Contraction Sub-Table

| Attribute | Detail |
|---|---|
| **Type** | Data table |
| **Thresholds** | Volume Ratio < 0.8 (> 20% below avg) and < 0.5 (> 50% below avg); toggle between thresholds |
| **Columns** | Same columns as Widget 5.1 |
| **Color Logic** | Volume Ratio: light gray (0.8–0.5×), dark gray (< 0.5×). Unusual contraction alongside price decline: amber. |
| **Alert Highlights** | Volume Ratio < 0.5 AND Price Change % < −2%: "Illiquid Sell-Off" tag in amber |

---

#### Widget 5.3 — Nifty 50 Volume Ratio Heatmap

| Attribute | Detail |
|---|---|
| **Type** | Fixed 50-cell grid heatmap (5×10 cells), one cell per Nifty 50 constituent |
| **Data Fields** | Each cell: Ticker + Volume Ratio (e.g., "RELIANCE 2.3×"). Cells arranged alphabetically or by sector (user toggle). |
| **Color Logic** | Color scale: light yellow (ratio ≈ 1×) → amber (1.5–2×) → deep orange (2–3×) → burnt red (> 3×). Below-average volume: light gray → dark gray. |
| **Alert Highlights** | Cells with ratio > 3×: pulsing border animation |

---

#### Widget 5.4 — Volume Education Sidebar

| Attribute | Detail |
|---|---|
| **Type** | Collapsible text panel |
| **Content** | Static explanatory block: **Why abnormal volume matters for longer-horizon investors:** (1) Volume spikes often precede corporate announcements — institutional positioning before scheduled events leaves volume footprints before price moves. (2) High-volume declines suggest distribution by large holders; high-volume recoveries suggest re-accumulation — both are more structurally significant than low-volume moves. (3) Persistent volume contraction on a declining stock may indicate forced selling exhaustion — a potential setup for stabilization. (4) Delivery percentage alongside volume ratio distinguishes speculative intraday surges (low delivery %) from genuine institutional interest (high delivery %), sharpening signal quality. |

---

### View 6: Corporate Events Tracker

**Purpose:** Provide a unified, chronological feed of all material corporate events for Nifty 50 companies, with pre- and post-event price context built in.

**Layout:**
- Row 1: Filter bar (full width)
- Row 2: Scrollable event timeline table (full width, paginated — 25 rows per page)

---

#### Widget 6.1 — Event Filter Bar

| Control | Options |
|---|---|
| Date Range | Presets: Last 7D / Last 30D / Next 7D / Next 30D / Custom range |
| Event Type | Multi-select: Earnings / Dividend / Bonus / Split / Buyback / Rights / Leadership Change / M&A / Large Order / Pledging Change / Rating Change / Regulatory Action / General |
| Symbol | Typeahead search |
| Significance Score | Slider: 1–5 minimum threshold |
| Follow-up Required | Toggle: Show only flagged records |

---

#### Widget 6.2 — Corporate Events Timeline Table

| Attribute | Detail |
|---|---|
| **Type** | Scrollable, sortable data table with inline sparklines |
| **Columns** | Date (event date or announcement date); Symbol; Company Name; Sector; Event Type (color-coded pill badge — see below); Event Summary (truncated to 120 characters, expand on hover/click); Price Reaction +1D %; Price Reaction +5D %; Price Reaction +20D % (all blank for upcoming events); Volume Spike on Event Day (Y/N); Event Significance Score (1–5 star display); Follow-up Required Flag (checkbox, manually editable); 20-Day Price Sparkline (mini line chart: 10 days pre-event to 10 days post-event, event date marked with vertical line) |
| **Event Type Color Coding** | Earnings = blue; Dividend = green; Bonus = teal; Split = cyan; Buyback = indigo; Rights = navy; Leadership Change = amber; M&A = purple; Large Order = lime green; Pledging Change = orange; Rating Change = yellow-orange; Regulatory Action = red; General = gray |
| **Significance Score Logic (1–5)** | 1 = Routine (small dividend, general filing); 2 = Notable (earnings report, leadership change); 3 = Significant (large order > 5% of revenue, rating upgrade/downgrade); 4 = High Impact (merger announcement, buyback > 5% of market cap, regulatory notice); 5 = Transformative (merger completion, delisting notice, major regulatory penalty) |
| **Follow-up Required Flag Logic** | Auto-set to Y if: Significance Score ≥ 4, OR Regulatory Action event type, OR Leadership Change, OR Pledging Change increase > 5% of promoter holding, OR Price Reaction +1D > ±5%. User can manually override. |
| **Alert Highlights** | Future events (upcoming) displayed with light blue row background. Past events with Price Reaction +20D > ±10%: bold return value. Regulatory Action events: red left border stripe on row. |

---

### View 7: Watchlist Builder

**Purpose:** Auto-generate a curated, rules-based watchlist of actionable Nifty 50 candidates, classified by signal type, with a transparent composite scoring system.

**Layout:**
- Row 1: Four section tabs (Contrarian Opportunities / Momentum Leaders / Event-Driven Candidates / Volume-Confirmed Movers)
- Row 2: Watchlist table (left, 75%) + ISS Score Gauge panel (right, 25% — updates on row selection)
- Row 3: Export and pin controls

---

#### Widget 7.1 — Watchlist Section Tabs

| Tab | Population Logic |
|---|---|
| **Contrarian Opportunities** | Stocks in drawdown > 20% from 52W high, Signal Tag = "Potential Accumulation Candidate", ISS Score ≥ 40 |
| **Momentum Leaders** | Stocks with 3M return > 20%, Momentum Quality Tag = "Volume-Confirmed Trend" or "Event-Driven Pop", ISS Score ≥ 50 |
| **Event-Driven Candidates** | Stocks with a Significance Score ≥ 3 event in last 30 days or upcoming 14 days, Follow-up Required = Y, ISS Score ≥ 35 |
| **Volume-Confirmed Movers** | Stocks with Volume Ratio > 1.5× in last 5 trading days, Price Change % > 0% on volume spike day, ISS Score ≥ 40 |

---

#### Widget 7.2 — Watchlist Table

| Attribute | Detail |
|---|---|
| **Type** | Sortable, filterable data table with manual pin capability |
| **Columns** | Pin (toggle icon — pinned stocks float to top); Symbol; Company Name; Sector; Mkt Cap (₹ Cr); ISS Score (0–100, displayed as colored badge: 0–39 red, 40–59 amber, 60–79 green, 80–100 deep green); Primary Signal Category (one of the 4 tabs); Key Reason (1-line auto-generated text from rule logic, e.g., "Down 28% from 52W high, volume declining — accumulation setup"); Last Corporate Event (event type + date); Days on Watchlist (count of calendar days since first auto-populated) |
| **ISS Score Composition (displayed in tooltip and gauge panel)** | Score is sum of 5 sub-components (0–20 each): (1) Price Momentum Score (return vs Nifty 50 over 3M, normalized); (2) Volume Quality Score (delivery %, volume trend consistency); (3) Drawdown / Recovery Score (distance from 52W high/low, recovery trend); (4) Corporate Event Score (positive events +points, adverse events −points, based on significance and recency); (5) Relative Strength Score (RS vs Nifty 50 over 1M and 3M, equally weighted) |
| **Color Logic** | ISS Score badge color as above. Key Reason: plain text, no color. Days on Watchlist: amber if > 30 days (review or remove). |
| **Alert Highlights** | If a pinned stock develops a new adverse event (Significance ≥ 3, adverse type): row background turns light red with "New Risk Event" badge. |

---

#### Widget 7.3 — ISS Score Gauge (per selected stock)

| Attribute | Detail |
|---|---|
| **Type** | Arc/donut gauge with sub-score breakdown bar chart below |
| **Data Fields** | Total ISS Score (0–100) displayed in gauge center. Below gauge: horizontal stacked bar showing contribution of each of 5 sub-components with labels and values. |
| **Color Logic** | Gauge arc: red (0–39), amber (40–59), green (60–79), deep green (80–100). Sub-component bars: individual colors per component (consistent across dashboard). |
| **Interaction** | Updates on row click/hover in watchlist table. Sticky panel — does not scroll away. |

---

#### Widget 7.4 — Export and Pin Controls

| Control | Behavior |
|---|---|
| **Export to CSV** | Exports current tab's watchlist with all columns to `nifty50_watchlist_YYYYMMDD.csv`. Includes metadata row: export timestamp, filter settings applied, ISS Score formula version. |
| **Pin / Unpin** | Pin icon per row. Pinned stocks float to top within their tab, persist across sessions (stored in user profile or local storage). Pinned stocks not auto-removed when they fall below ISS threshold — instead flagged with "Below threshold — review" warning. |
| **Clear All Pins** | Button with confirmation dialog. |

---

*End of Part 1 — Sections 1 through 4.*
# Nifty 50 Investment Monitoring Dashboard — Specification Part 2
## Sections 5–9: Signals, Schemas, Engineering Phases

---

## Section 5: Table Schemas with Column Definitions

All tables follow a consistent naming convention: `dim_` for dimension/reference tables, `fact_` for raw transactional/event tables, and `mart_` for pre-computed analytical marts. Primary keys are annotated (PK, PK1/PK2 for composite keys). All timestamps use IST (Asia/Kolkata, UTC+5:30).

---

### Table 1: `dim_stock`

**Purpose:** Master stock dimension table. Single source of truth for stock metadata. One row per listed symbol. Updated whenever NSE publishes a security master update or index rebalancing occurs.

| Column Name | Data Type | Source Field | Nullable | Description |
|---|---|---|---|---|
| `symbol` | VARCHAR(20) | NSE Security Master | N | NSE trading symbol (e.g. "RELIANCE"). Primary Key. |
| `company_name` | VARCHAR(200) | NSE Security Master | N | Full registered company name (e.g. "Reliance Industries Ltd"). |
| `sector` | VARCHAR(100) | NSE / AMFI classification | N | Broad sector classification (e.g. "Financial Services", "Energy"). |
| `industry` | VARCHAR(100) | NSE / AMFI classification | Y | Sub-sector / industry group (e.g. "Private Banks", "Oil & Gas – Integrated"). |
| `nifty50_member` | BOOLEAN | dim_nifty50_constituent | N | TRUE if symbol is currently in Nifty 50 index. Derived from constituent table, refreshed at each rebalancing. |
| `market_cap_cr` | DECIMAL(18,2) | NSE / BSE market data | Y | Latest market capitalisation in Indian Crores (₹ Cr). Updated daily from EOD price × shares outstanding. |
| `listing_date` | DATE | NSE Security Master | N | Date the stock was first listed on NSE. |
| `face_value` | DECIMAL(10,2) | NSE Security Master | N | Face value per share (₹). Required for bonus/split ratio calculations. |
| `isin` | VARCHAR(12) | NSE Security Master | N | ISIN code (e.g. "INE002A01018"). Unique identifier across exchanges. |
| `last_updated` | TIMESTAMP | System generated | N | Timestamp (IST) when this record was last modified. |

---

### Table 2: `fact_eod_price`

**Purpose:** Daily OHLCV data sourced from NSE Bhavcopy CSV files. One row per (trade_date, symbol) combination. Composite PK. Delivery data is populated only when NSE publishes the delivery position file (typically released with a 1-day lag).

| Column Name | Data Type | Source Field | Nullable | Description |
|---|---|---|---|---|
| `trade_date` | DATE | Bhavcopy filename / TIMESTAMP column | N | NSE trading date. Part of composite PK. |
| `symbol` | VARCHAR(20) | SYMBOL column in Bhavcopy | N | NSE trading symbol. Part of composite PK. FK → dim_stock.symbol. |
| `open` | DECIMAL(12,2) | OPEN column | N | Opening price of the day (₹). |
| `high` | DECIMAL(12,2) | HIGH column | N | Intraday high price (₹). |
| `low` | DECIMAL(12,2) | LOW column | N | Intraday low price (₹). |
| `close` | DECIMAL(12,2) | CLOSE column | N | Closing price — used as primary price reference (₹). |
| `prev_close` | DECIMAL(12,2) | PREVCLOSE column | N | Previous trading session's close price (₹). Used for daily return calculation. |
| `total_traded_qty` | BIGINT | TOTTRDQTY column | N | Total shares traded in the session. |
| `total_traded_value_lakh` | DECIMAL(18,2) | TOTTRDVAL column | N | Total traded value in ₹ Lakh as reported by NSE. |
| `total_trades` | INTEGER | TOTALTRADES column | N | Number of individual trades executed. |
| `series` | VARCHAR(10) | SERIES column | N | NSE trading series (e.g. "EQ" for equity, "BE" for trade-to-trade, "BL" for block deals). |
| `delivery_qty` | BIGINT | NSE delivery position file | Y | Shares delivered (settled, not squared off). NULL until delivery file is published (T+1). |
| `delivery_pct` | DECIMAL(6,2) | NSE delivery position file | Y | Delivery quantity as % of total traded quantity. NULL until T+1. Range: 0–100. |
| `source_file` | VARCHAR(300) | Ingestion pipeline | N | Filename of the Bhavcopy CSV that sourced this row (e.g. "cm01JAN2024bhav.csv.zip"). Audit trail. |

---

### Table 3: `fact_52wk`

**Purpose:** Daily snapshot of 52-week high and low for each symbol, along with the date those extremes were reached and the percentage distance of current close from each extreme. Populated as part of the EOD analytics job after `fact_eod_price` is fully loaded for the day.

| Column Name | Data Type | Source Field | Nullable | Description |
|---|---|---|---|---|
| `trade_date` | DATE | Derived from fact_eod_price | N | Calculation date (= today's EOD). Part of composite PK. |
| `symbol` | VARCHAR(20) | fact_eod_price.symbol | N | NSE trading symbol. Part of composite PK. FK → dim_stock. |
| `wk52_high` | DECIMAL(12,2) | Rolling MAX(close) over prior 252 trading days | N | Highest closing price in the past 52 weeks (₹). |
| `wk52_low` | DECIMAL(12,2) | Rolling MIN(close) over prior 252 trading days | N | Lowest closing price in the past 52 weeks (₹). |
| `wk52_high_date` | DATE | Date of MAX(close) in lookback window | N | Date on which the 52-week high closing price was recorded. |
| `wk52_low_date` | DATE | Date of MIN(close) in lookback window | N | Date on which the 52-week low closing price was recorded. |
| `pct_from_high` | DECIMAL(8,4) | Computed: (close - wk52_high) / wk52_high × 100 | N | Percentage decline from 52-week high. Negative value indicates drawdown (e.g. -18.5 means 18.5% below 52w high). |
| `pct_from_low` | DECIMAL(8,4) | Computed: (close - wk52_low) / wk52_low × 100 | N | Percentage rise from 52-week low. Positive value (e.g. +42.0 means 42% above 52w low). |

---

### Table 4: `dim_nifty50_constituent`

**Purpose:** Tracks current and historical Nifty 50 membership with effective dates. Supports point-in-time queries (e.g. "which 50 stocks were in the index on 15-Mar-2022?"). Updated whenever NSE announces an index rebalancing (typically semi-annual: March and September reviews).

| Column Name | Data Type | Source Field | Nullable | Description |
|---|---|---|---|---|
| `symbol` | VARCHAR(20) | NSE Index announcements | N | NSE trading symbol of the constituent. Part of composite PK. |
| `effective_from` | DATE | NSE rebalancing circular | N | Date from which this membership record became active. Part of composite PK. |
| `effective_to` | DATE | NSE rebalancing circular | Y | Date on which this membership ended. NULL if the record is currently active. |
| `index_weight_pct` | DECIMAL(8,4) | NSE Index factsheet | Y | Weight of the stock in the index at effective_from date (%). NULL for historical records predating weight tracking. |
| `replaced_symbol` | VARCHAR(20) | NSE Index circular | Y | For Addition type: the symbol that was removed to make room. NULL for Rebalance weight changes where no deletion occurred. |
| `change_type` | ENUM('Addition','Deletion','Rebalance') | NSE Index circular | N | Nature of the change: Addition = new entrant, Deletion = exited, Rebalance = weight adjustment without membership change. |
| `review_period` | VARCHAR(20) | NSE Index circular | N | Human-readable label for the rebalancing cycle (e.g. "Sep-2024", "Mar-2023"). Useful for grouping and display. |

---

### Table 5: `fact_corporate_action`

**Purpose:** Records NSE-published corporate actions that have a mechanical effect on share price and/or capital structure. Each record represents one corporate action for one symbol. Data sourced from NSE's corporate actions page (or its data API equivalent). Used to adjust historical prices and to annotate chart timelines.

| Column Name | Data Type | Source Field | Nullable | Description |
|---|---|---|---|---|
| `action_id` | BIGINT (AUTO) | System generated | N | Surrogate primary key. |
| `symbol` | VARCHAR(20) | NSE corporate actions | N | NSE trading symbol. FK → dim_stock.symbol. |
| `action_type` | ENUM('Dividend','Bonus','Split','Rights','Buyback') | NSE action type field | N | Type of corporate action. Determines which supplementary fields are populated. |
| `ex_date` | DATE | NSE corporate actions | N | Ex-date — the date from which the buyer does NOT receive the benefit. Critical for price adjustment. |
| `record_date` | DATE | NSE corporate actions | Y | Record date for eligibility determination. May be NULL if not separately announced. |
| `payment_date` | DATE | NSE corporate actions | Y | Payment date (for dividends/buybacks). NULL for bonus/split actions. |
| `purpose_text` | VARCHAR(500) | NSE corporate actions raw text | N | Raw "Purpose" string as announced (e.g. "DIVIDEND - RS 8 PER SHARE OF RE 1 EACH"). Preserved for audit. |
| `ratio_numerator` | DECIMAL(10,4) | Parsed from purpose_text | Y | Numerator of bonus/split/rights ratio (e.g. for "1:1 bonus", value = 1). NULL for dividend/buyback. |
| `ratio_denominator` | DECIMAL(10,4) | Parsed from purpose_text | Y | Denominator of ratio (e.g. for "1:1 bonus", value = 1; for "5:1 split", value = 1). NULL for dividend/buyback. |
| `face_value` | DECIMAL(10,2) | dim_stock.face_value at action time | Y | Face value per share at the time of action. Relevant for rights/split. NULL for dividends. |
| `dividend_amount_per_share` | DECIMAL(10,4) | Parsed from purpose_text | Y | Dividend declared per share in ₹. NULL for all non-dividend action types. |
| `data_source` | VARCHAR(100) | Ingestion pipeline | N | Source of this record (e.g. "NSE_API", "NSE_HTML_SCRAPE", "MANUAL"). |

---

### Table 6: `fact_corporate_event`

**Purpose:** Captures board-level announcements and qualitative corporate events (earnings, M&A, leadership changes, rating changes, etc.) that are relevant to investment decision-making. Unlike `fact_corporate_action`, these events do not have a mechanical price adjustment effect but carry informational significance. NLP categorization is applied to raw announcement text where available.

| Column Name | Data Type | Source Field | Nullable | Description |
|---|---|---|---|---|
| `event_id` | BIGINT (AUTO) | System generated | N | Surrogate primary key. |
| `symbol` | VARCHAR(20) | NSE announcement / manual entry | N | NSE trading symbol. FK → dim_stock.symbol. |
| `event_date` | DATE | NSE announcement date | N | Date the event was announced or effective. |
| `event_type` | ENUM('Earnings','Leadership_Change','M&A','Large_Order','Pledging_Change','Rating_Change','Regulatory','Other') | NLP classifier or manual tag | N | Category of the event. Drives significance scoring defaults. |
| `event_summary` | VARCHAR(500) | LLM/rule-generated summary | N | Concise human-readable summary of the event, max 500 characters. |
| `raw_announcement_text` | TEXT | NSE BSE filing text | Y | Full raw text of the announcement as received. NULL if sourced from aggregated news feed without full text. |
| `categorization_method` | ENUM('Manual','Rule','NLP') | Ingestion pipeline | N | How the event_type was assigned. Enables quality auditing. |
| `significance_score` | INTEGER (1-5) | Rule engine / Manual | N | Importance rating: 1 = Low, 2 = Moderate, 3 = Significant, 4 = High, 5 = Critical. See Section 9 Phase 3 for scoring rules. |
| `price_chg_1d` | DECIMAL(8,4) | Computed post-event | Y | Price change (%) on the event date itself. NULL until T+1. |
| `price_chg_5d` | DECIMAL(8,4) | Computed post-event | Y | Cumulative price change (%) over 5 trading days following event. NULL until T+5. |
| `price_chg_20d` | DECIMAL(8,4) | Computed post-event | Y | Cumulative price change (%) over 20 trading days following event. NULL until T+20. |
| `volume_spike_flag` | BOOLEAN | mart_volume_anomaly join | N | TRUE if volume ratio on event_date or the day after exceeded 1.5x the 20-day average. |
| `follow_up_required` | BOOLEAN | Signal engine | N | TRUE if this event triggers an EVT signal or has unresolved significance requiring review. |

---

### Table 7: `mart_stock_signals`

**Purpose:** Pre-computed daily analytical mart. One row per (calc_date, symbol). Refreshed by the EOD batch job after all `fact_` tables are updated. This is the primary table queried by dashboard pages and the alerting engine. All percentage fields are expressed as decimal percentages (e.g. 12.5 means 12.5%).

| Column Name | Data Type | Source Field | Nullable | Description |
|---|---|---|---|---|
| `calc_date` | DATE | EOD batch job date | N | Calculation date (= trade date of latest data). Composite PK Part 1. |
| `symbol` | VARCHAR(20) | dim_stock.symbol | N | NSE trading symbol. Composite PK Part 2. |
| `return_1d` | DECIMAL(8,4) | (close - prev_close) / prev_close × 100 | N | 1-day price return (%). |
| `return_1m` | DECIMAL(8,4) | (close_today - close_21d_ago) / close_21d_ago × 100 | N | ~1-month return (21 trading days). |
| `return_3m` | DECIMAL(8,4) | (close_today - close_63d_ago) / close_63d_ago × 100 | N | ~3-month return (63 trading days). |
| `return_1y` | DECIMAL(8,4) | (close_today - close_252d_ago) / close_252d_ago × 100 | Y | ~1-year return (252 trading days). NULL if less than 1 year of listing history. |
| `rs_vs_nifty_1m` | DECIMAL(8,4) | return_1m - nifty50_return_1m | N | Alpha vs Nifty 50 over 1 month (percentage points). Positive = outperforming index. |
| `rs_vs_nifty_3m` | DECIMAL(8,4) | return_3m - nifty50_return_3m | N | Alpha vs Nifty 50 over 3 months (percentage points). |
| `rs_vs_nifty_1y` | DECIMAL(8,4) | return_1y - nifty50_return_1y | Y | Alpha vs Nifty 50 over 1 year (percentage points). NULL if return_1y is NULL. |
| `vol_ratio_1d` | DECIMAL(8,4) | volume_today / avg_volume_20d | N | Today's volume as multiple of 20-day average volume. |
| `vol_ratio_5d` | DECIMAL(8,4) | avg(volume last 5d) / avg_volume_20d | N | 5-day average volume as multiple of 20-day average volume. |
| `vol_ratio_20d` | DECIMAL(8,4) | avg(volume last 20d) / avg_volume_60d | N | 20-day average volume as multiple of 60-day average. Measures medium-term volume trend. |
| `drawdown_from_52w_high_pct` | DECIMAL(8,4) | fact_52wk.pct_from_high | N | % decline from 52-week high. Negative value (e.g. -22.5 = 22.5% below high). |
| `distance_from_52w_low_pct` | DECIMAL(8,4) | fact_52wk.pct_from_low | N | % above 52-week low. Positive value (e.g. 35.0 = 35% above low). |
| `avg_volume_20d` | BIGINT | Rolling avg of total_traded_qty over 20 days | N | 20-day rolling average traded quantity. Denominator for volume ratio calculations. |
| `volume_trend_3m` | ENUM('Expanding','Contracting','Mixed') | Linear regression on 63-day volume series | N | Direction of volume trend over 3 months. Expanding = slope positive, Contracting = slope negative, Mixed = R² < 0.3. |
| `iss_score` | DECIMAL(6,2) | compute_iss() function output | N | Investment Signal Score, 0–100. Higher = stronger signal. |
| `signal_category` | ENUM('Accumulation','Momentum','EventDriven','Neutral') | Signal classification engine | N | Primary signal assigned to this stock on this date. |
| `accumulation_flag` | BOOLEAN | ACC rule evaluation | N | TRUE if stock passes all Accumulation Candidate rules on this date. |
| `momentum_flag` | BOOLEAN | MOM rule evaluation | N | TRUE if stock passes all Momentum Candidate rules on this date. |
| `event_flag` | BOOLEAN | EVT rule evaluation | N | TRUE if stock passes Event-Driven Review rules on this date. |
| `last_event_type` | VARCHAR(50) | fact_corporate_event join | Y | event_type of the most recent corporate event. NULL if no event recorded. |
| `last_event_date` | DATE | fact_corporate_event join | Y | Date of the most recent corporate event. NULL if no event recorded. |
| `days_since_last_event` | INTEGER | calc_date - last_event_date | Y | Trading days elapsed since the last corporate event. NULL if no event. |

---

### Table 8: `mart_volume_anomaly`

**Purpose:** Daily mart of volume spike detection results. One row per (calc_date, symbol) where an anomaly condition is met OR for all Nifty 50 stocks (to support full-table dashboard rendering). Populated after `mart_stock_signals` is complete.

| Column Name | Data Type | Source Field | Nullable | Description |
|---|---|---|---|---|
| `calc_date` | DATE | EOD batch job | N | Calculation date. Composite PK Part 1. |
| `symbol` | VARCHAR(20) | dim_stock.symbol | N | NSE trading symbol. Composite PK Part 2. |
| `volume_today` | BIGINT | fact_eod_price.total_traded_qty | N | Shares traded today. |
| `avg_vol_20d` | BIGINT | mart_stock_signals.avg_volume_20d | N | 20-day average volume. |
| `volume_ratio` | DECIMAL(8,4) | volume_today / avg_vol_20d | N | Volume multiple. 1.0 = exactly at average. |
| `spike_level` | ENUM('Normal','Mild','Moderate','High','Extreme') | Threshold classification | N | Normal: ratio < 1.2x · Mild: 1.2–1.5x · Moderate: 1.5–2.0x · High: 2.0–3.0x · Extreme: > 3.0x |
| `price_chg_on_spike_day` | DECIMAL(8,4) | fact_eod_price return calculation | N | Price change (%) on this date. |
| `delivery_pct` | DECIMAL(6,2) | fact_eod_price.delivery_pct | Y | Delivery % on spike day. NULL if not yet available (T+1 release). |
| `nearest_event_within_5d` | VARCHAR(500) | fact_corporate_event join | Y | event_summary of the nearest corporate event within ±5 trading days. NULL if no event in window. |
| `nearest_event_type` | VARCHAR(50) | fact_corporate_event join | Y | event_type of that nearest event. NULL if no event in window. |
| `anomaly_direction` | ENUM('Up','Down') | price_chg_on_spike_day sign | N | Up = price rose on the spike day, Down = price fell. Used for visual color coding. |

---

## Section 6: Signal Rules

### 6.1 Investment Signal Score (ISS) — 0 to 100

The ISS is a composite score that synthesises price momentum, relative strength, drawdown severity, volume behaviour, corporate event catalyst presence, trend stability, and technical positioning into a single 0–100 number. It is not a buy/sell recommendation — it is a prioritisation tool to surface stocks deserving closer analysis.

**Weight Allocation Summary**

| # | Factor | Weight | Measurement | Scoring Scale |
|---|---|---|---|---|
| 1 | Price Performance (3M + 1Y combined) | 25 | Absolute return over 3M and 1Y | 0–25 points |
| 2 | Relative Strength vs Nifty 50 | 20 | Alpha over 3M and 1Y (percentage points) | 0–20 points |
| 3 | Drawdown from 52-Week High | 15 | % decline from rolling 52-week high | 0–15 points (inverse — lower drawdown earns higher points in MOM; higher drawdown earns higher points in ACC mode) |
| 4 | Volume Confirmation | 15 | Volume trend aligns with price direction | 0–15 points |
| 5 | Corporate Event Presence | 10 | High-significance event within 20 days | 0–10 points |
| 6 | Trend Stability | 10 | Consistency of price direction; low choppiness | 0–10 points |
| 7 | Accumulation / Breakout Alignment | 5 | Price near long-term support or breakout zone | 0–5 points |

**Total: 100 points maximum.**

---

#### Factor 1: Price Performance — Weight 25

Split: 3M return contributes 15 points, 1Y return contributes 10 points.

**3M Return Sub-score (0–15):**

| 3M Return Threshold | Points |
|---|---|
| > +25% | 15 |
| +15% to +25% | 12 |
| +10% to +15% | 9 |
| +5% to +10% | 6 |
| 0% to +5% | 3 |
| -5% to 0% | 2 |
| -10% to -5% | 1 |
| < -10% | 0 |

**1Y Return Sub-score (0–10):**

| 1Y Return Threshold | Points |
|---|---|
| > +40% | 10 |
| +25% to +40% | 8 |
| +15% to +25% | 6 |
| +5% to +15% | 4 |
| 0% to +5% | 2 |
| -10% to 0% | 1 |
| < -10% | 0 |

---

#### Factor 2: Relative Strength vs Nifty 50 — Weight 20

Split: RS_3M contributes 12 points, RS_1Y contributes 8 points.

**RS_3M Sub-score (0–12):**

| RS vs Nifty 3M (Alpha %) | Points |
|---|---|
| > +10% | 12 |
| +5% to +10% | 9 |
| +2% to +5% | 6 |
| 0% to +2% | 4 |
| -2% to 0% | 2 |
| -5% to -2% | 1 |
| < -5% | 0 |

**RS_1Y Sub-score (0–8):**

| RS vs Nifty 1Y (Alpha %) | Points |
|---|---|
| > +15% | 8 |
| +8% to +15% | 6 |
| +3% to +8% | 4 |
| 0% to +3% | 2 |
| < 0% | 0 |

---

#### Factor 3: Drawdown from 52-Week High — Weight 15

Note: This factor is directionally **context-aware**. For stocks with `momentum_flag = TRUE`, lower drawdown earns more points (stock is holding near highs). For stocks in `accumulation` mode, a deep drawdown is intentional and points are awarded inversely to reward high-conviction value entry zones.

**Standard (Momentum) Scoring — Lower drawdown = higher score:**

| Drawdown from 52w High | Points |
|---|---|
| 0% to -5% (near all-time high) | 15 |
| -5% to -10% | 12 |
| -10% to -15% | 9 |
| -15% to -20% | 6 |
| -20% to -30% | 3 |
| > -30% | 0 |

**Accumulation Mode Scoring — Deeper drawdown = higher score (rewards beaten-down quality stocks):**

| Drawdown from 52w High | Points |
|---|---|
| > -40% | 15 |
| -30% to -40% | 12 |
| -20% to -30% | 9 |
| -15% to -20% | 6 |
| -10% to -15% | 3 |
| < -10% | 0 |

The signal engine applies the appropriate mode after Factor 1–2 assessment. Stocks where `return_3m < -10%` and `return_1y < -20%` are evaluated in Accumulation mode for this factor.

---

#### Factor 4: Volume Confirmation — Weight 15

Measures whether volume behaviour supports the price trend.

| Condition | Points |
|---|---|
| Price rising AND vol_ratio_1d > 2.0x (strong bullish confirmation) | 15 |
| Price rising AND vol_ratio_1d 1.5–2.0x | 12 |
| Price rising AND vol_ratio_1d 1.2–1.5x | 9 |
| Price rising AND vol_ratio_1d 0.8–1.2x (neutral volume) | 5 |
| Price falling AND vol_ratio_1d < 0.8x (declining on low volume — possible exhaustion, not distribution) | 5 |
| Price falling AND vol_ratio_1d 0.8–1.2x | 3 |
| Price falling AND vol_ratio_1d 1.2–2.0x (distribution signal) | 1 |
| Price falling AND vol_ratio_1d > 2.0x (panic/forced selling) | 0 |
| volume_trend_3m = Expanding AND price trend positive | Bonus +2 (capped at 15 total) |

---

#### Factor 5: Corporate Event Presence — Weight 10

| Condition | Points |
|---|---|
| significance_score = 5 event within 10 days | 10 |
| significance_score = 4 event within 10 days | 8 |
| significance_score = 5 event within 11–20 days | 7 |
| significance_score = 3 event within 10 days | 6 |
| significance_score = 4 event within 11–20 days | 5 |
| significance_score = 3 event within 11–20 days | 3 |
| significance_score ≤ 2 event within 20 days | 1 |
| No event within 20 days | 0 |
| Negative event (Rating_Change/Regulatory) of significance ≥ 4 within 10 days | Override: deduct 5 from total ISS |

---

#### Factor 6: Trend Stability — Weight 10

Measured using direction consistency: out of the last 20 trading days, what fraction closed in the same direction (up or down) as the overall 20-day trend?

| Direction Consistency (% of days in trend direction) | Points |
|---|---|
| ≥ 70% (very stable trend, low choppiness) | 10 |
| 60–70% | 8 |
| 50–60% | 5 |
| 40–50% (choppy, mixed) | 2 |
| < 40% (highly erratic) | 0 |

Additional rule: If `return_3m > 0` but the stock has experienced 3 or more intraday reversals of > 2% in the last 20 days, deduct 2 points (capped at 0).

---

#### Factor 7: Accumulation / Breakout Alignment — Weight 5

| Condition | Points |
|---|---|
| Price within 3% of 52-week low AND volume_trend_3m = Expanding (accumulation zone) | 5 |
| Price within 3% above 52-week high (breakout zone) | 5 |
| Price within 5% of 52-week low | 4 |
| Price within 5% above 52-week high | 4 |
| Price within 10% of 52-week low | 3 |
| Distance from both extremes > 15% (mid-range) | 1 |
| Price declining and > 20% below 52-week high | 0 |

---

### 6.2 Signal Category Rules (Exact Rule Logic)

#### Accumulation Candidate (tag: `ACC`)

A stock is tagged ACC when it satisfies **all** of the following conditions:

```
ACC_RULE = (
    return_1y < -20%
    AND return_3m < -10%
    AND drawdown_from_52w_high_pct < -25%           # i.e. more than 25% below peak
    AND volume_trend_3m IN ('Mixed', 'Contracting') # volume not accelerating downward
    AND NOT (
        last_event_type IN ('Regulatory', 'Rating_Change')
        AND last_event_date >= calc_date - 30 days
        AND significance_score >= 3                 # no recent significant negative event
    )
    AND nifty50_member = TRUE                       # index quality filter
    AND iss_score >= 35                             # minimum signal floor
)
```

**Falling Knife Risk Exclusion (sub-rule — overrides ACC tag):**

A stock that passes the ACC rule is downgraded from ACC to Neutral and flagged `falling_knife_risk = TRUE` if:

```
FALLING_KNIFE_EXCLUSION = (
    volume_trend_3m = 'Contracting'                 # volume drying up (lack of buyers)
    AND dividend_amount_per_share IS NULL            # no income cushion
    AND pe_ratio IS NOT NULL AND pe_ratio < pe_5yr_avg * 0.6   # P/E contracting aggressively
    AND return_3m < -20%                            # accelerating deterioration
)
```

> Rationale: A falling knife stock is one where the price decline is accelerating with no volume support and no fundamental anchor (dividend or mean-reverting P/E). Nifty 50 membership alone does not preclude this risk.

---

#### Momentum Candidate (tag: `MOM`)

A stock is tagged MOM when it satisfies **all** of the following:

```
MOM_RULE = (
    (return_3m > +15% OR return_1y > +30%)
    AND (vol_ratio_1d > 1.3 OR vol_ratio_5d > 1.3)  # volume expansion (either daily or 5-day)
    AND rs_vs_nifty_3m > +5%                        # outperforming index materially
    AND NOT (
        last_event_type IN ('Regulatory', 'Rating_Change', 'Leadership_Change')
        AND last_event_date >= calc_date - 20 days
        AND significance_score >= 3                 # no major negative event recently
    )
    AND iss_score >= 60                             # minimum quality floor for momentum tag
)
```

**Momentum Strength Tiers:**

| ISS Score | MOM Tier |
|---|---|
| 85–100 | MOM-Strong |
| 70–84 | MOM-Confirmed |
| 60–69 | MOM-Watch |

---

#### Event-Driven Review Candidate (tag: `EVT`)

```
EVT_RULE = (
    (
        significance_score >= 3
        AND event_date >= calc_date - 20 days       # recent high-significance event
        AND ABS(price_chg_5d) > 5%                 # material price reaction in 5 days post-event
    )
    OR (
        upcoming_event_date <= calc_date + 10 days  # upcoming scheduled event (e.g. earnings date)
        AND upcoming_significance_estimate >= 3
    )
)
```

- All stocks meeting the EVT rule must have `follow_up_required = TRUE` in `fact_corporate_event`.
- EVT tags co-exist with ACC or MOM — a stock can be tagged `MOM+EVT` or `ACC+EVT`.
- EVT-only stocks (neither ACC nor MOM) are placed in `signal_category = 'EventDriven'`.

---

### 6.3 Volume Anomaly Rules

The volume anomaly engine classifies each (date, symbol) observation into one of the following conditions. Rules are evaluated in priority order (first match wins).

| Condition ID | Rule | Label | Action |
|---|---|---|---|
| VA-1 | `volume_ratio > 2.0 AND price_chg > +3%` | **Bullish Volume Surge** | Flag for momentum review; check for event proximity |
| VA-2 | `volume_ratio > 2.0 AND price_chg < -3%` | **Distribution Signal** | Flag for risk review; check for negative event |
| VA-3 | `volume_ratio > 2.0 AND ABS(price_chg) < 1%` | **Accumulation/Distribution Unclear — Watch** | Monitor next 3 sessions for directional resolution |
| VA-4 | `volume_ratio < 0.4 for 5 consecutive sessions` | **Drying Up — Potential Breakout Setup** | Add to watchlist for breakout monitoring |
| VA-5 | `volume_ratio > 3.0 AND event within ±3 trading days` | **Event-Driven Volume — Categorize Event First** | Pause signal classification; verify event before acting |
| VA-6 | `volume_ratio > 1.5 AND delivery_pct > 60%` | **Institutional Accumulation Likely** | Positive signal; delivery quality confirms conviction |
| VA-7 | `volume_ratio > 1.5 AND delivery_pct < 25%` | **Speculative Activity — Low Delivery** | Caution; intraday/speculative driven, not accumulation |

---

## Section 7: Sample Scoring Formula

### 7.1 Python-Style Pseudocode: `compute_iss(stock)`

```python
def compute_iss(stock: dict) -> float:
    """
    Compute the Investment Signal Score (ISS) for a single stock record.
    
    Parameters
    ----------
    stock : dict
        A row from mart_stock_signals with all required fields populated.
        Keys: return_1d, return_1m, return_3m, return_1y,
              rs_vs_nifty_3m, rs_vs_nifty_1y,
              drawdown_from_52w_high_pct, distance_from_52w_low_pct,
              vol_ratio_1d, vol_ratio_5d, volume_trend_3m,
              days_since_last_event, last_event_significance,
              last_event_type, last_event_is_negative,
              direction_consistency_20d, intraday_reversal_count_20d,
              pct_from_52w_low, pct_below_52w_high,
              nifty50_member
    
    Returns
    -------
    float : ISS score, clamped to [0, 100]
    """
    score = 0.0
    
    # ─────────────────────────────────────────────────────
    # FACTOR 1: Price Performance (max 25 points)
    # ─────────────────────────────────────────────────────
    
    # Sub-factor 1a: 3M Return (max 15 points)
    r3m = stock["return_3m"]
    if r3m > 25:
        f1a = 15
    elif r3m > 15:
        f1a = 12
    elif r3m > 10:
        f1a = 9
    elif r3m > 5:
        f1a = 6
    elif r3m > 0:
        f1a = 3
    elif r3m > -5:
        f1a = 2
    elif r3m > -10:
        f1a = 1
    else:
        f1a = 0
    
    # Sub-factor 1b: 1Y Return (max 10 points)
    r1y = stock.get("return_1y")
    if r1y is None:
        f1b = 3  # default for newly listed stocks (< 1 year history)
    elif r1y > 40:
        f1b = 10
    elif r1y > 25:
        f1b = 8
    elif r1y > 15:
        f1b = 6
    elif r1y > 5:
        f1b = 4
    elif r1y > 0:
        f1b = 2
    elif r1y > -10:
        f1b = 1
    else:
        f1b = 0
    
    score += f1a + f1b  # max 25
    
    # ─────────────────────────────────────────────────────
    # FACTOR 2: Relative Strength vs Nifty 50 (max 20 points)
    # ─────────────────────────────────────────────────────
    
    # Sub-factor 2a: RS 3M (max 12 points)
    rs3m = stock["rs_vs_nifty_3m"]
    if rs3m > 10:
        f2a = 12
    elif rs3m > 5:
        f2a = 9
    elif rs3m > 2:
        f2a = 6
    elif rs3m > 0:
        f2a = 4
    elif rs3m > -2:
        f2a = 2
    elif rs3m > -5:
        f2a = 1
    else:
        f2a = 0
    
    # Sub-factor 2b: RS 1Y (max 8 points)
    rs1y = stock.get("rs_vs_nifty_1y")
    if rs1y is None:
        f2b = 2
    elif rs1y > 15:
        f2b = 8
    elif rs1y > 8:
        f2b = 6
    elif rs1y > 3:
        f2b = 4
    elif rs1y > 0:
        f2b = 2
    else:
        f2b = 0
    
    score += f2a + f2b  # max 20
    
    # ─────────────────────────────────────────────────────
    # FACTOR 3: Drawdown from 52-Week High (max 15 points)
    # Mode-aware: Accumulation vs Momentum context
    # ─────────────────────────────────────────────────────
    
    drawdown = stock["drawdown_from_52w_high_pct"]  # negative number, e.g. -22.5
    is_acc_mode = (stock["return_3m"] < -10 and stock.get("return_1y", 0) < -20)
    
    if is_acc_mode:
        # Deep drawdown earns MORE points in accumulation mode
        if drawdown < -40:
            f3 = 15
        elif drawdown < -30:
            f3 = 12
        elif drawdown < -20:
            f3 = 9
        elif drawdown < -15:
            f3 = 6
        elif drawdown < -10:
            f3 = 3
        else:
            f3 = 0
    else:
        # Standard: lower drawdown (stock near highs) earns more points
        if drawdown > -5:
            f3 = 15
        elif drawdown > -10:
            f3 = 12
        elif drawdown > -15:
            f3 = 9
        elif drawdown > -20:
            f3 = 6
        elif drawdown > -30:
            f3 = 3
        else:
            f3 = 0
    
    score += f3  # max 15
    
    # ─────────────────────────────────────────────────────
    # FACTOR 4: Volume Confirmation (max 15 points)
    # ─────────────────────────────────────────────────────
    
    vr1d = stock["vol_ratio_1d"]
    r1d  = stock["return_1d"]
    vtm  = stock["volume_trend_3m"]  # 'Expanding', 'Contracting', 'Mixed'
    
    price_rising = (r1d > 0)
    
    if price_rising:
        if vr1d > 2.0:
            f4 = 15
        elif vr1d > 1.5:
            f4 = 12
        elif vr1d > 1.2:
            f4 = 9
        elif vr1d >= 0.8:
            f4 = 5
        else:
            f4 = 3  # rising on declining volume — weak signal
    else:
        # Price falling
        if vr1d > 2.0:
            f4 = 0  # heavy distribution
        elif vr1d > 1.2:
            f4 = 1  # distribution
        elif vr1d >= 0.8:
            f4 = 3  # neutral volume on decline
        else:
            f4 = 5  # falling on low volume — possible exhaustion, not alarming
    
    # Bonus: 3M volume trend expanding with positive price trend
    if vtm == "Expanding" and price_rising:
        f4 = min(15, f4 + 2)
    
    score += f4  # max 15
    
    # ─────────────────────────────────────────────────────
    # FACTOR 5: Corporate Event Presence (max 10 points)
    # ─────────────────────────────────────────────────────
    
    days_since = stock.get("days_since_last_event")  # None if no event
    sig         = stock.get("last_event_significance", 0)
    is_negative = stock.get("last_event_is_negative", False)
    
    if days_since is None or days_since > 20:
        f5 = 0
    elif sig == 5 and days_since <= 10:
        f5 = 10
    elif sig == 4 and days_since <= 10:
        f5 = 8
    elif sig == 5 and days_since <= 20:
        f5 = 7
    elif sig == 3 and days_since <= 10:
        f5 = 6
    elif sig == 4 and days_since <= 20:
        f5 = 5
    elif sig == 3 and days_since <= 20:
        f5 = 3
    else:
        f5 = 1
    
    score += f5  # max 10
    
    # ─────────────────────────────────────────────────────
    # FACTOR 6: Trend Stability (max 10 points)
    # ─────────────────────────────────────────────────────
    
    consistency = stock["direction_consistency_20d"]  # fraction, e.g. 0.65
    reversals   = stock.get("intraday_reversal_count_20d", 0)
    
    if consistency >= 0.70:
        f6 = 10
    elif consistency >= 0.60:
        f6 = 8
    elif consistency >= 0.50:
        f6 = 5
    elif consistency >= 0.40:
        f6 = 2
    else:
        f6 = 0
    
    if reversals >= 3:
        f6 = max(0, f6 - 2)  # penalise erratic behaviour
    
    score += f6  # max 10
    
    # ─────────────────────────────────────────────────────
    # FACTOR 7: Accumulation / Breakout Alignment (max 5 points)
    # ─────────────────────────────────────────────────────
    
    pct_from_low  = stock["distance_from_52w_low_pct"]   # positive, e.g. 4.2 = 4.2% above low
    pct_below_high = abs(stock["drawdown_from_52w_high_pct"])  # positive, e.g. 2.1 = 2.1% below high
    vol_trend      = stock["volume_trend_3m"]
    
    near_low      = pct_from_low <= 3
    near_high     = pct_below_high <= 3
    vol_expanding = (vol_trend == "Expanding")
    
    if (near_low and vol_expanding) or near_high:
        f7 = 5
    elif pct_from_low <= 5 or pct_below_high <= 5:
        f7 = 4
    elif pct_from_low <= 10:
        f7 = 3
    elif pct_below_high > 15 and not price_rising:
        f7 = 0
    else:
        f7 = 1
    
    score += f7  # max 5
    
    # ─────────────────────────────────────────────────────
    # PENALTY: Recent high-significance negative event
    # ─────────────────────────────────────────────────────
    
    if is_negative and sig >= 4 and days_since is not None and days_since <= 10:
        score -= 5
    
    # ─────────────────────────────────────────────────────
    # CLAMP and RETURN
    # ─────────────────────────────────────────────────────
    
    return round(max(0.0, min(100.0, score)), 2)
```

---

### 7.2 Sample JSON Output Record — `mart_stock_signals`

The following illustrates a realistic record for BAJFINANCE (Bajaj Finance Ltd) on a date where it is showing emerging momentum characteristics after a correction phase.

```json
{
  "calc_date": "2024-11-15",
  "symbol": "BAJFINANCE",
  "return_1d": 1.82,
  "return_1m": 8.45,
  "return_3m": 17.30,
  "return_1y": 22.10,
  "rs_vs_nifty_1m": 5.12,
  "rs_vs_nifty_3m": 8.65,
  "rs_vs_nifty_1y": 6.20,
  "vol_ratio_1d": 1.68,
  "vol_ratio_5d": 1.42,
  "vol_ratio_20d": 1.15,
  "drawdown_from_52w_high_pct": -8.40,
  "distance_from_52w_low_pct": 38.60,
  "avg_volume_20d": 4820000,
  "volume_trend_3m": "Expanding",
  "iss_score": 74.50,
  "signal_category": "Momentum",
  "accumulation_flag": false,
  "momentum_flag": true,
  "event_flag": true,
  "last_event_type": "Earnings",
  "last_event_date": "2024-11-07",
  "days_since_last_event": 6,
  "last_event_significance": 4,
  "last_event_is_negative": false,
  "direction_consistency_20d": 0.65,
  "intraday_reversal_count_20d": 1,
  "wk52_high": 8190.00,
  "wk52_low": 5480.00,
  "close_price": 7502.35,
  "nifty50_member": true,
  "mom_tier": "MOM-Confirmed",
  "falling_knife_risk": false,
  "follow_up_required": true
}
```

**Score breakdown for this record:**
- F1 (Price Performance): r3m=17.3% → 12 pts; r1y=22.1% → 6 pts = **18 pts**
- F2 (Relative Strength): rs3m=8.65% → 9 pts; rs1y=6.2% → 4 pts = **13 pts**
- F3 (Drawdown): -8.4% in standard mode → 12 pts = **12 pts**
- F4 (Volume): price rising, vr1d=1.68x → 12 pts; volume_trend Expanding +2 = **14 pts** (capped at 15)
- F5 (Event): sig=4, 6 days ago → **8 pts**
- F6 (Trend Stability): consistency=0.65 → 8 pts; 1 reversal → no penalty = **8 pts**
- F7 (Alignment): pct_from_low=38.6%, pct_below_high=8.4% → neither near low nor high = **1 pt**
- **Raw total: 74 pts → ISS = 74.50** (slight rounding from float arithmetic)

---

## Section 8: Recommended Alert Rules

The alerting layer monitors `mart_stock_signals`, `mart_volume_anomaly`, `fact_corporate_event`, and `dim_nifty50_constituent` and fires notifications when conditions are met. Alert frequency is calibrated to avoid fatigue — daily EOD is the default for most signals; real-time is reserved for structurally significant or time-sensitive conditions.

| # | Alert Name | Trigger Condition | Target Persona | Channel | Frequency |
|---|---|---|---|---|---|
| A-01 | **Nifty 50 Deep Drawdown** | `drawdown_from_52w_high_pct < -20%` for any Nifty 50 stock | Long-term investor, risk monitor | Dashboard notification + Email | Daily EOD |
| A-02 | **ISS Momentum Breakout** | `iss_score` crosses above 70 (previous day < 70, today ≥ 70) | Active investor, trader | Dashboard notification + Email | Daily EOD |
| A-03 | **ISS Momentum Breakdown** | `iss_score` drops below 40 having been above 60 within prior 10 sessions | Portfolio holder of that stock | Dashboard notification + Email | Daily EOD |
| A-04 | **Extreme Volume Spike** | `spike_level = 'Extreme'` (volume ratio > 3.0x) for any Nifty 50 stock | All users | Dashboard notification (real-time if intraday feed available) | Real-time / Daily EOD fallback |
| A-05 | **Critical Corporate Event** | New `fact_corporate_event` row with `significance_score ≥ 4` for a Nifty 50 stock | All users | Dashboard notification + Email + SMS | Real-time (on event ingestion) |
| A-06 | **Index Reconstitution** | New row in `dim_nifty50_constituent` with `change_type IN ('Addition','Deletion')` | All users | Dashboard notification + Email | Real-time (on data ingestion) |
| A-07 | **Watchlist Large Single-Day Move** | `ABS(return_1d) ≥ 5%` for any stock in user's active watchlist | Watchlist owner | Dashboard notification + Email + SMS | Daily EOD |
| A-08 | **Market Breadth Stress** | Count of Nifty 50 stocks with `return_1d > 0` ÷ 50 < 20% (fewer than 10 stocks advancing) | Macro-aware investor | Dashboard notification + Email | Daily EOD |
| A-09 | **Multiple 52-Week Lows** | 3 or more Nifty 50 stocks record `drawdown_from_52w_high_pct` at new minimum (i.e. new 52w low hit today) in a single session | Risk monitor | Dashboard notification + Email | Daily EOD |
| A-10 | **Accumulation Candidate Volume Surge** | Stock has `accumulation_flag = TRUE` AND `vol_ratio_1d > 1.5` AND `return_1d > 0` — first such occurrence after 10+ consecutive sessions of `vol_ratio_1d < 1.0` | Value investor | Dashboard notification + Email | Daily EOD |
| A-11 | **Promoter Pledging Change** | New `fact_corporate_event` row with `event_type = 'Pledging_Change'` AND `symbol` in Nifty 50 | Risk-conscious investor | Dashboard notification + Email | Real-time (on event ingestion) |
| A-12 | **Rating Downgrade** | New `fact_corporate_event` with `event_type = 'Rating_Change'` AND `significance_score ≥ 3` AND the raw text contains keywords: ["downgrade", "negative watch", "outlook revised to negative", "CreditWatch Negative"] | All users holding or watching the stock | Dashboard notification + Email + SMS | Real-time (on event ingestion) |
| A-13 | **Breakout Near 52-Week High** | `pct_below_52w_high` crosses from > 2% to ≤ 1% (stock approaching prior peak) AND `vol_ratio_1d > 1.3` | Momentum investor | Dashboard notification | Daily EOD |
| A-14 | **Sustained Volume Dryup** | `vol_ratio_1d < 0.4` for 5 or more consecutive sessions (VA-4 condition) | Breakout trader | Dashboard notification | Daily EOD |

**Alert Deduplication Rule:** For A-01, A-02, A-03, A-07: once an alert has fired for a given (symbol, alert_type) pair, it will not re-fire for the same pair within 5 trading days unless the condition resets (stock exits and re-enters the threshold). This prevents daily spam on persistent conditions.

**Alert Severity Levels:**

| Severity | Colour | Channels Used |
|---|---|---|
| Critical | Red | Dashboard + Email + SMS |
| High | Orange | Dashboard + Email |
| Medium | Yellow | Dashboard notification only |
| Low | Grey | Dashboard (silent, visible on Alerts page) |

---

## Section 9: Engineering Design — Phases, Milestones, and LLM Prompt Stubs

### Phase Overview Table

| Phase | Name | Duration | Key Deliverables |
|---|---|---|---|
| 1 | Data Infrastructure | 2–3 weeks | Ingestion pipelines for Bhavcopy, 52-week file, constituents, corporate actions/events; DB schema; 5-year backfill |
| 2 | Core Analytics Engine | 2–3 weeks | Return computations, volume metrics, RS calculations, drawdown logic, mart_stock_signals daily job |
| 3 | Signal Engine | 1–2 weeks | ISS scoring function, ACC/MOM/EVT classifiers, volume anomaly detector, event significance scorer, watchlist logic |
| 4 | Dashboard UI | 3–4 weeks | 7 pages: Market Overview, Movers, Drawdown Scanner, Momentum Monitor, Volume Anomaly, Corporate Events, Watchlist Builder |
| 5 | Alerting + Automation | 1–2 weeks | EOD batch scheduler, alert condition engine, email/push delivery, optional intraday refresh |
| 6 | Validation + Hardening | 1–2 weeks | Data quality checks, 3-year signal back-test, query optimisation, documentation and runbook |

**Estimated Total: 10–16 weeks for a solo developer; 6–10 weeks with a 2-person team.**

---

### Phase 1: Data Infrastructure

#### Milestone 1.1 — NSE Bhavcopy Ingestion Pipeline

**LLM Prompt Stub:**

```
Task: Build a Python pipeline to download and ingest NSE Bhavcopy CSV files into a 
PostgreSQL table called `fact_eod_price`.

Context:
- NSE publishes daily Bhavcopy files at: https://archives.nseindia.com/content/historical/EQUITIES/<YYYY>/<MON>/cm<DDMMMYYYY>bhav.csv.zip
- Each file contains one row per listed security with columns: SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, PREVCLOSE, TOTTRDQTY, TOTTRDVAL, TIMESTAMP, TOTALTRADES, ISIN
- NSE delivery position files (for delivery_qty and delivery_pct) are published at: https://archives.nseindia.com/archives/equities/mto/MTO_<DDMMYYYY>.DAT

Inputs:
- Date range: configurable start_date to end_date (default: backfill 5 years)
- Target DB: PostgreSQL (connection string from environment variable NIFTY_DB_URL)

Outputs:
- Rows inserted into `fact_eod_price` per the schema defined in the dashboard spec
- Ingestion log table recording: file downloaded, rows inserted, rows failed, timestamp
- Delivery data joined in a T+1 update pass (separate scheduled job)

Tech stack: Python 3.11, pandas, SQLAlchemy, psycopg2, requests, zipfile

Edge cases to handle:
- NSE website 403/429 rate limits (add exponential backoff, 2s minimum delay between requests)
- Market holidays (no file published — skip gracefully, log as expected gap)
- Corrupted/partial downloads (checksum or row count validation against prior day)
- Duplicate ingestion runs (use INSERT ... ON CONFLICT (trade_date, symbol) DO NOTHING)
- Series filter: only ingest rows where SERIES IN ('EQ', 'BE', 'BL', 'SM', 'ST')

Produce: download_bhavcopy.py, ingest_bhavcopy.py, and a README.md explaining the schedule and retry logic.
```

---

#### Milestone 1.2 — 52-Week High/Low File Ingestion

**LLM Prompt Stub:**

```
Task: Build a Python job to compute and populate the `fact_52wk` table using data 
already present in `fact_eod_price`.

Context:
- NSE also publishes a 52-week high/low file, but computing it from `fact_eod_price` 
  is more reliable and avoids dependency on a separate feed.
- The lookback window is exactly 252 trading days (not calendar days).
- This job must run AFTER `fact_eod_price` is fully loaded for the current trading day.

Computation logic:
- For each (symbol, trade_date) where trade_date = today:
    wk52_high = MAX(close) over the past 252 rows for that symbol
    wk52_low  = MIN(close) over the past 252 rows for that symbol
    wk52_high_date = trade_date of that MAX row
    wk52_low_date  = trade_date of that MIN row
    pct_from_high  = (today_close - wk52_high) / wk52_high * 100
    pct_from_low   = (today_close - wk52_low) / wk52_low * 100

Tech stack: Python 3.11, pandas (use .rolling() or window functions), 
SQLAlchemy for DB read/write, PostgreSQL.

Alternatively: implement using a single SQL window function query for performance.

Edge cases:
- Symbols with fewer than 252 trading days of history (use available window, 
  set a min_history_flag = TRUE in the record)
- Corporate actions (bonus/split) can cause apparent spikes in historical price — 
  note that adjustment for corporate actions is out of scope for Phase 1 
  but must be designed to be addable later (do not hardcode raw prices as final)
- Ensure idempotency: use INSERT ... ON CONFLICT (trade_date, symbol) DO UPDATE

Output: compute_52wk.py and SQL migration file for fact_52wk table.
```

---

#### Milestone 1.3 — Nifty 50 Constituents and Reconstitution Table

**LLM Prompt Stub:**

```
Task: Create the `dim_nifty50_constituent` table and build a loader for historical 
and current Nifty 50 membership data.

Context:
- NSE publishes index composition changes via press releases and the NIFTY 50 
  factsheet PDF available at https://niftyindices.com/
- Historical reconstitution data for the past 5 years must be manually compiled 
  from NSE circulars into a seed CSV file: nifty50_history.csv
- Ongoing changes are ingested when NSE publishes new reconstitution announcements

Seed CSV columns: symbol, effective_from, effective_to, index_weight_pct, 
replaced_symbol, change_type, review_period

Loader behaviour:
- On first run: bulk insert all rows from nifty50_history.csv
- On subsequent runs (maintenance mode): accept a new_addition.json / new_deletion.json
  file and upsert the appropriate rows, automatically setting effective_to on 
  the outgoing stock record

Also create a helper function: is_nifty50_member(symbol, as_of_date) -> bool
that queries dim_nifty50_constituent for point-in-time membership. 
This is critical for back-testing.

Tech stack: Python, pandas, SQLAlchemy, PostgreSQL.

Edge cases:
- Same symbol re-entering after deletion (e.g. a stock added, removed, re-added) 
  — allow multiple rows per symbol with non-overlapping date ranges
- Weight changes without membership change (Rebalance type) — update weight only, 
  do not create a new membership interval
- Data entry errors in seed CSV — add schema validation before insert

Output: load_constituents.py, nifty50_history.csv (template), and 
is_nifty50_member() utility function.
```

---

#### Milestone 1.4 — Corporate Actions and Events Ingestion Pipeline

**LLM Prompt Stub:**

```
Task: Build two ingestion pipelines: one for `fact_corporate_action` (mechanical 
actions: dividends, bonus, splits) and one for `fact_corporate_event` 
(qualitative announcements: earnings, M&A, leadership changes, rating changes).

Source 1 — Corporate Actions:
- NSE Corporate Actions page: https://www.nseindia.com/companies-listing/corporate-filings-corporate-actions
- Fields available: Symbol, Company Name, Purpose, Ex-Date, Record Date, BC Start/End Date, ND Start/End Date, Payment Date
- Parse the "Purpose" free-text field to extract: action_type (Dividend/Bonus/Split/Rights/Buyback), 
  dividend_amount_per_share, ratio_numerator/denominator using regex patterns.

Source 2 — Corporate Events:
- NSE announcements feed (or BSE XML feed as fallback)
- For MVP, accept a daily CSV export from NSE's announcement section
- Apply keyword-based rule classification to assign event_type
- Leave raw_announcement_text populated for future NLP enrichment

Parsing rules for action_type from purpose_text:
  - Contains "DIVIDEND" → Dividend; parse "RS X.XX" for amount
  - Contains "BONUS" → Bonus; parse ratio like "X:Y"
  - Contains "SPLIT" → Split; parse ratio from "FROM RS X TO RS Y"
  - Contains "RIGHTS" → Rights
  - Contains "BUY BACK" or "BUYBACK" → Buyback

Tech stack: Python, pandas, regex, BeautifulSoup (for HTML tables), 
SQLAlchemy, PostgreSQL.

Edge cases:
- Duplicate announcements (same action_type + ex_date + symbol published twice) — 
  deduplicate on (symbol, action_type, ex_date) composite key
- Missing ex_date (use record_date as proxy, flag in data_source field)
- Multi-part purpose text (e.g. interim + final dividend combined) — split into 
  separate rows

Output: ingest_corporate_actions.py, ingest_corporate_events.py, 
purpose_parser.py (regex library), and unit tests.
```

---

#### Milestone 1.5 — Database Schema Creation and 5-Year Backfill

**LLM Prompt Stub:**

```
Task: Create all database tables (migration scripts) and run the full 5-year 
historical backfill for all `fact_` and `dim_` tables.

Schema requirements:
- Use PostgreSQL 15+
- Implement all 8 tables defined in the dashboard spec (dim_stock, fact_eod_price, 
  fact_52wk, dim_nifty50_constituent, fact_corporate_action, fact_corporate_event, 
  mart_stock_signals, mart_volume_anomaly)
- Apply appropriate indexes: (trade_date, symbol) on all fact_ tables; 
  symbol on all tables; trade_date DESC BRIN index on time-series tables
- Use Alembic for migrations (version-controlled schema changes)

Backfill sequence (order matters due to FK dependencies):
  1. dim_stock (seed from NSE security master CSV)
  2. dim_nifty50_constituent (from nifty50_history.csv)
  3. fact_eod_price (Bhavcopy, 5 years = ~1250 trading days × 2000 symbols)
  4. fact_52wk (derived from fact_eod_price, run after step 3 completes)
  5. fact_corporate_action (5-year NSE corporate actions dump)
  6. fact_corporate_event (best-effort from available announcements)

Performance targets for backfill:
- fact_eod_price: 5-year full load should complete in < 30 minutes using 
  bulk COPY or pandas to_sql with chunksize=10000
- fact_52wk: computed via SQL window function in a single query (< 5 minutes)

Edge cases:
- NSE download rate limiting during backfill — implement a polite crawler with 
  2-second sleep between requests; cache all downloaded ZIP files locally 
  to avoid re-downloading on failure
- Missing trading days in the middle of history — detect and log gaps; 
  do not attempt to fill synthetic data
- Symbol renames (e.g. INFRATEL → INDUSINDBK post-merger): handle via 
  a symbol_alias table, not by modifying primary records

Output: alembic migrations (versions/ folder), backfill_orchestrator.py 
(runs all steps in order with progress logging), and a validation report 
confirming row counts per year.
```

---

### Phase 2: Core Analytics Engine

#### Milestone 2.1 — Daily Return Computation

**LLM Prompt Stub:**

```
Task: Build a Python/SQL function compute_returns(symbol, calc_date) that calculates 
1D, 1M (21 trading days), 3M (63 trading days), and 1Y (252 trading days) 
price returns for a given symbol and populates the corresponding columns 
in mart_stock_signals.

Inputs: fact_eod_price table; symbol; calc_date (today's trading date)

Return formula for each period:
  return_Nd = (close_at_calc_date - close_at_calc_date_minus_N_trading_days) 
              / close_at_calc_date_minus_N_trading_days * 100

Lookback alignment rules:
- Use ONLY actual trading days (skip weekends and NSE holidays)
- Maintain a trading_calendar table (populated from Bhavcopy date sequence)
  to resolve "21 trading days ago" to a calendar date
- If insufficient history (< N trading days available), return NULL for that period
- Do NOT interpolate or forward-fill missing close prices for the lookback day

Output: populate return_1d, return_1m, return_3m, return_1y columns in 
mart_stock_signals for all Nifty 50 symbols for calc_date.

Implementation: prefer a single SQL window function query using LAG() 
with a trading day offset table for performance. 
Provide a Python wrapper that calls this SQL.

Tech stack: Python, SQLAlchemy, PostgreSQL, pandas (for validation).
Edge cases: corporate actions between lookback date and today 
(note: price adjustment is Phase 6; for now, flag records where a 
bonus/split occurred in the lookback window with an adjustment_needed flag).
```

---

#### Milestone 2.2 — Volume Averages, Ratios, and Trend Classification

**LLM Prompt Stub:**

```
Task: Build a module to compute volume metrics and populate vol_ratio_1d, 
vol_ratio_5d, vol_ratio_20d, avg_volume_20d, and volume_trend_3m 
columns in mart_stock_signals.

Computation steps:

1. avg_volume_20d: rolling 20-trading-day simple moving average of 
   total_traded_qty from fact_eod_price

2. vol_ratio_1d: total_traded_qty_today / avg_volume_20d
   vol_ratio_5d: mean(total_traded_qty over last 5 days) / avg_volume_20d
   vol_ratio_20d: avg_volume_20d / rolling_60d_avg_volume (measures medium-term trend)

3. volume_trend_3m:
   - Compute daily volume series for the past 63 trading days
   - Fit a linear regression (scipy.stats.linregress or numpy.polyfit) to the series
   - If slope > 0 AND R² ≥ 0.30: label 'Expanding'
   - If slope < 0 AND R² ≥ 0.30: label 'Contracting'
   - Else: label 'Mixed'

Performance note: vectorise using pandas groupby + rolling() across all 
symbols simultaneously rather than looping per symbol.

Edge cases:
- Symbols with fewer than 20 trading days of data: set vol_ratio to NULL
- Extreme outlier volumes (> 10x historical avg, e.g. due to index rebalancing 
  or block deals): cap at 10x for the rolling average calculation only 
  (preserve raw value in fact_eod_price)
- Block deal series (SERIES = 'BL'): exclude from avg_volume_20d calculation 
  to avoid distorting normal volume baseline

Output: compute_volume_metrics.py; update mart_stock_signals for all 
Nifty 50 symbols daily.
```

---

#### Milestone 2.3 — RS vs Nifty 50 Alpha Computation

**LLM Prompt Stub:**

```
Task: Compute relative strength (alpha) of each Nifty 50 stock vs the Nifty 50 
index itself over 1M, 3M, and 1Y periods.

Nifty 50 index returns:
- Source: NSE publishes Nifty 50 index close values in a separate file:
  https://archives.nseindia.com/content/indices/ind_close_all_<DDMMYYYY>.csv
- Build a nifty50_index_prices table (date, close) from this file (ingest 
  as part of Phase 1 Milestone 1.1 as a parallel stream)
- Compute nifty50_return_1m, nifty50_return_3m, nifty50_return_1y 
  using the same trading-day-aligned lookback logic as Milestone 2.1

Alpha computation:
  rs_vs_nifty_1m = stock_return_1m - nifty50_return_1m
  rs_vs_nifty_3m = stock_return_3m - nifty50_return_3m
  rs_vs_nifty_1y = stock_return_1y - nifty50_return_1y

Note: This is simple excess return (arithmetic alpha), NOT beta-adjusted alpha. 
Beta adjustment is a Phase 6 enhancement.

Output: compute_rs_alpha.py; populate rs_vs_nifty_1m, rs_vs_nifty_3m, 
rs_vs_nifty_1y in mart_stock_signals.

Edge cases:
- Index file not yet published (NSE sometimes publishes with 15-min lag after 
  market close): wait and retry up to 3 times before marking as data_pending
- NULL stock return (insufficient history): also set corresponding RS to NULL
```

---

#### Milestone 2.4 — Drawdown and 52-Week Distance Computation

**LLM Prompt Stub:**

```
Task: Populate drawdown_from_52w_high_pct and distance_from_52w_low_pct columns 
in mart_stock_signals by joining to fact_52wk for the same (symbol, calc_date).

These are direct reads from fact_52wk (already computed in Milestone 1.2), 
so this milestone is primarily a join and validation task.

Additional derived column to compute: 
  direction_consistency_20d:
  - Fetch the last 20 rows of fact_eod_price.return_1d for the symbol
  - Determine the overall 20-day direction: positive if return_1m > 0, else negative
  - Count rows where sign(return_1d) == sign(overall direction)
  - direction_consistency_20d = count / 20 (fraction from 0.0 to 1.0)

Also compute: intraday_reversal_count_20d:
  - Count sessions in the last 20 days where: 
    (high - open) / open > 0.02 AND (close - open) / open < -0.01 (bearish reversal)
    OR (open - low) / low > 0.02 AND (close - open) / open > 0.01 (bullish reversal)
  - Store as integer count

Output: compute_drawdown_metrics.py; validation job that checks 
no NULL values in drawdown columns for any current Nifty 50 member 
on any trading day with full data coverage.
```

---

#### Milestone 2.5 — `mart_stock_signals` Daily Population Job

**LLM Prompt Stub:**

```
Task: Build the master daily orchestration job that populates mart_stock_signals 
for all current Nifty 50 members for today's calc_date. 
This job must run after NSE data is fully ingested (typically 16:15–16:30 IST).

Job sequence:
  1. Verify fact_eod_price has data for today's trade_date for all 50 symbols
  2. Run compute_returns() → populate return_* columns
  3. Run compute_rs_alpha() → populate rs_vs_nifty_* columns
  4. Run compute_volume_metrics() → populate vol_* and avg_volume_20d
  5. Join fact_52wk → populate drawdown_from_52w_high_pct, distance_from_52w_low_pct
  6. Run compute_drawdown_metrics() → populate direction_consistency_20d, 
     intraday_reversal_count_20d
  7. Join fact_corporate_event → populate last_event_type, last_event_date, 
     days_since_last_event
  8. Compute event presence flags (follow_up_required, volume_spike_flag)
  9. Write all columns EXCEPT iss_score, signal_category, *_flag fields
     (these are populated by Phase 3 signal engine)
  10. Run data quality checks (see Phase 6 Milestone 6.1)

Use a transaction: either all 50 symbols commit or none do 
(prevents partial mart state serving stale data to the dashboard).

Scheduler: Apache Airflow DAG (or simple cron + Python if Airflow is out of scope). 
Trigger time: 16:30 IST, Monday–Friday, skipping NSE holidays.

Output: daily_mart_job.py (or Airflow DAG), job_log table schema, 
and a Slack/email notification on job completion or failure.
```

---

### Phase 3: Signal Engine

#### Milestone 3.1 — ISS Scoring Function Implementation

**LLM Prompt Stub:**

```
Task: Implement the compute_iss(stock: dict) -> float function as defined 
in the dashboard spec Section 7, and wire it into the daily mart population job.

The function takes a single row dict from mart_stock_signals (with all columns 
populated from Phase 2) and returns a float score in [0, 100].

Implementation requirements:
1. Implement all 7 factors exactly as specified in Section 6.1 of the dashboard spec
2. Apply the negative event penalty (-5 points) for significance ≥ 4 events 
   within 10 days that are negative
3. Clamp final output to [0.0, 100.0]
4. Include a score_breakdown dict in the return value for auditability:
   {"f1": 18, "f2": 13, "f3": 12, "f4": 14, "f5": 8, "f6": 8, "f7": 1, 
    "penalty": 0, "total": 74.0}
5. Store both iss_score (float) and a JSON blob iss_score_breakdown (JSONB column 
   in mart_stock_signals) for transparency and debugging

Unit tests required:
- Test a known MOM stock (e.g. return_3m=20%, rs=+8%, vr=1.7x): 
  expected ISS in range [65, 80]
- Test a known ACC stock (return_3m=-15%, return_1y=-30%, drawdown=-35%): 
  expected ISS in range [35, 55]
- Test edge case: new listing with NULL return_1y and NULL rs_vs_nifty_1y
- Test negative event penalty trigger

Output: signal_engine/iss_scorer.py, tests/test_iss_scorer.py
```

---

#### Milestone 3.2 — Signal Category Classification (ACC / MOM / EVT)

**LLM Prompt Stub:**

```
Task: Implement classify_signal(stock: dict) -> dict that evaluates 
ACC, MOM, and EVT rules (as defined in Section 6.2) and returns:
{
  "accumulation_flag": bool,
  "momentum_flag": bool,
  "event_flag": bool,
  "falling_knife_risk": bool,
  "signal_category": str,  # 'Accumulation' | 'Momentum' | 'EventDriven' | 'Neutral'
  "mom_tier": str | None,  # 'MOM-Strong' | 'MOM-Confirmed' | 'MOM-Watch' | None
  "follow_up_required": bool
}

Priority for signal_category when multiple flags are TRUE:
  - MOM takes priority over ACC (momentum is the stronger, more actionable signal)
  - EVT co-exists with MOM or ACC (signal_category can be 'Momentum' with event_flag=True)
  - If only EVT: signal_category = 'EventDriven'
  - If none: signal_category = 'Neutral'

Falling knife exclusion:
- After ACC is flagged, evaluate FALLING_KNIFE_EXCLUSION sub-rule
- If triggered: set accumulation_flag = False, falling_knife_risk = True
- Requires pe_ratio and pe_5yr_avg fields to be available in the stock dict 
  (add these to mart_stock_signals, sourced from external fundamental data or a stub)

Configuration: all threshold values (return thresholds, volume ratio thresholds, 
RS thresholds, lookback windows) must be defined in a config.yaml file, 
not hard-coded. This allows tuning without code changes.

Output: signal_engine/classifier.py, config.yaml, tests/test_classifier.py
```

---

#### Milestone 3.3 — Volume Anomaly Detector

**LLM Prompt Stub:**

```
Task: Build a daily job that evaluates the 7 volume anomaly rules (Section 6.3) 
and populates mart_volume_anomaly for all Nifty 50 symbols.

Input: mart_stock_signals (vol_ratio_1d, return_1d, delivery_pct, 
volume_trend_3m) + fact_corporate_event (nearest event within ±5 days)

Rule evaluation order (first match wins — use priority ordering VA-5 first 
to prevent event-driven volume from being misclassified):
  VA-5 → VA-1 → VA-2 → VA-3 → VA-6 → VA-7 → VA-4 → Normal

For VA-4 (sustained dryup): requires checking the past 5 consecutive sessions. 
Read the last 5 rows from mart_stock_signals.vol_ratio_1d for the symbol.

spike_level classification:
  < 1.2x → 'Normal'
  1.2–1.5x → 'Mild'
  1.5–2.0x → 'Moderate'
  2.0–3.0x → 'High'
  > 3.0x → 'Extreme'

Nearest event join logic:
  - Query fact_corporate_event WHERE symbol = X 
    AND ABS(event_date - calc_date) <= 5 trading days
  - Order by ABS(event_date - calc_date) ASC, pick the first result
  - Populate nearest_event_within_5d (summary) and nearest_event_type

Output: signal_engine/volume_anomaly.py; mart_volume_anomaly insert job; 
unit tests for each VA rule.
```

---

#### Milestone 3.4 — Corporate Event Significance Scorer and Categorizer

**LLM Prompt Stub:**

```
Task: Build the event significance scorer that assigns significance_score (1–5) 
and event_type to new rows in fact_corporate_event.

Scoring rules (significance_score):

5 = Critical:
  - Earnings: Net profit beat/miss > 20% vs consensus; extraordinary items
  - M&A: Major acquisition > 10% of market cap announced
  - Regulatory: SEBI enforcement action, court ruling against company
  - Leadership: CEO/MD resignation or abrupt change

4 = High:
  - Earnings: Beat/miss 10–20%; revenue guidance revision
  - Rating change: Credit rating downgrade (e.g. ICRA, CRISIL)
  - Pledging: Promoter pledge > 5% of total shares in single disclosure
  - Large order: Order win > 5% of annual revenue

3 = Significant:
  - Earnings: Beat/miss 5–10%
  - Leadership: CFO or other key executive change
  - Dividends: Special dividend or dividend cut
  - Rating: Outlook change (Negative/Positive Watch)

2 = Moderate:
  - Routine quarterly earnings (no surprise)
  - Board meeting date announcements
  - Small buyback (<1% of market cap)

1 = Low:
  - Routine AGM/EGM notice
  - Minor regulatory filings
  - Dividend confirmation (no change vs prior year)

Categorization method:
  - Rule: Apply keyword matching from a YAML config file 
    (no ML dependency for Phase 3)
  - NLP: Reserved for Phase 6 enhancement using a lightweight LLM API call

Negative event flag (is_negative_event):
  - TRUE for: Rating_Change with "downgrade"/"negative" keywords, 
    Regulatory with enforcement keywords, 
    Leadership_Change with "resign"/"quit" keywords,
    Pledging_Change with ratio > threshold,
    Earnings miss > 10%

Output: signal_engine/event_scorer.py, event_keywords.yaml, 
tests/test_event_scorer.py
```

---

#### Milestone 3.5 — Watchlist Auto-Population Logic

**LLM Prompt Stub:**

```
Task: Build the watchlist auto-population logic that suggests stocks 
to a user's watchlist based on their signal preferences.

Tables needed:
  - user_watchlist: (user_id, symbol, added_date, added_reason, 
    signal_category_at_add, is_auto_added, is_active)
  - user_preferences: (user_id, preferred_signal_types JSON, 
    min_iss_score, exclude_sectors JSON)

Auto-population logic:
  1. Every EOD, query mart_stock_signals for today's calc_date
  2. Filter to records where:
     - nifty50_member = TRUE
     - signal_category matches any of the user's preferred_signal_types
     - iss_score >= user's min_iss_score
     - sector NOT IN user's exclude_sectors
     - falling_knife_risk = FALSE (always excluded from auto-add)
  3. For each matching stock not already in the user's watchlist (or last 
     removed > 30 days ago): auto-insert with is_auto_added = TRUE 
     and added_reason = signal_category + ISS score snapshot

Manual override: 
  - User can manually add any Nifty 50 stock regardless of ISS score
  - User can dismiss an auto-added stock (dismissed_by_user = TRUE) 
    — it will not be re-added within 10 trading days

API endpoint (FastAPI):
  GET /api/watchlist/{user_id} → list of active watchlist items with 
    current mart_stock_signals data joined
  POST /api/watchlist/{user_id}/add → manual add
  DELETE /api/watchlist/{user_id}/{symbol} → remove / dismiss

Output: watchlist_manager.py, user_watchlist table migration, 
FastAPI route handlers, and unit tests.
```

---

### Phase 4: Dashboard UI

#### Milestone 4.1 — Market Overview Page

**LLM Prompt Stub:**

```
Task: Build the Market Overview page of the Nifty 50 dashboard using Streamlit 
(or React + FastAPI if React is preferred).

Page layout:
  - Header: "Nifty 50 | Market Overview — [today's date]"
  - Row 1 (KPI cards, 5 columns):
    Nifty 50 index level | 1D change % | 1M change % | 3M change % | 
    Advance/Decline ratio (e.g. "32 Adv / 18 Dec")
  - Row 2: Sector heatmap — 11 sectors as coloured tiles, 
    colour = 1D return (green/red spectrum), size = market cap weight
  - Row 3: ISS Distribution histogram — bar chart showing number of Nifty 50 
    stocks in each ISS band (0-20, 20-40, 40-60, 60-80, 80-100)
  - Row 4: Signal Summary table — one row per signal_category 
    (Accumulation / Momentum / EventDriven / Neutral) with count, avg ISS, 
    best performer (1D return), worst performer (1D return)
  - Row 5: Market Breadth — sparkline of last 20 days advance/decline ratio

Data source: mart_stock_signals (today's calc_date) joined to dim_stock (sector).

Tech stack: Streamlit 1.30+, Plotly for charts, pandas for data transforms, 
FastAPI backend (or Streamlit's built-in data cache via @st.cache_data).

Interactivity: clicking any sector tile navigates to the Movers page 
pre-filtered to that sector.

Output: pages/market_overview.py, api/routes/overview.py (FastAPI endpoint), 
and component tests.
```

---

#### Milestone 4.2 — Movers and Extremes Page

**LLM Prompt Stub:**

```
Task: Build the Movers and Extremes page showing the top and bottom performers 
across multiple time horizons.

Page sections:
  1. Top 5 / Bottom 5 by 1D return (today's movers)
  2. Top 5 / Bottom 5 by 1M return
  3. Top 5 / Bottom 5 by 3M return
  4. Top 5 / Bottom 5 by ISS score
  5. Filter bar: allow filtering by sector (dropdown from dim_stock.sector)

Table columns for each section:
  Symbol | Company Name | Sector | Return (%) | ISS Score | Signal Category | 
  Volume Ratio (1D) | 52w High/Low %

Colour coding:
  - Return column: green gradient (positive) / red gradient (negative)
  - ISS score: traffic light (≥70 = green, 40–70 = amber, <40 = red)
  - Signal category: badge (ACC = blue, MOM = green, EVT = purple, Neutral = grey)

Data source: mart_stock_signals (today's calc_date) with dim_stock join.

Output: pages/movers_extremes.py, FastAPI endpoint /api/movers/{period} 
where period ∈ {1d, 1m, 3m}.
```

---

#### Milestone 4.3 — Drawdown Scanner Page

**LLM Prompt Stub:**

```
Task: Build the Drawdown Scanner page to identify Nifty 50 stocks in various 
stages of peak-to-trough decline.

Page sections:
  1. Drawdown Severity Table:
     - All 50 stocks sorted by drawdown_from_52w_high_pct (most negative first)
     - Columns: Symbol | Close Price | 52w High | 52w High Date | 
       Drawdown % | Distance from 52w Low % | Signal Category | 
       Accumulation Flag | Falling Knife Risk Flag
  2. Drawdown Zone Chart (scatter plot):
     - X-axis: distance_from_52w_low_pct (0–100%)
     - Y-axis: drawdown_from_52w_high_pct (0 to -60%)
     - Each bubble = one stock, size = market_cap_cr, 
       colour = signal_category
     - Quadrants: top-right = near highs (momentum), 
       bottom-left = near lows (accumulation candidates)
  3. Historical Drawdown Trend:
     - User selects a symbol from the table
     - Line chart showing drawdown_from_52w_high_pct over the past 
       252 trading days for that symbol

Data source: mart_stock_signals + fact_52wk + dim_stock.

Output: pages/drawdown_scanner.py, /api/drawdown endpoint, 
/api/drawdown/history/{symbol} endpoint.
```

---

#### Milestone 4.4 — Breakout / Momentum Monitor Page

**LLM Prompt Stub:**

```
Task: Build the Momentum Monitor page showing stocks with active MOM signals 
and approaching breakout zones.

Page sections:
  1. Active Momentum Stocks (momentum_flag = TRUE):
     - Table: Symbol | MOM Tier | ISS Score | 3M Return % | RS vs Nifty 3M | 
       Volume Ratio (5D) | Days Since Positive Event | 52w High Distance %
  2. Near-Breakout Radar (not yet MOM but approaching):
     - Filter: drawdown_from_52w_high_pct > -5% AND iss_score >= 50 
       AND NOT momentum_flag
     - Table with same columns
  3. RS Ranking Chart:
     - Horizontal bar chart of all 50 stocks sorted by rs_vs_nifty_3m
     - Colour: positive alpha = green, negative = red
     - Reference line at 0 (index parity)

Interactivity:
  - Click any symbol → opens a mini stock detail panel (right sidebar):
    - Price chart (last 63 days from fact_eod_price)
    - ISS score gauge (0–100 arc)
    - Signal history timeline (last 3 signal_category changes)
    - Last 3 corporate events

Output: pages/momentum_monitor.py, /api/momentum endpoint.
```

---

#### Milestone 4.5 — Volume Anomaly Monitor Page

**LLM Prompt Stub:**

```
Task: Build the Volume Anomaly Monitor page displaying today's 
mart_volume_anomaly results and historical anomaly patterns.

Page sections:
  1. Today's Anomalies Table (all non-Normal spike_level stocks):
     Columns: Symbol | Spike Level (badge) | Volume Ratio | Price Change % | 
     Delivery % | Anomaly Direction (Up/Down arrow) | 
     Nearest Event (if any) | ISS Score
  2. Spike Level Summary: 5 count cards (Normal / Mild / Moderate / High / Extreme)
  3. Historical Volume Heatmap:
     - Grid: symbols (rows) × last 20 trading days (columns)
     - Cell colour: spike_level category
     - Hover: shows volume_ratio and price_chg values
  4. Volume + Price Chart (symbol-level):
     - User selects symbol
     - Dual-axis chart: price (line) + volume (bar) for last 63 trading days
     - Volume bars coloured by anomaly_direction (green/red)
     - Corporate event markers overlaid on price line

Output: pages/volume_anomaly.py, /api/volume-anomaly endpoint.
```

---

#### Milestone 4.6 — Corporate Events Tracker Page

**LLM Prompt Stub:**

```
Task: Build the Corporate Events Tracker page presenting fact_corporate_event 
and fact_corporate_action data in a calendar and timeline format.

Page sections:
  1. Event Calendar (30-day rolling):
     - Calendar grid showing event dots by significance colour
     - Click a date → shows all events for that day in a side panel
  2. High-Significance Events Feed (significance ≥ 3, last 30 days):
     - Card layout: Symbol badge | Event Type | Summary | Date | 
       Significance stars (1–5) | Price change on day | Follow-up badge
  3. Upcoming Events (next 10 days, from any pre-announced board meetings):
     - Table: Symbol | Expected Event Type | Estimated Significance | Days Until
  4. Corporate Actions Timeline:
     - Upcoming ex-dates for dividends/bonus/splits in next 30 days
     - Columns: Symbol | Action Type | Ex-Date | Details | Face Value

Filter controls: event_type multi-select, significance_score minimum slider, 
symbol search.

Output: pages/corporate_events.py, /api/corporate-events endpoint, 
/api/corporate-actions/upcoming endpoint.
```

---

#### Milestone 4.7 — Watchlist Builder Page

**LLM Prompt Stub:**

```
Task: Build the Watchlist Builder page where users can view, manage, 
and customise their stock watchlists.

Page sections:
  1. My Watchlist (active stocks):
     - Table: Symbol | Company | Signal Category | ISS Score | 1D Return % | 
       1M Return % | Volume Ratio | Added Date | Added Reason | Remove button
     - Row click: expands to show full mart_stock_signals detail for that stock
  2. Auto-Suggestions Panel (right sidebar):
     - Stocks suggested by the auto-population engine (Milestone 3.5) 
       not yet in the watchlist
     - Each suggestion shows: Symbol | Why Suggested | ISS Score | Add button
  3. Watchlist Settings:
     - User preference controls: 
       min_iss_score slider, preferred_signal_types checkboxes, 
       exclude_sectors multi-select
     - Save to user_preferences table via API
  4. Watchlist Performance Summary:
     - Aggregate return of watchlist stocks since added (equal weight)
     - vs Nifty 50 return over the same period

If no authentication system is in scope, use a simple session-based 
user_id (UUID stored in browser session / Streamlit session_state).

Output: pages/watchlist_builder.py, /api/watchlist/{user_id} routes, 
user_preferences table migration.
```

---

### Phase 5: Alerting + Automation

#### Milestone 5.1 — EOD Batch Pipeline (Scheduled)

**LLM Prompt Stub:**

```
Task: Build the end-to-end EOD batch pipeline that runs after NSE market close 
(15:30 IST) and completes all data ingestion, analytics, and signal computation 
before 17:30 IST.

Pipeline DAG (Apache Airflow or cron-based):

  Task 1 [16:00 IST]: Download today's Bhavcopy ZIP
  Task 2 [16:05 IST]: Ingest fact_eod_price (depends on Task 1)
  Task 3 [16:05 IST]: Download Nifty 50 index close file (parallel to Task 2)
  Task 4 [16:15 IST]: Compute fact_52wk (depends on Task 2)
  Task 5 [16:15 IST]: Ingest corporate actions and events (parallel to Task 4)
  Task 6 [16:20 IST]: Score corporate events — event_scorer (depends on Task 5)
  Task 7 [16:25 IST]: Populate mart_stock_signals Phase 2 metrics 
                      (depends on Tasks 2, 3, 4)
  Task 8 [16:35 IST]: Run ISS scorer and signal classifier (depends on Task 7)
  Task 9 [16:40 IST]: Populate mart_volume_anomaly (depends on Task 8)
  Task 10 [16:45 IST]: Run alert engine (depends on Task 8, 9)
  Task 11 [17:00 IST]: Run data quality checks (depends on Tasks 7, 8, 9)
  Task 12 [17:10 IST]: Send completion notification (depends on Task 11)

SLA: All tasks must complete by 17:30 IST. 
Alert on-call if Task 11 fails or pipeline duration > 90 minutes.

Tech stack: Apache Airflow 2.7+ (or alternatively: simple Python orchestrator 
using subprocess chaining + SQLite for run state).

Output: dags/eod_pipeline_dag.py (Airflow) or orchestrator/eod_runner.py 
(simple cron), pipeline_run_log table schema, monitoring dashboard stub.
```

---

#### Milestone 5.2 — Alert Engine with Condition Evaluation

**LLM Prompt Stub:**

```
Task: Build the alert evaluation engine that checks all 14 alert conditions 
(Section 8) after mart tables are populated and generates alert records 
for delivery.

Alert record schema (alerts table):
  alert_id (UUID), alert_name (A-01 through A-14), symbol (nullable), 
  triggered_at (timestamp), trigger_value (JSONB — the metric values 
  that caused the trigger), user_ids_to_notify (array of user IDs), 
  delivery_status (Pending / Sent / Failed), dedup_key (VARCHAR — 
  symbol + alert_name + date, for deduplication)

Deduplication logic:
  - Before inserting a new alert, check if dedup_key already exists 
    with triggered_at within the deduplication window (5 trading days 
    for most alerts, 0 for real-time alerts like A-05, A-06)
  - If duplicate exists: skip insert, increment suppressed_count on existing record

Alert routing:
  - Per-user routing: A-07 (watchlist move) and A-10 (accumulation surge) 
    are user-specific (join to user_watchlist)
  - Global routing: all other alerts go to all registered users 
    (or all users with notification_enabled = TRUE)

Output: alerting/alert_engine.py, alerts table migration, 
alerting/routing.py, tests/test_alert_dedup.py
```

---

#### Milestone 5.3 — Notification Delivery (Email / Dashboard Push)

**LLM Prompt Stub:**

```
Task: Build the notification delivery layer for the alert engine.

Delivery channels:

1. Dashboard notification (in-app):
   - notifications table: (notification_id, user_id, alert_id, message_text, 
     is_read, created_at)
   - FastAPI SSE endpoint: GET /api/notifications/stream/{user_id} 
     (Server-Sent Events for real-time push to Streamlit / React frontend)
   - Notification bell icon in dashboard header showing unread count

2. Email (via SMTP or SendGrid):
   - Template: HTML email with alert name, trigger details, 
     affected stock(s), current ISS score, and a link to the relevant 
     dashboard page
   - Daily digest option: batch all EOD alerts into one email per user 
     instead of individual emails per alert

3. SMS (via Twilio or MSG91 — optional, for Critical severity only):
   - 160-character limit; format: "[NIFTY ALERT] {alert_name}: 
     {symbol} — {trigger_value}. Check dashboard."

Configuration (environment variables):
  - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
  - SENDGRID_API_KEY (alternative)
  - TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM (for SMS)

Output: alerting/email_sender.py, alerting/sms_sender.py, 
alerting/dashboard_push.py, email templates (Jinja2 HTML), 
/api/notifications/* FastAPI routes.
```

---

#### Milestone 5.4 — Intraday Refresh Integration (Optional)

**LLM Prompt Stub:**

```
Task: Design and build an optional intraday data refresh module 
that polls a real-time or near-real-time NSE data vendor 
and updates a subset of dashboard metrics during market hours 
(09:15–15:30 IST).

Scope (intraday only — does NOT replace EOD pipeline):
  - Update fact_eod_price with the latest OHLCV snapshot every 15 minutes
  - Recompute vol_ratio_1d, return_1d, and drawdown_from_52w_high_pct
  - Refresh mart_stock_signals for these columns only (partial update)
  - Re-evaluate alert conditions A-04 (Extreme Volume) and A-07 (Watchlist Move)

Data vendor options (in priority order):
  1. NSE live data API (if subscribed): use official websocket feed
  2. Unofficial NSE quote API: https://www.nseindia.com/api/quote-equity?symbol=RELIANCE
     (rate limit: 1 request / 2 seconds per symbol; session cookie required)
  3. Yahoo Finance API (yfinance Python library): free, 15-min delayed

Architecture:
  - Intraday scheduler: runs every 15 minutes, 09:15–15:30 IST
  - Only processes current Nifty 50 symbols (50 requests per cycle)
  - Writes to fact_intraday_snapshot table (separate from fact_eod_price) 
    to avoid contaminating EOD data
  - Dashboard shows "Live" badge when intraday data is fresher than 20 minutes

Output: intraday/intraday_poller.py, fact_intraday_snapshot table schema, 
intraday/partial_mart_updater.py, configuration flag: 
ENABLE_INTRADAY_REFRESH=true/false in .env
```

---

### Phase 6: Validation + Hardening

#### Milestone 6.1 — Data Quality Checks

**LLM Prompt Stub:**

```
Task: Build a comprehensive data quality check module that runs as the 
final step of the EOD pipeline and generates a daily DQ report.

Checks to implement:

1. Missing trading days: 
   Compare fact_eod_price dates against the NSE trading calendar. 
   Alert if any expected trading date is absent.

2. Symbol coverage check: 
   Verify all current Nifty 50 members have a row in fact_eod_price 
   for today's trade_date. Flag any missing symbol.

3. OHLC integrity: 
   Assert HIGH >= OPEN, HIGH >= CLOSE, LOW <= OPEN, LOW <= CLOSE, 
   HIGH >= LOW for every row today. Log violations.

4. Volume sanity: 
   Flag any stock where total_traded_qty = 0 (suspended trading?). 
   Flag any stock where vol_ratio_1d > 20x (extreme outlier).

5. Return range check: 
   NSE circuit limits are ±20%. Flag any return_1d outside [-22%, +22%].

6. mart_stock_signals completeness: 
   Assert no NULL values in non-nullable columns for current Nifty 50 members.

7. Bhavcopy gap detection: 
   Check source_file dates are consecutive. Alert if a gap > 1 trading day 
   (excluding known holidays) is detected in the archive.

8. Duplicate row check: 
   Assert no duplicate (trade_date, symbol) combinations in fact_eod_price.

DQ report output:
  - Table: dq_run_log (run_date, check_name, status [Pass/Fail/Warn], 
    affected_rows, detail_json)
  - Email summary if any check = Fail
  - Dashboard DQ status badge (green/amber/red) visible in page footer

Output: validation/dq_checks.py, dq_run_log table migration, 
validation/dq_report.py (email/dashboard reporter).
```

---

#### Milestone 6.2 — Back-Test Signal Rules Against 3-Year History

**LLM Prompt Stub:**

```
Task: Build a back-testing module that applies the ISS scoring and 
ACC/MOM/EVT classification rules to all historical data 
(3 years = ~756 trading days) and evaluates how predictive the signals were.

Back-test methodology:
  1. For each historical calc_date (oldest to newest), recompute ISS score 
     and signal_category for all Nifty 50 stocks using historical data 
     available AS OF that date (no lookahead bias — use only data with 
     trade_date ≤ calc_date)
  2. Record the signal assigned on each date
  3. Measure forward returns: 1M, 3M, and 6M after the signal date
  4. Compare forward returns of ACC-tagged stocks vs MOM-tagged stocks 
     vs Neutral stocks vs Nifty 50 index over the same periods

Output metrics:
  - Hit rate: % of MOM signals followed by positive 3M forward return
  - Avg 3M forward return by signal_category
  - Max drawdown during 3M holding period by signal_category
  - ISS score correlation with forward 3M return (Pearson r)
  - Distribution of ISS scores over time (did the thresholds need adjustment?)

Visualisation: 
  - Backtest results saved as backtest_report.html with 4 charts:
    cumulative return of signal baskets vs Nifty 50, 
    hit rate by ISS bucket, signal frequency over time, 
    forward return distribution histogram

Important: Use is_nifty50_member(symbol, as_of_date) for point-in-time 
Nifty 50 filter (prevents survivorship bias from looking at today's members 
for historical dates).

Output: backtest/backtest_runner.py, backtest/metrics.py, 
backtest/report_generator.py (Plotly HTML report).
```

---

#### Milestone 6.3 — Performance Profiling and Query Optimisation

**LLM Prompt Stub:**

```
Task: Profile dashboard query performance and optimise the slowest queries 
to meet page load time targets.

Performance targets:
  - Market Overview page: < 2 seconds (cold), < 0.5 seconds (cached)
  - Any single-stock detail view: < 1 second
  - Historical price chart (252 days): < 1.5 seconds
  - Drawdown scanner full table (50 rows): < 1 second

Profiling steps:
  1. Use PostgreSQL EXPLAIN ANALYZE on the top 10 most frequent queries 
     (identified from query logs)
  2. Identify sequential scans on large tables (fact_eod_price may contain 
     2M+ rows after 5-year backfill)
  3. Add or adjust indexes as needed:
     - BRIN index on fact_eod_price.trade_date (time-series data)
     - Composite index on (symbol, trade_date DESC) for per-symbol queries
     - Partial index on mart_stock_signals WHERE calc_date = CURRENT_DATE 
       (if DB supports function-based or expression indexes)
  4. Implement Redis caching for mart_stock_signals today's data 
     (TTL = 15 minutes during market hours, 6 hours after close)
  5. For Streamlit: use @st.cache_data with ttl=900 on all data-fetching functions

Output: performance/query_profiler.py (runs EXPLAIN ANALYZE and captures 
results), performance/add_indexes.sql (migration file for new indexes), 
performance/cache_layer.py (Redis integration), 
PERFORMANCE_REPORT.md summarising before/after query times.
```

---

#### Milestone 6.4 — Documentation and Runbook

**LLM Prompt Stub:**

```
Task: Write the complete technical documentation and operational runbook 
for the Nifty 50 dashboard system.

Documentation required:

1. README.md (root):
   - Project overview and architecture diagram (ASCII or Mermaid)
   - Prerequisites (Python 3.11, PostgreSQL 15, Redis optional)
   - Installation steps (pip install, .env setup, DB init, backfill)
   - Running the dashboard (streamlit run app.py)
   - Running the EOD pipeline manually (python orchestrator/eod_runner.py)

2. SCHEMA.md:
   - All 8 table schemas with column descriptions (derived from Section 5 of spec)
   - ER diagram (Mermaid markdown format)
   - Indexing strategy and rationale

3. SIGNAL_RULES.md:
   - ISS scoring formula (with example calculation)
   - ACC / MOM / EVT rule logic in plain English + code reference
   - Config.yaml parameters and recommended tuning guidance

4. RUNBOOK.md (operational):
   - Daily pipeline: expected run times, success criteria, failure indicators
   - Alert severity and on-call response procedures
   - Common failure scenarios:
     a. NSE website returns 403 (rate limited) — steps to recover
     b. Bhavcopy file not published by 18:00 IST — manual fallback steps
     c. PostgreSQL disk full — archiving strategy
     d. mart_stock_signals not populated — dashboard graceful degradation mode
   - Monthly maintenance tasks (index vacuum, partition management, 
     Nifty 50 rebalancing update procedure)

5. CONTRIBUTING.md:
   - Code style guide (black + isort), test requirements (pytest, 80% coverage), 
     PR review checklist

Output: README.md, SCHEMA.md, SIGNAL_RULES.md, RUNBOOK.md, CONTRIBUTING.md — 
all in the repository root. Commit all files together as the 
"documentation complete" milestone.
```

---

*End of Specification Part 2 — Sections 5 through 9.*

*Document saved: /home/user/workspace/spec_part2.md*
*Version: 1.0 | Prepared for Nifty 50 Investment Monitoring Dashboard*
# Nifty 50 Investment Monitoring Dashboard — Specification Part 3
## Sections 10–13: Output Schema, Daily Workflow, Enhancements, Technology Stack

---

## Section 10: Sample Output Schema

### 10.1 Sample `mart_stock_signals` Records

Five representative records as of **2 April 2026** (post-FY26 close), each illustrating a different signal category.

```json
[
  {
    "calc_date": "2026-04-02",
    "symbol": "BAJFINANCE",
    "return_1d": 0.0187,
    "return_1m": 0.0621,
    "return_3m": 0.1143,
    "return_1y": 0.2834,
    "rs_vs_nifty_1m": 0.0312,
    "rs_vs_nifty_3m": 0.0558,
    "rs_vs_nifty_1y": 0.1021,
    "vol_ratio_1d": 2.14,
    "drawdown_from_52w_high_pct": -0.0381,
    "distance_from_52w_low_pct": 0.3217,
    "volume_trend_3m": "EXPANDING",
    "iss_score": 82,
    "signal_category": "MOMENTUM",
    "accumulation_flag": true,
    "momentum_flag": true,
    "event_flag": false,
    "last_event_type": "RESULTS",
    "days_since_last_event": 14
  },
  {
    "calc_date": "2026-04-02",
    "symbol": "HDFCBANK",
    "return_1d": -0.0043,
    "return_1m": -0.0218,
    "return_3m": 0.0087,
    "return_1y": 0.0934,
    "rs_vs_nifty_1m": -0.0527,
    "rs_vs_nifty_3m": -0.0498,
    "rs_vs_nifty_1y": -0.0889,
    "vol_ratio_1d": 0.74,
    "drawdown_from_52w_high_pct": -0.1842,
    "distance_from_52w_low_pct": 0.0612,
    "volume_trend_3m": "DRYING_UP",
    "iss_score": 38,
    "signal_category": "CONTRARIAN",
    "accumulation_flag": false,
    "momentum_flag": false,
    "event_flag": true,
    "last_event_type": "AGM",
    "days_since_last_event": 3
  },
  {
    "calc_date": "2026-04-02",
    "symbol": "ADANIPORTS",
    "return_1d": 0.0312,
    "return_1m": 0.0894,
    "return_3m": 0.1677,
    "return_1y": 0.3541,
    "rs_vs_nifty_1m": 0.0585,
    "rs_vs_nifty_3m": 0.1092,
    "rs_vs_nifty_1y": 0.1728,
    "vol_ratio_1d": 3.87,
    "drawdown_from_52w_high_pct": -0.0214,
    "distance_from_52w_low_pct": 0.4108,
    "volume_trend_3m": "SURGE",
    "iss_score": 91,
    "signal_category": "VOLUME_CONFIRMED",
    "accumulation_flag": true,
    "momentum_flag": true,
    "event_flag": true,
    "last_event_type": "BLOCK_DEAL",
    "days_since_last_event": 1
  },
  {
    "calc_date": "2026-04-02",
    "symbol": "TATAMOTORS",
    "return_1d": 0.0156,
    "return_1m": -0.0312,
    "return_3m": -0.0871,
    "return_1y": -0.1423,
    "rs_vs_nifty_1m": -0.0621,
    "rs_vs_nifty_3m": -0.1456,
    "rs_vs_nifty_1y": -0.3246,
    "vol_ratio_1d": 1.82,
    "drawdown_from_52w_high_pct": -0.3714,
    "distance_from_52w_low_pct": 0.0287,
    "volume_trend_3m": "STABILIZING",
    "iss_score": 44,
    "signal_category": "EVENT_DRIVEN",
    "accumulation_flag": false,
    "momentum_flag": false,
    "event_flag": true,
    "last_event_type": "ANALYST_UPGRADE",
    "days_since_last_event": 0
  },
  {
    "calc_date": "2026-04-02",
    "symbol": "SUNPHARMA",
    "return_1d": 0.0071,
    "return_1m": 0.0334,
    "return_3m": 0.0712,
    "return_1y": 0.1987,
    "rs_vs_nifty_1m": 0.0025,
    "rs_vs_nifty_3m": 0.0127,
    "rs_vs_nifty_1y": 0.0174,
    "vol_ratio_1d": 1.03,
    "drawdown_from_52w_high_pct": -0.0862,
    "distance_from_52w_low_pct": 0.1943,
    "volume_trend_3m": "NEUTRAL",
    "iss_score": 61,
    "signal_category": "WATCH",
    "accumulation_flag": true,
    "momentum_flag": false,
    "event_flag": false,
    "last_event_type": "DIVIDEND",
    "days_since_last_event": 22
  }
]
```

**Field notes:**
- `vol_ratio_1d`: Today's volume ÷ 20-day average volume. Values >1.5 are notable; >3.0 are high-conviction signals.
- `iss_score`: Integrated Signal Score, 0–100. Scores ≥75 = strong signal; 50–74 = watchlist; <50 = weak/contrarian candidates only.
- `signal_category`: One of `MOMENTUM`, `CONTRARIAN`, `EVENT_DRIVEN`, `VOLUME_CONFIRMED`, `WATCH`.
- `drawdown_from_52w_high_pct`: Negative value. -0.37 = 37% below 52-week high (deep value/distress territory).
- `distance_from_52w_low_pct`: Positive value. 0.03 = 3% above 52-week low (near-bottom contrarian setup).

---

### 10.2 Sample Corporate Events Records

| event_id | symbol | event_date | event_type | event_summary | significance_score | price_chg_1d | price_chg_5d | volume_spike_flag | follow_up_required |
|---|---|---|---|---|---|---|---|---|---|
| EVT-20260402-001 | ADANIPORTS | 2026-04-01 | BLOCK_DEAL | FII block deal: 1.2 Cr shares at ₹1,347, buyer undisclosed — likely domestic MF accumulation | 88 | +3.12% | +5.41% | true | true |
| EVT-20260402-002 | TATAMOTORS | 2026-04-02 | ANALYST_UPGRADE | Nomura upgrades to BUY, target ₹920 (+28% upside); cites EV margin recovery in JLR | 74 | +1.56% | null | true | true |
| EVT-20260402-003 | HDFCBANK | 2026-03-30 | AGM | AGM held; MD guided for NIM stabilisation at 3.4–3.5% in FY27; no interim dividend declared | 61 | -0.43% | -1.87% | false | false |
| EVT-20260402-004 | SUNPHARMA | 2026-03-11 | DIVIDEND | Final dividend ₹3.25/share declared for FY26; ex-date 2026-03-28; yield 0.38% | 42 | +0.71% | +1.23% | false | false |
| EVT-20260402-005 | BAJFINANCE | 2026-03-19 | RESULTS | Q4 FY26 PAT ₹4,218 Cr (+21% YoY); NPA stable at 1.1%; AUM growth 28% YoY. Beat on all metrics | 91 | +4.32% | +6.21% | true | false |

**Field notes:**
- `significance_score`: 0–100 proprietary weighting. Calculated from event type base weight × analyst coverage rank × volume spike multiplier.
- `follow_up_required`: Set `true` when the event warrants monitoring over the next 5 sessions (upgrades, block deals, management guidance changes). Auto-clears after 5 trading days unless manually kept.
- `price_chg_5d`: `null` for same-day events where the 5-day window is still open.

---

### 10.3 Sample Volume Anomaly Records

| anomaly_id | symbol | detected_date | anomaly_type | vol_ratio | price_change | avg_vol_20d | today_vol | price_at_detection | interpretation | alert_level |
|---|---|---|---|---|---|---|---|---|---|---|
| ANO-20260402-001 | ADANIPORTS | 2026-04-01 | BULLISH_SURGE | 3.87 | +3.12% | 8,240,000 | 31,889,000 | ₹1,347.50 | Price breakout on 3.9× average volume; high-conviction accumulation by institutional players. Confirmed by block deal. | HIGH |
| ANO-20260402-002 | HDFCBANK | 2026-04-02 | DISTRIBUTION | 2.31 | -1.84% | 12,650,000 | 29,221,000 | ₹1,612.30 | High volume on a down day; distribution pattern. Selling pressure despite AGM reassurance. Watch for follow-through selling. | HIGH |
| ANO-20260402-003 | SUNPHARMA | 2026-04-02 | DRYING_UP | 0.31 | +0.71% | 3,870,000 | 1,199,700 | ₹1,854.20 | Volume at 70% below 20-day average on slight uptick. Classic drying-up pattern after consolidation; potential base formation. No sellers left. | MEDIUM |

**Interpretation guide:**
- `BULLISH_SURGE`: vol_ratio > 2.5, price change positive. High-conviction buy signal.
- `DISTRIBUTION`: vol_ratio > 2.0, price change negative. Smart money exiting. Avoid fresh longs.
- `DRYING_UP`: vol_ratio < 0.4, price relatively flat or slightly positive. Selling exhaustion; watch for reversal catalyst.

---

### 10.4 Sample Watchlist Builder Output

| rank | symbol | category | iss_score | primary_signal | key_reason |
|---|---|---|---|---|---|
| 1 | BAJFINANCE | MOMENTUM | 82 | Strong RS + Volume Expansion | Q4 beat + 28% AUM growth driving institutional re-rating; trending above all key MAs |
| 2 | ADANIPORTS | VOLUME_CONFIRMED | 91 | Institutional Block Deal + Breakout | 3.9× volume surge on FII block deal; price at 52-week high with expanding RS |
| 3 | HDFCBANK | CONTRARIAN | 38 | Near 52-week Low + Drying Volume | 18% drawdown from high, volume drying up post-distribution; watch for reversal trigger |
| 4 | TATAMOTORS | EVENT_DRIVEN | 44 | Analyst Upgrade on Deep Value | Nomura upgrade on beaten-down JLR story; 37% off highs, potential mean-reversion trade |
| 5 | INFY | MOMENTUM | 78 | Consistent RS Outperformance | 3M RS vs Nifty +8.2%; steady volume expansion; FY27 deal wins pipeline positive |
| 6 | COALINDIA | CONTRARIAN | 41 | Oversold + High Dividend Yield | 24% off highs, dividend yield 6.8%, PSU divestment overhang fading; value accumulation zone |

---

## Section 11: Example Daily Workflow for an Investor

### A Day in the Life with the Nifty 50 Dashboard

---

**7:00 AM — Pre-Market Intelligence**

The investor's morning begins not with guesswork but with a structured intelligence briefing. She opens the dashboard's **Overnight Alerts** panel on her phone while brewing coffee. The system has already processed SGX Nifty futures data and any post-market NSE announcements filed after 4:00 PM the previous day.

This morning, three alerts are waiting. ADANIPORTS has triggered a "Block Deal Follow-Up" flag — yesterday's institutional activity warrants checking whether pre-market futures indicate continuation. TATAMOTORS shows a new "Analyst Upgrade" event filed at 6:45 PM. And a macro alert fires: crude oil spiked 4.2% overnight on OPEC+ supply cut news — the dashboard's macro overlay tags this as a potential headwind for aviation and paints sector-level annotations across INDIGO.

She also checks the **Today's Event Calendar** tab: BAJFINANCE has a concall at 10:30 AM. NTPC reports Q4 results after market hours. These are not surprises — the calendar was pre-populated when results dates were announced — but having them surface in a single view means she knows where to focus attention today.

---

**8:00 AM — Watchlist Δ Review**

By 8:00 AM, last evening's EOD pipeline has finished. She reviews the **Watchlist Changes** view — a diff-style panel showing which symbols entered, exited, or changed category since yesterday.

ADANIPORTS has upgraded from `WATCH` to `VOLUME_CONFIRMED` (ISS score: 91). The system has automatically promoted it and pushed a digest: "Price +3.1% on 3.9× volume; block deal confirmed by exchange data; RS vs Nifty 1M now +5.9%." She does not need to do any manual calculation.

HDFCBANK has moved from `MOMENTUM` to `CONTRARIAN` after three consecutive sessions of high-volume selling. Its ISS score dropped from 67 to 38. The dashboard flags this not as a short candidate — the system is long-only — but as a name to avoid for fresh capital. This is the quiet kind of risk management that prevents costly averaging-down mistakes.

She updates her trading journal with a single note against each changed name. The discipline of noting *why* she agrees or disagrees with the signal will form her backtesting baseline later.

---

**9:15 AM — Market Open: First Fifteen Minutes**

The opening bell is the noisiest part of any trading day, and the dashboard is designed to cut through it. She switches to the **Intraday View** — a live-refreshing panel (data delay: 15 minutes via NSE data feed) showing:

- Top 5 Nifty 50 gainers and losers by percentage, colour-coded against their overnight signal category.
- Volume bars for each stock against the intraday VWAP band.
- A red flag on any name where opening volume already exceeds 50% of its 20-day daily average in the first 15 minutes.

ADANIPORTS opens +1.8% and immediately hits the volume flag by 9:22 AM. She sizes into a position. TATAMOTORS opens flat despite the analyst upgrade — a note appears: "Upgrade published after market close; price discovery still in progress." She watches rather than reacts.

The market breadth indicator at the top of the dashboard reads "37 of 50 advancing" — broadly positive tape. This context matters; a signal on a stock moving against a red market is categorically different from one moving with it.

---

**11:00 AM — Mid-Morning: Volume Anomaly Monitor**

The first anomaly alert of the session fires at 10:54 AM. SUNPHARMA's volume is running at 28% of its 20-day average with a flat price — a textbook "drying up" pattern. She adds a note: *"Volume exhaustion developing. Watch for catalyst — FDA outcome or results."* No action today, but the stock moves to the top of her watchlist for the next 5–10 sessions.

She also checks the **Event-Driven Panel**, which has now been updated with BAJFINANCE's concall highlights (scraped from NSE announcement feed and summarised). Key points surfaced: management raised FY27 AUM growth guidance from 25% to 30%. The dashboard has already recalculated the significance score upward to 94 and flagged BAJFINANCE as "Strong Hold / Accumulate on dips."

---

**1:00 PM — Lunch-Hour: Drawdown Scanner**

Markets quiet down around 1:00 PM IST. She uses this window for structured research rather than reactive trading. The **Drawdown Scanner** is sorted by `drawdown_from_52w_high_pct` descending — deepest drawdowns at the top.

TATAMOTORS sits at -37.1% from its 52-week high, with distance from 52-week low at only 2.9%. This is the kind of asymmetric setup she looks for in the CONTRARIAN bucket. She cross-references the signal: analyst upgrade is fresh, volume is beginning to stabilise, and the stock is just 14 days post-Q4 results (which were weak but in-line). The dashboard shows a "Days Since Last Event: 0" — today's upgrade is the catalyst she needs. She decides to initiate a small starter position.

The scanner also shows COALINDIA at -24% from highs with a 6.8% dividend yield. She flags it as a "watch" for next week — no fresh catalyst yet, but the value case is building.

---

**3:30 PM — Market Close: EOD Pipeline Fires**

At 3:35 PM, the daily ingestion pipeline begins automatically (managed by the `daily_pipeline.py` scheduler). She does not need to trigger it manually. Within 20 minutes, the pipeline has:

1. Downloaded and parsed the NSE Bhavcopy for all Nifty 50 constituents.
2. Recalculated all return fields (1D, 1M, 3M, 1Y) using split/bonus-adjusted prices.
3. Updated all volume ratios, RS vs Nifty scores, and drawdown metrics.
4. Run the signal engine and recomputed all ISS scores.
5. Re-evaluated watchlist membership for all 50 symbols.
6. Queued tomorrow's alert digest.

She receives a push notification at 3:58 PM: "EOD pipeline complete. 3 signals changed category. 2 new events detected."

---

**6:00 PM — Evening Review: Full Signal Refresh**

This is the primary analytical session. She opens the dashboard on her laptop for the full desktop experience. The **Signal Dashboard** is the home screen — a 5×10 heatmap of all 50 Nifty stocks, coloured by ISS score tier (green: 75+, yellow: 50–74, red: <50), with today's category overlay.

She works through each changed signal methodically. For each MOMENTUM→CONTRARIAN downgrade, she checks: is the volume pattern distribution or simply thin? Is there a known negative catalyst? For each new VOLUME_CONFIRMED signal, she checks: is this a genuine breakout or a one-day anomaly?

The **RS vs Nifty Comparison** view gets her full attention for 15 minutes. She looks for names consistently in the top-right quadrant — strong 1M and 3M RS — as these are the high-conviction momentum candidates for fresh capital. Today: BAJFINANCE, ADANIPORTS, LT.

She documents three action items in her journal, linked directly to the signal IDs. If she looks back in six months, she will know exactly which signals drove which decisions.

---

**8:00 PM — Weekly Review (Sundays)**

On Sunday evenings, the workflow extends to a portfolio-level review. She pulls the **Weekly Heatmap** — a seven-session summary of RS vs Nifty for all 50 names. The goal is sector-level pattern recognition: is money rotating out of FMCG and into Industrials? Is the Financial sector broadening (both HDFCBANK and BAJFINANCE moving) or narrow (only NBFCs outperforming)?

She also reviews **Signal Persistence**: how many of last Sunday's MOMENTUM picks sustained their signal through the week? A MOMENTUM signal that degrades to WATCH within 3 sessions is a low-quality signal; one that persists or upgrades to VOLUME_CONFIRMED is high-conviction. This self-calibration against recent signal quality sharpens her position sizing discipline.

---

**9:00 PM — Alert Setup for Next Day**

The final act is configuring tomorrow's alert thresholds. She sets:

- Price alert: TATAMOTORS at ₹645 (stop loss for her starter position).
- Volume alert: SUNPHARMA if vol_ratio_1d exceeds 1.8 (confirmation of the drying-up reversal).
- Event alert: NTPC results — flag if Q4 PAT deviation from estimate exceeds ±10%.

The dashboard's alert engine writes these to the `user_alerts` table. They will evaluate at 9:16 AM tomorrow, the moment the first tick data arrives.

She closes the laptop. The entire workflow — from 7:00 AM coffee to 9:00 PM alert setup — has taken perhaps 90 minutes of actual focused attention. Everything else was handled by the pipeline.

---

## Section 12: Nice-to-Have Enhancements (Prioritized Roadmap)

| # | Priority | Enhancement Name | Description | Effort | Business Value | Data Requirement |
|---|---|---|---|---|---|---|
| 1 | P1 | Historical Signal Backtesting View | Show how past ACC/MOM/EVENT signals performed over 6M/1Y (hit rate, avg return, max drawdown). Essential for investor trust calibration and position sizing discipline. | L | High | mart_stock_signals (historical), adjusted price history |
| 2 | P1 | FII/DII Net Buying/Selling | Daily and rolling 30-day FII/DII flow for each Nifty 50 stock. Smart money flow is the highest-conviction overlay for any signal. | M | High | SEBI/NSE FII-DII daily reports (public) |
| 3 | P1 | Technical Indicator Overlay | RSI (14), MACD, Bollinger Bands on the price chart for any symbol. Allows confirmation of signal-engine output with classical TA before entry. | M | High | OHLCV daily data (already ingested) |
| 4 | P1 | Portfolio Overlay | User inputs their holdings (symbol + quantity + cost). Dashboard shows custom P&L, alert priority based on owned positions, and risk concentration flags. | L | High | User-provided via UI; no external feed required |
| 5 | P1 | Sector Rotation Heatmap | Weekly and monthly money-flow heatmap across Nifty 50 sectors (Financials, IT, Auto, Pharma, etc.). Identifies which sectors are receiving institutional allocation. | M | High | Sector classification table + aggregated RS scores |
| 6 | P1 | PDF/Excel Export | One-click export of any table or signal view to PDF or Excel. Essential for sharing research with PMS clients or investment committees. | S | High | Dashboard data layer (already computed) |
| 7 | P2 | F&O Open Interest + PCR | Daily OI changes and Put-Call Ratio for Nifty 50 stocks with active F&O contracts. OI buildup on a MOMENTUM signal is a high-confidence confirmation. | M | High | NSE F&O bhavcopy (public, daily) |
| 8 | P2 | Earnings Estimate Revisions | Consensus EPS revision % (1M and 3M) from broker estimates. Upward revision trends are among the most reliable leading indicators for stock outperformance. | L | High | Bloomberg, Refinitiv, or Trendlyne API |
| 9 | P2 | News Headline Feed | NSE-announcement-based categorised news feed (Results, Management Change, Pledge, Insider Sale) with auto-tagging by event type. Eliminates manual event monitoring. | M | High | NSE EDGAR XML feed (public) |
| 10 | P2 | Promoter Shareholding Trend | Quarterly promoter holding % with trend over 8 quarters and pledge % overlay. Promoter buying is a high-conviction long signal; pledge increase is a red flag. | M | High | NSE shareholding pattern filings (quarterly) |
| 11 | P2 | Peer Group Comparison | Within-sector relative view: for any stock, show its RS, volume trend, and ISS score vs. sector peers in Nifty 50. Enables sector-relative rather than absolute allocation decisions. | M | Medium | Sector classification + existing signal mart |
| 12 | P2 | Macro Overlay | Annotate the Nifty 50 index chart with RBI rate decisions, India CPI prints, INR/USD moves, and crude oil spikes. Macro events explain sudden correlations across sectors. | M | Medium | RBI website, MOSPI, Bloomberg (free tiers available) |
| 13 | P2 | Alert Fatigue Management | Smart deduplication: suppress repeat alerts for the same symbol+signal combination within a configurable window (e.g., 3 days). Preserves alert discipline. | S | Medium | alert_engine.py extension; no new data feed |
| 14 | P2 | Insider Trading Disclosure Tracker | Track SEBI Form C (UPSI) and Form D (transaction) filings for Nifty 50 promoters and key management. Insider buying is among the strongest fundamental signals available. | M | High | SEBI insider trading disclosure portal (public XML) |
| 15 | P3 | Institutional Block Deal Tracker | Log and display NSE block deal and bulk deal data for Nifty 50 stocks. Identifies when institutional money moves in volume too large for order books. | S | High | NSE block/bulk deal archive (public, daily) |
| 16 | P3 | Mobile-Friendly Responsive Layout | Optimised mobile view with collapsible panels, swipe-able signal cards, and alert notifications via PWA. Enables on-the-go monitoring without a laptop. | L | Medium | UI layer only; no new data required |
| 17 | P3 | Nifty 50 Dividend Yield + Forward P/E Aggregates | Index-level dividend yield and forward P/E based on constituent weightings and consensus estimates. Provides macro valuation context — is the market cheap or expensive? | M | Medium | Consensus estimates (Trendlyne/Refinitiv) + NSE weights |
| 18 | P3 | API Endpoint Layer | Public-facing REST API (authenticated) so institutional clients or algo desks can pull signals programmatically — `/signals/latest`, `/watchlist`, `/events`. | L | High | Existing FastAPI layer + OAuth/API key management |
| 19 | P3 | ESG and Governance Score Overlay | Overlay ESG ratings (CRISIL/Sustainalytics) on the signal heatmap. Filters out high-momentum names with governance flags — relevant for ESG-mandate funds. | M | Low | Paid ESG data vendors (CRISIL ESG, MSCI) |
| 20 | P3 | Multi-Index Support | Extend the entire pipeline to support Nifty Bank (12 stocks), Nifty Midcap 150, and Nifty IT (10 stocks). Enables the same workflow for sector-specialist investors. | L | Medium | Additional bhavcopy parsing; index constituent lists from NSE |

---

## Section 13: Technology Stack Recommendation

### 13.1 Stack Comparison

| Dimension | Stack A: Python + Streamlit | Stack B: dbt + DuckDB + FastAPI + React | Stack C: Python + PostgreSQL + Power BI/Tableau | Stack D: Airflow/Prefect + Snowflake + FastAPI + React |
|---|---|---|---|---|
| **Pros** | Fastest time to working prototype. Single language (Python) end-to-end. No frontend expertise needed. Pandas + SQLAlchemy are familiar to any quant. Streamlit's built-in charting covers 80% of dashboard needs. | Separation of concerns is production-grade. dbt handles lineage, testing, and documentation natively. DuckDB is blazingly fast for analytical queries on 2–5 years of daily data. React gives full UI flexibility. | No custom frontend work. Power BI / Tableau handle all chart types out of the box. Familiar to finance teams. Works with existing BI licenses in most banks/funds. | Fully cloud-native. Airflow/Prefect handles complex DAG orchestration with retry logic, alerting, and monitoring. Snowflake scales to any data volume. Best option for multi-index expansion. |
| **Cons** | Streamlit is not production-grade for concurrent users. State management is clunky. No version-controlled data transformations. Scaling beyond 5 concurrent users requires session hacks or Streamlit Cloud. | Steeper learning curve. Requires JavaScript/TypeScript frontend skills. dbt + DuckDB combination lacks row-level security without additional tooling. React adds 2–3× the frontend development time vs. Streamlit. | Vendor lock-in to BI tool. Power BI's Python/API integration is brittle. Real-time/intraday data requires expensive DirectQuery modes. Limited customisation of alert logic within BI tools. | Highest cost (Snowflake credits, Airflow infra). Over-engineered for a single-user or small-team use case. Snowflake has cold-start latency unsuitable for sub-second dashboard queries without caching. |
| **Best for** | Solo investor, individual developer, or early-stage prototype. Anyone who wants to go from zero to working dashboard in under 2 weeks. | Small team (2–5 engineers) building a product that will be maintained. Fintech startups, boutique PMS firms. Prioritises code quality and long-term maintainability. | Enterprise setting where the BI tool is already licensed and the audience is non-technical (analysts who need self-service slicing). PMO or fund research teams. | Institutional asset management firm with 10+ indices, 100+ concurrent users, and DevOps/DataOps team. Multi-tenant SaaS aspirations. |
| **Est. Setup Time** | 1–2 weeks to MVP | 4–8 weeks to MVP | 2–4 weeks to MVP | 8–16 weeks to production |
| **Ongoing Maintenance** | Low — one repo, one language, few moving parts | Medium — dbt model changes, React build pipeline, schema evolution | Medium-High — BI tool version upgrades, dataset refresh scheduling, DAX/calculated fields drift | High — Snowflake cost management, Airflow DAG maintenance, React + API versioning |

### 13.2 Recommended Stack: Stack B (dbt + DuckDB + FastAPI + React) for Production; Stack A for Rapid Prototyping

**Opinionated recommendation:** Start with Stack A to validate signal logic and data pipeline correctness. Once the signal engine is proven and you have at least 6 months of signal history, migrate to Stack B for the production dashboard. DuckDB is exceptional for this use case — analytical queries on 2–5 years of daily Nifty 50 data (≈50 stocks × 1,250 sessions × ~20 columns) fit entirely in memory, making query latency sub-50ms without indexing tricks.

Do not choose Stack D unless you already have a cloud budget, a DevOps engineer, and plans to serve institutional clients programmatically. The operational overhead is disproportionate to the data volume involved.

---

### 13.3 Recommended Project Structure

```
nifty50-dashboard/
│
├── ingestion/                        # Raw data acquisition layer
│   ├── bhavcopy_loader.py            # Downloads & parses NSE daily bhavcopy ZIP
│   ├── nifty50_constituents.py       # Fetches and caches Nifty 50 index composition
│   ├── corporate_events.py           # Parses NSE EDGAR XML for results, dividends, AGMs
│   ├── fii_dii_loader.py             # (Enhancement P1) Parses SEBI FII/DII daily reports
│   └── realtime_feed.py              # Optional: NSE WebSocket feed for intraday data
│
├── analytics/                        # Transformation and signal computation layer
│   ├── returns_engine.py             # Computes 1D/1M/3M/1Y returns, adjusted for splits/bonus
│   ├── volume_engine.py              # Vol ratio, volume trend classification, anomaly detection
│   ├── rs_engine.py                  # Relative strength vs. Nifty 50 across all timeframes
│   ├── drawdown_engine.py            # 52-week high/low metrics, drawdown pct
│   ├── signal_engine.py              # ISS score computation, category assignment logic
│   └── watchlist_builder.py          # Watchlist candidate selection and ranking
│
├── db/                               # Database layer
│   ├── schema.sql                    # DDL for all raw, intermediate, and mart tables
│   ├── duckdb_init.py                # DuckDB database initialisation and connection factory
│   └── migrations/                   # Versioned schema migration scripts (Alembic or Flyway)
│       ├── V001__initial_schema.sql
│       ├── V002__add_event_tables.sql
│       └── V003__add_iss_score.sql
│
├── api/                              # FastAPI backend
│   ├── main.py                       # App factory, middleware, CORS, startup events
│   ├── dependencies.py               # DB session injection, auth token validation
│   └── routers/
│       ├── signals.py                # GET /signals/latest, /signals/{symbol}
│       ├── watchlist.py              # GET /watchlist, POST /watchlist/refresh
│       ├── events.py                 # GET /events, GET /events/{symbol}
│       ├── anomalies.py              # GET /anomalies/volume
│       └── alerts.py                 # GET /alerts, POST /alerts, DELETE /alerts/{id}
│
├── dashboard/                        # Frontend layer
│   ├── app.py                        # Streamlit entry point (Stack A / prototype)
│   ├── pages/                        # Streamlit multi-page structure
│   │   ├── 01_signal_heatmap.py
│   │   ├── 02_watchlist.py
│   │   ├── 03_events.py
│   │   ├── 04_volume_anomalies.py
│   │   └── 05_drawdown_scanner.py
│   └── react-app/                    # React frontend (Stack B / production)
│       ├── src/
│       │   ├── components/
│       │   │   ├── SignalHeatmap.tsx
│       │   │   ├── WatchlistTable.tsx
│       │   │   ├── VolumeAnomalyCard.tsx
│       │   │   └── EventTimeline.tsx
│       │   ├── hooks/
│       │   │   └── useSignals.ts
│       │   └── pages/
│       └── package.json
│
├── alerts/                           # Alert engine
│   ├── alert_engine.py               # Evaluates user alert rules against latest signal data
│   ├── dedup_engine.py               # Alert fatigue deduplication (Enhancement P2)
│   └── notification_adapters/
│       ├── email_sender.py
│       └── webhook_sender.py          # Slack/Telegram webhook support
│
├── tests/                            # Test suite
│   ├── unit/
│   │   ├── test_returns_engine.py
│   │   ├── test_signal_engine.py
│   │   └── test_volume_engine.py
│   ├── integration/
│   │   ├── test_pipeline_e2e.py
│   │   └── test_api_endpoints.py
│   └── fixtures/
│       └── sample_bhavcopy.csv
│
├── scheduler/                        # Orchestration
│   ├── daily_pipeline.py             # Orchestrates full EOD pipeline (can be run via cron or Prefect)
│   ├── intraday_pipeline.py          # 15-min intraday refresh (optional)
│   └── pipeline_config.yaml          # Schedule definitions, retry policy, alerting thresholds
│
├── config/
│   ├── settings.py                   # Pydantic BaseSettings: DB path, API keys, schedule times
│   └── logging_config.yaml
│
├── notebooks/                        # Exploratory analysis and signal backtesting
│   ├── signal_backtest.ipynb
│   └── rs_analysis.ipynb
│
├── docker-compose.yml                # Local development: API + DuckDB + optional Postgres
├── Makefile                          # make pipeline, make test, make migrate
├── requirements.txt
└── README.md
```

**Key architectural decisions embedded in this structure:**

1. **`analytics/` is entirely stateless and pure Python.** Each engine takes a DataFrame in, returns a DataFrame out. This makes unit testing trivial and allows the signal logic to be ported to any execution environment (cron, Prefect, Airflow, or a Jupyter notebook) without refactoring.

2. **`db/migrations/` uses versioned SQL files.** Whether you use Alembic (Python-native) or Flyway (JVM-native, familiar to Goldman-level Java engineers), the principle is identical: never mutate the schema manually. Every schema change is a reviewed, version-controlled migration.

3. **`dashboard/` contains both Streamlit and React source.** This supports the recommended two-phase approach: prototype in Streamlit, migrate to React as user count and feature complexity grow. The FastAPI layer is identical for both.

4. **`alerts/notification_adapters/`** is an abstract adapter pattern. Adding a new notification channel (WhatsApp, Bloomberg terminal message, Telegram) requires only a new adapter file — the alert engine itself does not change.

5. **`notebooks/`** is first-class. Signal backtesting (Enhancement P1) lives here during development and promotes to `analytics/backtest_engine.py` once methodology is locked down.

---

*End of Specification — Part 3 (Sections 10–13)*
