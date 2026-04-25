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


def find_record_highs(limit=100, gu_code=None, min_date=None, deal_date=None):
    init_db()

    filters = []
    params = {"limit": limit}

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

    filters = ["is_backfill = 0", "first_seen_date = :seen_date"]
    params = {"seen_date": seen_date}

    if gu_code:
        filters.append("sgg_cd = :gu_code")
        params["gu_code"] = gu_code

    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT :limit"
        params["limit"] = limit

    query = f"""
        SELECT *
        FROM apartment_trades
        WHERE {" AND ".join(filters)}
        ORDER BY gu_name ASC, umd_nm ASC, apt_name ASC, deal_amount DESC, deal_date DESC
        {limit_sql}
    """

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def latest_newly_seen_record_high_date(max_seen_date=None):
    init_db()

    filters = ["t.is_backfill = 0", "t.first_seen_date IS NOT NULL"]
    params = {}
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
    if max_seen_date:
        filters.append("first_seen_date <= :max_seen_date")
        params["max_seen_date"] = max_seen_date

    query = f"""
        SELECT MAX(first_seen_date) AS latest_seen_date
        FROM apartment_trades
        WHERE {" AND ".join(filters)}
    """

    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return row["latest_seen_date"] if row else None


def latest_record_high_date():
    rows = find_record_highs(limit=1)
    if not rows:
        return None
    return rows[0]["deal_date"]
