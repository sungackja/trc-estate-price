import argparse
from datetime import datetime, timedelta, timezone

from build_static_site import build_site
from collector import collect_all
from complexes import get_household_count, get_household_count_for_trade
from records import find_newly_seen_record_highs, find_newly_seen_trades
from telegram_sender import send_telegram_report, telegram_is_configured


def current_and_previous_months(today):
    previous_year = today.year
    previous_month = today.month - 1
    if previous_month == 0:
        previous_year -= 1
        previous_month = 12

    return f"{previous_year}{previous_month:02d}", f"{today.year}{today.month:02d}"


def default_report_date():
    today_kst = datetime.now(timezone(timedelta(hours=9))).date()
    return (today_kst - timedelta(days=1)).isoformat()


def parse_args():
    parser = argparse.ArgumentParser(description="Run daily refresh and rebuild the report site.")
    parser.add_argument("--report-date", default=default_report_date(), help="First-seen date to report")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds to wait between API calls")
    parser.add_argument("--max-failures", type=int, default=10, help="Stop after this many consecutive failures")
    parser.add_argument("--send-telegram", action="store_true", help="Send the generated report to Telegram")
    return parser.parse_args()


def warm_household_count_cache(report_date):
    rows = list(find_newly_seen_record_highs(limit=None, seen_date=report_date))
    rows.extend(find_newly_seen_trades(limit=None, seen_date=report_date))

    unique_rows = {}
    for row in rows:
        unique_rows[row["id"]] = row

    missing_before = 0
    missing_after = 0
    for row in unique_rows.values():
        if get_household_count(row["gu_name"], row["umd_nm"], row["apt_name"], row["jibun"]):
            continue
        missing_before += 1
        if not get_household_count_for_trade(row):
            missing_after += 1

    resolved = missing_before - missing_after
    print(
        "Household count check: "
        f"rows={len(unique_rows)}, resolved={resolved}, remaining_missing={missing_after}"
    )


def main():
    args = parse_args()
    today_kst = datetime.now(timezone(timedelta(hours=9))).date()
    start_ym, end_ym = current_and_previous_months(today_kst)

    print("Daily update started")
    print(f"Report date: {args.report_date}")
    print(f"Refreshing months: {start_ym} to {end_ym}")

    collect_all(
        start_ym=start_ym,
        end_ym=end_ym,
        sleep_seconds=args.sleep,
        max_failures=args.max_failures,
        mode="daily",
        first_seen_date=args.report_date,
    )

    warm_household_count_cache(args.report_date)

    image_path, html_path = build_site(target_date=args.report_date)
    print(f"Built image: {image_path}")
    print(f"Built site: {html_path}")

    if args.send_telegram or telegram_is_configured():
        send_telegram_report(image_path=image_path, report_date=args.report_date)

    print("Daily update finished")


if __name__ == "__main__":
    main()
