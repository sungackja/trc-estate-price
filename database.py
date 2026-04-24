import sqlite3

from config import DATA_DIR, DB_PATH


def get_connection():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (sgg_cd, apt_name, exclusive_area, floor, deal_date, deal_amount, apt_seq, jibun)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_record_lookup
            ON apartment_trades (sgg_cd, apt_name, exclusive_area, deal_date, deal_amount)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_deal_date
            ON apartment_trades (deal_date)
        """)


def insert_trades(trades):
    if not trades:
        return 0
    with get_connection() as conn:
        before = conn.total_changes
        conn.executemany("""
            INSERT OR IGNORE INTO apartment_trades (
                sgg_cd, gu_name, umd_nm, apt_name, apt_seq, jibun, exclusive_area,
                floor, build_year, deal_year, deal_month, deal_day, deal_date, deal_amount, raw_xml
            ) VALUES (
                :sgg_cd, :gu_name, :umd_nm, :apt_name, :apt_seq, :jibun, :exclusive_area,
                :floor, :build_year, :deal_year, :deal_month, :deal_day, :deal_date, :deal_amount, :raw_xml
            )
        """, trades)
        return conn.total_changes - before


def get_summary():
    with get_connection() as conn:
        return conn.execute("""
            SELECT COUNT(*) AS total_trades, MIN(deal_date) AS first_deal_date, MAX(deal_date) AS last_deal_date
            FROM apartment_trades
        """).fetchone()
