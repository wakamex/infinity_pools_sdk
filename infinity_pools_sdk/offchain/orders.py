"""Fetches and displays historical order data for a specific wallet from the Infinity Pools API.

This script queries the `/orders` endpoint using a hardcoded wallet address
in the cookie. It prints the JSON response, which is typically a list of order
objects, each detailing a past trade.

Example run output (for a test wallet, showing first order only):
--------------------------------------------
Status Code: 200
Response JSON:
[
  {
    "id": "34116754-5889-40e0-90a9-d7e96bcbd6a7",
    "status": "FILLED",
    "baseAsset": "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452",
    "quoteAsset": "0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2",
    "side": "LONG",
    "price": 2455.1501699786522,
    "size": 0.9019874861260282,
    "filledPrice": 1640.223796205894,
    "collateralToken": "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452",
    "collateralAmount": 0.05,
    "filledAt": 1744224309717,
    "expiration": 1744227908278,
    "type": "MARKET",
    "hourlyInterestRateTolerance": null,
    "cancelReason": null
  }
  // ... (other orders truncated for brevity)
]
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

# The new URL for fetching orders
url = "https://prod.api.infinitypools.finance/orders"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Origin": "https://infinitypools.finance",
    "DNT": "1",
    "Connection": "keep-alive",
    "Referer": "https://infinitypools.finance/",
    # Same cookie as before - be mindful if this is session-specific and might expire
    "Cookie": "wallet=0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "TE": "trailers",
}

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

    print(f"Status Code: {response.status_code}")

    # Check if the response is JSON
    if "application/json" in response.headers.get("Content-Type", ""):
        try:
            data = response.json()
            print("Response JSON:")
            print(json.dumps(data, indent=2))  # Pretty print JSON
        except json.JSONDecodeError:
            print("Failed to decode JSON. Response Text:")
            print(response.text)
    else:
        print("Response Text:")
        print(response.text)

except HTTPError as errh:
    print(f"Http Error: {errh}")
    print(f"Response content: {response.content.decode(errors='ignore')}")  # Try to decode for better error visibility
except RequestsConnectionError as errc:
    print(f"Error Connecting: {errc}")
except Timeout as errt:
    print(f"Timeout Error: {errt}")
except RequestException as err:
    print(f"Oops: Something Else: {err}")
