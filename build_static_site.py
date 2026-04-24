import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from complexes import get_household_count_for_trade
from database import get_summary, init_db
from records import find_newly_seen_record_highs
from report_image import REPORT_IMAGE_PATH, create_report_image, default_target_date


PUBLIC_DIR = Path("public")

PAGE_TITLE = "\uc624\ub298 \uc0c8\ub85c \ud3ec\ucc29\ub41c \uc11c\uc6b8 \uc544\ud30c\ud2b8 \uc2e0\uace0\uac00"
EYEBROW = "\uacf5\uac1c/\ud3ec\ucc29\uc77c \uae30\uc900"
REPORT_DATE = "\ub9ac\ud3ec\ud2b8 \uae30\uc900\uc77c"
UPDATED_AT = "\ucd5c\uadfc \uc5c5\ub370\uc774\ud2b8 \uc2dc\uac04"
DB_RANGE = "DB \ubc94\uc704"
TOTAL_TRADES = "\ub204\uc801 \uac70\ub798"
IMAGE_LABEL = "\uc774\ubbf8\uc9c0\ud615 \ub9ac\ud3ec\ud2b8"
LIST_TITLE = "\uc804\uccb4 \uc2e0\uace0\uac00 \ub9ac\uc2a4\ud2b8"
DISTRICT = "\uad6c"
ALL = "\uc804\uccb4"
MIN_AREA = "\ucd5c\uc18c \uba74\uc801"
MAX_AREA = "\ucd5c\ub300 \uba74\uc801"
MIN_PRICE = "\ucd5c\uc18c \uac00\uaca9"
MAX_PRICE = "\ucd5c\ub300 \uac00\uaca9"
SEEN_DATE = "\uacf5\uac1c\uc77c"
DEAL_DATE = "\uacc4\uc57d\uc77c"
DONG = "\ub3d9"
APT_NAME = "\ub2e8\uc9c0\uba85"
AREA = "\uc804\uc6a9"
HOUSEHOLDS = "\uc138\ub300\uc218"
PREVIOUS_HIGH = "\uc804\uace0\uac00"
DEAL_PRICE = "\uac70\ub798\uae08\uc561"
INCREASE = "\uc99d\uac10"
EMPTY = "\uc870\uac74\uc5d0 \ub9de\ub294 \uc2e0\uace0\uac00\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."
COUNT_SUFFIX = "\uac74"
EOK = "\uc5b5"


def price_eok(value):
    return round(value / 10000, 3)


def format_update_time():
    now = datetime.now(timezone(timedelta(hours=9)))
    return now.strftime("%Y-%m-%d %H:%M KST")


def row_to_dict(row):
    previous_high = row["previous_high"] or 0
    increase = row["deal_amount"] - previous_high
    household_count = get_household_count_for_trade(row)
    return {
        "gu": row["gu_name"],
        "dong": row["umd_nm"] or "",
        "apt": row["apt_name"],
        "area": row["exclusive_area"],
        "dealDate": row["deal_date"],
        "seenDate": row["first_seen_date"],
        "price": row["deal_amount"],
        "priceEok": price_eok(row["deal_amount"]),
        "previousHigh": previous_high,
        "previousHighEok": price_eok(previous_high),
        "increase": increase,
        "increaseEok": price_eok(increase),
        "households": household_count,
        "floor": row["floor"],
    }


