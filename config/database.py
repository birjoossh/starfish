"""Database session and engine factory.

Shared by ingestion, analytics, and API modules.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    """Get or create the SQLAlchemy engine (singleton)."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create the session factory (singleton)."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a database session with automatic commit/rollback."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def read_sql_df(query: str, params: dict | None = None) -> pd.DataFrame:
    """Execute a SQL query and return results as a DataFrame."""
    engine = get_engine()
    return pd.read_sql_query(text(query), engine, params=params)


def write_df_to_sql(
    df: pd.DataFrame,
    table_name: str,
    if_exists: str = "append",
    index: bool = False,
    chunksize: int = 10000,
) -> int:
    """Write a DataFrame to a SQL table. Returns row count."""
    engine = get_engine()
    df.to_sql(table_name, engine, if_exists=if_exists, index=index, chunksize=chunksize)
    return len(df)


def check_db_health() -> dict:
    """Check DB connectivity and return table row counts."""
    engine = get_engine()
    result = {"status": "ok", "tables": {}}
    try:
        with engine.connect() as conn:
            tables = [
                "dim_stock", "fact_eod_price", "fact_52wk",
                "dim_nifty50_constituent", "fact_corporate_action",
                "fact_corporate_event", "mart_stock_signals",
                "mart_volume_anomaly", "ingestion_log",
            ]
            for table in tables:
                try:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    result["tables"][table] = count
                except Exception:
                    result["tables"][table] = "error"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result
