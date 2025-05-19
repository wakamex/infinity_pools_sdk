"""Fetches historical price bar (candle) data from the Infinity Pools API.

This script makes a GET request to the /pool_price_bars endpoint with
predefined parameters for base asset, quote asset, bar type, and time range.

Example run output (truncated for brevity):
--------------------------------------------
Status Code: 200
Requested URL: https://prod.api.infinitypools.finance/pool_price_bars?baseAsset=0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452&quoteAsset=0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2&barType=CANDLE_1M&startTimeMillis=1746996950000&stopTimeMillis=1747589150000&adjustPrice=false
Response JSON:
{
  "bars": [
    {
      "timestampMillis": 1746996960000,
      "open": 2403.7392754656303,
      "close": 2403.7392754656303,
      "high": 2403.7392754656303,
      "low": 2403.7392754656303,
      "avg": 2403.7392754656303
    },
    // ... many intermediate bars ...
    {
      "timestampMillis": 1747588620000,
      "open": 2634.965496215399,
      "close": 2630.1793448371536,
      "high": 2634.965496215399,
      "low": 2630.1793448371536,
      "avg": 2631.374275885361
    },
    {
      "timestampMillis": 1747589100000,
      "open": 2627.7911282413465,
      "close": 2627.7911282413465,
      "high": 2627.7911282413465,
      "low": 2627.7911282413465,
      "avg": 2627.7911282413465
    }
  ]
}
--------------------------------------------
"""

import json  # For pretty printing the JSON response

import requests
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
)
from requests.exceptions import (
    HTTPError,
    RequestException,
    Timeout,
)

# Base URL for the endpoint
url = "https://prod.api.infinitypools.finance/pool_price_bars"

# Query parameters from the URL
params = {
    "baseAsset": "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452",
    "quoteAsset": "0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2",
    "barType": "CANDLE_1M",
    "startTimeMillis": "1746996950000",  # Note: these are passed as strings
    "stopTimeMillis": "1747589150000",
    "adjustPrice": "false",
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Accept": "*/*",  # As per curl, though often "application/json, text/plain, */*"
    "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br, zstd",  # requests handles gzip/deflate
    "Referer": "https://infinitypools.finance/",
    "Origin": "https://infinitypools.finance",
    "DNT": "1",
    "Connection": "keep-alive",  # requests handles this
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Priority": "u=4",  # This is a hint, may not be strictly necessary for requests to work
    "TE": "trailers",
}

try:
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

    print(f"Status Code: {response.status_code}")
    print(f"Requested URL: {response.url}")  # To see the full URL requests built

    # Check if the response is likely JSON (even with Accept: */*)
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            data = response.json()
            print("Response JSON:")
            print(json.dumps(data, indent=2))  # Pretty print JSON
        except json.JSONDecodeError:
            print("Content-Type was JSON, but failed to decode. Response Text:")
            print(response.text)
    else:
        print("Response Text (Content-Type not JSON):")
        print(response.text)

except HTTPError as errh:
    print(f"Http Error: {errh}")
    if response is not None and response.content:
        print(f"Response content: {response.content.decode(errors='ignore')}")
except RequestsConnectionError as errc:
    print(f"Error Connecting: {errc}")
except Timeout as errt:
    print(f"Timeout Error: {errt}")
except RequestException as err:
    print(f"Oops: Something Else Happened: {err}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
