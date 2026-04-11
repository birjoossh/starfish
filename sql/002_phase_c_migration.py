"""Phase C Schema Migration.

Mutating test-enum logic out of mart_stock_signals and safely structuring 
ISS parameter foundations.
"""

from config.database import get_engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    engine = get_engine()
    
    statements = [
        # Remove old placeholder defaults 
        "UPDATE mart_stock_signals SET signal_category = 'Neutral' WHERE signal_category IN ('Bullish', 'Bearish');",
        "UPDATE mart_stock_signals SET volume_trend_3m = 'Mixed' WHERE volume_trend_3m IN ('Rising', 'Falling');",
        
        # Drop strict checking
        "ALTER TABLE mart_stock_signals DROP CONSTRAINT IF EXISTS mart_stock_signals_signal_category_check;",
        "ALTER TABLE mart_stock_signals ADD CONSTRAINT mart_stock_signals_signal_category_check CHECK (signal_category IN ('Accumulation', 'Momentum', 'EventDriven', 'Neutral'));",
        
        "ALTER TABLE mart_stock_signals DROP CONSTRAINT IF EXISTS mart_stock_signals_volume_trend_3m_check;",
        "ALTER TABLE mart_stock_signals ADD CONSTRAINT mart_stock_signals_volume_trend_3m_check CHECK (volume_trend_3m IN ('Expanding', 'Contracting', 'Mixed'));",
        
        # Insert Required Columns
        "ALTER TABLE mart_stock_signals ADD COLUMN IF NOT EXISTS last_event_significance INTEGER;",
        "ALTER TABLE mart_stock_signals ADD COLUMN IF NOT EXISTS last_event_is_negative BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE mart_stock_signals ADD COLUMN IF NOT EXISTS nifty50_member BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE mart_stock_signals ADD COLUMN IF NOT EXISTS iss_score_breakdown JSONB;"
    ]
    
    with engine.begin() as conn:
        for stmt in statements:
            logger.info(f"Executing: {stmt}")
            conn.execute(text(stmt))
    logger.info("Migrated Phase C successfully!")

if __name__ == "__main__":
    migrate()
