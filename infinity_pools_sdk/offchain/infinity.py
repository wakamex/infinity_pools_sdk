"""Fetches the current liquidity ratio for a given pair of assets and price range from the Infinity Pools API.

This script demonstrates querying the Infinity Pools API's liquidity ratio endpoint.
It can be used to determine the proportional amount of one token relative to another
for a specified liquidity range, based on the API's current view of the pool's state.

--- Official Endpoint Documentation ---

## Get Liquidity Ratio

Get the required ratio of tokens to be deposited when providing liquidity that crosses the pool price.

### Endpoint

`GET liquidityRatio/:baseAsset/:quoteAsset`

Path parameters are used for baseAsset and quoteAsset. Optional query parameters include
`upperPrice`, `lowerPrice`, `baseSize`, and `quoteSize`.
Example: `/liquidityRatio/{token0_address}/{token1_address}?lowerPrice={lower_price_val}&upperPrice={upper_price_val}`

### Request Parameters

| Parameter  | Type   | Description                                                                                                                               |
|------------|--------|-------------------------------------------------------------------------------------------------------------------------------------------|
| baseAsset  | string | (Path Parameter) The base asset for the market. Can be the symbol or contract address.                                                     |
| quoteAsset | string | (Path Parameter) The quote asset for the market. Can be the symbol or contract address.                                                    |
| upperPrice | string | (Query Parameter, Optional) The upper bound price. Must be a number in the set: 1.01^n, -2048 <= n <= 2048. Defaults to 'Infinity'.        |
| lowerPrice | string | (Query Parameter, Optional) The lower bound price. Must be a number in the set: 1.01^n, -2048 <= n <= 2048. Defaults to '0'.              |
| baseSize   | string | (Query Parameter, Optional) The amount of base tokens. Only one of `baseSize` or `quoteSize` should be provided.                            |
| quoteSize  | string | (Query Parameter, Optional) The amount of quote tokens. Only one of `baseSize` or `quoteSize` should be provided.                          |

*Note on prices: See [Notion link](https://www.notion.so/2e8ed3b223514b9ea0f0cb489bd74622?pvs=21) for details on price formatting.*

### Response Body

```json
{
  "baseSize": "1",
  "quoteSize": "3000"
}
```

| Attribute | Type   | Description                             |
|-----------|--------|-----------------------------------------|
| baseSize  | string | The amount of base tokens to deposit.   |
| quoteSize | string | The amount of quote tokens to deposit.  |

--- Script Usage Examples ---

Command-line arguments for this script allow specifying:
- A predefined market (e.g., "sUSDe/wstETH") to automatically use its known token addresses.
- Token addresses for baseAsset (token0) and quoteAsset (token1) directly.
- `lowerPrice` and `upperPrice` for the liquidity range (defaults to "0" and "Infinity" for full range).
- `input_amount` and `input_token` to specify a size for one of the tokens (mimicking `baseSize` or `quoteSize`).

Example for a predefined market (sUSDe/wstETH, default full range, default 1.0 input for token0):
    python infinity_pools_sdk/offchain/infinity.py --market sUSDe/wstETH

Example with explicit parameters (token addresses, prices, and an input amount for token0):
    python infinity_pools_sdk/offchain/infinity.py \
        --token0 0xYourToken0Address \
        --token1 0xYourToken1Address \
        --lowerPrice "1000" \
        --upperPrice "2000" \
        --input-amount 5.5 \
        --input-token token0

Example run output for the sUSDe/wstETH pool, full range, with 1.0 sUSDe (token0) input:
Requesting URL: https://prod.api.infinitypools.finance/liquidityRatio/0xc1cb.../0x211cc...?baseSize=1.0
------------------------------
Status Code: 200
Raw Response JSON:
{
  "baseSize": "1.0",
  "quoteSize": "0.0003909391093384665"
}
Interpreted API Normalized Ratio:
For 1.0 of token0 (sUSDe), you get 0.0003909391093384665 of token1 (wstETH).
Derived Prices:
  1 token1 (wstETH) = 2557.945... token0 (sUSDe)
  1 token0 (sUSDe) = 0.000390... token1 (wstETH)
"""

