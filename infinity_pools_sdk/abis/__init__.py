"""Pre-loaded contract ABIs for the Infinity Pools SDK."""

from .loader import load_abi

# Pre-load all ABIs needed by the SDK
PERIPHERY_ABI = load_abi("InfinityPoolsPeriphery.json")

ERC20_ABI = load_abi("ERC20.json")

ERC721_ABI = load_abi("ERC721.json")