import argparse
from datetime import datetime, timedelta, timezone

from build_static_site import build_site
from collector import collect_all


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
    return parser.parse_args()


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

    image_path, html_path = build_site(target_date=args.report_date)
    print(f"Built image: {image_path}")
    print(f"Built site: {html_path}")
    print("Daily update finished")


if __name__ == "__main__":
    main()
