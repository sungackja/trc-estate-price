from complexes import get_household_count
from database import get_connection, init_db


HOUSEHOLD_COUNT_300_GU_NAMES = {
    "\uac15\ub0a8\uad6c",
    "\uc1a1\ud30c\uad6c",
    "\uc11c\ucd08\uad6c",
    "\ub9c8\ud3ec\uad6c",
    "\uc6a9\uc0b0\uad6c",
    "\uc131\ub3d9\uad6c",
}
AREA_EXEMPT_GU_NAMES = {
    "\uac15\ub0a8\uad6c",
    "\uc1a1\ud30c\uad6c",
    "\uc11c\ucd08\uad6c",
}
MIN_HOUSEHOLD_COUNT_300_GU = 300
MIN_HOUSEHOLD_COUNT_OTHER_GU = 500
MIN_NON_EXEMPT_AREA = 59
MIN_DISPLAY_DEAL_AMOUNT = 50000


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


def add_display_prefilter_params(params):
    params["min_display_deal_amount"] = MIN_DISPLAY_DEAL_AMOUNT
    params["min_non_exempt_area"] = MIN_NON_EXEMPT_AREA
    for index, gu_name in enumerate(sorted(AREA_EXEMPT_GU_NAMES)):
        params[f"area_exempt_gu_{index}"] = gu_name
    return params


def display_prefilter_sql(alias):
    area_exempt_params = ", ".join(
        f":area_exempt_gu_{index}" for index, _ in enumerate(sorted(AREA_EXEMPT_GU_NAMES))
    )
    return (
        f"{alias}.deal_amount >= :min_display_deal_amount "
        f"AND ({alias}.gu_name IN ({area_exempt_params}) "
        f"OR {alias}.exclusive_area >= :min_non_exempt_area)"
    )


def household_count_threshold(gu_name):
    if gu_name in HOUSEHOLD_COUNT_300_GU_NAMES:
        return MIN_HOUSEHOLD_COUNT_300_GU
    return MIN_HOUSEHOLD_COUNT_OTHER_GU


def get_display_household_count(row):
    household_count = get_household_count(
        row["gu_name"],
        row["umd_nm"],
        row["apt_name"],
        row["jibun"],
    )
    if household_count:
        return household_count

    from building_register import cache_key, get_cached_count, registry_location_from_trade

    location = registry_location_from_trade(row)
    if not location["bjdong_cd"] or not location["bonbun"]:
        return None
    return get_cached_count(cache_key(location))


def trade_passes_display_filter(row):
    if row["deal_amount"] < MIN_DISPLAY_DEAL_AMOUNT:
        return False

    if row["gu_name"] not in AREA_EXEMPT_GU_NAMES and row["exclusive_area"] < MIN_NON_EXEMPT_AREA:
        return False

    household_count = get_display_household_count(row)
    if household_count is None:
        return False

    return household_count >= household_count_threshold(row["gu_name"])


def apply_display_filter(rows, limit=None, enabled=True):
    if not enabled:
        return rows if limit is None else rows[:limit]

    filtered_rows = []
    for row in rows:
        if not trade_passes_display_filter(row):
            continue

        filtered_rows.append(row)
        if limit is not None and len(filtered_rows) >= limit:
            break

    return filtered_rows


