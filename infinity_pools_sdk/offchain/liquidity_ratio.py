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
from decimal import ROUND_HALF_UP, Context, Decimal, getcontext
from typing import Optional, Tuple

import requests
from requests.exceptions import HTTPError

# Set precision for Decimal calculations
getcontext().prec = 64

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
        "token1_address": WST_ETH_ADDRESS
    },
    "USDC/wETH": {
        "token0_address": USDC_BASE_ADDRESS,
        "token1_address": WETH_BASE_ADDRESS
    },
    "crvUSD/wETH": {
        "token0_address": CRVUSD_BASE_ADDRESS,
        "token1_address": WETH_BASE_ADDRESS
    },
}

DEFAULT_LOWER_PRICE = "0"
DEFAULT_UPPER_PRICE = "Infinity"
API_BASE_URL = "https://prod.api.infinitypools.finance/liquidityRatio"

# Constants for tick-to-price conversion
TICK_PRICE_PRECISION = 100  # Internal precision for decimal calculations
LOWER_PRICE_DECIMAL_PLACES = 64
UPPER_PRICE_DECIMAL_PLACES = 63
# Uniswap V3-style ticks usually range from -887272 to 887272.
# These can be used as min/max if needed, but the "infinity" endpoint logic
# here will primarily rely on lower_tick/upper_tick being None or default
# string price inputs "0" and "Infinity".

def tick_to_price_string(tick: int, num_decimal_places: int, precision: int = TICK_PRICE_PRECISION) -> str:
    """Convert a Uniswap V3-style tick to its corresponding price string.

    The price is rounded to a specific number of decimal places.
    Price = 1.01 ^ tick.

    Args:
        tick: The tick value (integer).
        num_decimal_places: The number of decimal places to round the price to.
        precision: The internal decimal precision for calculation.

    Returns:
        A string representation of the price.
    """
    # Use a local context for precision to avoid changing global context
    ctx = Context(prec=precision)
    base = ctx.create_decimal("1.01")

    price_calculated = ctx.power(base, ctx.create_decimal(tick))

    quantizer_str = '1e-' + str(num_decimal_places)
    quantizer = ctx.create_decimal(quantizer_str)

    price_rounded = price_calculated.quantize(quantizer, rounding=ROUND_HALF_UP)

    return str(price_rounded)


