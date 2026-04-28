import json
import xml.etree.ElementTree as ET
from functools import lru_cache

import requests

from config import BLD_REGISTRY_API_BASE_URL, BLD_REGISTRY_API_KEY, REQUEST_TIMEOUT_SECONDS
from database import get_connection, init_db


COUNT_KEYS = (
    "hhldCnt",
    "fmlyCnt",
    "hoCnt",
    "householdCount",
    "householdCnt",
    "hshldCnt",
)


REMOVE_NAME_WORDS = (
    "아파트",
    "APT",
    "apt",
    "주상복합",
    "단지",
)


def normalize_name(value):
    text = value or ""
    for word in REMOVE_NAME_WORDS:
        text = text.replace(word, "")
    return "".join(char for char in text if char.isalnum()).lower()


def clean_text(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def to_int(value):
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        count = int(float(text))
    except ValueError:
        return None
    return count if count > 0 else None


def xml_element_to_dict(element):
    return {child.tag: clean_text(child.text) for child in element}


def extract_items(text):
    root = ET.fromstring(text)
    result_code = clean_text(root.findtext(".//resultCode"))
    result_msg = clean_text(root.findtext(".//resultMsg"))
    if result_code and result_code not in ("00", "000", "NORMAL_CODE"):
        raise RuntimeError(f"Building register API error: {result_code} / {result_msg}")
    return [xml_element_to_dict(item) for item in root.findall(".//item")]


def first_count(item):
    for key in COUNT_KEYS:
        count = to_int(item.get(key))
        if count:
            return count
    return None


def trade_xml_value(row, key):
    raw_xml = row["raw_xml"]
    if not raw_xml:
        return ""
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return ""
    return clean_text(root.findtext(key))


def split_jibun(jibun):
    text = clean_text(jibun)
    if not text:
        return "", ""
    left, _, right = text.partition("-")
    return left.zfill(4), (right or "0").zfill(4)


def registry_location_from_trade(row):
    bonbun = trade_xml_value(row, "bonbun")
    bubun = trade_xml_value(row, "bubun")
    if not bonbun:
        bonbun, bubun = split_jibun(row["jibun"])

    land_cd = trade_xml_value(row, "landCd") or "1"
    return {
        "sgg_cd": row["sgg_cd"],
        "bjdong_cd": trade_xml_value(row, "umdCd"),
        "land_cd": land_cd,
        "bonbun": bonbun.zfill(4) if bonbun else "",
        "bubun": bubun.zfill(4) if bubun else "0000",
        "gu_name": row["gu_name"],
        "umd_nm": row["umd_nm"],
        "apt_name": row["apt_name"],
        "jibun": row["jibun"],
    }


def plat_gb_cd(land_cd):
    # RTMS landCd: 1 일반 대지, 2 산. Building-register platGbCd: 0 대지, 1 산.
    return "1" if clean_text(land_cd) == "2" else "0"


def cache_key(location):
    return "|".join(
        clean_text(location.get(key))
        for key in ("sgg_cd", "bjdong_cd", "land_cd", "bonbun", "bubun", "apt_name")
    )


def get_cached_count(key):
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT household_count
            FROM household_count_cache
            WHERE cache_key = :cache_key
            """,
            {"cache_key": key},
        ).fetchone()
    if not row:
        return None
    return row["household_count"]


def save_cached_count(location, count, source, raw_items):
    init_db()
    key = cache_key(location)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO household_count_cache (
                cache_key,
                sgg_cd,
                bjdong_cd,
                land_cd,
                bonbun,
                bubun,
                gu_name,
                umd_nm,
                apt_name,
                jibun,
                household_count,
                source,
                raw_xml,
                updated_at
            )
            VALUES (
                :cache_key,
                :sgg_cd,
                :bjdong_cd,
                :land_cd,
                :bonbun,
                :bubun,
                :gu_name,
                :umd_nm,
                :apt_name,
                :jibun,
                :household_count,
                :source,
                :raw_xml,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(cache_key) DO UPDATE SET
                household_count = excluded.household_count,
                source = excluded.source,
                raw_xml = excluded.raw_xml,
                updated_at = CURRENT_TIMESTAMP
            """,
            {
                **location,
                "cache_key": key,
                "household_count": count,
                "source": source,
                "raw_xml": json.dumps(raw_items, ensure_ascii=False),
            },
        )


def request_register(operation, location):
    if not BLD_REGISTRY_API_KEY:
        return []

    params = {
        "serviceKey": BLD_REGISTRY_API_KEY,
        "sigunguCd": location["sgg_cd"],
        "bjdongCd": location["bjdong_cd"],
        "platGbCd": plat_gb_cd(location["land_cd"]),
        "bun": location["bonbun"],
        "ji": location["bubun"],
        "numOfRows": "100",
        "pageNo": "1",
    }
    response = requests.get(
        f"{BLD_REGISTRY_API_BASE_URL}/{operation}",
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return extract_items(response.text)


def choose_count(items, apt_name):
    target = normalize_name(apt_name)
    counts = []
    for item in items:
        count = first_count(item)
        if not count:
            continue
        bld_name = normalize_name(item.get("bldNm") or item.get("bldNmDc") or "")
        score = 0
        if target and bld_name:
            if target == bld_name:
                score = 100
            elif target in bld_name or bld_name in target:
                score = 80
        counts.append((score, count))

    if not counts:
        return None
    counts.sort(reverse=True)
    if counts[0][0] > 0:
        return counts[0][1]

    unique_counts = {count for _, count in counts}
    if len(unique_counts) == 1:
        return counts[0][1]
    return max(unique_counts)


@lru_cache(maxsize=2000)
def get_building_register_household_count_by_key(
    sgg_cd,
    bjdong_cd,
    land_cd,
    bonbun,
    bubun,
    gu_name,
    umd_nm,
    apt_name,
    jibun,
):
    location = {
        "sgg_cd": sgg_cd,
        "bjdong_cd": bjdong_cd,
        "land_cd": land_cd,
        "bonbun": bonbun,
        "bubun": bubun,
        "gu_name": gu_name,
        "umd_nm": umd_nm,
        "apt_name": apt_name,
        "jibun": jibun,
    }
    if not bjdong_cd or not bonbun:
        return None

    key = cache_key(location)
    cached_count = get_cached_count(key)
    if cached_count:
        return cached_count

    all_items = []
    for operation in ("getBrRecapTitleInfo", "getBrTitleInfo"):
        try:
            items = request_register(operation, location)
        except Exception:
            continue
        all_items.extend({"operation": operation, **item} for item in items)
        count = choose_count(items, apt_name)
        if count:
            save_cached_count(location, count, operation, all_items)
            return count

    return None


def get_building_register_household_count_for_trade(row):
    location = registry_location_from_trade(row)
    return get_building_register_household_count_by_key(
        location["sgg_cd"],
        location["bjdong_cd"],
        location["land_cd"],
        location["bonbun"],
        location["bubun"],
        location["gu_name"],
        location["umd_nm"],
        location["apt_name"],
        location["jibun"],
    )
