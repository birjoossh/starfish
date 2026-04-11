# Starfish: Nifty 50 Investment Signal Dashboard

**Starfish** is an information-dense, terminal-inspired financial dashboard designed for rapid analysis of Nifty 50 stocks. It combines technical indicators, relative strength metrics, and corporate events into a unified **Investment Signal Score (ISS)**.

![Starfish Logo](starfish_logo.svg)

## Key Features

- **Morning Digest**: Instant overview of the top 3 high-conviction signals with rationales.
- **Unified Terminal UI**: A single-page, vertically-dense layout for maximum speed-to-insight.
- **Investment Signal Score (ISS)**: A proprietary 0-100 score based on:
  - Price Performance (3M/1Y)
  - Relative Strength vs Nifty 50
  - Drawdown & Base Recovery
  - Volume Confirmation
  - Corporate Events (Earnings, Dividends, Splits, etc.)
- **Signal Classification**:
  - `Momentum`: High ISS with positive trend and volume confirmation.
  - `Accumulation`: Deep pullbacks with contracting volume and fundamental base.
  - `EventDriven`: Priority signals for upcoming or recent corporate actions.
- **Interactive Visualizations**:
  - Sector Rotation & Breadth Heatmap.
  - Volatility vs Return Scatter Plots.
  - Sector Treemaps.

## Technology Stack

- **Backend**: FastAPI (Python)
- **Frontend**: Streamlit
- **Database**: PostgreSQL
- **Analytics**: Pandas & SQLAlchemy
- **Visualizations**: Plotly

## Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL

### Installation

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd nifty50-dashboard
   ```

2. Set up virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure environment variables in `.env`:
   ```
   DATABASE_URL=postgresql://user:pass@localhost:5432/nifty50
   ```

### Running the Dashboard

Launch both the API and the Streamlit dashboard using the provided script:
```bash
./run.sh
```

## Project Status

Current Phase: **Phase E Completed** (Corporate Events & Ingestion Layers).
Next Phase: **Phase F** (Sector Rotation & Breadth Tracking).

## Credits
Designed and built by **Antigravity** for the Starfish Project.
