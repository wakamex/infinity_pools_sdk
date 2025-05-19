import os
import time
from decimal import Decimal
from typing import Optional

from infinity_pools_sdk.constants import BASE_RPC_URL, ContractAddresses
from infinity_pools_sdk.core.connector import InfinityPoolsConnector
from infinity_pools_sdk.offchain.liquidity_positions import (
    get_liquidity_positions_by_wallet,
)
from infinity_pools_sdk.sdk import InfinityPoolsSDK
from infinity_pools_sdk.tests.conftest import load_env_file

load_env_file(".env")  # Load environment variables

NETWORK = "base"
RPC_URL = BASE_RPC_URL  # Assuming BASE_RPC_URL is correctly set up in constants
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PERIPHERY_CONTRACT_ADDRESS = ContractAddresses.BASE["proxy"]

# --- User-specific details ---
RECIPIENT_ADDRESS = None
DEADLINE_SECONDS_FROM_NOW = 300  # 5 minutes


def get_first_open_lp_token_id(owner_address: str) -> tuple[Optional[int], Optional[int]]:
    """Get the 'lpNum' (token_id) and raw liquidity of the first open liquidity position for the owner via API."""
    print(f"Fetching liquidity positions for wallet: {owner_address} using imported function...")
    positions = get_liquidity_positions_by_wallet(owner_address)

    if positions is None:
        print("Failed to fetch positions or an error occurred.")
        return None, None

    if not isinstance(positions, list):
        print(f"Error: API response (from imported function) is not a list. Type: {type(positions)}")
        return None, None

    for position in positions:
        for k,v in position.items():
            print(f"{k}: {v}")
        if isinstance(position, dict) and position.get("status") == "OPEN":
            lp_num = position.get("lpNum")
            if isinstance(lp_num, int) and position.get("status") == "OPEN":
                print(f"Found OPEN position with lpNum (token_id): {lp_num}")
                raw_liquidity = None
                try:
                    locked_base_size_str = str(position.get("lockedBaseSize", "0"))
                    locked_quote_size_str = str(position.get("lockedQuoteSize", "0"))

                    locked_base_decimal = Decimal(locked_base_size_str)
                    locked_quote_decimal = Decimal(locked_quote_size_str)

                    # TODO: Dynamically fetch or correctly map token decimals based on asset addresses
                    # position.get("baseAsset") and position.get("quoteAsset")
                    # For now, assuming 18 decimals for both as sUSDe and wstETH typically have 18.
                    base_token_decimals = 18
                    quote_token_decimals = 18

                    if locked_base_decimal > Decimal(0):
                        raw_liquidity = int(locked_base_decimal * (Decimal(10)**base_token_decimals))
                        print(f"Using lockedBaseSize: {locked_base_decimal} (raw: {raw_liquidity}) for position {lp_num}")
                    elif locked_quote_decimal > Decimal(0):
                        raw_liquidity = int(locked_quote_decimal * (Decimal(10)**quote_token_decimals))
                        print(f"Using lockedQuoteSize: {locked_quote_decimal} (raw: {raw_liquidity}) for position {lp_num}")
                    else:
                        print(f"Warning: Both lockedBaseSize and lockedQuoteSize are zero or not found for OPEN position {lp_num}. Cannot determine off-chain liquidity.")
                        # Fallback to on-chain call by returning None for raw_liquidity, or treat as zero liquidity.
                        # Forcing removal of 0 liquidity if this occurs.
                        raw_liquidity = 0 

                    return lp_num, raw_liquidity
                
                except Exception as e:
                    print(f"Error processing liquidity fields for position {lp_num}: {e}. API values: base='{position.get("lockedBaseSize")}', quote='{position.get("lockedQuoteSize")}'")
                    # Fallback to on-chain call attempt
                    return lp_num, None
            elif isinstance(lp_num, int):
                print(f"Skipping position {lp_num} with status: {position.get('status')}")
            else:
                print(f"Found open position, but 'lpNum' is not an int: {position}")

    print("No open liquidity positions found for this address.")
    return None, None


def main():
    if not PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY not found in environment variables. Please set it in your .env file.")
    if not RPC_URL:
        raise ValueError(f"RPC URL for {NETWORK} not found or not configured.")

    print(f"Connecting to {NETWORK} via {RPC_URL}...")
    connector = InfinityPoolsConnector(rpc_url=RPC_URL, network=NETWORK, private_key=PRIVATE_KEY)

    if not connector.account:
        print("Error: Account could not be loaded from private key.")
        return
    my_address = connector.account.address
    print(f"Using account: {my_address}")

    sdk = InfinityPoolsSDK(connector=connector, periphery_address=PERIPHERY_CONTRACT_ADDRESS)
    print(f"InfinityPoolsSDK initialized for periphery: {PERIPHERY_CONTRACT_ADDRESS}")

    token_id, current_liquidity_raw = get_first_open_lp_token_id(my_address)

    if token_id is None:
        print("No active (open) liquidity position token_id found to close.")
        return

    recipient = RECIPIENT_ADDRESS if RECIPIENT_ADDRESS else my_address
    deadline = int(time.time()) + DEADLINE_SECONDS_FROM_NOW

    print(f"\nAttempting to remove liquidity for token ID: {token_id}")
    print(f"  Recipient: {recipient}")
    print(f"  Deadline: {deadline} (timestamp)")
    print(f"  Liquidity Percentage: 100%")  # Default in SDK is 100% if not specified

    try:
        # remove_liquidity expects liquidity_percentage as Decimal if provided,
        # but defaults to 100% (Decimal('1')) if omitted.
        result = sdk.remove_liquidity(
            token_id=token_id, 
            liquidity_percentage=Decimal("1.0"), # Attempting to remove 100%
            recipient=recipient, 
            deadline=deadline,
            current_position_liquidity_raw=current_liquidity_raw # Pass the determined raw liquidity
        )
        print("\nSuccessfully removed liquidity!")
        print(f"  Transaction Hash: {result.get('tx_hash')}")
        # print(f"  Receipt: {result.get('receipt')}") # Can be very verbose
    except Exception as e:
        print(f"\nError removing liquidity: {e}")


if __name__ == "__main__":
    main()
