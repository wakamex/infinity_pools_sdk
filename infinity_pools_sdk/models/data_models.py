from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class AddLiquidityParams:
    """Represents the IInfinityPoolsPeriphery.AddLiquidityParams struct expected by the addLiquidity function.

    The struct fields in Solidity are: token0, token1, useVaultDeposit, startEdge, stopEdge, 
    amount0Desired, amount1Desired, amount0Min, amount1Min.
    """

    token0: str  # Address of token0
    token1: str  # Address of token1
    useVaultDeposit: bool # Whether to use funds from the vault
    startEdge: int      # The lower tick boundary of the position (corresponds to tickLower in some contexts).
    stopEdge: int       # The upper tick boundary of the position (corresponds to tickUpper in some contexts).
    amount0Desired: Decimal  # Desired amount of token0
    amount1Desired: Decimal  # Desired amount of token1
    amount0Min: Decimal  # Minimum amount of token0
    amount1Min: Decimal  # Minimum amount of token1
    # Note: fee, recipient, deadline, earnEra are not part of this specific ABI struct as per InfinityPoolsPeriphery.json for addLiquidity.

    def to_contract_tuple(self, token0_decimals: int = 18, token1_decimals: int = 18) -> tuple:
        """Convert to the 9-element tuple format expected by the addLiquidity contract function.
        
        Order: token0, token1, useVaultDeposit, startEdge, stopEdge, 
               amount0Desired, amount1Desired, amount0Min, amount1Min.
        """
        return (
            self.token0,
            self.token1,
            self.useVaultDeposit,
            self.startEdge,
            self.stopEdge,
            int(self.amount0Desired),
            int(self.amount1Desired),
            int(self.amount0Min),
            int(self.amount1Min),
        )


@dataclass
class RemoveLiquidityParams:
    """Represents the parameters for removing liquidity (draining a position)."""

    token_id: int  # The ID of the LP NFT
    recipient: str  # Address to receive the withdrawn tokens
    deadline: int  # Transaction deadline as a Unix timestamp

    def to_contract_tuple(self) -> Tuple[int, str, int]:
        """Convert to tuple format expected by the contract if deadline is included."""
        return (
            self.token_id,
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


class PositionType(Enum):
    """Type of position."""

    LP = 0
    SWAPPER = 1

@dataclass
class PositionInfo:
    """Represents the details of a liquidity position or swapper position."""

    token_id: int
    owner: str
    pool_address: str 
    position_type: PositionType
    token0: str  # Symbol or address of token0
    token1: str  # Symbol or address of token1
    
    # LP specific fields
    lp_number: Optional[int] = None # The unique identifier for an LP position within its type and pool
    start_edge: Optional[int] = None
    stop_edge: Optional[int] = None
    min_price: Optional[Decimal] = field(default_factory=Decimal)
    max_price: Optional[Decimal] = field(default_factory=Decimal)
    
    # Swapper specific fields
    swapper_number: Optional[int] = None # The unique identifier for a Swapper position within its type and pool
    # Add other swapper-specific fields if any, e.g., swap parameters if they are static

    # Financials - common or could be specialized
    amount0_total: Decimal = field(default_factory=Decimal)  # Total amount of token0 ever deposited or current if tracking that way
    amount1_total: Decimal = field(default_factory=Decimal)  # Total amount of token1 ever deposited
    fees0_earned: Decimal = field(default_factory=Decimal)
    fees1_earned: Decimal = field(default_factory=Decimal)
    amount0_collected: Decimal = field(default_factory=Decimal)
    amount1_collected: Decimal = field(default_factory=Decimal)
    liquidity: int = 0 # Current liquidity units if applicable

    # Could add more fields like transaction hashes of creation/modification, timestamps, etc.

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
