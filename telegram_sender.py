from pathlib import Path

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED, REQUEST_TIMEOUT_SECONDS
from report_image import REPORT_IMAGE_PATH, default_target_date


TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"
SITE_URL = "https://sungackja.github.io/trc-estate-price/"
TELEGRAM_PNG_PATH = Path("public") / "today-record-highs-telegram.png"


def telegram_is_configured():
    return bool(TELEGRAM_ENABLED and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def build_caption(report_date=None):
    report_date = report_date or default_target_date()
    return (
        f"\uc624\ub298 \uc0c8\ub85c \ud3ec\ucc29\ub41c \uc11c\uc6b8 \uc544\ud30c\ud2b8 \uc2e0\uace0\uac00\n"
        f"\ub9ac\ud3ec\ud2b8 \uae30\uc900\uc77c: {report_date}\n"
        f"{SITE_URL}"
    )


def make_telegram_png(image_path):
    image_path = Path(image_path)
    if image_path.suffix.lower() != ".svg":
        return image_path

    try:
        import cairosvg
    except ImportError as error:
        raise RuntimeError("cairosvg is required to convert the SVG report to PNG.") from error

    TELEGRAM_PNG_PATH.parent.mkdir(exist_ok=True)
    cairosvg.svg2png(
        url=str(image_path),
        write_to=str(TELEGRAM_PNG_PATH),
        output_width=900,
    )
    return TELEGRAM_PNG_PATH


def send_telegram_report(image_path=REPORT_IMAGE_PATH, report_date=None):
    if not telegram_is_configured():
        print("Telegram is not configured. Skipping message.")
        return False

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Report image not found: {image_path}")

    image_path = make_telegram_png(image_path)
    url = TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN, method="sendPhoto")
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": build_caption(report_date),
    }

    with image_path.open("rb") as file:
        response = requests.post(
            url,
            data=data,
            files={"photo": file},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    if response.status_code != 200:
        raise RuntimeError(f"Telegram send failed: HTTP {response.status_code} / {response.text[:300]}")

    print("Telegram PNG report sent.")
    return True


if __name__ == "__main__":
    send_telegram_report()
