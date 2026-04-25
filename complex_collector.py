import argparse
import json
import time
import xml.etree.ElementTree as ET

import requests

from config import (
    APT_BASIC_INFO_API_URL,
    APT_INFO_API_KEY,
    APT_LIST_API_URL,
    REQUEST_TIMEOUT_SECONDS,
)
from database import get_connection, init_db, upsert_complexes


RETRY_STATUS_CODES = {500, 502, 503, 504}


def clean_text(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def to_int(value):
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def xml_element_to_dict(element):
    return {child.tag: clean_text(child.text) for child in element}


def parse_response(response):
    try:
        data = response.json()
    except ValueError:
        root = ET.fromstring(response.text)
        header = root.find(".//header")
        body = root.find(".//body")
        items = [xml_element_to_dict(item) for item in root.findall(".//item")]
        return {
            "response": {
                "header": xml_element_to_dict(header) if header is not None else {},
                "body": {
                    "items": {"item": items},
                    "totalCount": clean_text(body.findtext("totalCount")) if body is not None else len(items),
                },
            }
        }
    return data


def request_api(url, params, retries=2, retry_sleep=1.0):
    if not APT_INFO_API_KEY:
        raise RuntimeError("APT_INFO_API_KEY is missing. Add it to your .env file.")

    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.exceptions.Timeout:
            last_error = "API request timed out."
            response = None
        except requests.exceptions.RequestException:
            last_error = "API request failed. Check network, API key, and service approval."
            response = None

        if response is not None and response.status_code not in RETRY_STATUS_CODES:
            break

        if response is not None:
            body = response.text[:300].replace("\n", " ")
            last_error = f"API request failed with HTTP {response.status_code}. Body: {body}"

        if attempt < retries:
            time.sleep(retry_sleep)
    else:
        raise RuntimeError(last_error or "API request failed.")

    if response is None:
        raise RuntimeError(last_error or "API request failed.")

    if response.status_code == 403:
        raise RuntimeError(
            "API request was forbidden with HTTP 403. "
            "Check that this key is approved for the V3 apartment list/basic-info APIs "
            "on data.go.kr."
        )

    if response.status_code != 200:
        body = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"API request failed with HTTP {response.status_code}. Body: {body}")

    data = parse_response(response)
    header = data.get("response", {}).get("header", {})
    result_code = clean_text(header.get("resultCode"))
    result_msg = clean_text(header.get("resultMsg"))
    if result_code and result_code not in ("00", "000", "NORMAL_CODE"):
        raise RuntimeError(f"API error: {result_code} / {result_msg}")

    return data


def extract_body(data):
    return data.get("response", {}).get("body", {})


def extract_items(data):
    body = extract_body(data)
    items = body.get("items") or body.get("item") or []
    if isinstance(items, dict):
        nested_item = items.get("item")
        if nested_item is not None:
            items = nested_item
        else:
            items = [items]
    return as_list(items)


def extract_total_count(data):
    body = extract_body(data)
    total_count = body.get("totalCount")
    return to_int(total_count) or len(extract_items(data))


def fetch_complex_list_page(page_no=1, num_rows=1000):
    params = {
        "serviceKey": APT_INFO_API_KEY,
        "sidoCode": "11",
        "pageNo": page_no,
        "numOfRows": num_rows,
    }
    return request_api(APT_LIST_API_URL, params)


def fetch_seoul_complex_list(num_rows=1000):
    first_data = fetch_complex_list_page(page_no=1, num_rows=num_rows)
    items = extract_items(first_data)
    total_count = extract_total_count(first_data)
    total_pages = (total_count + num_rows - 1) // num_rows

    for page_no in range(2, total_pages + 1):
        data = fetch_complex_list_page(page_no=page_no, num_rows=num_rows)
        items.extend(extract_items(data))

    return items


def fetch_basic_info(kapt_code):
    params = {
        "serviceKey": APT_INFO_API_KEY,
        "kaptCode": kapt_code,
    }
    data = request_api(APT_BASIC_INFO_API_URL, params)
    items = extract_items(data)
    if items:
        item = items[0]
        if isinstance(item, dict) and item:
            return item
    body = extract_body(data)
    body_item = body.get("item") if isinstance(body, dict) else None
    if isinstance(body_item, dict) and body_item:
        return body_item
    if isinstance(body, dict) and body:
        return body
    raise RuntimeError("Basic info response did not contain usable apartment fields.")


