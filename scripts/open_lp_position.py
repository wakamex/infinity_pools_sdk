"""Script to open a new liquidity position (add liquidity) in an Infinity Pool.

This script demonstrates how to use the InfinityPoolsSDK to add liquidity,
exposing key parameters and using a slippage percentage to calculate minimum amounts.

Example Usage (replace with your actual values and network):

# Make sure your .env file has PRIVATE_KEY. 
# For 'base' network, RPC_URL and PERIPHERY_CONTRACT_ADDRESS can often use SDK defaults.
# For other networks, ensure FOO_RPC_URL and FOO_PERIPHERY_CONTRACT_ADDRESS are set.

python scripts/open_lp_position.py \
    --token0-address 0x211Cc4DD073734dA055fbF44a2b4667d5E5fE5d2 \
    --token1-address 0xc1CBa3fCea344f92D9239c08C0568f6F2F0ee452 \
    --tick-lower -807 \
    --tick-upper -767 \
    --amount0-desired 1.0 \
    --amount1-desired 0.000418388 \
    --slippage 1.0 \
    --token0-decimals 18 \
    --token1-decimals 18

To use vault deposit:
python scripts/open_lp_position.py ... --use-vault-deposit

To disable auto-approval (requires manual approval first):
python scripts/open_lp_position.py ... --no-auto-approve

To specify a recipient for the LP NFT other than the sender:
python scripts/open_lp_position.py ... --recipient THEIR_ADDRESS_HERE

"""

# Standard library imports (alphabetical)
import argparse
import logging
import os
import sys
from decimal import Decimal
from typing import cast

# Third-party library imports (alphabetical)
from eth_account.signers.local import LocalAccount
from web3 import HTTPProvider, Web3
from web3.middleware import ExtraDataToPOAMiddleware

# Local application/library imports (alphabetical by module, then by imported name)
from infinity_pools_sdk.constants import (
    BASE_RPC_URL as DEFAULT_BASE_RPC_URL,
)
from infinity_pools_sdk.constants import (
    ContractAddresses,
)
from infinity_pools_sdk.constants import (
    Web3Objects as SDK_Web3Objects,
)
from infinity_pools_sdk.core.connector import InfinityPoolsConnector
from infinity_pools_sdk.erc.erc20 import ERC20Helper  # Added import
from infinity_pools_sdk.offchain.liquidity_ratio import fetch_liquidity_ratio
from infinity_pools_sdk.sdk import InfinityPoolsSDK
from infinity_pools_sdk.tests.conftest import load_env_file


