from database import get_connection, init_db


GROUP_MATCH_SQL = """
    p.exclusive_area = t.exclusive_area
    AND (
        (t.apt_seq <> '' AND p.apt_seq = t.apt_seq)
        OR (
            (t.apt_seq = '' OR p.apt_seq = '')
            AND p.sgg_cd = t.sgg_cd
            AND p.apt_name = t.apt_name
        )
    )
"""


EXCLUDED_DISPLAY_TRADES = (
    ("\uc1a1\ud30c\uad6c", "\uc1a1\ud30c\ub3d9", "\uacbd\ub0a8\ub808\uc774\ud06c\ud30c\ud06c"),
)


def excluded_display_trade_sql(alias):
    conditions = []
    for index, _ in enumerate(EXCLUDED_DISPLAY_TRADES):
        conditions.append(
            f"NOT ({alias}.gu_name = :excluded_gu_{index} "
            f"AND {alias}.umd_nm = :excluded_dong_{index} "
            f"AND {alias}.apt_name = :excluded_apt_{index})"
        )
    return " AND ".join(conditions) or "1 = 1"


def add_excluded_display_trade_params(params):
    for index, (gu_name, dong_name, apt_name) in enumerate(EXCLUDED_DISPLAY_TRADES):
        params[f"excluded_gu_{index}"] = gu_name
        params[f"excluded_dong_{index}"] = dong_name
        params[f"excluded_apt_{index}"] = apt_name
    return params


def find_record_highs(limit=100, gu_code=None, min_date=None, deal_date=None):
    init_db()

    filters = []
    params = {"limit": limit}
    add_excluded_display_trade_params(params)

    if gu_code:
        filters.append("t.sgg_cd = :gu_code")
        params["gu_code"] = gu_code

    if min_date:
        filters.append("t.deal_date >= :min_date")
        params["min_date"] = min_date

    if deal_date:
        filters.append("t.deal_date = :deal_date")
        params["deal_date"] = deal_date

    where_sql = ""
    if filters:
        where_sql = "AND " + " AND ".join(filters)

    query = f"""
        WITH candidates AS (
            SELECT
                t.*,
                (
                    SELECT MAX(p.deal_amount)
                    FROM apartment_trades p
                    WHERE {GROUP_MATCH_SQL}
                      AND p.deal_date < t.deal_date
                ) AS previous_high
            FROM apartment_trades t
            WHERE {excluded_display_trade_sql("t")}
        )
        SELECT
            *
        FROM candidates t
        WHERE previous_high IS NOT NULL
          AND t.deal_amount > previous_high
          {where_sql}
        ORDER BY t.deal_date DESC, t.deal_amount DESC
        LIMIT :limit
    """

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def find_newly_seen_record_highs(limit=100, seen_date=None, gu_code=None):
    init_db()

    filters = ["t.is_backfill = 0", "t.first_seen_date = :seen_date"]
    params = {"seen_date": seen_date}
    add_excluded_display_trade_params(params)

    if gu_code:
        filters.append("t.sgg_cd = :gu_code")
        params["gu_code"] = gu_code

    where_sql = " AND ".join(filters)
    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT :limit"
        params["limit"] = limit

    query = f"""
        WITH candidates AS (
            SELECT
                t.*,
                (
                    SELECT MAX(p.deal_amount)
                    FROM apartment_trades p
                    WHERE {GROUP_MATCH_SQL}
                      AND p.id <> t.id
                ) AS previous_high
            FROM apartment_trades t
            WHERE {where_sql}
              AND {excluded_display_trade_sql("t")}
        )
        SELECT *
        FROM candidates
        WHERE previous_high IS NOT NULL
          AND deal_amount > previous_high
        ORDER BY deal_amount DESC, deal_date DESC
        {limit_sql}
    """

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def find_newly_seen_trades(limit=1000, seen_date=None, gu_code=None):
    init_db()

    filters = ["t.is_backfill = 0", "t.first_seen_date = :seen_date"]
    params = {"seen_date": seen_date}
    add_excluded_display_trade_params(params)

    if gu_code:
        filters.append("t.sgg_cd = :gu_code")
        params["gu_code"] = gu_code

    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT :limit"
        params["limit"] = limit

    query = f"""
        WITH candidates AS (
            SELECT
                t.*,
                (
                    SELECT MAX(p.deal_amount)
                    FROM apartment_trades p
                    WHERE {GROUP_MATCH_SQL}
                      AND p.id <> t.id
                ) AS previous_high
            FROM apartment_trades t
            WHERE {" AND ".join(filters)}
              AND {excluded_display_trade_sql("t")}
        )
        SELECT *
        FROM candidates
        ORDER BY gu_name ASC, umd_nm ASC, apt_name ASC, deal_amount DESC, deal_date DESC
        {limit_sql}
    """

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def latest_newly_seen_record_high_date(max_seen_date=None):
    init_db()

    filters = ["t.is_backfill = 0", "t.first_seen_date IS NOT NULL"]
    params = {}
    add_excluded_display_trade_params(params)
    if max_seen_date:
        filters.append("t.first_seen_date <= :max_seen_date")
        params["max_seen_date"] = max_seen_date

    query = f"""
        WITH candidates AS (
            SELECT
                t.*,
                (
                    SELECT MAX(p.deal_amount)
                    FROM apartment_trades p
                    WHERE {GROUP_MATCH_SQL}
                      AND p.id <> t.id
                ) AS previous_high
            FROM apartment_trades t
            WHERE {" AND ".join(filters)}
              AND {excluded_display_trade_sql("t")}
        )
        SELECT MAX(first_seen_date) AS latest_seen_date
        FROM candidates
        WHERE previous_high IS NOT NULL
          AND deal_amount > previous_high
    """

    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return row["latest_seen_date"] if row else None


def latest_newly_seen_trade_date(max_seen_date=None):
    init_db()

    filters = ["is_backfill = 0", "first_seen_date IS NOT NULL"]
    params = {}
    add_excluded_display_trade_params(params)
    if max_seen_date:
        filters.append("first_seen_date <= :max_seen_date")
        params["max_seen_date"] = max_seen_date

    query = f"""
        SELECT MAX(first_seen_date) AS latest_seen_date
        FROM apartment_trades
        WHERE {" AND ".join(filters)}
          AND {excluded_display_trade_sql("apartment_trades")}
    """

    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return row["latest_seen_date"] if row else None


def latest_record_high_date():
    rows = find_record_highs(limit=1)
    if not rows:
        return None
    return rows[0]["deal_date"]
