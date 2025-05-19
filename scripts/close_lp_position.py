import argparse
import os
import sys
import time  # Added time import back
from decimal import Decimal
from typing import Optional

from web3 import HTTPProvider, Web3
from web3.middleware import ExtraDataToPOAMiddleware

from infinity_pools_sdk.constants import BASE_RPC_URL, ContractAddresses, Web3Objects
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


def get_lp_details_by_lpnum(owner_address: str, target_lp_num: int) -> tuple[Optional[int], Optional[int]]:
    """Get the full encoded 'id' (as int) and raw liquidity of a specific liquidity position by its 'lpNum'."""
    print(f"Fetching liquidity positions for wallet: {owner_address} using imported function...")
    positions = get_liquidity_positions_by_wallet(owner_address)

    if positions is None:
        print("Failed to fetch positions or an error occurred.")
        return None, None

    if not isinstance(positions, list):
        print(f"Error: API response (from imported function) is not a list. Type: {type(positions)}")
        return None, None

    for position in positions:
        for k, v in position.items():
            print(f"{k}: {v}")
        lp_num = position.get("lpNum")
        if isinstance(lp_num, int) and lp_num == target_lp_num:
            print(f"Found target position with lpNum: {lp_num}. Status: {position.get('status')}")
            encoded_id_hex = position.get("id")
            if not (isinstance(encoded_id_hex, str) and encoded_id_hex.startswith("0x")):
                print(
                    f"Warning: Target position with lpNum {lp_num} has missing or invalid 'id': '{encoded_id_hex}'. Cannot proceed with this position."
                )
                return None, None  # Cannot proceed without a valid encoded ID

            token_id_for_sdk: Optional[int] = None
            try:
                token_id_for_sdk = int(encoded_id_hex, 16)
                print(f"Using Encoded ID for TX: {encoded_id_hex} (for lpNum {lp_num})")
            except ValueError:
                print(
                    f"Error: Could not convert encoded_id_hex '{encoded_id_hex}' to an integer for lpNum {lp_num}. Cannot proceed."
                )
                return None, None

            raw_liquidity = None
            try:
                # Note: Liquidity calculation might not be relevant if the position was already drained/closed by UI
                # but we calculate it for completeness or if it's still partially open.
                locked_base_size_str = str(position.get("lockedBaseSize", "0"))
                locked_quote_size_str = str(position.get("lockedQuoteSize", "0"))
                available_base_size_str = str(position.get("availableBaseSize", "0"))  # Consider available if draining
                available_quote_size_str = str(position.get("availableQuoteSize", "0"))

                # Prefer available amounts if draining, otherwise locked might be okay for 'current_position_liquidity_raw'
                # The `drain` function doesn't need this, but the SDK call has the param.
                # For `drain` this value is less critical, but let's try to be accurate.
                effective_base_decimal = (
                    Decimal(available_base_size_str)
                    if Decimal(available_base_size_str) > 0
                    else Decimal(locked_base_size_str)
                )
                effective_quote_decimal = (
                    Decimal(available_quote_size_str)
                    if Decimal(available_quote_size_str) > 0
                    else Decimal(locked_quote_size_str)
                )

                base_token_decimals = 18
                quote_token_decimals = 18

                if effective_base_decimal > Decimal(0):
                    raw_liquidity = int(effective_base_decimal * (Decimal(10) ** base_token_decimals))
                    print(
                        f"Using effectiveBaseSize: {effective_base_decimal} (raw: {raw_liquidity}) for position {lp_num}"
                    )
                elif effective_quote_decimal > Decimal(0):
                    raw_liquidity = int(effective_quote_decimal * (Decimal(10) ** quote_token_decimals))
                    print(
                        f"Using effectiveQuoteSize: {effective_quote_decimal} (raw: {raw_liquidity}) for position {lp_num}"
                    )
                else:
                    print(
                        f"Warning: Both effectiveBaseSize and effectiveQuoteSize are zero for position {lp_num}. Raw liquidity set to 0."
                    )
                    raw_liquidity = 0

                return token_id_for_sdk, raw_liquidity

            except Exception as e:
                print(f"Error processing liquidity fields for lpNum {lp_num} (Encoded ID {encoded_id_hex}): {e}.")
                if token_id_for_sdk is not None:
                    print("Proceeding with token ID but raw liquidity will be None.")
                    return token_id_for_sdk, None  # Return ID, but None for liquidity if calculation failed
                return None, None  # Critical error if ID also failed

    print(f"Target liquidity position with lpNum {target_lp_num} not found for this address.")
    return None, None


