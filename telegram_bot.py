import time
from datetime import date

import requests

from config import (
    REQUEST_TIMEOUT_SECONDS,
    SEOUL_GU_CODES,
    TELEGRAM_ALLOWED_CHAT_IDS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
from database import get_complex_summary, get_summary, init_db
from records import (
    find_newly_seen_record_highs,
    find_newly_seen_trades,
    find_record_highs,
    latest_newly_seen_record_high_date,
    latest_newly_seen_trade_date,
)
from report_image import default_target_date
from report_pages import (
    create_latest_trade_cover_page,
    create_latest_trade_report_pages,
    create_record_high_cover_page,
    create_record_high_report_pages,
)
from telegram_sender import SITE_URL, build_caption, send_message, send_photo


TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"
DEFAULT_LIMIT = 10
MAX_TEXT_LIMIT = 30
LONG_POLL_TIMEOUT_SECONDS = 30

HELP_TEXT = """타이거 실거래가 봇

/today [YYYY-MM-DD]
신규 신고가와 신규 실거래가 이미지 리포트를 보냅니다.

/records [YYYY-MM-DD] [개수]
신규 신고가를 텍스트로 봅니다.

/latest [YYYY-MM-DD] [개수]
신규 공개 실거래가를 텍스트로 봅니다.

/highs [구명|구코드] [개수]
현재 신고가 목록을 봅니다. 예: /highs 강남구 10

/summary
DB 수집 현황을 봅니다.

/gu
서울 구 코드를 봅니다.
"""


def telegram_api(method, **params):
    url = TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN, method=method)
    params = {key: value for key, value in params.items() if value is not None}
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS + LONG_POLL_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise RuntimeError(f"Telegram API failed: HTTP {response.status_code} / {response.text[:300]}")

    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API failed: {payload}")
    return payload["result"]


def allowed_chat_ids():
    raw_value = TELEGRAM_ALLOWED_CHAT_IDS or TELEGRAM_CHAT_ID or ""
    return {value.strip() for value in raw_value.split(",") if value.strip()}


def is_allowed_chat(chat_id):
    allowed_ids = allowed_chat_ids()
    return not allowed_ids or str(chat_id) in allowed_ids


def parse_date(value):
    if not value:
        return default_target_date()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError("날짜는 YYYY-MM-DD 형식으로 입력해주세요.")


def parse_limit(value, default=DEFAULT_LIMIT):
    if not value:
        return default
    try:
        limit = int(value)
    except ValueError:
        raise ValueError("개수는 숫자로 입력해주세요.")
    return max(1, min(limit, MAX_TEXT_LIMIT))


def parse_date_and_limit(args):
    if args and "-" in args[0]:
        return parse_date(args[0]), parse_limit(args[1] if len(args) > 1 else None)
    return default_target_date(), parse_limit(args[0] if args else None)


def split_command(text):
    parts = (text or "").strip().split()
    if not parts:
        return "", []
    command = parts[0].split("@", 1)[0].lower()
    return command, parts[1:]


def resolve_gu_code(value):
    if not value:
        return None
    if value in SEOUL_GU_CODES:
        return value
    for code, name in SEOUL_GU_CODES.items():
        if value == name or value == name.removesuffix("구"):
            return code
    raise ValueError("구 이름이나 구 코드를 확인해주세요. 예: 강남구 또는 11680")


def format_price(value):
    if value is None:
        return "-"
    if value >= 10000:
        return f"{value / 10000:g}억"
    return f"{value:,}만원"


def format_trade_row(row, include_previous=False):
    parts = [
        row["deal_date"],
        row["gu_name"],
        row["umd_nm"] or "",
        f"{row['apt_name']} {row['exclusive_area']:.0f}m2",
        format_price(row["deal_amount"]),
    ]
    if row["floor"] is not None:
        parts.append(f"{row['floor']}층")
    if include_previous and row["previous_high"] is not None:
        increase = row["deal_amount"] - row["previous_high"]
        parts.append(f"전고 {format_price(row['previous_high'])}")
        parts.append(f"+{format_price(increase)}")
    return " | ".join(parts)


def send_long_message(chat_id, text):
    chunk = ""
    for line in text.splitlines():
        candidate = f"{chunk}\n{line}" if chunk else line
        if len(candidate) > 3500:
            send_message(chunk, chat_id=chat_id)
            chunk = line
        else:
            chunk = candidate
    if chunk:
        send_message(chunk, chat_id=chat_id)


def handle_today(chat_id, args):
    report_date = parse_date(args[0] if args else None)
    record_rows = find_newly_seen_record_highs(limit=None, seen_date=report_date)
    latest_trade_rows = find_newly_seen_trades(limit=None, seen_date=report_date)
    sent_count = 0

    if record_rows:
        cover_path = create_record_high_cover_page(report_date)
        title = "오늘 새로 포착된 서울 아파트 신고가"
        send_photo(cover_path, build_caption(title, report_date, 1, 1), chat_id=chat_id)
        sent_count += 1
        paths = create_record_high_report_pages(record_rows, report_date)
        page_count = len(paths)
        for index, path in enumerate(paths, start=1):
            send_photo(path, build_caption(title, report_date, index, page_count), chat_id=chat_id)
            sent_count += 1
    else:
        latest_date = latest_newly_seen_record_high_date(max_seen_date=report_date)
        extra = f"\n최근 신고가 표시일: {latest_date}" if latest_date else ""
        send_message(f"{report_date} 신규 신고가가 없습니다.{extra}", chat_id=chat_id)

    if latest_trade_rows:
        cover_path = create_latest_trade_cover_page(report_date)
        title = "오늘 새로 포착된 서울 아파트 실거래가"
        send_photo(cover_path, build_caption(title, report_date, 1, 1), chat_id=chat_id)
        sent_count += 1
        paths = create_latest_trade_report_pages(latest_trade_rows, report_date)
        page_count = len(paths)
        for index, path in enumerate(paths, start=1):
            send_photo(path, build_caption(title, report_date, index, page_count), chat_id=chat_id)
            sent_count += 1
    else:
        latest_date = latest_newly_seen_trade_date(max_seen_date=report_date)
        extra = f"\n최근 실거래가 표시일: {latest_date}" if latest_date else ""
        send_message(f"{report_date} 신규 실거래가가 없습니다.{extra}", chat_id=chat_id)

    if sent_count:
        send_message(f"{report_date} 이미지 리포트 {sent_count}장을 보냈습니다.\n{SITE_URL}", chat_id=chat_id)


