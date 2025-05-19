"""Constants for the Infinity Pools SDK.

This module contains constants used throughout the SDK, such as token addresses,
contract addresses, and other configuration values.
"""

import os

from web3 import Web3

from infinity_pools_sdk.utils.env_loader import load_env_vars

# Load environment variables from .env file (if it exists)
load_env_vars()

BASE_RPC_URL = os.getenv("BASE_RPC_URL")
if not BASE_RPC_URL:
    raise ValueError("BASE_RPC_URL not found in environment variables. Please set it in your .env file or ensure it's set directly in your environment.")

BASE_DEPLOYMENT_BLOCK = 24888601

PROXY = Web3.to_checksum_address("0xf8fad01b2902ff57460552c920233682c7c011a7")
IMPERSONATEE = Web3.to_checksum_address("0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207")

# ERC721 Transfer Event Signature
ERC721_TRANSFER_EVENT_SIGNATURE = "0xc422e2654d2f828eb032bd5145419574b150eaa4901569fe8f3bfaa17628564c"

# Base network token addresses
class BaseTokens:
    """Token addresses on the Base network."""
    
    # Native tokens
    ETH = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"  # Native ETH representation
    WETH = "0x4200000000000000000000000000000000000006"  # Wrapped ETH on Base
    
    # Stablecoins
    USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"  # USDC on Base
    sUSDe = "0x211Cc4DD073734dA055fbF44a2b4667d5E5fE5d2"  # sUSDe on Base
    
    # Liquid staking tokens
    wstETH = "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452"  # Wrapped staked ETH on Base

# Contract addresses on different networks
class ContractAddresses:
    """Contract addresses for Infinity Pools on different networks."""
    
    # Base network
    BASE = {
        "proxy": "0xF8FAD01B2902fF57460552C920233682c7c011a7",  # InfinityPoolsProxy on Base
        "implementation": "0x6C711E6bbD9955449bBcc833636a9199DfA7cA65",  # Current implementation
    }

# Fee tiers
class FeeTiers:
    """Common fee tiers used in Infinity Pools."""
    
    FEE_0_01 = 100     # 0.01%
    FEE_0_05 = 500     # 0.05%
    FEE_0_3 = 3000     # 0.3%
    FEE_1 = 10000      # 1%

# Web3 objects
class Web3Objects:
    """Web3 objects for different networks."""
    
    # Base network
    BASE = Web3(Web3.HTTPProvider(BASE_RPC_URL))
