"""Fetches and displays current trading positions for a specific wallet from the Infinity Pools API.

This script queries the `/trading_positions` endpoint using a hardcoded wallet
address in the cookie. It prints the JSON response, which is a list of trading
position objects detailing current or recent trades.

Example run output (for a test wallet, showing one closed position):
--------------------------------------------
Status Code: 200
Response JSON:
[
  {
    "baseAsset": "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452",
    "quoteAsset": "0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2",
    "status": "CLOSED",
    "side": "SHORT",
    "targetSize": 0.0,
    "currentSize": 0.0,
    "hourlyInterestRate": 0.0,
    "hourlyInterestRateTolerance": null,
    "interestPaid": 0.3071848861219507,
    "totalFundingPaid": 0.3071848861219507,
    "unrealizedPnl": -0.0,
    "realizedPnl": -0.9777071138044684,
    "inTheMoneySize": 0.0,
    "unwindPrice": null,
    "protectedFor": null,
    "leverage": 0.0,
    "entryPrice": 2473.066122640429,
    "closePrice": 2475.718521714498,
    "openedAt": 1747444836943,
    "closedAt": 1747445867595
  }
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

url = "https://prod.api.infinitypools.finance/trading_positions?"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br, zstd",  # requests handles gzip/deflate automatically
    "Origin": "https://infinitypools.finance",
    "DNT": "1",
    "Connection": "keep-alive",  # requests handles this by default
    "Referer": "https://infinitypools.finance/",
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

    # Check if the response is JSON (based on the Accept header)
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
    print(f"Response content: {response.content.decode(errors='ignore')}")
except RequestsConnectionError as errc:
    print(f"Error Connecting: {errc}")
except Timeout as errt:
    print(f"Timeout Error: {errt}")
except RequestException as err:
    print(f"Oops: Something Else: {err}")
