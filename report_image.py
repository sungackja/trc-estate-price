import base64
from datetime import datetime, timedelta, timezone
from html import escape
from mimetypes import guess_type
from pathlib import Path

from complexes import get_household_count_for_trade
from records import find_newly_seen_record_highs


OUTPUT_DIR = Path("public")
REPORT_IMAGE_PATH = OUTPUT_DIR / "today-record-highs.svg"
TIGER_IMAGE_PATHS = [
    OUTPUT_DIR / "tiger.png",
    OUTPUT_DIR / "tiger.jpg",
    OUTPUT_DIR / "tiger.jpeg",
    OUTPUT_DIR / "tiger.webp",
]

WIDTH = 900
MARGIN = 14
ROW_HEIGHT = 28
REPORT_INNER_WIDTH = WIDTH - MARGIN * 2

LABEL_TODAY = "\uc624\ub298\uc758"
REPORT_TITLE = "\uc11c\uc6b8 \uc544\ud30c\ud2b8 \uc2e0\uace0\uac00 \ub9ac\uc2a4\ud2b8"
TAGLINE = "\uc5b4\ub514\uc5d0\ub3c4 \uc5c6\ub294 \ubd80\ub3d9\uc0b0 \uc774\uc57c\uae30"
INSTAGRAM_ID = "@tiger.rich.company"
NO_ROWS = "\uc2e0\uaddc \uacf5\uac1c \uc2e0\uace0\uac00\uac00 \uc544\uc9c1 \uc5c6\uc2b5\ub2c8\ub2e4."


def default_target_date():
    today_kst = datetime.now(timezone(timedelta(hours=9))).date()
    return (today_kst - timedelta(days=1)).isoformat()


def format_price(value):
    return f"{value / 10000:g}"


def fit_text(text, max_chars):
    text = str(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 2] + ".."


def build_report_rows(target_date=None, limit=38):
    target_date = target_date or default_target_date()
    rows = find_newly_seen_record_highs(limit=limit, seen_date=target_date)
    return target_date, rows


def svg_text(x, y, value, size=16, weight=400, fill="#111111", anchor="middle"):
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" dominant-baseline="middle">'
        f"{escape(str(value))}</text>"
    )


def svg_rect(x, y, width, height, fill="white", stroke="#d9d9d9"):
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
    )


def find_tiger_image_path():
    for path in TIGER_IMAGE_PATHS:
        if path.exists():
            return path
    return None


def svg_tiger_logo(today_text, x=30, y=20, height=58):
    tiger_image_path = find_tiger_image_path()
    if tiger_image_path is None:
        return [
            '<polygon points="42,36 172,20 184,58 54,74" fill="#001a9b"/>',
            svg_text(112, 54, LABEL_TODAY, size=25, weight=700, fill="white"),
        ]

    mime_type = guess_type(tiger_image_path.name)[0] or "image/png"
    encoded = base64.b64encode(tiger_image_path.read_bytes()).decode("ascii")
    circle_size = height - 4
    circle_cx = x + circle_size / 2
    circle_cy = y + height / 2
    image_width = circle_size * 0.92
    image_height = circle_size * 1.12
    image_x = circle_cx - image_width / 2
    image_y = circle_cy - image_height / 2 - 1

    return [
        f'<circle cx="{circle_cx}" cy="{circle_cy}" r="{circle_size / 2}" fill="#ffc43d"/>',
        f'<circle cx="{circle_cx}" cy="{circle_cy}" r="{circle_size / 2}" fill="none" stroke="white" stroke-width="2"/>',
        f'<image x="{image_x}" y="{image_y}" width="{image_width}" height="{image_height}" '
        f'preserveAspectRatio="xMidYMid meet" '
        f'href="data:{mime_type};base64,{encoded}"/>',
        svg_text(x + 118, y + height / 2 + 1, LABEL_TODAY, size=36, weight=700, fill="white"),
        svg_text(x + 238, y + height / 2 + 2, today_text, size=24, weight=700, fill="#ffe082"),
    ]


def svg_instagram_id(x=500, y=97):
    icon_size = 15
    icon_y = y - icon_size / 2
    text_x = x + icon_size + 6
    return [
        (
            f'<rect x="{x}" y="{icon_y}" width="{icon_size}" height="{icon_size}" rx="4" '
            f'fill="#e4405f" stroke="#e4405f" stroke-width="1"/>'
        ),
        (
            f'<circle cx="{x + icon_size / 2}" cy="{y}" r="3.5" '
            f'fill="none" stroke="white" stroke-width="1.5"/>'
        ),
        f'<circle cx="{x + icon_size - 3.8}" cy="{icon_y + 3.8}" r="1.3" fill="white"/>',
        svg_text(text_x, y + 0.5, INSTAGRAM_ID, size=13, fill="#333333", anchor="start"),
    ]


