from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from complexes import get_household_count_for_trade
from report_image import (
    INSTAGRAM_ID,
    INSTAGRAM_LOGO_PATH,
    HEADER_TITLE,
    LABEL_TODAY,
    MARGIN,
    NO_ROWS,
    REPORT_IMAGE_PATH,
    REPORT_INNER_WIDTH,
    REPORT_TITLE,
    ROW_HEIGHT,
    TAGLINE,
    WIDTH,
    build_report_rows,
    find_tiger_image_path,
    fit_text,
    format_price,
)


TELEGRAM_PNG_PATH = Path("public") / "today-record-highs-telegram.png"

REGULAR_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgun.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
]
BOLD_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgunbd.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Bold.otf",
]


def find_font_path(candidates):
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


REGULAR_FONT_PATH = find_font_path(REGULAR_FONT_CANDIDATES)
BOLD_FONT_PATH = find_font_path(BOLD_FONT_CANDIDATES) or REGULAR_FONT_PATH


def font(size, bold=False):
    font_path = BOLD_FONT_PATH if bold else REGULAR_FONT_PATH
    if font_path:
        return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()


def draw_text(draw, xy, text, size=16, fill="#111111", bold=False, anchor="mm"):
    draw.text(xy, str(text), font=font(size, bold=bold), fill=fill, anchor=anchor)


def draw_cell(draw, x, y, width, height, fill="white", outline="#d9d9d9"):
    draw.rectangle((x, y, x + width, y + height), fill=fill, outline=outline)


def draw_tiger_logo(image, draw, x=30, y=20, height=58):
    tiger_image_path = find_tiger_image_path()
    circle_size = height - 4
    circle_cx = x + circle_size / 2
    circle_cy = y + height / 2
    if tiger_image_path is None:
        circle_box = (
            circle_cx - circle_size / 2,
            circle_cy - circle_size / 2,
            circle_cx + circle_size / 2,
            circle_cy + circle_size / 2,
        )
        draw.ellipse(circle_box, fill="#ffc43d", outline="white", width=2)
        draw_text(draw, (circle_cx, circle_cy + 1), "T", size=30, bold=True, fill="#b40000")
        return

    circle_box = (
        circle_cx - circle_size / 2,
        circle_cy - circle_size / 2,
        circle_cx + circle_size / 2,
        circle_cy + circle_size / 2,
    )
    draw.ellipse(circle_box, fill="#ffc43d", outline="white", width=2)

    tiger = Image.open(tiger_image_path).convert("RGBA")
    target_size = (int(circle_size * 0.92), int(circle_size * 1.12))
    tiger.thumbnail(target_size, Image.Resampling.LANCZOS)
    image_x = int(circle_cx - tiger.width / 2)
    image_y = int(circle_cy - tiger.height / 2 - 1)
    image.alpha_composite(tiger, (image_x, image_y))


def draw_instagram_id(image, draw, x=500, y=97):
    icon_size = 15
    icon_y = y - icon_size / 2
    if INSTAGRAM_LOGO_PATH.exists():
        logo = Image.open(INSTAGRAM_LOGO_PATH).convert("RGBA")
        logo = logo.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        image.alpha_composite(logo, (int(x), int(icon_y)))
        draw_text(draw, (x + icon_size + 6, y + 0.5), INSTAGRAM_ID, size=13, fill="#333333", anchor="lm")
        return

    scale = 4
    large_size = icon_size * scale
    gradient = Image.new("RGBA", (large_size, large_size), (0, 0, 0, 0))
    gradient_pixels = gradient.load()
    stops = [
        (0.0, (255, 176, 0)),
        (0.32, (255, 61, 0)),
        (0.62, (255, 0, 105)),
        (1.0, (138, 0, 255)),
    ]
    for gy in range(large_size):
        for gx in range(large_size):
            t = ((large_size - 1 - gy) + gx) / (2 * (large_size - 1))
            for index in range(len(stops) - 1):
                left_t, left_color = stops[index]
                right_t, right_color = stops[index + 1]
                if left_t <= t <= right_t:
                    local_t = (t - left_t) / (right_t - left_t)
                    color = tuple(
                        int(left_color[channel] + (right_color[channel] - left_color[channel]) * local_t)
                        for channel in range(3)
                    )
                    gradient_pixels[gx, gy] = (*color, 255)
                    break

    mask = Image.new("L", (large_size, large_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, large_size - 1, large_size - 1), radius=4 * scale, fill=255)
    gradient.putalpha(mask)
    icon = gradient.resize((icon_size, icon_size), Image.Resampling.LANCZOS)

    base_image = draw.im
    if isinstance(base_image, Image.Image):
        base_image.alpha_composite(icon, (int(x), int(icon_y)))
    else:
        draw.bitmap((x, icon_y), icon)

    draw.rounded_rectangle(
        (x + 3.3, icon_y + 3.3, x + icon_size - 3.3, icon_y + icon_size - 3.3),
        radius=2.7,
        outline="white",
        width=2,
    )
    draw.ellipse((x + 5.0, y - 2.5, x + 10.0, y + 2.5), outline="white", width=2)
    draw.ellipse((x + icon_size - 5.5, icon_y + 3.2, x + icon_size - 3.2, icon_y + 5.5), fill="white")
    draw_text(draw, (x + icon_size + 6, y + 0.5), INSTAGRAM_ID, size=13, fill="#333333", anchor="lm")


