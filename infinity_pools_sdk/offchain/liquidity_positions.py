import json
from typing import Dict, List, Optional

import requests

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

    except requests.exceptions.HTTPError as errh:
        print(f"Http Error fetching positions for {wallet_address}: {errh}")
        if hasattr(errh, 'response') and errh.response is not None:
            print(f"Response content: {errh.response.content.decode(errors='ignore')[:500]}...")
    except requests.exceptions.RequestException as e:
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
