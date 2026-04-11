# DESIGN.md — Nifty 50 Dashboard

Design system for the Nifty 50 Investment Monitoring Dashboard.
All UI decisions reference this file. Updated as new components are added.

## Design Philosophy

Terminal-inspired investment tool. Dense data, minimal chrome, fast scanning.
The user opens the dashboard to answer "what needs my attention today?" in under 10 minutes.
Every pixel earns its place. If it doesn't inform a decision, it's cut.

## Color Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#1a1a2e` | Main background |
| `--bg-secondary` | `#16213e` | Card/section backgrounds |
| `--bg-surface` | `#0f3460` | Table header, elevated surfaces |
| `--text-primary` | `#e0e0e0` | Body text, data |
| `--text-muted` | `#888888` | Labels, timestamps, secondary info |
| `--positive` | `#00d4aa` | Positive returns, advancing counts |
| `--negative` | `#ff4757` | Negative returns, declining counts |
| `--accent` | `#ffd700` | Watchlist highlight, gold badges |
| `--neutral` | `#6c757d` | Unchanged, zero values |
| `--amber` | `#ffa502` | Warnings, volume spikes, moderate signals |
| `--border` | `#2a2a4a` | Table borders, dividers |

## Typography

| Role | Font | Size | Weight | Usage |
|------|------|------|--------|-------|
| Data | JetBrains Mono | 13px | 400 | Table cells, numbers, returns |
| Header | Inter (or system) | 14px | 600 | Table headers, section titles |
| Title | Inter (or system) | 20px | 700 | Dashboard title |
| Label | Inter (or system) | 12px | 400 | Status bar, timestamps, tooltips |
| Digest | JetBrains Mono | 14px | 400 | Morning digest output |

Numbers are right-aligned. Text is left-aligned. Symbol column is left-aligned monospace.

## Spacing Scale

Base unit: 4px

| Token | Value | Usage |
|-------|-------|-------|
| `--sp-1` | 4px | Inline padding |
| `--sp-2` | 8px | Cell padding, small gaps |
| `--sp-3` | 12px | Section padding |
| `--sp-4` | 16px | Card padding, between sections |
| `--sp-6` | 24px | Major section gaps |
| `--sp-8` | 32px | Page margins |

## Component Specs

### Data Table (Stock Screener)

- Row height: 36px (dense, 50 rows visible without scrolling on desktop)
- Row hover: `--bg-secondary` background highlight
- Column order: Symbol, Company, Sector, Price, 1D%, 1M%, 3M%, Vol Ratio, 52W Dist
- Sort indicator: small triangle in header, default sort = 1D% descending
- Sticky header: table header stays visible on scroll
- Number columns: right-aligned, monospace
- Return colors: positive = `--positive`, negative = `--negative`, zero = `--neutral`
- Volume ratio colors: >1.5x = `--amber`, >2x = `--negative` (orange-red)
- 52W distance: red gradient, deeper red closer to -50%

### Signal Badge

Compact inline indicator for signal strength:
- Green badge: `--positive` background, dark text. Used for "Accumulation", positive signals.
- Red badge: `--negative` background, white text. Used for "Falling Knife", adverse signals.
- Amber badge: `--amber` background, dark text. Used for "Needs Review", moderate signals.
- Gold badge: `--accent` background, dark text. Used for watchlist items.

Badge format: pill shape, 2px horizontal padding, 10px font.

### Watchlist Highlight

Symbols on the watchlist get a 3px gold left-border stripe on their table row.
No other visual change — the gold border is enough to scan 50 rows quickly.
Watchlist panel (top-right) shows symbol + key signal + one-line reason.

### Sector Breadth Table

- Compact table, no hover effects
- Advancing count: `--positive` text
- Declining count: `--negative` text
- Average return: colored by direction
- Row background: light red tint if all declining, light green if all advancing

### Status Bar

Fixed at bottom of dashboard:
- Left: "Showing N stocks | Watchlist: M highlighted"
- Right: "Last updated: YYYY-MM-DD HH:MM IST" or "Pipeline not run today"

## Interaction Patterns

| Pattern | Behavior |
|---------|----------|
| Sort | Click column header to sort. Click again to reverse. Default: 1D% desc. |
| Filter | Sector dropdown (multi-select). Watchlist toggle. Period selector (1D/1M/3M/1Y). |
| Hover | Row highlight + tooltip with full company name and sector |
| Click | No click action in M1 (read-only dashboard). M2+: click row to expand detail. |

## Empty/Error State Templates

### Empty (no data)
```
[Icon: chart-line]
No stock data loaded yet.
Run `python -m ingestion.daily_run` to load today's data.
```

### Error (DB down)
```
[Icon: alert-triangle]
Cannot connect to database.
Check that PostgreSQL is running and try again.
[Retry]
```

### Partial (some stocks missing)
```
[Icon: info]
43 of 50 stocks loaded.
7 symbols had no data today: TCS, WIPRO, ...
```

### Loading
```
10 skeleton rows with gray shimmer animation.
"Loading stock data..."
```

## Responsive

**M1: Desktop-only.** Target 1024px+ width. Streamlit is desktop-first.

| Viewport | Behavior |
|----------|----------|
| 1024px+ | Full layout: breadth + watchlist on top (side-by-side), stocks table below |
| 768-1024px | Table gets horizontal scroll. Sections remain side-by-side. |
| <768px | Streamlit stacks sections vertically (default behavior). Table scrolls horizontally. |
| <480px | Not supported in M1. |

No custom mobile layout in M1. M2 (React migration) will include proper mobile design with touch-optimized interactions.

## Accessibility

M1 accessibility is limited by Streamlit's built-in support. Documented commitments:

- **Color contrast:** All text/background combinations meet WCAG AA (4.5:1 for body text). The dark theme tokens are pre-checked: `#e0e0e0` on `#1a1a2e` = 10.3:1. `#00d4aa` on `#1a1a2e` = 7.8:1. `#ff4757` on `#1a1a2e` = 4.7:1.
- **Not color alone:** Return percentages include the + or - sign. Signal badges include text labels ("Accumulation", "Falling Knife"), not just color.
- **Keyboard:** Streamlit components are keyboard-accessible by default. Sort headers are clickable buttons (keyboard reachable).
- **Screen readers:** Table headers are semantic (`<th>`). Streamlit handles ARIA labels on interactive elements.

M2 (React): full WCAG AA compliance, ARIA landmarks, skip-nav, focus management.

## What This Does NOT Cover

- Animations and transitions (Streamlit doesn't support these well)
- Dark/light mode toggle (dark only for M1)
- Custom Streamlit components (stock components only for M1)
- Print styles (not needed for M1)
