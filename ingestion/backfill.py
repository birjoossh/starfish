"""Backfill orchestration.

Main CLI for backfilling historical NSE data.
Downloads and loads both Bhavcopy and Index prices.

Usage:
    python -m ingestion.backfill --days 365
"""

import argparse
import logging
from datetime import date, datetime, timedelta
import pandas as pd
from sqlalchemy import text
from pathlib import Path
import traceback
import sys

from config.settings import settings
from config.database import get_engine
from ingestion.nse_client import NSEClient, CircuitBreakerOpen
from ingestion.bhavcopy_parser import BhavcopyParser, BhavcopyParseError
from ingestion.bhavcopy_loader import BhavcopyLoader
from analytics.compute_52wk import compute_52wk
from analytics.compute_signals import compute_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class BackfillOrchestrator:
    def __init__(self, local_dir=None):
        self.local_dir = Path(local_dir) if local_dir else None
        self.client = NSEClient()
        self.parser = BhavcopyParser()
        self.loader = BhavcopyLoader()
        self.engine = get_engine()
        
    def _get_bhavcopy_cache_path(self, trade_date: date) -> Path:
        """Get expected path for cached bhavcopy CSV."""
        cache_dir = settings.project_root / "data" / "bhavcopy"
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Matches NSE naming
        month_upper = trade_date.strftime("%b").upper()
        return cache_dir / f"cm{trade_date.strftime('%d')}{month_upper}{trade_date.year}bhav.csv"

    def _get_index_cache_path(self, trade_date: date) -> Path:
        """Get expected path for cached index CSV."""
        cache_dir = settings.project_root / "data" / "index"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"ind_close_all_{trade_date.strftime('%d%m%Y')}.csv"

    def download_index_csv(self, trade_date: date, output_dir: Path | None = None) -> Path:
        """Download index prices CSV using NSEClient's session to maintain rate limits."""
        if output_dir is None:
            output_dir = settings.project_root / "data" / "index"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"ind_close_all_{trade_date.strftime('%d%m%Y')}.csv"
        url = f"{self.client.base_url}/content/indices/{filename}"
        output_path = output_dir / filename
        
        logger.info(f"Downloading index prices: {url}")
        resp = self.client._request_with_retry(url)
        
        with open(output_path, "wb") as f:
            f.write(resp.content)
            
        return output_path

    def parse_and_load_index_csv(self, csv_path: Path, trade_date: date) -> int:
        """Parse index CSV and upsert Nifty 50 close price."""
        try:
            df = pd.read_csv(csv_path)
            
            # Filter for Nifty 50
            if "Index Name" not in df.columns or "Closing Index Value" not in df.columns:
                logger.warning(f"Invalid index CSV shape in {csv_path}")
                return 0
                
            nifty_row = df[df["Index Name"].str.upper() == "NIFTY 50"]
            if nifty_row.empty:
                logger.warning(f"Nifty 50 not found in {csv_path}")
                return 0
                
            close_price = float(nifty_row.iloc[0]["Closing Index Value"])
            
            upsert_sql = text("""
                INSERT INTO nifty50_index_prices (trade_date, close)
                VALUES (:trade_date, :close)
                ON CONFLICT (trade_date) DO UPDATE SET
                    close = EXCLUDED.close
            """)
            
            with self.engine.connect() as conn:
                conn.execute(upsert_sql, {
                    "trade_date": trade_date,
                    "close": close_price
                })
                conn.commit()
            
            return 1
            
        except Exception as e:
            logger.error(f"Failed to load index data from {csv_path}: {e}")
            return 0
            
    def _is_holiday(self, e: Exception) -> bool:
        """Check if request error is likely due to market holiday."""
        err_str = str(e)
        return "404" in err_str or "Not Found" in err_str
            
    def run(self, start_date: date, end_date: date, skip_index=False, skip_analytics=False):
        """Run backfill orchestration."""
        logger.info(f"Starting backfill from {start_date} to {end_date}")
        
        stats = {
            "days_processed": 0,
            "bhavcopy_loaded": 0,
            "index_loaded": 0,
            "errors": 0
        }
        
        current = end_date
        while current >= start_date:
            if current.weekday() >= 5:  # Skip weekends
                current -= timedelta(days=1)
                continue
                
            logger.info(f"Processing date: {current}")
            date_errors = 0
            
            # 1. Bhavcopy
            bhav_path = self._get_bhavcopy_cache_path(current)
            if not bhav_path.exists() and not self.local_dir:
                try:
                    bhav_path = self.client.download_bhavcopy(current)
                except CircuitBreakerOpen as e:
                    logger.error("Circuit breaker tripped on Bhavcopy. Stopping.")
                    break
                except Exception as e:
                    if self._is_holiday(e):
                        logger.info(f"Holiday/No data for Bhavcopy on {current}")
                        self.client.reset_circuit()
                    else:
                        logger.warning(f"Bhavcopy download failed for {current}: {e}")
                        date_errors += 1
                    bhav_path = None
                    
            if bhav_path and bhav_path.exists():
                try:
                    df = self.parser.parse(bhav_path, trade_date=current)
                    load_stats = self.loader.load(df, source_file=bhav_path.name)
                    if load_stats["status"] == "success":
                        stats["bhavcopy_loaded"] += 1
                    else:
                        date_errors += 1
                except Exception as e:
                    logger.error(f"Failed to parse/load Bhavcopy for {current}: {e}")
                    date_errors += 1
            
            # 2. Index prices
            if not skip_index:
                index_path = self._get_index_cache_path(current)
                if not index_path.exists() and not self.local_dir:
                    try:
                        index_path = self.download_index_csv(current)
                    except CircuitBreakerOpen as e:
                        logger.error("Circuit breaker tripped on Index. Stopping.")
                        break
                    except Exception as e:
                        if self._is_holiday(e):
                            logger.info(f"Holiday/No data for Index on {current}")
                            self.client.reset_circuit()
                        else:
                            logger.warning(f"Index download failed for {current}: {e}")
                            date_errors += 1
                        index_path = None
                
                if index_path and index_path.exists():
                    rows = self.parse_and_load_index_csv(index_path, current)
                    if rows > 0:
                        stats["index_loaded"] += 1
                    else:
                        date_errors += 1
                        
            stats["days_processed"] += 1
            if date_errors > 0:
                stats["errors"] += 1
                
            # Log progress every 20 days
            if stats["days_processed"] % 20 == 0:
                logger.info(f"Progress: Processed {stats['days_processed']} days. "
                            f"Bhavcopies loaded: {stats['bhavcopy_loaded']}. "
                            f"Indices loaded: {stats['index_loaded']}")
                
            current -= timedelta(days=1)
            
        logger.info(f"Load complete. Processed {stats['days_processed']} days. "
                    f"Errors on {stats['errors']} days.")
                    
        # 3. Post-load analytics
        if not skip_analytics:
            logger.info("Running post-load analytics (52-week & signals)...")
            try:
                c52 = compute_52wk()
                logger.info(f"Computed 52-week data: {c52} rows.")
                cs = compute_signals()
                logger.info(f"Computed signals: {cs} rows.")
            except Exception as e:
                logger.error(f"Analytics failed: {e}")
                logger.debug(traceback.format_exc())

def main():
    parser = argparse.ArgumentParser(description="Nifty 50 1-Year Backfill")
    parser.add_argument("--days", type=int, help="Number of calendar days to backfill from today")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--skip-index", action="store_true", help="Skip index prices")
    parser.add_argument("--skip-analytics", action="store_true", help="Skip post-load analytics")
    parser.add_argument("--local", type=str, help="Local directory with cached CSVs")
    
    args = parser.parse_args()
    
    if args.days:
        end_date = date.today()
        start_date = end_date - timedelta(days=args.days)
    elif args.start and args.end:
        start_date = date.fromisoformat(args.start)
        end_date = date.fromisoformat(args.end)
    else:
        logger.error("Must provide either --days or both --start and --end")
        sys.exit(1)
        
    orchestrator = BackfillOrchestrator(local_dir=args.local)
    orchestrator.run(
        start_date=start_date, 
        end_date=end_date, 
        skip_index=args.skip_index, 
        skip_analytics=args.skip_analytics
    )

if __name__ == "__main__":
    main()