import json
import sys
from decimal import Decimal, getcontext
from typing import Optional

import requests
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
)
from requests.exceptions import (
    HTTPError,
    RequestException,
    Timeout,
)

# Set precision for Decimal calculations
getcontext().prec = 50

# Token Addresses
SUSD_E_ADDRESS = "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452"
WST_ETH_ADDRESS = "0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2"
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
CRVUSD_BASE_ADDRESS = "0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E"
WETH_BASE_ADDRESS = "0x4200000000000000000000000000000000000006"

MARKETS = {
    "sUSDe/wstETH": {
        "token0_address": SUSD_E_ADDRESS,
        "token1_address": WST_ETH_ADDRESS,
        "token0_decimals": 18,
        "token1_decimals": 18
    },
    "USDC/wETH": {
        "token0_address": USDC_BASE_ADDRESS,
        "token1_address": WETH_BASE_ADDRESS,
        "token0_decimals": 1,
        "token1_decimals": 18
    },
    "crvUSD/wETH": {
        "token0_address": CRVUSD_BASE_ADDRESS,
        "token1_address": WETH_BASE_ADDRESS,
        "token0_decimals": 18,
        "token1_decimals": 18
    },
}

DEFAULT_LOWER_PRICE = "0"
DEFAULT_UPPER_PRICE = "Infinity"
API_BASE_URL = "https://prod.api.infinitypools.finance/liquidityRatio"

