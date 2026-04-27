from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw

from complexes import get_household_count_for_trade
from report_image import (
    INSTAGRAM_ID,
    INSTAGRAM_LOGO_PATH,
    LABEL_TODAY,
    NO_ROWS,
    TAGLINE,
    find_tiger_image_path,
    fit_text,
    format_price,
)
from report_png import draw_text


PAGE_WIDTH = 1080
PAGE_HEIGHT = 1440
MARGIN = 18
INNER_WIDTH = PAGE_WIDTH - MARGIN * 2
HEADER_Y = 18
HEADER_HEIGHT = 96
META_Y = HEADER_Y + HEADER_HEIGHT + 4
META_HEIGHT = 34
TABLE_Y = META_Y + META_HEIGHT + 8
TABLE_HEADER_HEIGHT = 40
ROW_HEIGHT = 29
ROWS_PER_PAGE = (PAGE_HEIGHT - TABLE_Y - TABLE_HEADER_HEIGHT - 24) // ROW_HEIGHT
OUTPUT_DIR = Path("public")


def draw_cell(draw, x, y, width, height, fill="white", outline="#d9d9d9", width_px=1):
    draw.rectangle((x, y, x + width, y + height), fill=fill, outline=outline, width=width_px)


def draw_tiger_badge(image, draw, today_text):
    tiger_image_path = find_tiger_image_path()
    circle_size = 70
    circle_cx = MARGIN + 50
    circle_cy = HEADER_Y + HEADER_HEIGHT / 2
    draw.ellipse(
        (
            circle_cx - circle_size / 2,
            circle_cy - circle_size / 2,
            circle_cx + circle_size / 2,
            circle_cy + circle_size / 2,
        ),
        fill="#ffc43d",
        outline="white",
        width=3,
    )

    if tiger_image_path:
        tiger = Image.open(tiger_image_path).convert("RGBA")
        target_size = (int(circle_size * 0.9), int(circle_size * 1.08))
        tiger.thumbnail(target_size, Image.Resampling.LANCZOS)
        image.alpha_composite(
            tiger,
            (
                int(circle_cx - tiger.width / 2),
                int(circle_cy - tiger.height / 2 - 1),
            ),
        )


def draw_instagram(image, draw):
    icon_size = 24
    x = MARGIN + 535
    y = META_Y + META_HEIGHT / 2
    icon_y = int(y - icon_size / 2)
    if INSTAGRAM_LOGO_PATH.exists():
        logo = Image.open(INSTAGRAM_LOGO_PATH).convert("RGBA")
        logo = logo.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        image.alpha_composite(logo, (x, icon_y))
    draw_text(
        draw,
        (x + icon_size + 8, y + 1),
        f"{INSTAGRAM_ID}   {TAGLINE}",
        size=17,
        fill="#333333",
        anchor="lm",
    )


def draw_header(image, draw, *, title, today_text, date_text, page_number, page_count):
    draw.rectangle((MARGIN, HEADER_Y, MARGIN + INNER_WIDTH, HEADER_Y + HEADER_HEIGHT), fill="#b40000")
    draw_tiger_badge(image, draw, today_text)
    header_title = f"{LABEL_TODAY} {title.replace(' 리스트', '')}"
    draw_text(draw, (PAGE_WIDTH / 2, HEADER_Y + HEADER_HEIGHT / 2 + 2), header_title, size=44, bold=True, fill="white")
    draw_text(
        draw,
        (MARGIN + INNER_WIDTH - 20, HEADER_Y + HEADER_HEIGHT / 2 + 3),
        today_text,
        size=36,
        bold=True,
        fill="#ffe082",
        anchor="rm",
    )

    draw_cell(draw, MARGIN, META_Y, INNER_WIDTH, META_HEIGHT, fill="#f5f8fb")
    draw_instagram(image, draw)
    draw_text(
        draw,
        (MARGIN + 430, META_Y + META_HEIGHT / 2 + 1),
        f"{page_number}/{page_count}",
        size=18,
        fill="#6b7280",
    )


