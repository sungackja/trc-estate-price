import argparse
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

import requests

from config import (
    MOLIT_API_KEY,
    MOLIT_API_URL,
    REQUEST_TIMEOUT_SECONDS,
    SEOUL_GU_CODES,
)
from database import init_db, insert_trades


def clean_text(value, default=""):
    if value is None:
        return default
    return value.strip()


def to_int(value):
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    return int(text)


def to_float(value):
    text = clean_text(value)
    if not text:
        return None
    return float(text)


def month_range(start_ym, end_ym):
    year = int(start_ym[:4])
    month = int(start_ym[4:])
    end_year = int(end_ym[:4])
    end_month = int(end_ym[4:])

    while (year, month) <= (end_year, end_month):
        yield f"{year}{month:02d}"
        month += 1
        if month == 13:
            year += 1
            month = 1


def default_start_ym(years=8):
    today = date.today()
    return f"{today.year - years}{today.month:02d}"


def default_end_ym():
    today = date.today()
    return f"{today.year}{today.month:02d}"


def default_report_date():
    today_kst = datetime.now(timezone(timedelta(hours=9))).date()
    return (today_kst - timedelta(days=1)).isoformat()


def parse_trade(item, sgg_cd, gu_name):
    deal_year = to_int(item.findtext("dealYear"))
    deal_month = to_int(item.findtext("dealMonth"))
    deal_day = to_int(item.findtext("dealDay"))
    deal_amount = to_int(item.findtext("dealAmount"))
    apt_name = clean_text(item.findtext("aptNm"))
    exclusive_area = to_float(item.findtext("excluUseAr"))

    if not all([deal_year, deal_month, deal_day, deal_amount, apt_name, exclusive_area]):
        return None

    return {
        "sgg_cd": sgg_cd,
        "gu_name": gu_name,
        "umd_nm": clean_text(item.findtext("umdNm")),
        "apt_name": apt_name,
        "apt_seq": clean_text(item.findtext("aptSeq")),
        "jibun": clean_text(item.findtext("jibun")),
        "exclusive_area": exclusive_area,
        "floor": to_int(item.findtext("floor")),
        "build_year": to_int(item.findtext("buildYear")),
        "deal_year": deal_year,
        "deal_month": deal_month,
        "deal_day": deal_day,
        "deal_date": f"{deal_year:04d}-{deal_month:02d}-{deal_day:02d}",
        "deal_amount": deal_amount,
        "raw_xml": ET.tostring(item, encoding="unicode"),
    }


def fetch_month(sgg_cd, deal_ym, page_no=1, num_rows=1000):
    if not MOLIT_API_KEY:
        raise RuntimeError("MOLIT_API_KEY is missing. Add it to your .env file.")

    params = {
        "serviceKey": MOLIT_API_KEY,
        "LAWD_CD": sgg_cd,
        "DEAL_YMD": deal_ym,
        "pageNo": page_no,
        "numOfRows": num_rows,
    }
    response = requests.get(MOLIT_API_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    result_code = root.findtext(".//resultCode")
    result_msg = root.findtext(".//resultMsg")
    if result_code and result_code not in ("00", "000"):
        raise RuntimeError(f"API error: {result_code} / {result_msg}")

    return root


def read_total_count(root):
    total_count = root.findtext(".//totalCount")
    return to_int(total_count) or 0


def fetch_all_month_items(sgg_cd, deal_ym, num_rows=1000):
    first_root = fetch_month(sgg_cd, deal_ym, page_no=1, num_rows=num_rows)
    items = list(first_root.findall(".//item"))
    total_count = read_total_count(first_root)

    total_pages = (total_count + num_rows - 1) // num_rows
    for page_no in range(2, total_pages + 1):
        root = fetch_month(sgg_cd, deal_ym, page_no=page_no, num_rows=num_rows)
        items.extend(root.findall(".//item"))

    return items


def collect_month(sgg_cd, gu_name, deal_ym, is_backfill=True, first_seen_date=None):
    items = fetch_all_month_items(sgg_cd, deal_ym)
    trades = []
    for item in items:
        trade = parse_trade(item, sgg_cd, gu_name)
        if trade:
            trades.append(trade)
    inserted = insert_trades(trades, is_backfill=is_backfill, first_seen_date=first_seen_date)
    return len(trades), inserted


def collect_all(
    start_ym,
    end_ym,
    gu_codes=None,
    sleep_seconds=0.2,
    max_failures=10,
    mode="backfill",
    first_seen_date=None,
):
    init_db()
    selected_codes = gu_codes or SEOUL_GU_CODES.keys()
    is_backfill = mode == "backfill"
    if not is_backfill and first_seen_date is None:
        first_seen_date = default_report_date()

    total_seen = 0
    total_inserted = 0
    failures = 0
    for deal_ym in month_range(start_ym, end_ym):
        for sgg_cd in selected_codes:
            gu_name = SEOUL_GU_CODES[sgg_cd]
            print(f"Collecting {deal_ym} {gu_name}({sgg_cd})...")
            try:
                seen, inserted = collect_month(
                    sgg_cd,
                    gu_name,
                    deal_ym,
                    is_backfill=is_backfill,
                    first_seen_date=first_seen_date,
                )
            except Exception as error:
                failures += 1
                print(f"  failed: {type(error).__name__}")
                if failures >= max_failures:
                    print(f"Stopped after {failures} failures. Check API key, network, or service approval.")
                    print(f"Partial result. API rows: {total_seen}, new DB rows: {total_inserted}")
                    return
                continue

            failures = 0
            total_seen += seen
            total_inserted += inserted
            print(f"  rows: {seen}, new: {inserted}")
            time.sleep(sleep_seconds)

    print(f"Done. API rows: {total_seen}, new DB rows: {total_inserted}")


def parse_args():
    parser = argparse.ArgumentParser(description="Collect Seoul apartment trade data into SQLite.")
    parser.add_argument("--start", default=default_start_ym(), help="Start month, for example 202104")
    parser.add_argument("--end", default=default_end_ym(), help="End month, for example 202604")
    parser.add_argument("--gu", nargs="*", choices=SEOUL_GU_CODES.keys(), help="Optional LAWD_CD list")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds to wait between API calls")
    parser.add_argument("--max-failures", type=int, default=10, help="Stop after this many consecutive failures")
    parser.add_argument(
        "--mode",
        choices=("backfill", "daily"),
        default="backfill",
        help="backfill marks inserted rows as baseline; daily marks new rows as first seen today",
    )
    parser.add_argument("--first-seen-date", help="Override first_seen_date for daily mode, for example 2026-04-23")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    collect_all(
        args.start,
        args.end,
        args.gu,
        args.sleep,
        args.max_failures,
        args.mode,
        args.first_seen_date,
    )
