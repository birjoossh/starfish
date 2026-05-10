"""Copy data from `nifty50` to `new_nifty50` for fast local iteration.

Strategy:
    * dim/aux tables are copied in full.
    * fact/mart/log tables are filtered to the last N trading days (default 60).
    * Target tables are TRUNCATEd (CASCADE, RESTART IDENTITY) before insert,
      so the script is deterministic and re-runnable.

Usage:
    python scripts/migrate_to_new_nifty50.py [--days 60] \
        [--source-url postgresql://.../nifty50] \
        [--target-url postgresql://.../new_nifty50]

Defaults pull URLs from $SOURCE_DB_URL / $TARGET_DB_URL, falling back to the
local docker-compose Postgres on port 5433.
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import time
from dataclasses import dataclass

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate")

DEFAULT_SOURCE_URL = "postgresql://myuser:myuser1234@localhost:5433/nifty50"
DEFAULT_TARGET_URL = "postgresql://myuser:myuser1234@localhost:5433/new_nifty50"


@dataclass(frozen=True)
class TableSpec:
    """Migration plan for a single table.

    `date_column` is the column used to filter recent rows. If None, the
    entire table is copied. Order in MIGRATION_PLAN determines insert order
    so foreign keys resolve correctly.
    """

    name: str
    date_column: str | None = None


# Order matters: parents before children for FK resolution.
MIGRATION_PLAN: tuple[TableSpec, ...] = (
    # Dimensions (full copy)
    TableSpec("dim_stock"),
    TableSpec("watchlist_users"),
    TableSpec("watchlist_categories"),
    TableSpec("symbol_alias"),
    TableSpec("dim_nifty50_constituent"),
    # Per-day facts (windowed)
    TableSpec("fact_eod_price", date_column="trade_date"),
    TableSpec("fact_52wk", date_column="trade_date"),
    TableSpec("nifty50_index_prices", date_column="trade_date"),
    TableSpec("fact_corporate_action", date_column="ex_date"),
    TableSpec("fact_corporate_event", date_column="event_date"),
    # Marts (windowed)
    # TableSpec("mart_stock_signals", date_column="calc_date"),
    # TableSpec("mart_volume_anomaly", date_column="calc_date"),
    # User/alert tables (full copy — small, FK to watchlist_users/dim_stock)
    TableSpec("user_watchlist"),
    TableSpec("user_alert_preferences"),
    # Logs / event streams (windowed by timestamp)
    # TableSpec("ingestion_log", date_column="started_at"),
    TableSpec("alerts", date_column="triggered_at"),
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--days",
        type=int,
        default=60,
        help="Number of trailing days of fact/mart/log data to copy (default: 60).",
    )
    p.add_argument(
        "--source-url",
        default=os.environ.get("SOURCE_DB_URL", DEFAULT_SOURCE_URL),
        help="Source DB URL (default: $SOURCE_DB_URL or local nifty50).",
    )
    p.add_argument(
        "--target-url",
        default=os.environ.get("TARGET_DB_URL", DEFAULT_TARGET_URL),
        help="Target DB URL (default: $TARGET_DB_URL or local new_nifty50).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print row counts that would be migrated; do not write.",
    )
    return p.parse_args()


def safety_check(source_url: str, target_url: str) -> None:
    if source_url == target_url:
        sys.exit("Refusing to run: source and target URLs are identical.")
    if "/nifty50" in target_url.rsplit("/", 1)[-1].split("?")[0]:
        sys.exit(
            "Refusing to run: target appears to be the production `nifty50` DB. "
            "Set --target-url explicitly to the smaller DB."
        )


def truncate_targets(target_conn: psycopg2.extensions.connection) -> None:
    """One TRUNCATE statement so CASCADE works and FKs don't fight us."""
    table_list = ", ".join(t.name for t in MIGRATION_PLAN)
    sql = f"TRUNCATE {table_list} RESTART IDENTITY CASCADE;"
    log.info("Truncating %d target tables...", len(MIGRATION_PLAN))
    with target_conn.cursor() as cur:
        cur.execute(sql)
    target_conn.commit()