def create_report_image(target_date=None, output_path=REPORT_IMAGE_PATH, limit=38):
    target_date, rows = build_report_rows(target_date, limit=limit)
    today = datetime.now(timezone(timedelta(hours=9))).date()
    today_text = f"{today.year}\ub144 {today.month:02d}\uc6d4 {today.day:02d}\uc77c"
    today_short = f"{today.month:02d}\uc6d4 {today.day:02d}\uc77c"

    fixed_column_width = 72 + 78 + 96 + 96 + 70 + 82
    apt_column_width = REPORT_INNER_WIDTH - fixed_column_width
    columns = [
        ("\uad6c\ubd84", 72, "center"),
        ("\uc804\uc6a9(m2)", 78, "center"),
        ("\ub2e8\uc9c0\uba85", apt_column_width, "left"),
        ("\uc804\uace0\uac00", 96, "center"),
        ("\uac70\ub798\uae08\uc561", 96, "center"),
        ("\uc138\ub300\uc218", 70, "center"),
        ("\uc99d\uac10", 82, "center"),
    ]
    table_width = sum(col[1] for col in columns)
    row_count = max(len(rows), 1)
    height = 128 + row_count * ROW_HEIGHT + 22

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">',
        "<style>",
        "text { font-family: 'Malgun Gothic', 'Noto Sans CJK KR', Arial, sans-serif; }",
        "</style>",
        svg_rect(0, 0, WIDTH, height, fill="white", stroke="white"),
        svg_rect(MARGIN, 18, REPORT_INNER_WIDTH, 64, fill="#b40000", stroke="#b40000"),
        *svg_tiger_logo(today_short),
        svg_text(602, 53, REPORT_TITLE, size=38, weight=700, fill="white"),
        svg_rect(MARGIN, 84, REPORT_INNER_WIDTH, 24, fill="#f5f8fb", stroke="#d9d9d9"),
        svg_text(MARGIN + 14, 97, today_text, size=15, anchor="start"),
        *svg_instagram_id(),
        svg_text(WIDTH - 36, 97, TAGLINE, size=15, anchor="end"),
    ]

    x = MARGIN
    y = 112
    parts.append(svg_rect(x, y, table_width, ROW_HEIGHT, fill="#d00000", stroke="#d00000"))
    cursor = x
    for title, width, _ in columns:
        parts.append(svg_rect(cursor, y, width, ROW_HEIGHT, fill="#d00000", stroke="white"))
        parts.append(svg_text(cursor + width / 2, y + ROW_HEIGHT / 2 + 1, title, size=16, weight=700, fill="white"))
        cursor += width

    y += ROW_HEIGHT
    if not rows:
        parts.append(svg_rect(x, y, table_width, ROW_HEIGHT))
        parts.append(svg_text(x + table_width / 2, y + ROW_HEIGHT / 2 + 1, f"{target_date} {NO_ROWS}"))
    else:
        for row in rows:
            increase = row["deal_amount"] - row["previous_high"]
            household_count = get_household_count_for_trade(row)
            values = [
                row["gu_name"],
                f"{row['exclusive_area']:.0f}",
                fit_text(f"{row['apt_name']} ({row['umd_nm']})", 32),
                format_price(row["previous_high"]),
                format_price(row["deal_amount"]),
                f"{household_count}" if household_count else "-",
                f"\u25b2{format_price(increase)}",
            ]
            cursor = x
            for index, ((_, width, align), value) in enumerate(zip(columns, values)):
                parts.append(svg_rect(cursor, y, width, ROW_HEIGHT))
                anchor = "start" if align == "left" else "middle"
                text_x = cursor + 8 if align == "left" else cursor + width / 2
                fill = "#d00000" if index == 6 else "#111111"
                weight = 700 if index in (2, 4) else 400
                parts.append(svg_text(text_x, y + ROW_HEIGHT / 2 + 1, value, size=16, weight=weight, fill=fill, anchor=anchor))
                cursor += width
            y += ROW_HEIGHT

    parts.append("</svg>")
    output_path = Path(output_path)
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    path = create_report_image()
    print(f"Created {path}")
