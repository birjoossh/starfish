"""baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-16

Applies the full project schema captured in sql/schema.sql at the time of
Alembic adoption. Every CREATE TABLE / CREATE INDEX in that file uses
IF NOT EXISTS, so this migration is idempotent on existing databases —
running it against a DB that already has the schema is a no-op.

For DBs that already have the schema applied, the conventional path is:

    alembic stamp 0001_baseline

which marks the DB as caught up without re-running the DDL. ``alembic
upgrade head`` will then take it the rest of the way for any later
revisions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

from alembic import op


revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SCHEMA_FILE = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"


def upgrade() -> None:
    sql = _SCHEMA_FILE.read_text()
    op.execute(sql)


def downgrade() -> None:
    raise NotImplementedError(
        "Baseline migration cannot be downgraded — it would drop every table "
        "in the schema. Restore from a backup if you need to roll back."
    )