def count_source_rows(
    source_conn: psycopg2.extensions.connection, spec: TableSpec, days: int
) -> int:
    where = ""
    params: tuple = ()
    if spec.date_column is not None:
        where = f" WHERE {spec.date_column} >= CURRENT_DATE - %s::int"
        params = (days,)
    with source_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {spec.name}{where}", params)
        return cur.fetchone()[0]


def copy_table(
    source_conn: psycopg2.extensions.connection,
    target_conn: psycopg2.extensions.connection,
    spec: TableSpec,
    days: int,
) -> int:
    """Stream one table from source to target via CSV through memory."""
    if spec.date_column is None:
        select_sql = f"SELECT * FROM {spec.name}"
    else:
        select_sql = (
            f"SELECT * FROM {spec.name} "
            f"WHERE {spec.date_column} >= CURRENT_DATE - {days}"
        )

    buf = io.StringIO()
    with source_conn.cursor() as src_cur:
        src_cur.copy_expert(
            f"COPY ({select_sql}) TO STDOUT WITH CSV HEADER", buf
        )
    buf.seek(0)

    with target_conn.cursor() as tgt_cur:
        tgt_cur.copy_expert(
            f"COPY {spec.name} FROM STDIN WITH CSV HEADER", buf
        )
        tgt_cur.execute(f"SELECT COUNT(*) FROM {spec.name}")
        return tgt_cur.fetchone()[0]


def reset_identity_sequences(target_conn: psycopg2.extensions.connection) -> None:
    """After bulk insert, advance IDENTITY sequences past the max imported PK."""
    sql = """
    SELECT
        c.table_schema,
        c.table_name,
        c.column_name
    FROM information_schema.columns c
    WHERE c.is_identity = 'YES'
      AND c.table_schema = 'public'
      AND c.table_name = ANY(%s)
    """
    table_names = [t.name for t in MIGRATION_PLAN]
    with target_conn.cursor() as cur:
        cur.execute(sql, (table_names,))
        identity_cols = cur.fetchall()
        for schema, table, col in identity_cols:
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence(%s, %s), "
                f"COALESCE((SELECT MAX({col}) FROM {schema}.{table}), 1), true)",
                (f"{schema}.{table}", col),
            )
    target_conn.commit()


def main() -> int:
    args = parse_args()
    safety_check(args.source_url, args.target_url)

    log.info("Source : %s", args.source_url)
    log.info("Target : %s", args.target_url)
    log.info("Window : last %d days for date-filtered tables", args.days)
    if args.dry_run:
        log.info("DRY RUN — no data will be written.")

    source_conn = psycopg2.connect(args.source_url)
    target_conn = psycopg2.connect(args.target_url)
    source_conn.set_session(readonly=True)

    try:
        if args.dry_run:
            total = 0
            for spec in MIGRATION_PLAN:
                n = count_source_rows(source_conn, spec, args.days)
                window = f"(last {args.days}d)" if spec.date_column else "(full)"
                log.info("  %-28s %10d rows %s", spec.name, n, window)
                total += n
            log.info("Total rows that would be migrated: %d", total)
            return 0

        truncate_targets(target_conn)

        grand_total = 0
        for spec in MIGRATION_PLAN:
            t0 = time.perf_counter()
            try:
                n = copy_table(source_conn, target_conn, spec, args.days)
            except Exception as exc:
                target_conn.rollback()
                log.error("FAILED %s: %s", spec.name, exc)
                return 1
            target_conn.commit()
            elapsed = time.perf_counter() - t0
            window = f"(last {args.days}d)" if spec.date_column else "(full)"
            log.info(
                "  %-28s %10d rows %s in %.2fs", spec.name, n, window, elapsed
            )
            grand_total += n

        reset_identity_sequences(target_conn)
        log.info("Migration complete. %d total rows in target.", grand_total)
        return 0
    finally:
        source_conn.close()
        target_conn.close()


if __name__ == "__main__":
    sys.exit(main())
