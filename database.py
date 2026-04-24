import sqlite3
from datetime import date

from config import DATA_DIR, DB_PATH


def get_connection():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS apartment_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sgg_cd TEXT NOT NULL,
                gu_name TEXT NOT NULL,
                umd_nm TEXT,
                apt_name TEXT NOT NULL,
                apt_seq TEXT,
                jibun TEXT,
                exclusive_area REAL NOT NULL,
                floor INTEGER,
                build_year INTEGER,
                deal_year INTEGER NOT NULL,
                deal_month INTEGER NOT NULL,
                deal_day INTEGER NOT NULL,
                deal_date TEXT NOT NULL,
                deal_amount INTEGER NOT NULL,
                raw_xml TEXT,
                is_backfill INTEGER NOT NULL DEFAULT 1,
                first_seen_date TEXT,
                first_seen_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (
                    sgg_cd,
                    apt_name,
                    exclusive_area,
                    floor,
                    deal_date,
                    deal_amount,
                    apt_seq,
                    jibun
                )
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trades_record_lookup
            ON apartment_trades (sgg_cd, apt_name, exclusive_area, deal_date, deal_amount)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trades_deal_date
            ON apartment_trades (deal_date)
            """
        )
        ensure_trade_metadata_columns(conn)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trades_first_seen
            ON apartment_trades (first_seen_date, is_backfill)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS apartment_complexes (
                kapt_code TEXT PRIMARY KEY,
                kapt_name TEXT NOT NULL,
                as1 TEXT,
                as2 TEXT,
                as3 TEXT,
                as4 TEXT,
                bjd_code TEXT,
                household_count INTEGER,
                dong_count INTEGER,
                used_date TEXT,
                address TEXT,
                road_address TEXT,
                raw_xml TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_complex_match
            ON apartment_complexes (as2, as3, kapt_name)
            """
        )


def column_exists(conn, table_name, column_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def ensure_trade_metadata_columns(conn):
    if not column_exists(conn, "apartment_trades", "is_backfill"):
        conn.execute("ALTER TABLE apartment_trades ADD COLUMN is_backfill INTEGER NOT NULL DEFAULT 1")
    if not column_exists(conn, "apartment_trades", "first_seen_date"):
        conn.execute("ALTER TABLE apartment_trades ADD COLUMN first_seen_date TEXT")
    if not column_exists(conn, "apartment_trades", "first_seen_at"):
        conn.execute("ALTER TABLE apartment_trades ADD COLUMN first_seen_at TEXT")
    conn.execute(
        """
        UPDATE apartment_trades
        SET is_backfill = 1,
            first_seen_date = NULL,
            first_seen_at = NULL
        WHERE is_backfill IS NULL
        """
    )


def mark_existing_trades_as_backfill():
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE apartment_trades
            SET is_backfill = 1,
                first_seen_date = NULL,
                first_seen_at = NULL
            """
        )


def insert_trades(trades, is_backfill=True, first_seen_date=None):
    if not trades:
        return 0

    if first_seen_date is None and not is_backfill:
        first_seen_date = date.today().isoformat()

    prepared_trades = []
    for trade in trades:
        prepared = dict(trade)
        prepared["is_backfill"] = 1 if is_backfill else 0
        prepared["first_seen_date"] = None if is_backfill else first_seen_date
        prepared_trades.append(prepared)

    with get_connection() as conn:
        before = conn.total_changes
        conn.executemany(
            """
            INSERT OR IGNORE INTO apartment_trades (
                sgg_cd,
                gu_name,
                umd_nm,
                apt_name,
                apt_seq,
                jibun,
                exclusive_area,
                floor,
                build_year,
                deal_year,
                deal_month,
                deal_day,
                deal_date,
                deal_amount,
                raw_xml,
                is_backfill,
                first_seen_date,
                first_seen_at
            )
            VALUES (
                :sgg_cd,
                :gu_name,
                :umd_nm,
                :apt_name,
                :apt_seq,
                :jibun,
                :exclusive_area,
                :floor,
                :build_year,
                :deal_year,
                :deal_month,
                :deal_day,
                :deal_date,
                :deal_amount,
                :raw_xml,
                :is_backfill,
                :first_seen_date,
                CASE
                    WHEN :first_seen_date IS NULL THEN NULL
                    ELSE CURRENT_TIMESTAMP
                END
            )
            """,
            prepared_trades,
        )
        return conn.total_changes - before


def upsert_complexes(complexes):
    if not complexes:
        return 0

    with get_connection() as conn:
        before = conn.total_changes
        conn.executemany(
            """
            INSERT INTO apartment_complexes (
                kapt_code,
                kapt_name,
                as1,
                as2,
                as3,
                as4,
                bjd_code,
                household_count,
                dong_count,
                used_date,
                address,
                road_address,
                raw_xml,
                updated_at
            )
            VALUES (
                :kapt_code,
                :kapt_name,
                :as1,
                :as2,
                :as3,
                :as4,
                :bjd_code,
                :household_count,
                :dong_count,
                :used_date,
                :address,
                :road_address,
                :raw_xml,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(kapt_code) DO UPDATE SET
                kapt_name = excluded.kapt_name,
                as1 = excluded.as1,
                as2 = excluded.as2,
                as3 = excluded.as3,
                as4 = excluded.as4,
                bjd_code = excluded.bjd_code,
                household_count = excluded.household_count,
                dong_count = excluded.dong_count,
                used_date = excluded.used_date,
                address = excluded.address,
                road_address = excluded.road_address,
                raw_xml = excluded.raw_xml,
                updated_at = CURRENT_TIMESTAMP
            """,
            complexes,
        )
        return conn.total_changes - before


def get_summary():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                COUNT(*) AS total_trades,
                MIN(deal_date) AS first_deal_date,
                MAX(deal_date) AS last_deal_date
            FROM apartment_trades
            """
        ).fetchone()


def get_complex_summary():
    init_db()
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                COUNT(*) AS total_complexes,
                SUM(CASE WHEN household_count IS NOT NULL THEN 1 ELSE 0 END) AS complexes_with_households,
                MAX(updated_at) AS latest_complex_update
            FROM apartment_complexes
            """
        ).fetchone()
