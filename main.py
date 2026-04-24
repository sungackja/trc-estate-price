import os
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv


load_dotenv()

API_KEY = os.getenv("MOLIT_API_KEY")
BASE_URL = (
    "https://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/"
    "RTMSOBJSvc/getRTMSDataSvcAptTradeDev"
)

TAG_APARTMENT = "\uc544\ud30c\ud2b8"
TAG_PRICE = "\uac70\ub798\uae08\uc561"
TAG_DAY = "\uc77c"


def get_apartment_data(lawd_cd, deal_ym):
    if not API_KEY:
        print("MOLIT_API_KEY is missing. Add it to your .env file.")
        return

    print(f"[{deal_ym}] Requesting apartment data for LAWD_CD={lawd_cd}...\n")

    params = {
        "serviceKey": API_KEY,
        "pageNo": 1,
        "numOfRows": 10,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ym,
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=15)
    except requests.exceptions.RequestException as error:
        print(f"Request failed: {error}")
        return

    if response.status_code != 200:
        print(f"HTTP request failed. Status code: {response.status_code}")
        print(response.text[:500])
        return

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        print("Could not parse XML response.")
        print(response.text[:500])
        return

    result_code = root.findtext(".//resultCode")
    result_msg = root.findtext(".//resultMsg")
    if result_code and result_code != "00":
        print(f"API error: {result_code} / {result_msg}")
        return

    items = root.findall(".//item")
    if not items:
        print("No trade data found for this month, or the API key is not active yet.")
        return

    print(f"Loaded {len(items)} records. Showing up to {len(items)} records.\n")

    for item in items:
        apt_name = (item.findtext(TAG_APARTMENT) or "Unknown").strip()
        price = (item.findtext(TAG_PRICE) or "0").strip()
        day = (item.findtext(TAG_DAY) or "").strip()

        print(f"Apartment: {apt_name}")
        print(f"Price: {price} ten-thousand KRW")
        print(f"Deal date: {deal_ym[:4]}-{deal_ym[4:]}-{day}")
        print("-" * 30)


if __name__ == "__main__":
    get_apartment_data("11680", "202403")