def str_to_bool(value):
    """Convert a string representation of truth to true (True) or false (False)."""
    if isinstance(value, bool):
        return value
    if value.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif value.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Open a new liquidity position in an Infinity Pool.")

    # Configuration arguments
    parser.add_argument("--env-file", type=str, default=".env", help="Path to the .env file to load environment variables from.")
    # Updated network help text and removed choices that relied on non-existent RPC_URLS.keys()
    _help = "Network to connect to (e.g., 'base'). For 'base', defaults from constants are used if env vars are not set. For other networks, ensure FOO_RPC_URL and FOO_PERIPHERY_CONTRACT_ADDRESS env vars are set."
    parser.add_argument("--network", type=str, default="base", help=_help)

    # Arguments for identifying the pool and position range (with defaults from example)
    parser.add_argument("--token0-address", type=str, default="0x211Cc4DD073734dA055fbF44a2b4667d5E5fE5d2", help="Address of token0.")
    parser.add_argument("--token1-address", type=str, default="0xc1CBa3fCea344f92D9239c08C0568f6F2F0ee452", help="Address of token1.")
    parser.add_argument("--tick-lower", type=int, default=-807, help="The lower tick boundary of the position.")
    parser.add_argument("--tick-upper", type=int, default=-767, help="The upper tick boundary of the position.")

    # Arguments for amounts (with defaults from example)
    parser.add_argument("--amount0-desired", type=Decimal, default=Decimal("1.0"), help="Desired amount of token0 to add.")
    parser.add_argument("--amount1-desired", type=Decimal, default=None, help="Desired amount of token1 to add. Optional.")
    parser.add_argument("--slippage", type=Decimal, default=Decimal("1.0"), help="Slippage tolerance in percentage (e.g., 1.0 for 1.0%%). Used to calculate min amounts.")

    # Optional arguments for token details and transaction behavior
    parser.add_argument("--auto-approve", type=str_to_bool, nargs="?", const=True, default=True, help="Automatically approve token spending (default: True)")
    parser.add_argument("--gas-limit", type=int, help="Optional gas limit for the add liquidity transaction.")
    parser.add_argument("--token0-decimals", type=int, default=18, help="Decimals for token0. Defaults to 18.")
    parser.add_argument("--token1-decimals", type=int, default=18, help="Decimals for token1. Defaults to 18.")
    parser.add_argument("--use-vault-deposit", action="store_true", help="Use funds from the vault for this deposit.")
    parser.add_argument("--no-auto-approve", action="store_false", dest="auto_approve", help="Disable automatic token approval by the SDK.")
    parser.set_defaults(auto_approve=True)
    parser.add_argument("--dryrun", action="store_true")

    args = parser.parse_args()

    # Load environment variables from .env file
    load_env_file(args.env_file)

    # Get configuration from environment variables or constants
    private_key = os.getenv("PRIVATE_KEY")
    rpc_url = None
    periphery_address = None

    network_arg_upper = args.network.upper()

    if args.network.lower() == "base":
        rpc_url = os.getenv("BASE_RPC_URL", DEFAULT_BASE_RPC_URL)
        # Conventionally, an environment variable might override the constant for periphery address
        periphery_address = os.getenv("BASE_PERIPHERY_CONTRACT_ADDRESS", ContractAddresses.BASE.get("proxy"))
    else:
        # For networks other than 'base', rely on specific environment variables
        rpc_url = os.getenv(f"{network_arg_upper}_RPC_URL")
        periphery_address = os.getenv(f"{network_arg_upper}_PERIPHERY_CONTRACT_ADDRESS")
        if not periphery_address:
            network_config_from_sdk = getattr(ContractAddresses, args.network.upper(), None)
            if network_config_from_sdk:
                periphery_address = network_config_from_sdk.get("proxy")
            else:
                periphery_address = None  # Explicitly None if not found

    if not rpc_url:
        logger.error(f"RPC_URL for network '{args.network}' not found in environment variables or constants. Exiting.")
        sys.exit(1)
    if not private_key:
        logger.error("PRIVATE_KEY not found in environment variables. Please set it. Exiting.")
        sys.exit(1)
    if not periphery_address:
        logger.error(f"PERIPHERY_CONTRACT_ADDRESS for network '{args.network}' not found in environment variables or constants. Exiting.")
        sys.exit(1)
    assert periphery_address is not None, "Periphery address should not be None here due to prior check."

    # Get Web3 instance
    w3_instance = None
    if args.network.lower() == "base":
        w3_instance = SDK_Web3Objects.BASE
        logger.info(f"Using pre-configured Web3 instance for network '{args.network}' from SDK constants.")
    elif rpc_url:  # Fallback for other networks if RPC URL is still determined
        logger.warning(f"Network '{args.network}' does not have a pre-configured Web3 instance in SDK_Web3Objects. Exiting.")
        sys.exit(1)
    assert w3_instance is not None, "w3_instance should be guaranteed to be Web3 by this point due to the sys.exit check above."

    logger.info(f"Initializing InfinityPoolsConnector for network '{args.network}'.")
    connector = InfinityPoolsConnector(w3_instance=w3_instance, network=args.network, private_key=private_key)

    if connector.account is None:
        logger.error("Failed to load account from private key. Exiting.")
        sys.exit(1)
    assert connector.account is not None, "Connector account should not be None here due to prior check."
    # Explicitly cast to satisfy linter after assertion and None check.
    # Assuming LocalAccount is the specific non-None type of connector.account
    # If connector.account can be other non-None types, adjust cast accordingly.
    # However, the linter implies it knows about LocalAccount | None.
    # from eth_account.signers.local import LocalAccount # Import moved to top
    loaded_account = cast(LocalAccount, connector.account)
    active_address = loaded_account.address
    logger.info(f"Using account: {active_address}")

    sdk = InfinityPoolsSDK(connector=connector, periphery_address=periphery_address)
    logger.info(f"InfinityPoolsSDK initialized for periphery contract: {periphery_address}")

    logger.info("Attempting to add liquidity...")
    logger.info(f"  Token0: {args.token0_address} (Decimals: {args.token0_decimals})")
    logger.info(f"  Token1: {args.token1_address} (Decimals: {args.token1_decimals})")
    logger.info(f"  Ticks: {args.tick_lower} to {args.tick_upper}")
    logger.info(f"  Slippage Tolerance: {args.slippage}%")
    # Min amounts will be calculated and logged before the transaction
    logger.info(f"  Use Vault Deposit: {args.use_vault_deposit}")
    logger.info(f"  Auto Approve: {args.auto_approve}")
    # Recipient is handled by SDK (msg.sender for addLiquidity)

    if args.amount0_desired is not None and args.amount0_desired > 0:
        logger.info(f"Amount0 Provided ({args.amount0_desired} smallest units), Amount1 Desired will be calculated using API for range [{args.tick_lower}, {args.tick_upper}].")
        logger.info(f"Fetching ratio for {args.token0_address}/{args.token1_address} range [{args.tick_lower}, {args.tick_upper}] based on token0 amount {args.amount0_desired}")
        try:
            ratio_data = fetch_liquidity_ratio(
                token0_address=args.token0_address,
                token1_address=args.token1_address,
                lower_tick=args.tick_lower,
                upper_tick=args.tick_upper,
                base_size=args.amount0_desired,
                quote_size=None,
            )
            if ratio_data is None:
                logger.error("  Error: fetch_liquidity_ratio returned None unexpectedly. Cannot calculate amount1_desired.")
                return
            # API is assumed to return amounts in smallest units; SDK converts them to Decimal.
            base_size_lr, quote_size_lr = ratio_data
            logger.info(f"  API returned: baseSize={base_size_lr}, quoteSize={quote_size_lr}")

            # Convert API response (smallest units) to standard units for the SDK's add_liquidity function
            actual_amount0_desired = base_size_lr * (Decimal(10) ** args.token0_decimals)
            actual_amount1_desired = quote_size_lr * (Decimal(10) ** args.token1_decimals)
            # actual_amount0_desired = base_size_lr
            # actual_amount1_desired = quote_size_lr
            logger.info(f"  Converted for SDK: amount0_std_unit={actual_amount0_desired}, amount1_std_unit={actual_amount1_desired}")
        except Exception as e:
            logger.error(f"  Error fetching ratio: {e}. Cannot calculate amount1_desired.")
            return
    elif args.amount1_desired is not None and args.amount1_desired > 0:
        logger.info(f"Amount1 Provided ({args.amount1_desired} smallest units), Amount0 Desired will be calculated using API for range [{args.tick_lower}, {args.tick_upper}].")
        logger.info(f"Fetching ratio for {args.token0_address}/{args.token1_address} range [{args.tick_lower}, {args.tick_upper}] based on token1 amount {args.amount1_desired}")
        try:
            ratio_data = fetch_liquidity_ratio(
                token0_address=args.token0_address,
                token1_address=args.token1_address,
                lower_tick=args.tick_lower,
                upper_tick=args.tick_upper,
                base_size=None,
                quote_size=args.amount1_desired,
            )
            if ratio_data is None:
                logger.error("  Error: fetch_liquidity_ratio returned None unexpectedly. Cannot calculate amount0_desired.")
                return
            # API is assumed to return amounts in smallest units; SDK converts them to Decimal.
            base_size_lr, quote_size_lr = ratio_data
            logger.info(f"  API returned: baseSize={base_size_lr}, quoteSize={quote_size_lr}")

            # Convert API response (smallest units) to standard units for the SDK's add_liquidity function
            actual_amount0_desired = base_size_lr * (Decimal(10) ** args.token0_decimals)
            actual_amount1_desired = quote_size_lr * (Decimal(10) ** args.token1_decimals)
            # actual_amount0_desired = base_size_lr
            # actual_amount1_desired = quote_size_lr
            logger.info(f"  Converted for SDK: amount0_std_unit={actual_amount0_desired}, amount1_std_unit={actual_amount1_desired}")
        except Exception as e:
            logger.error(f"  Error fetching ratio: {e}. Cannot calculate amount0_desired.")
            return
    else:
        logger.error("Error: Neither amount0_desired nor amount1_desired are specified meaningfully (both zero or not provided after conversion to std units). One must be specified.")
        return

    # Ensure actual_amount0_desired and actual_amount1_desired are valid Decimals at this point
    if not isinstance(actual_amount0_desired, Decimal) or actual_amount0_desired <= Decimal(0) or not isinstance(actual_amount1_desired, Decimal) or actual_amount1_desired <= Decimal(0):
        logger.error(f"Could not determine valid positive desired amounts. Amount0: {actual_amount0_desired}, Amount1: {actual_amount1_desired}. Exiting.")
        sys.exit(1)

    actual_amount0_desired = actual_amount0_desired.quantize(Decimal('1'))
    actual_amount1_desired = actual_amount1_desired.quantize(Decimal('1'))
    logger.info(f"  Calculated Amount0 Desired: {actual_amount0_desired}")
    logger.info(f"  Calculated Amount1 Desired: {actual_amount1_desired}")

    # Ensure calculations use Decimal for precision
    slippage_factor = Decimal("1") - (args.slippage / Decimal("100"))
    amount0_min_calculated = actual_amount0_desired * slippage_factor
    amount1_min_calculated = actual_amount1_desired * slippage_factor

    amount0_min_calculated = amount0_min_calculated.quantize(Decimal('1'))
    amount1_min_calculated = amount1_min_calculated.quantize(Decimal('1'))
    logger.info(f"  Calculated Amount0 Min (after slippage): {amount0_min_calculated}")
    logger.info(f"  Calculated Amount1 Min (after slippage): {amount1_min_calculated}")

    # Log parameters in the requested on-chain format
    onchain_params_log_string = (
        "Preparing to call addLiquidity with the following parameters (on-chain format):\\n"
        "Function: addLiquidity((address,address,bool,int256,int256,uint256,uint256,uint256,uint256))\\n"
        "#\tName\tType\tData\n"
        f"0\tparams.token0\t\taddress\t{args.token0_address}\n"
        f"0\tparams.token1\t\taddress\t{args.token1_address}\n"
        f"0\tparams.useVaultDeposit\tbool\t{args.use_vault_deposit}\n"
        f"0\tparams.startEdge\tint256\t{args.tick_lower}\n"
        f"0\tparams.stopEdge\t\tint256\t{args.tick_upper}\n"
        f"0\tparams.amount0Desired\tuint256\t{actual_amount0_desired}\n"
        f"0\tparams.amount1Desired\tuint256\t{actual_amount1_desired}\n"
        f"0\tparams.amount0Min\tuint256\t{amount0_min_calculated}\n"
        f"0\tparams.amount1Min\tuint256\t{amount1_min_calculated}"
    )
    logger.info(f"\n{onchain_params_log_string}\n")

    try:
        tx_overrides = {}
        if args.gas_limit:
            tx_overrides["gas"] = args.gas_limit

        if args.dryrun:
            logger.info("Dry run mode enabled. Not executing transaction.")
            return

        result = sdk.add_liquidity(
            token0_address=args.token0_address,
            token1_address=args.token1_address,
            use_vault_deposit=args.use_vault_deposit,
            tick_lower=args.tick_lower,
            tick_upper=args.tick_upper,
            amount0_desired=actual_amount0_desired,
            amount1_desired=actual_amount1_desired,
            amount0_min=amount0_min_calculated,
            amount1_min=amount1_min_calculated,
            token0_decimals=args.token0_decimals,
            token1_decimals=args.token1_decimals,
            auto_approve=args.auto_approve,
            transaction_overrides=tx_overrides if tx_overrides else None,
        )

        logger.info("Add liquidity transaction processed.")
        logger.info(f"  Transaction Hash: {result['tx_hash']}")
        if "receipt" in result and result["receipt"] is not None and "status" in result["receipt"]:
            logger.info(f"  Transaction Status: {'Success' if result['receipt']['status'] == 1 else 'Failed'}")
        else:
            logger.warning("  Transaction receipt or status not available in the result.")

    except Exception as e:  # Catching a general exception
        logger.error(f"Error adding liquidity: {e}")


if __name__ == "__main__":
    main()
