from pathlib import Path

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED, REQUEST_TIMEOUT_SECONDS
from report_image import REPORT_IMAGE_PATH, default_target_date


TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"
SITE_URL = "https://sungackja.github.io/trc-estate-price/"


def telegram_is_configured():
    return bool(TELEGRAM_ENABLED and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def build_caption(report_date=None):
    report_date = report_date or default_target_date()
    return (
        f"오늘 새로 포착된 서울 아파트 신고가\n"
        f"리포트 기준일: {report_date}\n"
        f"{SITE_URL}"
    )


def send_telegram_report(image_path=REPORT_IMAGE_PATH, report_date=None):
    if not telegram_is_configured():
        print("Telegram is not configured. Skipping message.")
        return False

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Report image not found: {image_path}")

    method = "sendPhoto"
    file_field = "photo"
    if image_path.suffix.lower() == ".svg":
        method = "sendDocument"
        file_field = "document"

    url = TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN, method=method)
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": build_caption(report_date),
    }

    with image_path.open("rb") as file:
        response = requests.post(
            url,
            data=data,
            files={file_field: file},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    if response.status_code != 200:
        raise RuntimeError(f"Telegram send failed: HTTP {response.status_code} / {response.text[:300]}")

    print("Telegram report sent.")
    return True


if __name__ == "__main__":
    send_telegram_report()
