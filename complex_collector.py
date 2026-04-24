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
from database import init_db, upsert_complexes


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
        items = items.get("item") or []
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
        return items[0]
    body = extract_body(data)
    if isinstance(body, dict) and any(key.startswith("kapt") or key == "kaptdaCnt" for key in body):
        return body
    return {}


def value(data, key, default=""):
    if not isinstance(data, dict):
        return default
    return clean_text(data.get(key), default)


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
        "bjd_code": value(basic_item, "bjdCode", value(list_item, "bjdCode")),
        "household_count": to_int(basic_item.get("kaptdaCnt")) if isinstance(basic_item, dict) else None,
        "dong_count": to_int(basic_item.get("kaptDongCnt")) if isinstance(basic_item, dict) else None,
        "used_date": value(basic_item, "kaptUsedate"),
        "address": value(basic_item, "kaptAddr"),
        "road_address": value(basic_item, "doroJuso"),
        "raw_xml": json.dumps(basic_item, ensure_ascii=False),
    }


def collect_complexes(limit=None, sleep_seconds=0.05, verbose=False, list_only=False):
    init_db()
    list_items = fetch_seoul_complex_list()
    if limit:
        list_items = list_items[:limit]

    saved = 0
    full_info_count = 0
    list_only_count = 0
    for index, list_item in enumerate(list_items, start=1):
        kapt_code = value(list_item, "kaptCode")
        kapt_name = value(list_item, "kaptName")
        print(f"[{index}/{len(list_items)}] {kapt_code} {kapt_name}")

        if list_only:
            complex_row = parse_complex(list_item, {})
            saved += upsert_complexes([complex_row])
            list_only_count += 1
            time.sleep(sleep_seconds)
            continue

        try:
            basic_item = fetch_basic_info(kapt_code)
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
        f"List only: {list_only_count}."
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Collect Seoul apartment complex basic info.")
    parser.add_argument("--limit", type=int, help="Small test limit")
    parser.add_argument("--sleep", type=float, default=0.05, help="Seconds to wait between API calls")
    parser.add_argument("--verbose", action="store_true", help="Print sample list data when basic info fails")
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
    )
