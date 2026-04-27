import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from complexes import get_household_count_for_trade
from database import get_complex_summary, get_summary, init_db
from records import (
    find_newly_seen_record_highs,
    find_newly_seen_trades,
    latest_newly_seen_record_high_date,
    latest_newly_seen_trade_date,
)
from report_image import REPORT_IMAGE_PATH, create_report_image, default_target_date


PUBLIC_DIR = Path("public")

PAGE_TITLE = "오늘 새로 포착된 서울 아파트 거래"
EYEBROW = "공개/포착일 기준"
REQUESTED_DATE = "조회 기준일"
RECORD_REPORT_DATE = "신고가 표시일"
LATEST_REPORT_DATE = "실거래가 표시일"
UPDATED_AT = "최근 업데이트 시간"
DB_RANGE = "DB 범위"
TOTAL_TRADES = "누적 거래"
COMPLEX_INFO = "단지정보"
IMAGE_LABEL = "이미지형 리포트"
RECORD_LIST_TITLE = "전체 신고가 리스트"
LATEST_LIST_TITLE = "오늘 업데이트된 실거래가 리스트"
DISTRICT = "구"
ALL = "전체"
MIN_AREA = "최소 면적"
MAX_AREA = "최대 면적"
MIN_PRICE = "최소 가격"
MAX_PRICE = "최대 가격"
SEEN_DATE = "공개일"
DEAL_DATE = "계약일"
DONG = "동"
APT_NAME = "단지명"
AREA = "전용"
HOUSEHOLDS = "세대수"
FLOOR = "층"
PREVIOUS_HIGH = "전고가"
DEAL_PRICE = "거래금액"
INCREASE = "증감"
RECORD_EMPTY = "조건에 맞는 신고가가 없습니다."
LATEST_EMPTY = "조건에 맞는 실거래가가 없습니다."
COUNT_SUFFIX = "건"
EOK = "억"


def price_eok(value):
    return round(value / 10000, 3)


def format_update_time():
    now = datetime.now(timezone(timedelta(hours=9)))
    return now.strftime("%Y-%m-%d %H:%M KST")


def record_row_to_dict(row):
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


def latest_trade_to_dict(row):
    household_count = get_household_count_for_trade(row)
    previous_high = row["previous_high"]
    is_record_high = previous_high is not None and row["deal_amount"] > previous_high
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
        "previousHighEok": price_eok(previous_high) if previous_high else None,
        "isRecordHigh": is_record_high,
        "households": household_count,
        "floor": row["floor"],
    }


