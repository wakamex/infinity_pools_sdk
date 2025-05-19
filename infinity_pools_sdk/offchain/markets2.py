"""Fetches and displays data for all available markets from the Infinity Pools API, with the 'adjustPrice=true' parameter.

This script queries the `/markets` endpoint, including `adjustPrice=true` in the
request parameters. It prints the JSON response, which is typically a list of
market objects. The 'adjustPrice' parameter may influence the returned price
data or other calculated metrics.

Example run output:
--------------------------------------------
Status Code: 200
Full requested URL: https://prod.api.infinitypools.finance/markets?adjustPrice=true
Response JSON:
[
  {
    "chainId": 8453,
    "goodTillBlkno": 30444826,
    "tokens": [
      "0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2",
      "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
    ],
    "defaultBase": "0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2",
    "defaultQuote": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
    "address": "0x2175a80b99ff2e945ccce92fd0365f0cb5c5e98d",
    "price": 1.174585720074999,
    "volume24H": 308184.42353792733,
    "change24H": 0.17737806862077973,
    "openInterest": 0.0,
    "tvl": 2535720.5032572355,
    "apr7D": 9.009764798839365,
    "utilization": 0.46581645693794743
  },
  {
    "chainId": 8453,
    "goodTillBlkno": 30444826,
    "tokens": [
      "0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2",
      "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452"
    ],
    "defaultBase": "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452",
    "defaultQuote": "0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2",
    "address": "0xc3a51f01bc43b1a41b1a1ccaa64c0578cf40ba1f",
    "price": 0.00040197763392075755,
    "volume24H": 273059.3763363039,
    "change24H": -1.0798217310076028,
    "openInterest": 0.0,
    "tvl": 1090392.3867065802,
    "apr7D": 16.9282816799015,
    "utilization": 0.3856882798222398
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

# Base URL for the markets endpoint
url = "https://prod.api.infinitypools.finance/markets"

# Parameters to be sent in the query string
# requests will append this to the URL as ?adjustPrice=true
params = {
    "adjustPrice": "true"  # Note: parameter values are typically strings
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Origin": "https://infinitypools.finance",
    "DNT": "1",
    "Connection": "keep-alive",
    "Referer": "https://infinitypools.finance/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "TE": "trailers",
}

try:
    # Pass the params dictionary to the requests.get() method
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

    print(f"Status Code: {response.status_code}")
    print(f"Full requested URL: {response.url}")  # You can print this to see the final URL requests constructed

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
    print(f"Response content: {response.content.decode(errors='ignore')}")
except RequestsConnectionError as errc:
    print(f"Error Connecting: {errc}")
except Timeout as errt:
    print(f"Timeout Error: {errt}")
except RequestException as err:
    print(f"Oops: Something Else: {err}")