def draw_table(draw, *, columns, rows, empty_text):
    x = MARGIN
    y = TABLE_Y
    cursor = x
    for title, width, _ in columns:
        draw_cell(draw, cursor, y, width, TABLE_HEADER_HEIGHT, fill="#d00000", outline="white")
        draw_text(draw, (cursor + width / 2, y + TABLE_HEADER_HEIGHT / 2 + 1), title, size=21, bold=True, fill="white")
        cursor += width

    y += TABLE_HEADER_HEIGHT
    if not rows:
        draw_cell(draw, x, y, INNER_WIDTH, ROW_HEIGHT)
        draw_text(draw, (x + INNER_WIDTH / 2, y + ROW_HEIGHT / 2 + 1), empty_text, size=22)
        return

    for row_values in rows:
        cursor = x
        for index, ((_, width, align), value) in enumerate(zip(columns, row_values)):
            draw_cell(draw, cursor, y, width, ROW_HEIGHT)
            anchor = "lm" if align == "left" else "mm"
            text_x = cursor + 8 if align == "left" else cursor + width / 2
            fill = "#d00000" if value.startswith("▲") else "#111111"
            bold = index in (2, 4)
            draw_text(draw, (text_x, y + ROW_HEIGHT / 2 + 1), value, size=18, bold=bold, fill=fill, anchor=anchor)
            cursor += width
        y += ROW_HEIGHT


def record_row_values(row):
    increase = row["deal_amount"] - row["previous_high"]
    household_count = get_household_count_for_trade(row)
    return [
        row["gu_name"],
        f"{row['exclusive_area']:.0f}",
        fit_text(f"{row['apt_name']} ({row['umd_nm']})", 34),
        format_price(row["previous_high"]),
        format_price(row["deal_amount"]),
        f"{household_count}" if household_count else "-",
        f"▲{format_price(increase)}",
    ]


def trade_row_values(row):
    household_count = get_household_count_for_trade(row)
    floor = row["floor"] if row["floor"] is not None else "-"
    return [
        row["gu_name"],
        f"{row['exclusive_area']:.0f}",
        fit_text(f"{row['apt_name']} ({row['umd_nm']})", 36),
        row["deal_date"],
        format_price(row["deal_amount"]),
        str(floor),
        f"{household_count}" if household_count else "-",
    ]


def create_paginated_report_pngs(
    *,
    rows,
    target_date,
    title,
    file_prefix,
    columns,
    row_formatter,
    empty_text,
):
    OUTPUT_DIR.mkdir(exist_ok=True)
    for old_path in OUTPUT_DIR.glob(f"{file_prefix}-*.png"):
        old_path.unlink()

    rows = list(rows)
    page_count = max(1, ceil(len(rows) / ROWS_PER_PAGE))
    created_paths = []
    today_month_day = target_date[5:7] + "월 " + target_date[8:10] + "일"
    date_text = target_date[:4] + "년 " + target_date[5:7] + "월 " + target_date[8:10] + "일"

    for page_index in range(page_count):
        start = page_index * ROWS_PER_PAGE
        page_rows = rows[start : start + ROWS_PER_PAGE]
        row_values = [row_formatter(row) for row in page_rows]

        image = Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), "white")
        draw = ImageDraw.Draw(image)
        draw_header(
            image,
            draw,
            title=title,
            today_text=today_month_day,
            date_text=date_text,
            page_number=page_index + 1,
            page_count=page_count,
        )
        draw_table(draw, columns=columns, rows=row_values, empty_text=empty_text)

        output_path = OUTPUT_DIR / f"{file_prefix}-{page_index + 1:03d}.png"
        image.convert("RGB").save(output_path, format="PNG", optimize=True)
        created_paths.append(output_path)

    return created_paths


def create_record_high_report_pages(rows, target_date):
    columns = [
        ("구분", 80, "center"),
        ("전용(m2)", 90, "center"),
        ("단지명", 474, "left"),
        ("전고가", 110, "center"),
        ("거래금액", 115, "center"),
        ("세대수", 80, "center"),
        ("증감", 95, "center"),
    ]
    return create_paginated_report_pngs(
        rows=rows,
        target_date=target_date,
        title="서울 아파트 신고가 리스트",
        file_prefix="telegram-record-highs",
        columns=columns,
        row_formatter=record_row_values,
        empty_text=f"{target_date} {NO_ROWS}",
    )


def create_latest_trade_report_pages(rows, target_date):
    columns = [
        ("구분", 80, "center"),
        ("전용(m2)", 88, "center"),
        ("단지명", 486, "left"),
        ("계약일", 110, "center"),
        ("거래금액", 116, "center"),
        ("층", 60, "center"),
        ("세대수", 104, "center"),
    ]
    return create_paginated_report_pngs(
        rows=rows,
        target_date=target_date,
        title="서울 아파트 실거래가 리스트",
        file_prefix="telegram-latest-trades",
        columns=columns,
        row_formatter=trade_row_values,
        empty_text=f"{target_date} 신규 공개 실거래가가 아직 없습니다.",
    )