def build_site(target_date=None):
    init_db()
    target_date = target_date or default_target_date()
    record_report_date = latest_newly_seen_record_high_date(max_seen_date=target_date) or target_date
    latest_report_date = latest_newly_seen_trade_date(max_seen_date=target_date) or target_date
    image_path = create_report_image(target_date=record_report_date)
    record_rows = find_newly_seen_record_highs(limit=1000, seen_date=record_report_date)
    latest_trade_rows = find_newly_seen_trades(limit=5000, seen_date=latest_report_date)
    record_rows_json = json.dumps([record_row_to_dict(row) for row in record_rows], ensure_ascii=False)
    latest_rows_json = json.dumps([latest_trade_to_dict(row) for row in latest_trade_rows], ensure_ascii=False)
    summary = get_summary()
    complex_summary = get_complex_summary()

    total_trades = summary["total_trades"] or 0
    first_date = summary["first_deal_date"] or "-"
    last_date = summary["last_deal_date"] or "-"
    total_complexes = complex_summary["total_complexes"] or 0
    complexes_with_households = complex_summary["complexes_with_households"] or 0
    complex_rate = 0
    if total_complexes:
        complex_rate = round(complexes_with_households / total_complexes * 100, 1)
    update_time = format_update_time()

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

        .title-row {{
            align-items: start;
            display: flex;
            gap: 18px;
            justify-content: space-between;
        }}

        h1 {{
            font-size: 32px;
            line-height: 1.25;
            margin: 0;
        }}

        .view-buttons {{
            background: #f8fafc;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            display: inline-flex;
            flex: 0 0 auto;
            overflow: hidden;
            padding: 3px;
        }}

        .view-button {{
            background: transparent;
            border: 0;
            border-radius: 6px;
            color: #475467;
            cursor: pointer;
            font: inherit;
            font-size: 14px;
            font-weight: 700;
            height: 36px;
            padding: 0 14px;
        }}

        .view-button.active {{
            background: #b40000;
            color: #ffffff;
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

        .tab-panel[hidden] {{
            display: none;
        }}

        .report-image {{
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            margin-bottom: 28px;
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
            margin: 0 0 12px;
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

        .record-high-row td {{
            color: #d00000;
        }}

        .empty {{
            color: #6b7280;
            padding: 30px;
            text-align: center;
        }}

        @media (max-width: 860px) {{
            .title-row {{
                display: grid;
            }}

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

            .view-buttons {{
                width: 100%;
            }}

            .view-button {{
                flex: 1;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-inner">
            <p class="eyebrow">{EYEBROW}</p>
            <div class="title-row">
                <h1>{PAGE_TITLE}</h1>
                <nav class="view-buttons" aria-label="목록 전환">
                    <button class="view-button active" type="button" data-view="records">신고가 목록</button>
                    <button class="view-button" type="button" data-view="latest">실거래가 목록</button>
                </nav>
            </div>
            <div class="submeta">
                <span>{REQUESTED_DATE}: {target_date}</span>
                <span>{RECORD_REPORT_DATE}: {record_report_date}</span>
                <span>{LATEST_REPORT_DATE}: {latest_report_date}</span>
                <span>{UPDATED_AT}: {update_time}</span>
                <span>{DB_RANGE}: {first_date} ~ {last_date}</span>
                <span>{TOTAL_TRADES}: {total_trades:,}{COUNT_SUFFIX}</span>
                <span>{COMPLEX_INFO}: {complexes_with_households:,}/{total_complexes:,}{COUNT_SUFFIX} ({complex_rate}%)</span>
            </div>
        </div>
    </header>

    <main>
        <section class="tab-panel" id="recordsPanel">
            <section class="report-image" aria-label="{IMAGE_LABEL}">
                <img src="{REPORT_IMAGE_PATH.name}" alt="{RECORD_LIST_TITLE} {IMAGE_LABEL}">
            </section>

            <div class="section-title">
                <h2>{RECORD_LIST_TITLE}</h2>
                <span class="count" id="recordCount">0{COUNT_SUFFIX}</span>
            </div>
            <div class="filters" id="recordFilters">
                <label>{DISTRICT}<select id="recordGu"><option value="">{ALL}</option></select></label>
                <label>{MIN_AREA}<input id="recordMinArea" type="number" min="0" step="1" placeholder="m2"></label>
                <label>{MAX_AREA}<input id="recordMaxArea" type="number" min="0" step="1" placeholder="m2"></label>
                <label>{MIN_PRICE}<input id="recordMinPrice" type="number" min="0" step="0.1" placeholder="{EOK}"></label>
                <label>{MAX_PRICE}<input id="recordMaxPrice" type="number" min="0" step="0.1" placeholder="{EOK}"></label>
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
                    <tbody id="recordRows"></tbody>
                </table>
                <div class="empty" id="recordEmpty">{RECORD_EMPTY}</div>
            </div>
        </section>

        <section class="tab-panel" id="latestPanel" hidden>
            <div class="section-title">
                <h2>{LATEST_LIST_TITLE}</h2>
                <span class="count" id="latestCount">0{COUNT_SUFFIX}</span>
            </div>
            <div class="filters" id="latestFilters">
                <label>{DISTRICT}<select id="latestGu"><option value="">{ALL}</option></select></label>
                <label>{MIN_AREA}<input id="latestMinArea" type="number" min="0" step="1" placeholder="m2"></label>
                <label>{MAX_AREA}<input id="latestMaxArea" type="number" min="0" step="1" placeholder="m2"></label>
                <label>{MIN_PRICE}<input id="latestMinPrice" type="number" min="0" step="0.1" placeholder="{EOK}"></label>
                <label>{MAX_PRICE}<input id="latestMaxPrice" type="number" min="0" step="0.1" placeholder="{EOK}"></label>
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
                            <th>{FLOOR}</th>
                            <th>{HOUSEHOLDS}</th>
                            <th>{DEAL_PRICE}</th>
                        </tr>
                    </thead>
                    <tbody id="latestRows"></tbody>
                </table>
                <div class="empty" id="latestEmpty">{LATEST_EMPTY}</div>
            </div>
        </section>
    </main>

    <script>
        const recordRows = {record_rows_json};
        const latestRows = {latest_rows_json};

        function money(value) {{
            return Number(value).toLocaleString("ko-KR");
        }}

        function price(value) {{
            return Number(value).toLocaleString("ko-KR", {{ maximumFractionDigits: 3 }});
        }}

        function setupTable(config) {{
            const guFilter = document.getElementById(config.gu);
            const minArea = document.getElementById(config.minArea);
            const maxArea = document.getElementById(config.maxArea);
            const minPrice = document.getElementById(config.minPrice);
            const maxPrice = document.getElementById(config.maxPrice);
            const body = document.getElementById(config.body);
            const empty = document.getElementById(config.empty);
            const count = document.getElementById(config.count);

            [...new Set(config.rows.map((row) => row.gu))].sort().forEach((gu) => {{
                const option = document.createElement("option");
                option.value = gu;
                option.textContent = gu;
                guFilter.appendChild(option);
            }});

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
                const filtered = config.rows.filter(passes);
                body.innerHTML = filtered.map(config.renderRow).join("");
                empty.style.display = filtered.length ? "none" : "block";
                count.textContent = `${{filtered.length.toLocaleString("ko-KR")}}{COUNT_SUFFIX}`;
            }}

            [guFilter, minArea, maxArea, minPrice, maxPrice].forEach((element) => {{
                element.addEventListener("input", render);
            }});

            render();
            return render;
        }}

        setupTable({{
            rows: recordRows,
            gu: "recordGu",
            minArea: "recordMinArea",
            maxArea: "recordMaxArea",
            minPrice: "recordMinPrice",
            maxPrice: "recordMaxPrice",
            body: "recordRows",
            empty: "recordEmpty",
            count: "recordCount",
            renderRow: (row) => `
                <tr class="${{row.isRecordHigh ? "record-high-row" : ""}}">
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
            `,
        }});

        setupTable({{
            rows: latestRows,
            gu: "latestGu",
            minArea: "latestMinArea",
            maxArea: "latestMaxArea",
            minPrice: "latestMinPrice",
            maxPrice: "latestMaxPrice",
            body: "latestRows",
            empty: "latestEmpty",
            count: "latestCount",
            renderRow: (row) => `
                <tr class="${{row.isRecordHigh ? "record-high-row" : ""}}">
                    <td>${{row.seenDate || "-"}}</td>
                    <td>${{row.dealDate}}</td>
                    <td>${{row.gu}}</td>
                    <td>${{row.dong}}</td>
                    <td class="apt">${{row.apt}}</td>
                    <td>${{Number(row.area).toFixed(2)}} m2</td>
                    <td>${{row.floor ?? "-"}}</td>
                    <td>${{row.households ? money(row.households) : "-"}}</td>
                    <td class="price">${{price(row.priceEok)}}{EOK}</td>
                </tr>
            `,
        }});

        const buttons = document.querySelectorAll(".view-button");
        const recordsPanel = document.getElementById("recordsPanel");
        const latestPanel = document.getElementById("latestPanel");

        buttons.forEach((button) => {{
            button.addEventListener("click", () => {{
                const view = button.dataset.view;
                buttons.forEach((item) => item.classList.toggle("active", item === button));
                recordsPanel.hidden = view !== "records";
                latestPanel.hidden = view !== "latest";
            }});
        }});
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