def build_site(target_date=None):
    init_db()
    target_date = target_date or default_target_date()
    image_path = create_report_image(target_date=target_date)
    rows = find_newly_seen_record_highs(limit=500, seen_date=target_date)
    report_rows = [row_to_dict(row) for row in rows]
    summary = get_summary()

    total_trades = summary["total_trades"] or 0
    first_date = summary["first_deal_date"] or "-"
    last_date = summary["last_deal_date"] or "-"
    update_time = format_update_time()
    rows_json = json.dumps(report_rows, ensure_ascii=False)

    html = f"""<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{PAGE_TITLE}</title>
    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: #f3f4f6;
            color: #111827;
            font-family: Arial, "Malgun Gothic", sans-serif;
        }}

        header {{
            background: #ffffff;
            border-bottom: 1px solid #e5e7eb;
            padding: 28px 24px 18px;
        }}

        .header-inner,
        main {{
            margin: 0 auto;
            max-width: 1120px;
        }}

        .eyebrow {{
            color: #b40000;
            font-size: 13px;
            font-weight: 700;
            margin: 0 0 8px;
        }}

        h1 {{
            font-size: 32px;
            line-height: 1.25;
            margin: 0;
        }}

        .submeta {{
            color: #4b5563;
            display: flex;
            flex-wrap: wrap;
            gap: 10px 18px;
            margin-top: 12px;
        }}

        main {{
            padding: 22px 24px 40px;
        }}

        .report-image {{
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            overflow: hidden;
        }}

        .report-image img {{
            display: block;
            height: auto;
            width: 100%;
        }}

        .section-title {{
            align-items: baseline;
            display: flex;
            justify-content: space-between;
            margin: 28px 0 12px;
        }}

        h2 {{
            font-size: 20px;
            margin: 0;
        }}

        .count {{
            color: #6b7280;
            font-size: 14px;
        }}

        .filters {{
            align-items: end;
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            display: grid;
            gap: 12px;
            grid-template-columns: 1.3fr repeat(4, 1fr);
            padding: 14px;
        }}

        label {{
            color: #4b5563;
            display: grid;
            font-size: 13px;
            gap: 6px;
        }}

        select,
        input {{
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            font: inherit;
            height: 38px;
            padding: 0 10px;
            width: 100%;
        }}

        .table-wrap {{
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            margin-top: 14px;
            overflow: auto;
        }}

        table {{
            border-collapse: collapse;
            min-width: 960px;
            width: 100%;
        }}

        th,
        td {{
            border-bottom: 1px solid #edf0f3;
            font-size: 14px;
            padding: 12px;
            text-align: left;
            white-space: nowrap;
        }}

        th {{
            background: #f8fafc;
            color: #475467;
            font-size: 12px;
        }}

        .apt,
        .price,
        .up {{
            font-weight: 700;
        }}

        .up {{
            color: #d00000;
        }}

        .empty {{
            color: #6b7280;
            padding: 30px;
            text-align: center;
        }}

        @media (max-width: 860px) {{
            h1 {{
                font-size: 25px;
            }}

            .filters {{
                grid-template-columns: 1fr 1fr;
            }}
        }}

        @media (max-width: 560px) {{
            .filters {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-inner">
            <p class="eyebrow">{EYEBROW}</p>
            <h1>{PAGE_TITLE}</h1>
            <div class="submeta">
                <span>{REPORT_DATE}: {target_date}</span>
                <span>{UPDATED_AT}: {update_time}</span>
                <span>{DB_RANGE}: {first_date} ~ {last_date}</span>
                <span>{TOTAL_TRADES}: {total_trades:,}{COUNT_SUFFIX}</span>
            </div>
        </div>
    </header>

    <main>
        <section class="report-image" aria-label="{IMAGE_LABEL}">
            <img src="{REPORT_IMAGE_PATH.name}" alt="{PAGE_TITLE} {IMAGE_LABEL}">
        </section>

        <section>
            <div class="section-title">
                <h2>{LIST_TITLE}</h2>
                <span class="count" id="resultCount">0{COUNT_SUFFIX}</span>
            </div>

            <div class="filters">
                <label>
                    {DISTRICT}
                    <select id="guFilter">
                        <option value="">{ALL}</option>
                    </select>
                </label>
                <label>
                    {MIN_AREA}
                    <input id="minArea" type="number" min="0" step="1" placeholder="m2">
                </label>
                <label>
                    {MAX_AREA}
                    <input id="maxArea" type="number" min="0" step="1" placeholder="m2">
                </label>
                <label>
                    {MIN_PRICE}
                    <input id="minPrice" type="number" min="0" step="0.1" placeholder="{EOK}">
                </label>
                <label>
                    {MAX_PRICE}
                    <input id="maxPrice" type="number" min="0" step="0.1" placeholder="{EOK}">
                </label>
            </div>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>{SEEN_DATE}</th>
                            <th>{DEAL_DATE}</th>
                            <th>{DISTRICT}</th>
                            <th>{DONG}</th>
                            <th>{APT_NAME}</th>
                            <th>{AREA}</th>
                            <th>{HOUSEHOLDS}</th>
                            <th>{PREVIOUS_HIGH}</th>
                            <th>{DEAL_PRICE}</th>
                            <th>{INCREASE}</th>
                        </tr>
                    </thead>
                    <tbody id="rowsBody"></tbody>
                </table>
                <div class="empty" id="emptyState">{EMPTY}</div>
            </div>
        </section>
    </main>

    <script>
        const rows = {rows_json};
        const guFilter = document.getElementById("guFilter");
        const minArea = document.getElementById("minArea");
        const maxArea = document.getElementById("maxArea");
        const minPrice = document.getElementById("minPrice");
        const maxPrice = document.getElementById("maxPrice");
        const rowsBody = document.getElementById("rowsBody");
        const emptyState = document.getElementById("emptyState");
        const resultCount = document.getElementById("resultCount");

        function money(value) {{
            return Number(value).toLocaleString("ko-KR");
        }}

        function price(value) {{
            return Number(value).toLocaleString("ko-KR", {{ maximumFractionDigits: 3 }});
        }}

        function fillDistricts() {{
            [...new Set(rows.map((row) => row.gu))].sort().forEach((gu) => {{
                const option = document.createElement("option");
                option.value = gu;
                option.textContent = gu;
                guFilter.appendChild(option);
            }});
        }}

        function passes(row) {{
            const gu = guFilter.value;
            const minA = Number(minArea.value || 0);
            const maxA = Number(maxArea.value || Infinity);
            const minP = Number(minPrice.value || 0);
            const maxP = Number(maxPrice.value || Infinity);
            return (!gu || row.gu === gu)
                && row.area >= minA
                && row.area <= maxA
                && row.priceEok >= minP
                && row.priceEok <= maxP;
        }}

        function render() {{
            const filtered = rows.filter(passes);
            rowsBody.innerHTML = filtered.map((row) => `
                <tr>
                    <td>${{row.seenDate || "-"}}</td>
                    <td>${{row.dealDate}}</td>
                    <td>${{row.gu}}</td>
                    <td>${{row.dong}}</td>
                    <td class="apt">${{row.apt}}</td>
                    <td>${{Number(row.area).toFixed(2)}} m2</td>
                    <td>${{row.households ? money(row.households) : "-"}}</td>
                    <td>${{price(row.previousHighEok)}}{EOK}</td>
                    <td class="price">${{price(row.priceEok)}}{EOK}</td>
                    <td class="up">▲${{price(row.increaseEok)}}{EOK}</td>
                </tr>
            `).join("");
            emptyState.style.display = filtered.length ? "none" : "block";
            resultCount.textContent = `${{filtered.length.toLocaleString("ko-KR")}}{COUNT_SUFFIX}`;
        }}

        [guFilter, minArea, maxArea, minPrice, maxPrice].forEach((element) => {{
            element.addEventListener("input", render);
        }});

        fillDistricts();
        render();
    </script>
</body>
</html>
"""
    PUBLIC_DIR.mkdir(exist_ok=True)
    html_path = PUBLIC_DIR / "index.html"
    html_path.write_text(html, encoding="utf-8")
    return image_path, html_path


if __name__ == "__main__":
    image_path, html_path = build_site()
    print(f"Created {image_path}")
    print(f"Created {html_path}")