def fetch_liquidity_ratio(
    token0_address: str,
    token1_address: str,
    lower_price: str = DEFAULT_LOWER_PRICE,
    upper_price: str = DEFAULT_UPPER_PRICE,
    base_size: Optional[str] = None,  # New parameter
    quote_size: Optional[str] = None, # New parameter
    api_base_url: str = API_BASE_URL,
) -> tuple[Decimal, Decimal] | None:
    """Fetch liquidity ratio from the Infinity Pools API.

    Args:
        token0_address: Address of token0.
        token1_address: Address of token1.
        lower_price: Lower price of the range for the API query.
        upper_price: Upper price of the range for the API query.
        base_size: Optional amount of base_size to query with.
        quote_size: Optional amount of quote_size to query with.
        api_base_url: The base URL for the API.

    Returns:
        A tuple (quote_size_token0, base_size_token1) or None if an error occurs.
    """
    # Construct the URL with token addresses and price range in the path
    # Note: API expects token addresses in reverse order compared to our function parameter names
    # Format: /liquidityRatio/{token1_address}/{token0_address}/{lower_price}/{upper_price}
    url = f"{api_base_url}/{token1_address}/{token0_address}/{lower_price}/{upper_price}"
    
    # Prepare query parameters
    query_params = {}
    if base_size:
        query_params["baseSize"] = base_size
    if quote_size:
        query_params["quoteSize"] = quote_size

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://infinitypools.finance",
        "Referer": "https://infinitypools.finance/",
    }

    # Log the URL with query parameters if any
    log_url = url
    if query_params:
        log_url += "?" + "&".join([f"{k}={v}" for k, v in query_params.items()])
    print(f"Requesting URL for ratio: {log_url}", file=sys.stderr)
    
    try:
        response = requests.get(url, headers=headers, params=query_params if query_params else None)
        response.raise_for_status()
        data = response.json()
        
        response_quote_size_token0 = Decimal(data["quoteSize"])
        response_base_size_token1 = Decimal(data["baseSize"])
        return response_quote_size_token0, response_base_size_token1
    except HTTPError as errh:
        print(f"Http Error fetching ratio: {errh}\nURL: {log_url}\nResponse: {errh.response.text if errh.response else 'No response text'}", file=sys.stderr)
    except requests.exceptions.RequestException as e:
        print(f"Error during API request for ratio: {e}\nURL: {log_url}", file=sys.stderr)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response from API for ratio.\nURL: {log_url}", file=sys.stderr)
    except KeyError as e:
        print(f"Error: Missing key {e} in API response for ratio.\nURL: {log_url}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred while fetching ratio: {e}\nURL: {log_url}", file=sys.stderr)
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Fetch liquidity ratio for a token pair and price range.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    market_group = parser.add_argument_group('Market Selection')
    market_group.add_argument(
        "--market",
        type=str,
        choices=list(MARKETS.keys()),
        help="Predefined market pair to use. This will set token0 and token1.",
        required=False,
    )
    market_group.add_argument(
        "--token0",
        type=str,
        help="Address of token0. Required if --market is not specified.",
        required=False,
    )
    market_group.add_argument(
        "--token1",
        type=str,
        help="Address of token1. Required if --market is not specified.",
        required=False,
    )

    parser.add_argument(
        "--lowerPrice",
        type=str,
        default=DEFAULT_LOWER_PRICE,
        help="Lower price of the range.",
    )
    parser.add_argument(
        "--upperPrice",
        type=str,
        default=DEFAULT_UPPER_PRICE,
        help="Upper price of the range.",
    )

    size_group = parser.add_argument_group('Optional Size Specification (mutually exclusive)')
    size_group.add_argument(
        "--baseSize",
        type=str,
        help="Optional: Amount of base tokens (token0) to specify for the ratio query.",
        required=False,
    )
    size_group.add_argument(
        "--quoteSize",
        type=str,
        help="Optional: Amount of quote tokens (token1) to specify for the ratio query.",
        required=False,
    )

    args = parser.parse_args()

    token0_address = args.token0
    token1_address = args.token1
    lower_price = args.lowerPrice
    upper_price = args.upperPrice

    token0_decimals_for_market = 18 
    token1_decimals_for_market = 18 

    if args.market:
        if args.market not in MARKETS:
            print(f"Error: Market '{args.market}' not defined in MARKETS dictionary.")
            return
        market_config = MARKETS[args.market]
        token0_address = market_config["token0_address"]
        token1_address = market_config["token1_address"]
        token0_decimals_for_market = market_config["token0_decimals"]
        
        print(f"Using market: {args.market} (Token0: {token0_address}, Token1: {token1_address})\n")

    if not token0_address or not token1_address:
        parser.error("Either --market or both --token0 and --token1 must be specified.")

    if args.baseSize and args.quoteSize:
        parser.error("Only one of --baseSize or --quoteSize can be specified, not both.")

    ratio_data = fetch_liquidity_ratio(
        token0_address,
        token1_address,
        lower_price,
        upper_price,
        base_size=args.baseSize,
        quote_size=args.quoteSize
    )

    if ratio_data is None:
        print("Failed to fetch liquidity ratio.", file=sys.stderr)
        return

    # The API returns (quoteSize, baseSize) relative to token params in URL
    # Since we reversed the token order in the URL, we need to interpret these correctly
    token0_amount, token1_amount = ratio_data

    print("\nInterpreted API Normalized Ratio:")
    print(f"The API indicates that {token0_amount} units of token0 ({token0_address}) are equivalent to {token1_amount} units of token1 ({token1_address}).")

    token0_name_for_print = args.market.split('/')[0] if args.market else "token0"
    token1_name_for_print = args.market.split('/')[1] if args.market else "token1"

    if token0_amount != Decimal("0") and token1_amount != Decimal("0"):
        # For sUSDe (token0) and wstETH (token1) in our example
        # If API returns token0 = 0.00038... and token1 = 1.0, then:
        # 1 wstETH = ~2,582 sUSDe (derived from 1.0/0.00038...)
        # 1 sUSDe = ~0.00038... wstETH (derived directly from API response)
        token1_per_token0 = token1_amount / token0_amount  # How many token1 per 1 token0
        token0_per_token1 = token0_amount / token1_amount  # How many token0 per 1 token1
        
        print("\nDerived Prices from API ratio:")
        # In the sUSDe/wstETH example:
        # 1 wstETH (token1) = 2582.65 sUSDe (token0)
        print(f"  1 {token1_name_for_print} = {1/token0_per_token1:.8f} {token0_name_for_print}")
        # 1 sUSDe (token0) = 0.00038... wstETH (token1)
        print(f"  1 {token0_name_for_print} = {token0_per_token1:.8f} {token1_name_for_print}")
    else:
        print("\nCould not derive prices: one of the token amounts from API was zero.", file=sys.stderr)


if __name__ == "__main__":
    main()
