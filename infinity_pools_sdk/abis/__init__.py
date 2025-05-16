"""Pre-loaded contract ABIs for the Infinity Pools SDK."""

from .loader import load_abi

# Pre-load all ABIs needed by the SDK
PERIPHERY_ABI = load_abi("InfinityPoolsPeriphery.json")

# Example for future ABIs that might be added:
# CORE_POOL_ABI = load_abi("InfinityPoolsCorePool.json") 
# ERC20_ABI = load_abi("ERC20.json")
