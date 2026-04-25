from pathlib import Path

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED, REQUEST_TIMEOUT_SECONDS
from report_image import REPORT_IMAGE_PATH, default_target_date
from report_pages import create_latest_trade_report_pages, create_record_high_report_pages
from records import find_newly_seen_record_highs, find_newly_seen_trades


TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"
SITE_URL = "https://sungackja.github.io/trc-estate-price/"


def telegram_is_configured():
    return bool(TELEGRAM_ENABLED and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def build_caption(title, report_date=None, page_number=1, page_count=1):
    return (
        f"{title} ({page_number}/{page_count})\n"
        f"\ub9ac\ud3ec\ud2b8 \uae30\uc900\uc77c: {report_date}\n"
        f"{SITE_URL}"
    )


def send_photo(image_path, caption):
    url = TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN, method="sendPhoto")
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption,
    }

    with Path(image_path).open("rb") as file:
        response = requests.post(
            url,
            data=data,
            files={"photo": file},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    if response.status_code != 200:
        raise RuntimeError(f"Telegram send failed: HTTP {response.status_code} / {response.text[:300]}")


def send_telegram_report(image_path=REPORT_IMAGE_PATH, report_date=None):
    if not telegram_is_configured():
        print("Telegram is not configured. Skipping message.")
        return False

    report_date = report_date or default_target_date()
    record_rows = find_newly_seen_record_highs(limit=None, seen_date=report_date)
    latest_trade_rows = find_newly_seen_trades(limit=None, seen_date=report_date)

    batches = [
        (
            "\uc624\ub298 \uc0c8\ub85c \ud3ec\ucc29\ub41c \uc11c\uc6b8 \uc544\ud30c\ud2b8 \uc2e0\uace0\uac00",
            create_record_high_report_pages(record_rows, report_date),
        ),
        (
            "\uc624\ub298 \uc0c8\ub85c \ud3ec\ucc29\ub41c \uc11c\uc6b8 \uc544\ud30c\ud2b8 \uc2e4\uac70\ub798\uac00",
            create_latest_trade_report_pages(latest_trade_rows, report_date),
        ),
    ]

    sent_count = 0
    for title, paths in batches:
        page_count = len(paths)
        for index, path in enumerate(paths, start=1):
            send_photo(path, build_caption(title, report_date, index, page_count))
            sent_count += 1

    print(f"Telegram PNG reports sent: {sent_count}")
    return True


if __name__ == "__main__":
    send_telegram_report()