def create_report_png(target_date=None, output_path=TELEGRAM_PNG_PATH, limit=38):
    target_date, rows = build_report_rows(target_date, limit=limit)
    today = datetime.now(timezone(timedelta(hours=9))).date()
    today_text = f"{today.year}년 {today.month:02d}월 {today.day:02d}일"
    today_short = f"{today.month:02d}월 {today.day:02d}일"

    fixed_column_width = 72 + 78 + 96 + 96 + 70 + 82
    apt_column_width = REPORT_INNER_WIDTH - fixed_column_width
    columns = [
        ("구분", 72, "center"),
        ("전용(m2)", 78, "center"),
        ("단지명", apt_column_width, "left"),
        ("전고가", 96, "center"),
        ("거래금액", 96, "center"),
        ("세대수", 70, "center"),
        ("증감", 82, "center"),
    ]
    table_width = sum(col[1] for col in columns)
    row_count = max(len(rows), 1)
    height = 128 + row_count * ROW_HEIGHT + 22

    image = Image.new("RGBA", (WIDTH, height), "white")
    draw = ImageDraw.Draw(image)

    draw.rectangle((MARGIN, 18, MARGIN + REPORT_INNER_WIDTH, 82), fill="#b40000")
    draw_tiger_logo(image, draw)
    draw_text(draw, (400, 53), HEADER_TITLE, size=44, bold=True, fill="white")
    draw_text(draw, (WIDTH - 32, 53), today_short, size=36, bold=True, fill="#ffe082", anchor="rm")

    draw_cell(draw, MARGIN, 84, REPORT_INNER_WIDTH, 24, fill="#f5f8fb")
    draw_instagram_id(image, draw, x=MARGIN + 14)
    draw_text(draw, (WIDTH - 36, 97), TAGLINE, size=15, anchor="rm")

    x = MARGIN
    y = 112
    draw_cell(draw, x, y, table_width, ROW_HEIGHT, fill="#d00000", outline="#d00000")
    cursor = x
    for title, width, _ in columns:
        draw_cell(draw, cursor, y, width, ROW_HEIGHT, fill="#d00000", outline="white")
        draw_text(draw, (cursor + width / 2, y + ROW_HEIGHT / 2 + 1), title, size=16, bold=True, fill="white")
        cursor += width

    y += ROW_HEIGHT
    if not rows:
        draw_cell(draw, x, y, table_width, ROW_HEIGHT)
        draw_text(draw, (x + table_width / 2, y + ROW_HEIGHT / 2 + 1), f"{target_date} {NO_ROWS}", size=16)
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
                f"▲{format_price(increase)}",
            ]
            cursor = x
            for index, ((_, width, align), value) in enumerate(zip(columns, values)):
                draw_cell(draw, cursor, y, width, ROW_HEIGHT)
                anchor = "lm" if align == "left" else "mm"
                text_x = cursor + 8 if align == "left" else cursor + width / 2
                fill = "#d00000" if index == 6 else "#111111"
                bold = index in (2, 4)
                draw_text(draw, (text_x, y + ROW_HEIGHT / 2 + 1), value, size=16, bold=bold, fill=fill, anchor=anchor)
                cursor += width
            y += ROW_HEIGHT

    output_path = Path(output_path)
    output_path.parent.mkdir(exist_ok=True)
    image.convert("RGB").save(output_path, format="PNG", optimize=True)
    return output_path


if __name__ == "__main__":
    path = create_report_png()
    print(f"Created {path}")