def main():
    if not PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY not found in environment variables. Please set it in your .env file.")
    if not RPC_URL:
        raise ValueError(f"RPC URL for {NETWORK} not found or not configured.")

    # Get Web3 instance
    w3_instance = None
    resolved_rpc_url = RPC_URL  # Use the RPC_URL determined earlier in the script

    if NETWORK.lower() == "base":
        w3_instance = Web3Objects.BASE
        print(f"Using pre-configured Web3 instance for network '{NETWORK}' from SDK constants.")
    elif resolved_rpc_url:  # Fallback for other networks if RPC_URL is available
        # from web3 import Web3, HTTPProvider # Imports moved to top
        print(
            f"Network '{NETWORK}' does not have a pre-configured Web3 instance in SDK_Web3Objects. Creating a new Web3 instance from RPC URL: {resolved_rpc_url}. Consider adding it to constants.Web3Objects for consistency."
        )
        provider = HTTPProvider(resolved_rpc_url)
        w3_instance = Web3(provider)
        # Optionally inject POA middleware for non-base networks
        if NETWORK.lower() in ["polygon", "mumbai", "bsc", "goerli", "sepolia"]:
            # from web3.middleware import ExtraDataToPOAMiddleware # Import moved to top
            w3_instance.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not w3_instance:
        print(f"Could not obtain a Web3 instance for network '{NETWORK}'. Exiting.")
        sys.exit(1)
    assert w3_instance is not None, "w3_instance should be guaranteed to be Web3 by this point."

    print(f"Initializing InfinityPoolsConnector for network '{NETWORK}'.")
    connector = InfinityPoolsConnector(w3_instance=w3_instance, network=NETWORK, private_key=PRIVATE_KEY)

    # Ensure account is loaded before trying to access its address
    loaded_account = connector.account
    if loaded_account is None:  # Explicitly check for None
        print("Error: Account could not be loaded from private key or is None.")
        return
    my_address = loaded_account.address
    print(f"Using account: {my_address}")

    sdk = InfinityPoolsSDK(connector=connector, periphery_address=PERIPHERY_CONTRACT_ADDRESS)
    print(f"InfinityPoolsSDK initialized for periphery: {PERIPHERY_CONTRACT_ADDRESS}")

    target_lp_num_to_close = 97  # As requested by user
    print(f"Attempting to find details for position with lpNum: {target_lp_num_to_close}")
    token_id, current_liquidity_raw = get_lp_details_by_lpnum(my_address, target_lp_num_to_close)

    if token_id is None:
        print(f"Could not find details or a valid encoded ID for lpNum {target_lp_num_to_close} to close.")
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
            liquidity_percentage=Decimal("1.0"),  # Attempting to remove 100%
            recipient=recipient,
            deadline=deadline,
            current_position_liquidity_raw=current_liquidity_raw,  # Pass the determined raw liquidity
        )
        if result.get("status") == 1:
            print(f"\nSuccessfully removed liquidity!")
            print(f"  Transaction Hash: {result['tx_hash']}")
            print(f"  Receipt Status: {result.get('status')}")
        else:
            print(f"\nFailed to remove liquidity.")
            print(f"  Transaction Hash: {result['tx_hash']}")
            print(f"  Receipt Status: {result.get('status')} (Transaction Reverted)")
        # print(f"  Receipt: {result.get('receipt')}") # Can be very verbose
    except Exception as e:
        print(f"\nError removing liquidity: {e}")


if __name__ == "__main__":
    main()
