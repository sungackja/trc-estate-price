import requests


print("Starting internet connection test...\n")

try:
    response = requests.get("https://www.naver.com", timeout=10)

    if response.status_code == 200:
        print("Internet connection is working.")
        print("The public data API server may be unavailable, delayed, or rejecting the request.")
    else:
        print(f"Connected, but received an unexpected status code: {response.status_code}")
except requests.exceptions.RequestException as error:
    print("Internet connection test failed.")
    print("Check your network, firewall, security program, or VPN settings.")
    print(f"Error: {error}")
