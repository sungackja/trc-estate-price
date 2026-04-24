import json
from urllib.parse import urlencode

import requests

from config import APT_BASIC_INFO_API_URLS, APT_INFO_API_KEY, REQUEST_TIMEOUT_SECONDS


KAPT_CODE = "A10021295"

PARAM_VARIANTS = [
    {"kaptCode": KAPT_CODE},
    {"KAPT_CODE": KAPT_CODE},
    {"kapt_code": KAPT_CODE},
    {"aptCode": KAPT_CODE},
    {"kaptCode": KAPT_CODE, "_type": "json"},
    {"kaptCode": KAPT_CODE, "type": "json"},
    {"kaptCode": KAPT_CODE, "returnType": "json"},
]


def mask_url(url):
    if "serviceKey=" not in url:
        return url
    before, after = url.split("serviceKey=", 1)
    for separator in ("&", "%26"):
        if separator in after:
            return before + "serviceKey=***" + separator + after.split(separator, 1)[1]
    return before + "serviceKey=***"


def short_body(response):
    text = response.text.replace("\r", " ").replace("\n", " ").strip()
    return text[:500]


def main():
    if not APT_INFO_API_KEY:
        print("APT_INFO_API_KEY is missing.")
        return

    for endpoint in APT_BASIC_INFO_API_URLS:
        print("=" * 80)
        print(endpoint)
        for key_name in ("serviceKey", "ServiceKey"):
            for variant in PARAM_VARIANTS:
                params = {key_name: APT_INFO_API_KEY, **variant}
                try:
                    response = requests.get(endpoint, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
                except requests.exceptions.RequestException as error:
                    print(f"- {key_name} {json.dumps(variant)}")
                    print(f"  request failed: {type(error).__name__}: {error}")
                    continue

                print(f"- {key_name} {json.dumps(variant)}")
                print(f"  status: {response.status_code}")
                print(f"  url: {mask_url(response.url)}")
                print(f"  body: {short_body(response)}")


if __name__ == "__main__":
    main()