def fetch_liquidity_ratio(
    token0_address: str,
    token1_address: str,
    lower_price_str_input: str = DEFAULT_LOWER_PRICE, # Renamed to avoid confusion
    upper_price_str_input: str = DEFAULT_UPPER_PRICE, # Renamed to avoid confusion
    base_size: Optional[str] = None,
    quote_size: Optional[str] = None,
    api_base_url: str = API_BASE_URL,
    lower_tick: Optional[int] = None,
    upper_tick: Optional[int] = None,
) -> Optional[Tuple[Decimal, Decimal]]:
    """Fetch liquidity ratio from the Infinity Pools API.

    Constructs the URL based on whether ticks or string prices are provided.
    - If lower_tick and upper_tick are provided, they are converted to high-precision
      decimal strings and used in the path:
      /liquidityRatio/{token0_address}/{token1_address}/{lower_price_decimal_str}/{upper_price_decimal_str}
    - If ticks are not provided AND string prices are "0" and "Infinity" (default),
      the /infinity endpoint is used:
      /liquidityRatio/{token0_address}/{token1_address}/0/Infinity
    - Otherwise (custom string prices, no ticks), query parameters are used:
      /liquidityRatio/{token0_address}/{token1_address}?lowerPrice=X&upperPrice=Y

    Args:
        token0_address: Contract address of the first token.
        token1_address: Contract address of the second token.
        lower_price_str_input: Lower price boundary as a string (e.g., "0", "1000.5").
                               Defaults to "0".
        upper_price_str_input: Upper price boundary as a string (e.g., "Infinity", "2000.75").
                               Defaults to "Infinity".
        base_size: Optional amount of token0.
        quote_size: Optional amount of token1.
        api_base_url: Base URL for the API endpoint.
        lower_tick: Optional lower tick for the price range.
        upper_tick: Optional upper tick for the price range.

    Returns:
        A tuple (quote_size_decimal, base_size_decimal) or None if an error occurs.
        Note: The API returns `baseSize` and `quoteSize`. The tuple order might seem
        reversed, but it aligns with typical (amount_token1, amount_token0) pattern if
        token0 is base and token1 is quote.
    """
    query_params = {}
    if base_size:
        query_params["baseSize"] = base_size
    if quote_size:
        query_params["quoteSize"] = quote_size

    # Determine the API URL path structure
    if lower_tick is not None and upper_tick is not None:
        # Finite range specified by ticks, convert ticks to high-precision price strings
        actual_lower_price_str = tick_to_price_string(lower_tick, LOWER_PRICE_DECIMAL_PLACES)
        actual_upper_price_str = tick_to_price_string(upper_tick, UPPER_PRICE_DECIMAL_PLACES)
        url = f"{api_base_url}/{token0_address}/{token1_address}/{actual_lower_price_str}/{actual_upper_price_str}"
    elif lower_price_str_input == DEFAULT_LOWER_PRICE and upper_price_str_input == DEFAULT_UPPER_PRICE:
        # Full range (0 to Infinity) uses the /infinity endpoint
        url = f"{api_base_url}/{token0_address}/{token1_address}/0/Infinity"
    else:
        # Custom string prices, use query parameters
        url = f"{api_base_url}/{token0_address}/{token1_address}"
        if lower_price_str_input != DEFAULT_LOWER_PRICE:
            query_params["lowerPrice"] = lower_price_str_input
        if upper_price_str_input != DEFAULT_UPPER_PRICE:
            query_params["upperPrice"] = upper_price_str_input
            
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Accept": "application/json",
        "Origin": "https://infinitypools.finance",
        "Referer": "https://infinitypools.finance/",
    }

    log_url = url + (("?" + "&".join([f"{k}={v}" for k, v in query_params.items()])) if query_params else "")
    print(f"Requesting URL for ratio: {log_url}", file=sys.stderr)

    try:
        response = requests.get(url, headers=headers, params=query_params if query_params else None)
        response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
        data = response.json()
        # The API returns "baseSize" and "quoteSize".
        return Decimal(data["baseSize"]), Decimal(data["quoteSize"])
    except HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - {response.status_code} {response.reason}\nURL: {log_url}\nResponse text: {response.text}", file=sys.stderr)
    except requests.ConnectionError as conn_err:
        print(f"Connection error occurred: {conn_err}\nURL: {log_url}", file=sys.stderr)
    except requests.Timeout as timeout_err:
        print(f"Timeout error occurred: {timeout_err}\nURL: {log_url}", file=sys.stderr)
    except requests.RequestException as req_err:
        print(f"An unexpected error occurred with the request: {req_err}\nURL: {log_url}", file=sys.stderr)
    except json.JSONDecodeError:
        print(f"Error decoding JSON response from server.\nURL: {log_url}\nResponse text: {response.text if 'response' in locals() else 'N/A'}", file=sys.stderr)
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred: {e}\nURL: {log_url}", file=sys.stderr)
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
    parser.add_argument("--upperPrice", type=str, default=DEFAULT_UPPER_PRICE, help="Upper price of the range (used if ticks not provided)")

    # Tick-based price range arguments (override string prices if provided)
    tick_group = parser.add_argument_group('Tick-based Price Range (optional, overrides --lowerPrice/--upperPrice)')
    tick_group.add_argument("--lower_tick", type=int, help="Lower tick of the range (e.g., -80302)")
    tick_group.add_argument("--upper_tick", type=int, help="Upper tick of the range (e.g., -76326)")

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
        token0_address=token0_address, 
        token1_address=token1_address,
        lower_price_str_input=args.lowerPrice, 
        upper_price_str_input=args.upperPrice,
        base_size=args.baseSize, 
        quote_size=args.quoteSize,
        lower_tick=args.lower_tick, # Pass through the tick arguments
        upper_tick=args.upper_tick   # Pass through the tick arguments
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
        token0_per_token1 = token1_amount / token0_amount
        
        print("\nDerived Prices from API ratio:")
        print(f"  1 {token0_name} = {token0_per_token1:.8f} {token1_name}")
        print(f"  1 {token1_name} = {1/token0_per_token1:.8f} {token0_name}")
    else:
        print("\nCould not derive prices: one of the token amounts from API was zero.", file=sys.stderr)


if __name__ == "__main__":
    main()
