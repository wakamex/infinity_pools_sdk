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

"""Fetches the current liquidity ratio for a given token pair from the Infinity Pools API."""

import json
import sys
from decimal import Decimal, getcontext
from typing import Optional, Tuple

import requests
from requests.exceptions import HTTPError

# Set precision for Decimal calculations
getcontext().prec = 50

# Token Addresses 
SUSD_E_ADDRESS = "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452"
WST_ETH_ADDRESS = "0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2"
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
CRVUSD_BASE_ADDRESS = "0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E"
WETH_BASE_ADDRESS = "0x4200000000000000000000000000000000000006"

# Market configurations
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
    base_size: Optional[str] = None,
    quote_size: Optional[str] = None,
    api_base_url: str = API_BASE_URL,
) -> Optional[Tuple[Decimal, Decimal]]:
    """Fetch liquidity ratio from the Infinity Pools API.
    
    Returns: A tuple (token0_amount, token1_amount) or None if an error occurs.
    """
    # API URL format: /liquidityRatio/{token1_address}/{token0_address}/{lower_price}/{upper_price}
    url = f"{api_base_url}/{token1_address}/{token0_address}/{lower_price}/{upper_price}"
    
    # Prepare query parameters
    query_params = {}
    if base_size: query_params["baseSize"] = base_size
    if quote_size: query_params["quoteSize"] = quote_size

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Accept": "application/json",
        "Origin": "https://infinitypools.finance",
        "Referer": "https://infinitypools.finance/",
    }

    # Log the URL with query parameters
    log_url = url + ("?" + "&".join([f"{k}={v}" for k, v in query_params.items()]) if query_params else "")
    print(f"Requesting URL for ratio: {log_url}", file=sys.stderr)
    
    try:
        response = requests.get(url, headers=headers, params=query_params or None)
        response.raise_for_status()
        data = response.json()
        return Decimal(data["quoteSize"]), Decimal(data["baseSize"])
    except Exception as e:
        print(f"Error fetching liquidity ratio: {e}\nURL: {log_url}", file=sys.stderr)
        return None

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Fetch liquidity ratio for a token pair and price range.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Market selection arguments
    market_group = parser.add_argument_group('Market Selection')
    market_group.add_argument("--market", type=str, choices=list(MARKETS.keys()), help="Predefined market pair to use")
    market_group.add_argument("--token0", type=str, help="Address of token0 (if no market selected)")
    market_group.add_argument("--token1", type=str, help="Address of token1 (if no market selected)")

    # Price range arguments
    parser.add_argument("--lowerPrice", type=str, default=DEFAULT_LOWER_PRICE, help="Lower price of the range")
    parser.add_argument("--upperPrice", type=str, default=DEFAULT_UPPER_PRICE, help="Upper price of the range")

    # Token amount arguments
    size_group = parser.add_argument_group('Size Specification (mutually exclusive)')
    size_group.add_argument("--baseSize", type=str, help="Amount of base tokens (token0)")
    size_group.add_argument("--quoteSize", type=str, help="Amount of quote tokens (token1)")

    args = parser.parse_args()

    # Determine token addresses based on market or direct input
    token0_address = args.token0
    token1_address = args.token1
    token0_name = "token0"
    token1_name = "token1"
    
    if args.market:
        if args.market not in MARKETS:
            print(f"Error: Market '{args.market}' not defined in MARKETS dictionary.")
            return
        market_config = MARKETS[args.market]
        token0_address = market_config["token0_address"]
        token1_address = market_config["token1_address"]
        token0_name, token1_name = args.market.split('/')
        print(f"Using market: {args.market} (Token0: {token0_address}, Token1: {token1_address})\n")

    # Validate required parameters
    if not token0_address or not token1_address:
        parser.error("Either --market or both --token0 and --token1 must be specified.")
    if args.baseSize and args.quoteSize:
        parser.error("Only one of --baseSize or --quoteSize can be specified, not both.")

    # Fetch liquidity ratio
    ratio_data = fetch_liquidity_ratio(
        token0_address, token1_address,
        args.lowerPrice, args.upperPrice,
        base_size=args.baseSize, quote_size=args.quoteSize
    )

    if not ratio_data:
        print("Failed to fetch liquidity ratio.", file=sys.stderr)
        return

    # Process and display results
    token0_amount, token1_amount = ratio_data

    print("\nInterpreted API Normalized Ratio:")
    print(f"The API indicates that {token0_amount} units of token0 ({token0_address}) are equivalent to {token1_amount} units of token1 ({token1_address}).")

    if token0_amount != Decimal("0") and token1_amount != Decimal("0"):
        # Calculate price ratios
        token0_per_token1 = token0_amount / token1_amount
        
        print("\nDerived Prices from API ratio:")
        print(f"  1 {token1_name} = {1/token0_per_token1:.8f} {token0_name}")
        print(f"  1 {token0_name} = {token0_per_token1:.8f} {token1_name}")
    else:
        print("\nCould not derive prices: one of the token amounts from API was zero.", file=sys.stderr)


if __name__ == "__main__":
    main()