def get_existing_complex_status():
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT kapt_code, household_count
            FROM apartment_complexes
            """
        ).fetchall()
    return {row["kapt_code"]: row["household_count"] for row in rows}


def value(data, key, default=""):
    if not isinstance(data, dict):
        return default
    return clean_text(data.get(key), default)


def first_value(data, keys, default=""):
    for key in keys:
        found = value(data, key)
        if found:
            return found
    return default


HOUSEHOLD_COUNT_KEYS = (
    "kaptdaCnt",
    "householdCount",
    "householdCnt",
    "hshldCnt",
    "hhldCnt",
    "hhCnt",
    "totHshldCnt",
    "totalHouseholdCount",
    "totalHouseholdCnt",
    "totalHhldCnt",
    "kaptHouseholdCnt",
    "kaptHshldCnt",
    "kaptTotalHouseholdCnt",
    "kaptTotalHshldCnt",
    "hoCnt",
    "totalHoCnt",
    "cntPa",
    "\uc138\ub300\uc218",
)

DONG_COUNT_KEYS = (
    "kaptDongCnt",
    "dongCount",
    "dongCnt",
    "bldgCnt",
    "buildingCount",
    "\ub3d9\uc218",
)

USED_DATE_KEYS = (
    "kaptUsedate",
    "kaptUseDate",
    "useDate",
    "useAprDay",
    "useApprovalDate",
    "\uc0ac\uc6a9\uc2b9\uc778\uc77c",
)

ADDRESS_KEYS = (
    "kaptAddr",
    "addr",
    "address",
    "lnbrMnnm",
    "\uc8fc\uc18c",
)

ROAD_ADDRESS_KEYS = (
    "doroJuso",
    "roadAddress",
    "roadAddr",
    "newPlatPlc",
    "\ub3c4\ub85c\uba85\uc8fc\uc18c",
)

BJD_CODE_KEYS = (
    "bjdCode",
    "bjdongCode",
    "bjdongCd",
    "legalDongCode",
)


def parse_complex(list_item, basic_item=None):
    basic_item = basic_item or {}
    kapt_code = value(list_item, "kaptCode")
    kapt_name = value(list_item, "kaptName")

    return {
        "kapt_code": kapt_code,
        "kapt_name": value(basic_item, "kaptName", kapt_name),
        "as1": value(list_item, "as1"),
        "as2": value(list_item, "as2"),
        "as3": value(list_item, "as3"),
        "as4": value(list_item, "as4"),
        "bjd_code": first_value(basic_item, BJD_CODE_KEYS, value(list_item, "bjdCode")),
        "household_count": to_int(first_value(basic_item, HOUSEHOLD_COUNT_KEYS)),
        "dong_count": to_int(first_value(basic_item, DONG_COUNT_KEYS)),
        "used_date": first_value(basic_item, USED_DATE_KEYS),
        "address": first_value(basic_item, ADDRESS_KEYS),
        "road_address": first_value(basic_item, ROAD_ADDRESS_KEYS),
        "raw_xml": json.dumps(basic_item, ensure_ascii=False),
    }


def collect_complexes(
    limit=None,
    sleep_seconds=0.05,
    verbose=False,
    list_only=False,
    skip_existing=True,
    retry_missing=False,
):
    init_db()
    list_items = fetch_seoul_complex_list()
    existing_complexes = get_existing_complex_status()
    if retry_missing:
        list_items = [
            item
            for item in list_items
            if value(item, "kaptCode") not in existing_complexes
            or existing_complexes.get(value(item, "kaptCode")) is None
        ]
    if limit:
        list_items = list_items[:limit]

    saved = 0
    full_info_count = 0
    list_only_count = 0
    skipped_count = 0
    new_complex_count = 0
    missing_retry_count = 0
    for index, list_item in enumerate(list_items, start=1):
        kapt_code = value(list_item, "kaptCode")
        kapt_name = value(list_item, "kaptName")
        print(f"[{index}/{len(list_items)}] {kapt_code} {kapt_name}")
        is_new_complex = kapt_code not in existing_complexes
        has_household_count = existing_complexes.get(kapt_code) is not None

        if is_new_complex:
            new_complex_count += 1
            print("  new complex: requesting basic info.")
        elif not has_household_count:
            missing_retry_count += 1
            print("  missing household_count: requesting basic info.")

        if skip_existing and not retry_missing and has_household_count:
            skipped_count += 1
            print("  skipped: household_count already exists.")
            continue

        if list_only:
            complex_row = parse_complex(list_item, {})
            saved += upsert_complexes([complex_row])
            list_only_count += 1
            time.sleep(sleep_seconds)
            continue

        try:
            basic_item = fetch_basic_info(kapt_code)
            if not basic_item:
                raise RuntimeError("Basic info response was empty.")
            complex_row = parse_complex(list_item, basic_item)
            saved += upsert_complexes([complex_row])
            full_info_count += 1
        except Exception as error:
            fallback_row = parse_complex(list_item, {})
            saved += upsert_complexes([fallback_row])
            list_only_count += 1
            print(f"  basic info failed: {type(error).__name__}: {error}")
            print("  saved list info only; household_count will be empty for now.")
            if verbose:
                print(f"  list item: {json.dumps(list_item, ensure_ascii=False)[:500]}")

        time.sleep(sleep_seconds)

    print(
        "Done. "
        f"Saved/updated rows: {saved}. "
        f"Full basic info: {full_info_count}. "
        f"List only: {list_only_count}. "
        f"Skipped existing: {skipped_count}. "
        f"New complexes: {new_complex_count}. "
        f"Missing retries: {missing_retry_count}."
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Collect Seoul apartment complex basic info.")
    parser.add_argument("--limit", type=int, help="Small test limit")
    parser.add_argument("--sleep", type=float, default=0.05, help="Seconds to wait between API calls")
    parser.add_argument("--verbose", action="store_true", help="Print sample list data when basic info fails")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refresh every complex, including rows that already have household_count",
    )
    parser.add_argument(
        "--retry-missing",
        action="store_true",
        help="Only request new complexes and rows that do not have household_count yet",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Save apartment list data only and skip household/basic-info API calls",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    collect_complexes(
        limit=args.limit,
        sleep_seconds=args.sleep,
        verbose=args.verbose,
        list_only=args.list_only,
        skip_existing=not args.force,
        retry_missing=args.retry_missing,
    )
