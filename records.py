from database import get_connection, init_db


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
            SELECT t.*, (
                SELECT MAX(p.deal_amount)
                FROM apartment_trades p
                WHERE p.sgg_cd = t.sgg_cd
                  AND p.apt_name = t.apt_name
                  AND p.exclusive_area = t.exclusive_area
                  AND p.deal_date < t.deal_date
            ) AS previous_high
            FROM apartment_trades t
        )
        SELECT *
        FROM candidates t
        WHERE previous_high IS NOT NULL
          AND t.deal_amount > previous_high
          {where_sql}
        ORDER BY t.deal_date DESC, t.deal_amount DESC
        LIMIT :limit
    """
    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def latest_record_high_date():
    rows = find_record_highs(limit=1)
    if not rows:
        return None
    return rows[0]["deal_date"]