def handle_records(chat_id, args):
    report_date, limit = parse_date_and_limit(args)
    rows = find_newly_seen_record_highs(limit=limit, seen_date=report_date)
    if not rows:
        send_message(f"{report_date} 신규 신고가가 없습니다.", chat_id=chat_id)
        return

    lines = [f"{report_date} 신규 신고가 {len(rows)}건"]
    lines.extend(f"{index}. {format_trade_row(row, include_previous=True)}" for index, row in enumerate(rows, start=1))
    send_long_message(chat_id, "\n".join(lines))


def handle_latest(chat_id, args):
    report_date, limit = parse_date_and_limit(args)
    rows = find_newly_seen_trades(limit=limit, seen_date=report_date)
    if not rows:
        send_message(f"{report_date} 신규 실거래가가 없습니다.", chat_id=chat_id)
        return

    lines = [f"{report_date} 신규 실거래가 {len(rows)}건"]
    lines.extend(f"{index}. {format_trade_row(row)}" for index, row in enumerate(rows, start=1))
    send_long_message(chat_id, "\n".join(lines))


def handle_highs(chat_id, args):
    gu_code = None
    limit_arg_index = 0
    if args and (args[0] in SEOUL_GU_CODES or not args[0].isdigit()):
        gu_code = resolve_gu_code(args[0])
        limit_arg_index = 1
    limit = parse_limit(args[limit_arg_index] if len(args) > limit_arg_index else None)
    rows = find_record_highs(limit=limit, gu_code=gu_code)
    if not rows:
        send_message("신고가 목록이 없습니다.", chat_id=chat_id)
        return

    title = f"{SEOUL_GU_CODES[gu_code]} 신고가 {len(rows)}건" if gu_code else f"서울 신고가 {len(rows)}건"
    lines = [title]
    lines.extend(f"{index}. {format_trade_row(row, include_previous=True)}" for index, row in enumerate(rows, start=1))
    send_long_message(chat_id, "\n".join(lines))


def handle_summary(chat_id):
    init_db()
    summary = get_summary()
    complex_summary = get_complex_summary()
    send_message(
        "\n".join(
            [
                "타이거 실거래가 DB 요약",
                f"거래 수: {(summary['total_trades'] or 0):,}건",
                f"거래일 범위: {summary['first_deal_date'] or '-'} ~ {summary['last_deal_date'] or '-'}",
                f"단지 수: {(complex_summary['total_complexes'] or 0):,}개",
                f"세대수 확보 단지: {(complex_summary['complexes_with_households'] or 0):,}개",
                f"단지 최신 업데이트: {complex_summary['latest_complex_update'] or '-'}",
                SITE_URL,
            ]
        ),
        chat_id=chat_id,
    )


def handle_gu(chat_id):
    lines = ["서울 구 코드"]
    lines.extend(f"{code} {name}" for code, name in SEOUL_GU_CODES.items())
    send_message("\n".join(lines), chat_id=chat_id)


def handle_message(message):
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = message.get("text") or ""
    if chat_id is None:
        return
    if not is_allowed_chat(chat_id):
        send_message("허용되지 않은 채팅방입니다.", chat_id=chat_id)
        return

    command, args = split_command(text)
    try:
        if command in ("/start", "/help", "도움말"):
            send_message(HELP_TEXT, chat_id=chat_id)
        elif command in ("/today", "오늘"):
            handle_today(chat_id, args)
        elif command in ("/records", "/record", "신고가"):
            handle_records(chat_id, args)
        elif command in ("/latest", "/trades", "실거래"):
            handle_latest(chat_id, args)
        elif command in ("/highs", "/high", "랭킹"):
            handle_highs(chat_id, args)
        elif command in ("/summary", "요약"):
            handle_summary(chat_id)
        elif command in ("/gu", "구"):
            handle_gu(chat_id)
        else:
            send_message("알 수 없는 명령입니다.\n\n" + HELP_TEXT, chat_id=chat_id)
    except Exception as exc:
        send_message(f"처리 중 오류가 났습니다: {exc}", chat_id=chat_id)


def run_bot():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")

    print("Tiger Telegram bot started.")
    offset = None
    while True:
        try:
            updates = telegram_api(
                "getUpdates",
                timeout=LONG_POLL_TIMEOUT_SECONDS,
                offset=offset,
                allowed_updates='["message"]',
            )
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message")
                if message:
                    handle_message(message)
        except KeyboardInterrupt:
            print("Tiger Telegram bot stopped.")
            return
        except Exception as exc:
            print(f"Bot loop error: {exc}")
            time.sleep(5)


if __name__ == "__main__":
    run_bot()
