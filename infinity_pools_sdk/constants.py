"""Constants for the Infinity Pools SDK.

This module contains constants used throughout the SDK, such as token addresses,
contract addresses, and other configuration values.
"""


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
