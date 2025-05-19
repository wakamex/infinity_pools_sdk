"""Fetches and displays existing liquidity positions for a given wallet address from the Infinity Pools API.

This script defines a function `get_liquidity_positions_by_wallet` and demonstrates
its usage by fetching positions for a hardcoded test wallet address.

Example run output (for a test wallet):
--------------------------------------------
Fetching positions for test wallet: 0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207
Successfully fetched 3 positions.
First position (if any):
{
  "id": "0x00c3a51f01bc43b1a41b1a1ccaa64c0578cf40ba1f0000000000000000000061",
  "lpNum": 97,
  "baseAsset": "0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2",
  "quoteAsset": "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452",
  "status": "CLOSING",
  "lowerPrice": 0.0005354513853550592,
  "upperPrice": 0.0006341374484607739,
  "originalBaseSize": 23.9902,
  "originalQuoteSize": 0.025174798964847946,
  "lockedFor": 0.0,
  "lockedBaseSize": 9.329315046459516,
  "availableBaseSize": 5.752457854950193,
  "baseUnclaimedFees": 0.0,
  "baseClaimedFees": 1.3960268390757875,
  "lockedQuoteSize": 0.0,
  "availableQuoteSize": 1.5e-17,
  "quoteUnclaimedFees": 0.0,
  "quoteClaimedFees": 0.000647539681231489,
  "canDrain": true,
  "openedAt": 1744226057,
  "closedAt": 1747429373,
  "depletedAt": null,
  "withdrawnAt": null,
  "aggregatedApr": 18.0,
  "aggregatedApr7D": 18.00168902036051,
  "aggregatedUtilization": 2.9280903448446883e-26
}
--------------------------------------------
"""
import json
from typing import Dict, List, Optional

import requests
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
)
from requests.exceptions import (
    HTTPError,
    RequestException,
    Timeout,
)

API_URL = "https://prod.api.infinitypools.finance/liquidity_positions"

def get_liquidity_positions_by_wallet(wallet_address: str) -> Optional[List[Dict]]:
    """Fetch liquidity positions for a given wallet address from the Infinity Pools API.

    Args:
        wallet_address: The wallet address (hex string) to fetch positions for.

    Returns:
        A list of position dictionaries if successful, otherwise None.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Origin": "https://infinitypools.finance",
        "DNT": "1",
        "Connection": "keep-alive",
        "Referer": "https://infinitypools.finance/",
        "Cookie": f"wallet={wallet_address}",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "TE": "trailers"
    }

    try:
        response = requests.get(API_URL, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

        if "application/json" in response.headers.get("Content-Type", ""):
            return response.json()
        else:
            print(f"Error: Response from API was not JSON. URL: {API_URL}")
            print(f"Response text: {response.text[:500]}...")
            return None

    except HTTPError as errh:
        print(f"Http Error fetching positions for {wallet_address}: {errh}")
        if hasattr(errh, 'response') and errh.response is not None:
            print(f"Response content: {errh.response.content.decode(errors='ignore')[:500]}...")
    except RequestsConnectionError as errc:
        print(f"Connection Error fetching positions for {wallet_address}: {errc}")
    except Timeout as errt:
        print(f"Timeout Error fetching positions for {wallet_address}: {errt}")
    except RequestException as e:
        print(f"Request Exception fetching positions for {wallet_address}: {e}")
    except json.JSONDecodeError as e:
        # This might happen if content-type is json but body is not valid json
        print(f"JSON Decode Error for {wallet_address}: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"Response text: {response.text[:500]}...")
    return None

if __name__ == "__main__":
    # Example usage: Replace with an address you want to test
    test_wallet_address = "0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207" 
    print(f"Fetching positions for test wallet: {test_wallet_address}")
    positions = get_liquidity_positions_by_wallet(test_wallet_address)
    if positions is not None:
        print(f"Successfully fetched {len(positions)} positions.")
        print("First position (if any):")
        print(json.dumps(positions[0] if positions else {}, indent=2))
    else:
        print("Failed to fetch positions for the test wallet.")
