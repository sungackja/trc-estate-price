import argparse
import shutil
from datetime import datetime

from config import DB_PATH
from database import get_connection, init_db


def file_size_mb(path):
    if not path.exists():
        return 0
    return path.stat().st_size / 1024 / 1024


def compact_database(skip_backup=False):
    init_db()
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    backup_path = None
    if not skip_backup:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = DB_PATH.with_name(f"{DB_PATH.stem}.backup-{timestamp}{DB_PATH.suffix}")
        shutil.copy2(DB_PATH, backup_path)

    before_mb = file_size_mb(DB_PATH)
    with get_connection() as conn:
        conn.execute("UPDATE apartment_trades SET raw_xml = NULL WHERE raw_xml IS NOT NULL")
        conn.execute("UPDATE apartment_complexes SET raw_xml = NULL WHERE raw_xml IS NOT NULL")

    with get_connection() as conn:
        conn.execute("VACUUM")

    after_mb = file_size_mb(DB_PATH)

    print(f"Before: {before_mb:.1f} MB")
    print(f"After: {after_mb:.1f} MB")
    if backup_path:
        print(f"Backup: {backup_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Shrink the local SQLite DB before deployment.")
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Do not create a local backup before removing raw XML columns.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    compact_database(skip_backup=args.skip_backup)