def find_record_highs(
    limit=100,
    gu_code=None,
    min_date=None,
    deal_date=None,
    apply_filter=True,
):
    init_db()

    filters = []
    params = {}
    add_excluded_display_trade_params(params)
    candidate_filters = [excluded_display_trade_sql("t")]
    if apply_filter:
        add_display_prefilter_params(params)
        candidate_filters.append(display_prefilter_sql("t"))

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

    limit_sql = ""
    if limit is not None and not apply_filter:
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
                      AND p.deal_date < t.deal_date
                ) AS previous_high
            FROM apartment_trades t
            WHERE {" AND ".join(candidate_filters)}
        )
        SELECT
            *
        FROM candidates t
        WHERE previous_high IS NOT NULL
          AND t.deal_amount > previous_high
          {where_sql}
        ORDER BY t.deal_date DESC, t.deal_amount DESC
        {limit_sql}
    """

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return apply_display_filter(rows, limit, apply_filter)


def find_newly_seen_record_highs(
    limit=100,
    seen_date=None,
    gu_code=None,
    apply_filter=True,
):
    init_db()

    filters = ["t.is_backfill = 0", "t.first_seen_date = :seen_date"]
    params = {"seen_date": seen_date}
    add_excluded_display_trade_params(params)
    if apply_filter:
        add_display_prefilter_params(params)
        filters.append(display_prefilter_sql("t"))

    if gu_code:
        filters.append("t.sgg_cd = :gu_code")
        params["gu_code"] = gu_code

    where_sql = " AND ".join(filters)
    limit_sql = ""
    if limit is not None and not apply_filter:
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
        rows = conn.execute(query, params).fetchall()
        return apply_display_filter(rows, limit, apply_filter)


def find_newly_seen_trades(limit=1000, seen_date=None, gu_code=None, apply_filter=True):
    init_db()

    filters = ["t.is_backfill = 0", "t.first_seen_date = :seen_date"]
    params = {"seen_date": seen_date}
    add_excluded_display_trade_params(params)
    if apply_filter:
        add_display_prefilter_params(params)
        filters.append(display_prefilter_sql("t"))

    if gu_code:
        filters.append("t.sgg_cd = :gu_code")
        params["gu_code"] = gu_code

    limit_sql = ""
    if limit is not None and not apply_filter:
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
        rows = conn.execute(query, params).fetchall()
        return apply_display_filter(rows, limit, apply_filter)


def latest_newly_seen_record_high_date(max_seen_date=None, apply_filter=True):
    init_db()

    filters = ["is_backfill = 0", "first_seen_date IS NOT NULL"]
    params = {}
    add_excluded_display_trade_params(params)
    if apply_filter:
        add_display_prefilter_params(params)
        filters.append(display_prefilter_sql("apartment_trades"))
    if max_seen_date:
        filters.append("first_seen_date <= :max_seen_date")
        params["max_seen_date"] = max_seen_date

    query = f"""
        SELECT DISTINCT first_seen_date
        FROM apartment_trades
        WHERE {" AND ".join(filters)}
          AND {excluded_display_trade_sql("apartment_trades")}
        ORDER BY first_seen_date DESC
    """

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    for row in rows:
        seen_date = row["first_seen_date"]
        if find_newly_seen_record_highs(limit=1, seen_date=seen_date, apply_filter=apply_filter):
            return seen_date

    return None


def latest_newly_seen_trade_date(max_seen_date=None, apply_filter=True):
    init_db()

    filters = ["is_backfill = 0", "first_seen_date IS NOT NULL"]
    params = {}
    add_excluded_display_trade_params(params)
    if apply_filter:
        add_display_prefilter_params(params)
        filters.append(display_prefilter_sql("apartment_trades"))
    if max_seen_date:
        filters.append("first_seen_date <= :max_seen_date")
        params["max_seen_date"] = max_seen_date

    query = f"""
        SELECT DISTINCT first_seen_date
        FROM apartment_trades
        WHERE {" AND ".join(filters)}
          AND {excluded_display_trade_sql("apartment_trades")}
        ORDER BY first_seen_date DESC
    """

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    if not apply_filter:
        return rows[0]["first_seen_date"] if rows else None

    for row in rows:
        seen_date = row["first_seen_date"]
        if find_newly_seen_trades(limit=1, seen_date=seen_date, apply_filter=True):
            return seen_date

    return None


def latest_record_high_date():
    rows = find_record_highs(limit=1)
    if not rows:
        return None
    return rows[0]["deal_date"]
