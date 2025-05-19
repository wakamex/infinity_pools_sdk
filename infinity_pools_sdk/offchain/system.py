"""Fetches and displays system-wide information from the Infinity Pools API.

This script queries the `/system` endpoint and prints the JSON response.
The response typically includes details such as the current system timestamp,
latest block information, software release details, and various important
contract addresses (e.g., periphery, factory, quoter).

Example run output (structure and key fields):
--------------------------------------------
Status Code: 200
Response JSON:
{
  "currentSystemTimestampMillis": 1747679119386,
  "upSinceTimestampMillis": 1747331106073,
  "chainId": 8453,
  "latestBlockInfo": {
    "blockNumber": 30444885,
    // ... other block details
  },
  "releaseInfo": {
    "gitHash": "bf1765e04723f3325695b7c5e2af23450c2a17c8",
    "imageTag": "v0.1.34"
  },
  "contractAddresses": {
    "peripheryContractAddress": "0xF8FAD01B2902fF57460552C920233682c7c011a7",
    // ... many other contract addresses
  },
  "externalAddresses": {
    // ... external contract addresses
  },
  "systemAccounts": {
    // ... system account addresses
  }
  // ... other top-level keys like peripheryContractAddress, etc.
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

# The URL for fetching system information
url = "https://prod.api.infinitypools.finance/system"

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
    print(f"Response content: {response.content.decode(errors='ignore')}")
except RequestsConnectionError as errc:
    print(f"Error Connecting: {errc}")
except Timeout as errt:
    print(f"Timeout Error: {errt}")
except RequestException as err:
    print(f"Oops: Something Else: {err}")
