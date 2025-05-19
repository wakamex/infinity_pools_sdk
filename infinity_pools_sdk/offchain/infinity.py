import requests
import json # For pretty printing the JSON response

# The URL with path parameters
# It's often good practice to build such URLs if parameters might change,
# but for a direct translation, we can use the full string.
param1 = "0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2"
param2 = "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452"
param3 = "0"
param4 = "Infinity"

# Constructing the URL with f-string for clarity if parameters were dynamic
# url = f"https://prod.api.infinitypools.finance/liquidityRatio/{param1}/{param2}/{param3}/{param4}"

# Or directly using the provided URL:
url = "https://prod.api.infinitypools.finance/liquidityRatio/0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2/0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452/0/Infinity"


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Origin": "https://infinitypools.finance",
    "DNT": "1",
    "Connection": "keep-alive",
    "Referer": "https://infinitypools.finance/",
    "Cookie": "wallet=0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "TE": "trailers"
}

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

    print(f"Status Code: {response.status_code}")
    print(f"Requested URL: {response.url}") # To confirm the URL used

    # Check if the response is JSON
    if "application/json" in response.headers.get("Content-Type", ""):
        try:
            data = response.json()
            print("Response JSON:")
            print(json.dumps(data, indent=2)) # Pretty print JSON
        except json.JSONDecodeError:
            print("Failed to decode JSON. Response Text:")
            print(response.text)
    else:
        print("Response Text:")
        print(response.text)

except requests.exceptions.HTTPError as errh:
    print(f"Http Error: {errh}")
    print(f"Response content: {response.content.decode(errors='ignore')}")
except requests.exceptions.ConnectionError as errc:
    print(f"Error Connecting: {errc}")
except requests.exceptions.Timeout as errt:
    print(f"Timeout Error: {errt}")
except requests.exceptions.RequestException as err:
    print(f"Oops: Something Else: {err}")
