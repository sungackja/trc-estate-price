from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from config import SEOUL_GU_CODES
from database import get_summary, init_db
from records import find_record_highs


HOST = "127.0.0.1"
PORT = 8000


def money(value):
    return f"{value:,}"


def render_page(rows, summary, selected_gu, min_date):
    gu_options = ['<option value="">All Seoul</option>']
    for code, name in SEOUL_GU_CODES.items():
        selected = " selected" if selected_gu == code else ""
        gu_options.append(f'<option value="{code}"{selected}>{name}</option>')

    row_html = []
    for row in rows:
        increase = row["deal_amount"] - row["previous_high"]
        row_html.append(
            f"""
            <tr>
                <td>{escape(row["deal_date"])}</td>
                <td>{escape(row["gu_name"])}</td>
                <td>{escape(row["umd_nm"] or "")}</td>
                <td class="apt">{escape(row["apt_name"])}</td>
                <td>{row["exclusive_area"]:.2f}</td>
                <td>{money(row["deal_amount"])}</td>
                <td>{money(row["previous_high"])}</td>
                <td class="up">+{money(increase)}</td>
            </tr>
            """
        )

    if not row_html:
        row_html.append(
            """
            <tr>
                <td colspan="8" class="empty">No record-high trades found yet. Collect more data first.</td>
            </tr>
            """
        )

    total_trades = summary["total_trades"] or 0
    first_date = summary["first_deal_date"] or "-"
    last_date = summary["last_deal_date"] or "-"
    min_date_value = escape(min_date or "")

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Tiger Estate Price</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <header>
        <div>
            <p class="eyebrow">Seoul apartment trade scanner</p>
            <h1>Tiger Estate Price</h1>
        </div>
        <div class="summary">
            <span>{money(total_trades)} trades</span>
            <span>{first_date} to {last_date}</span>
        </div>
    </header>

    <main>
        <form class="filters" method="get">
            <label>
                District
                <select name="gu">
                    {''.join(gu_options)}
                </select>
            </label>
            <label>
                From date
                <input type="date" name="from" value="{min_date_value}">
            </label>
            <button type="submit">Apply</button>
        </form>

        <section class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>District</th>
                        <th>Dong</th>
                        <th>Apartment</th>
                        <th>Area m2</th>
                        <th>Price</th>
                        <th>Previous high</th>
                        <th>Increase</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(row_html)}
                </tbody>
            </table>
        </section>
    </main>
</body>
</html>"""


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/static/style.css":
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.end_headers()
            with open("static/style.css", "rb") as file:
                self.wfile.write(file.read())
            return

        if parsed.path != "/":
            self.send_error(404)
            return

        query = parse_qs(parsed.query)
        selected_gu = query.get("gu", [""])[0]
        min_date = query.get("from", [""])[0]
        if selected_gu not in SEOUL_GU_CODES:
            selected_gu = None
        if not min_date:
            min_date = None

        init_db()
        summary = get_summary()
        rows = find_record_highs(limit=200, gu_code=selected_gu, min_date=min_date)
        body = render_page(rows, summary, selected_gu, min_date).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run():
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Open http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
