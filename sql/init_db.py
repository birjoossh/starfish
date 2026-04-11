"""Initialize the database from schema.sql.

Usage:
    python -m sql.init_db
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from config.database import get_engine


def init_db() -> None:
    """Execute schema.sql to create all tables."""
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    ddl = schema_path.read_text()
    engine = get_engine()

    with engine.connect() as conn:
        conn.execute(text(ddl))
        conn.commit()

    print(f"Database initialized from {schema_path.name}")


if __name__ == "__main__":
    init_db()
