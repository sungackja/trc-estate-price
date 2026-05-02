from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from complexes import get_household_count_for_trade
from report_image import (
    INSTAGRAM_ID,
    INSTAGRAM_LOGO_PATH,
    LABEL_TODAY,
    NO_ROWS,
    TAGLINE,
    YOUTUBE_LABEL,
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
HEADER_HEIGHT = 116
META_Y = HEADER_Y + HEADER_HEIGHT + 4
META_HEIGHT = 34
TABLE_Y = META_Y + META_HEIGHT + 8
TABLE_HEADER_HEIGHT = 40
ROW_HEIGHT = 29
ROWS_PER_PAGE = (PAGE_HEIGHT - TABLE_Y - TABLE_HEADER_HEIGHT - 24) // ROW_HEIGHT
OUTPUT_DIR = Path("public")
RECORD_HIGH_COVER_PATH = OUTPUT_DIR / "telegram-record-highs-cover.png"
LATEST_TRADE_COVER_PATH = OUTPUT_DIR / "telegram-latest-trades-cover.png"
COVER_FONT_CANDIDATES = [
    Path(__file__).resolve().parent / "static" / "fonts" / "Pretendard-Black.otf",
    Path(__file__).resolve().parent / "static" / "fonts" / "Pretendard-Black.ttf",
    Path(r"C:\Windows\Fonts\Pretendard-Black.otf"),
    Path(r"C:\Windows\Fonts\Pretendard-Black.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"),
]


class ReportRow(list):
    def __init__(self, values, is_record_high=False):
        super().__init__(values)
        self.is_record_high = is_record_high


def draw_cell(draw, x, y, width, height, fill="white", outline="#d9d9d9", width_px=1):
    draw.rectangle((x, y, x + width, y + height), fill=fill, outline=outline, width=width_px)


def cover_font(size):
    for path in COVER_FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def draw_shadow_text(draw, xy, text, *, size, fill, bold=True, anchor="mm", shadow="#d8d8d8", offset=(5, 5)):
    shadow_xy = (xy[0] + offset[0], xy[1] + offset[1])
    text_font = cover_font(size)
    draw.text(shadow_xy, str(text), font=text_font, fill=shadow, anchor=anchor)
    draw.text(xy, str(text), font=text_font, fill=fill, anchor=anchor)


def cover_date_text(target_date):
    month = int(target_date[5:7])
    day = int(target_date[8:10])
    return f"{month}/{day}"


def remove_near_white_background(image):
    image = image.convert("RGBA")
    pixels = image.load()
    width, height = image.size
    queue = []
    seen = set()

    def is_background(x, y):
        red, green, blue, _ = pixels[x, y]
        return red > 218 and green > 218 and blue > 218 and max(red, green, blue) - min(red, green, blue) < 28

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.pop()
        if (x, y) in seen or not (0 <= x < width and 0 <= y < height):
            continue
        seen.add((x, y))
        if not is_background(x, y):
            continue

        red, green, blue, _ = pixels[x, y]
        pixels[x, y] = (red, green, blue, 0)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return image


def create_cover_page(target_date, report_type, output_path):
    OUTPUT_DIR.mkdir(exist_ok=True)

    image = Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(image)

    blue = "#0034a5"
    deep_blue = "#002582"
    yellow = "#f7cf28"
    orange = "#ff5a00"
    red = "#e80000"

    header_height = 320
    draw.rectangle((0, 0, PAGE_WIDTH, header_height), fill=blue)
    for x in range(PAGE_WIDTH):
        shade = int(22 * (x / PAGE_WIDTH))
        draw.line((x, 0, x, header_height), fill=(0, max(30, 47 - shade), 153 - shade, 255))

    tiger_path = find_tiger_image_path()
    if tiger_path:
        tiger = Image.open(tiger_path).convert("RGBA")
        tiger = ImageOps.fit(tiger, (310, 310), method=Image.Resampling.LANCZOS, centering=(0.48, 0.38))
        tiger = remove_near_white_background(tiger)
        image.alpha_composite(tiger, (24, 12))

    draw.polygon(((1004, 0), (PAGE_WIDTH, 0), (PAGE_WIDTH, header_height), (918, header_height)), fill="white")
    draw.polygon(((1048, 0), (PAGE_WIDTH, 0), (986, header_height), (950, header_height)), fill=orange)

    draw_shadow_text(draw, (552, 160), "타이거 TV", size=82, fill="white", shadow="#001f66", offset=(4, 4))
    draw_shadow_text(draw, (845, 160), "리포트", size=82, fill=yellow, shadow="#001f66", offset=(4, 4))
    draw.line((0, header_height, PAGE_WIDTH, header_height), fill="#eeeeee", width=2)

    draw_shadow_text(
        draw,
        (PAGE_WIDTH / 2, 540),
        cover_date_text(target_date),
        size=228,
        fill=deep_blue,
        shadow="#dddddd",
        offset=(6, 6),
    )
    draw_shadow_text(draw, (PAGE_WIDTH / 2, 735), "최신", size=188, fill=deep_blue, shadow="#dddddd", offset=(6, 6))
    draw_shadow_text(
        draw,
        (PAGE_WIDTH / 2, 970),
        "서울 아파트",
        size=182,
        fill=deep_blue,
        shadow="#dddddd",
        offset=(6, 6),
    )
    draw_shadow_text(draw, (PAGE_WIDTH / 2, 1240), report_type, size=220, fill=red, shadow="#dddddd", offset=(6, 6))

    output_path = Path(output_path)
    image.convert("RGB").save(output_path, format="PNG", optimize=True)
    return output_path


def create_record_high_cover_page(target_date):
    return create_cover_page(target_date, "신고가", RECORD_HIGH_COVER_PATH)


def create_latest_trade_cover_page(target_date):
    return create_cover_page(target_date, "실거래가", LATEST_TRADE_COVER_PATH)


def draw_tiger_badge(image, draw, today_text):
    tiger_image_path = find_tiger_image_path()
    circle_size = 86
    circle_cx = MARGIN + 62
    circle_cy = HEADER_Y + HEADER_HEIGHT / 2
    circle_box = (
        circle_cx - circle_size / 2,
        circle_cy - circle_size / 2,
        circle_cx + circle_size / 2,
        circle_cy + circle_size / 2,
    )
    if tiger_image_path is None:
        draw.ellipse(circle_box, fill="#ffc43d", outline="white", width=3)
        return

    tiger = Image.open(tiger_image_path).convert("RGBA")
    tiger = ImageOps.fit(tiger, (circle_size, circle_size), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", tiger.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, tiger.width - 1, tiger.height - 1), fill=255)
    image.paste(
        tiger,
        (int(circle_cx - circle_size / 2), int(circle_cy - circle_size / 2)),
        mask,
    )
    draw.ellipse(circle_box, outline="white", width=3)


def draw_instagram(image, draw):
    icon_size = 24
    x = MARGIN + 14
    y = META_Y + META_HEIGHT / 2
    icon_y = int(y - icon_size / 2)
    if INSTAGRAM_LOGO_PATH.exists():
        logo = Image.open(INSTAGRAM_LOGO_PATH).convert("RGBA")
        logo = logo.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        image.alpha_composite(logo, (x, icon_y))
    instagram_text_x = x + icon_size + 8
    youtube_x = instagram_text_x + 178
    youtube_y = y - 11
    draw_text(
        draw,
        (instagram_text_x, y + 1),
        INSTAGRAM_ID,
        size=17,
        fill="#333333",
        anchor="lm",
    )
    draw.rounded_rectangle((youtube_x, youtube_y, youtube_x + 32, youtube_y + 22), radius=6, fill="#ff0000")
    draw.polygon(
        (
            (youtube_x + 12, youtube_y + 6),
            (youtube_x + 12, youtube_y + 16),
            (youtube_x + 22, youtube_y + 11),
        ),
        fill="white",
    )
    draw_text(
        draw,
        (youtube_x + 40, y + 1),
        YOUTUBE_LABEL,
        size=17,
        fill="#333333",
        anchor="lm",
    )


def draw_header(image, draw, *, title, today_text, date_text, page_number, page_count):
    draw.rectangle((MARGIN, HEADER_Y, MARGIN + INNER_WIDTH, HEADER_Y + HEADER_HEIGHT), fill="#b40000")
    draw_tiger_badge(image, draw, today_text)
    header_title = f"{LABEL_TODAY} {title.replace(' 리스트', '')}"
    draw_text(draw, (PAGE_WIDTH / 2 - 28, HEADER_Y + HEADER_HEIGHT / 2 + 2), header_title, size=38, bold=True, fill="white")
    draw_text(
        draw,
        (MARGIN + INNER_WIDTH - 20, HEADER_Y + HEADER_HEIGHT / 2 + 3),
        today_text,
        size=38,
        bold=True,
        fill="#ffe082",
        anchor="rm",
    )

    draw_cell(draw, MARGIN, META_Y, INNER_WIDTH, META_HEIGHT, fill="#f5f8fb")
    draw_instagram(image, draw)
    draw_text(
        draw,
        (MARGIN + INNER_WIDTH - 18, META_Y + META_HEIGHT / 2 + 1),
        f"{page_number}/{page_count}",
        size=18,
        fill="#6b7280",
        anchor="rm",
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
        row_fill = "#d00000" if getattr(row_values, "is_record_high", False) else "#111111"
        for index, ((_, width, align), value) in enumerate(zip(columns, row_values)):
            draw_cell(draw, cursor, y, width, ROW_HEIGHT)
            anchor = "lm" if align == "left" else "mm"
            text_x = cursor + 8 if align == "left" else cursor + width / 2
            fill = "#d00000" if value.startswith("▲") else row_fill
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
    previous_high = row["previous_high"]
    is_record_high = previous_high is not None and row["deal_amount"] > previous_high
    return ReportRow([
        row["gu_name"],
        f"{row['exclusive_area']:.0f}",
        fit_text(f"{row['apt_name']} ({row['umd_nm']})", 36),
        row["deal_date"],
        format_price(row["deal_amount"]),
        str(floor),
        f"{household_count}" if household_count else "-",
    ], is_record_high=is_record_high)


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
