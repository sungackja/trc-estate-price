import argparse

from config import SEOUL_GU_CODES
from records import find_newly_seen_record_highs, find_record_highs


def parse_args():
    parser = argparse.ArgumentParser(description="Show record-high apartment trades from SQLite.")
    parser.add_argument("--limit", type=int, default=30, help="Number of rows to show")
    parser.add_argument("--gu", choices=SEOUL_GU_CODES.keys(), help="Optional LAWD_CD filter")
    parser.add_argument("--from-date", help="Optional minimum deal date, for example 2024-01-01")
    parser.add_argument("--seen-date", help="Show only trades first seen on this date, for example 2026-04-23")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.seen_date:
        rows = find_newly_seen_record_highs(limit=args.limit, gu_code=args.gu, seen_date=args.seen_date)
    else:
        rows = find_record_highs(limit=args.limit, gu_code=args.gu, min_date=args.from_date)

    if not rows:
        print("No record-high trades found. Collect more data first.")
        return

    for row in rows:
        increase = row["deal_amount"] - row["previous_high"]
        print(
            f"{row['deal_date']} | {row['gu_name']} | {row['umd_nm']} | "
            f"{row['apt_name']} | {row['exclusive_area']} m2 | "
            f"{row['deal_amount']:,} > {row['previous_high']:,} "
            f"(+{increase:,})"
        )


if __name__ == "__main__":
    main()
