from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List


@dataclass
class AddLiquidityParams:
    """Represents the AddLiquidityParams struct in the Infinity Pools contract."""

    token0: str  # Address of token0
    token1: str  # Address of token1
    fee: int  # Fee tier (e.g., 500, 3000, 10000)
    tickLower: int  # Lower tick boundary
    tickUpper: int  # Upper tick boundary
    amount0Desired: Decimal  # Desired amount of token0
    amount1Desired: Decimal  # Desired amount of token1
    amount0Min: Decimal  # Minimum amount of token0
    amount1Min: Decimal  # Minimum amount of token1
    recipient: str  # Address to receive the position NFT
    deadline: int  # Transaction deadline timestamp
    
    def to_contract_tuple(self, token0_decimals: int = 18, token1_decimals: int = 18) -> tuple:
        """Convert to tuple format expected by the contract."""
        return (
            self.token0,
            self.token1,
            self.fee,
            self.tickLower,
            self.tickUpper,
            int(self.amount0Desired * (10 ** token0_decimals)), # convert Decimal to int wei
            int(self.amount1Desired * (10 ** token1_decimals)), # convert Decimal to int wei
            int(self.amount0Min * (10 ** token0_decimals)),       # convert Decimal to int wei
            int(self.amount1Min * (10 ** token1_decimals)),       # convert Decimal to int wei
            self.recipient,
            self.deadline
        )

@dataclass
class SwapInfo:
    """Represents the SwapInfo struct in the Infinity Pools contract."""

    tokenIn: str  # Address of input token
    tokenOut: str  # Address of output token
    fee: int  # Fee tier
    amountIn: Decimal  # Amount of input token
    amountOutMinimum: Decimal  # Minimum amount of output token desired
    sqrtPriceLimitX96: int # The price limit for the swap, as a Q64.96 sqrt price

    def to_contract_tuple(self, tokenIn_decimals: int = 18, tokenOut_decimals: int = 18) -> tuple:
        """Convert to tuple format expected by the contract."""
        return (
            self.tokenIn,
            self.tokenOut,
            self.fee,
            int(self.amountIn * (10 ** tokenIn_decimals)), # convert Decimal to int wei
            int(self.amountOutMinimum * (10 ** tokenOut_decimals)), # convert Decimal to int wei
            self.sqrtPriceLimitX96
        )

@dataclass
class MulticallParams:
    """Represents parameters for a multicall."""

    swapperIds: List[int] # Array of swapper IDs to use for each action
    actions: List[bytes]  # Array of actions to perform (bytes4 function selectors)
    data: List[bytes]  # Additional data for each action
    
    def to_contract_tuple(self) -> tuple:
        """Convert to tuple format expected by the contract."""
        return (
            self.swapperIds,
            self.actions,
            self.data
        )

# Add more data models for other contract structs as needed

# Utility functions for encoding/decoding NFT position IDs:
# Constants for encoding/decoding position IDs
_OWNER_BITS = 160
_TICK_BITS = 24
_TICK_MASK = (1 << _TICK_BITS) - 1
_TICK_SIGN_BIT = 1 << (_TICK_BITS - 1)  # Sign bit for 24-bit tick representation
_TICK_LOWER_SHIFT = _TICK_BITS
_OWNER_SHIFT = _TICK_LOWER_SHIFT + _TICK_BITS

def encode_position_id(owner: str, tick_lower: int, tick_upper: int) -> int:
    """Encode NFT position details (owner, tick_lower, tick_upper) into a unique integer ID.

    The encoding scheme packs the owner's address and tick boundaries into a uint256 compatible integer:
    - tick_upper: lowest 24 bits
    - tick_lower: next 24 bits
    - owner: next 160 bits
    Total bits used: 24 (tick_upper) + 24 (tick_lower) + 160 (owner) = 208 bits.

    Args:
        owner: The owner's Ethereum address (hex string, e.g., "0x...").
        tick_lower: The lower tick boundary of the position.
        tick_upper: The upper tick boundary of the position.

    Returns:
        An integer representing the unique position ID.
    """
    try:
        owner_int = int(owner, 16)
    except ValueError as e:
        raise ValueError(f"Invalid owner address format: {owner}. Must be a hex string.") from e

    # Mask ticks to 24 bits. This handles potential negative numbers by taking their
    # 24-bit two's complement representation if Python's integers behave as such for bitwise ops,
    # or effectively just takes the lower 24 bits for positive numbers.
    tick_lower_encoded = tick_lower & _TICK_MASK
    tick_upper_encoded = tick_upper & _TICK_MASK

    position_id = (
        (owner_int << _OWNER_SHIFT) |
        (tick_lower_encoded << _TICK_LOWER_SHIFT) |
        tick_upper_encoded
    )
    return position_id


def decode_position_id(position_id: int) -> tuple[str, int, int]:
    """Decode a unique ID back into NFT position details (owner, tick_lower, tick_upper).

    Reverses the bit-packing performed by `encode_position_id`.

    Args:
        position_id: The unique integer ID representing the NFT position.

    Returns:
        A tuple containing:
            - owner (str): The owner's Ethereum address (hex string).
            - tick_lower (int): The lower tick boundary.
            - tick_upper (int): The upper tick boundary.
    """
    owner_int = position_id >> _OWNER_SHIFT
    owner_hex = f"0x{owner_int:040x}"

    tick_lower_encoded = (position_id >> _TICK_LOWER_SHIFT) & _TICK_MASK
    tick_upper_encoded = position_id & _TICK_MASK

    # Adjust for two's complement representation for negative ticks
    if tick_lower_encoded >= _TICK_SIGN_BIT:
        tick_lower = tick_lower_encoded - (1 << _TICK_BITS)
    else:
        tick_lower = tick_lower_encoded

    if tick_upper_encoded >= _TICK_SIGN_BIT:
        tick_upper = tick_upper_encoded - (1 << _TICK_BITS)
    else:
        tick_upper = tick_upper_encoded
    
    return owner_hex, tick_lower, tick_upper
