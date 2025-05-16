# Tests for data models in infinity_pools_sdk.models.data_models

from decimal import Decimal

# First-party imports
from infinity_pools_sdk.models.data_models import (
    AddLiquidityParams,
    MulticallParams,
    SwapInfo,
    decode_position_id,
    encode_position_id,
)


def test_add_liquidity_params_to_contract_tuple():
    """Test AddLiquidityParams.to_contract_tuple for correct type conversion and structure."""
    params = AddLiquidityParams(
        token0="0xToken0Address",
        token1="0xToken1Address",
        fee=3000,
        tickLower=-1000,
        tickUpper=1000,
        amount0Desired=Decimal("1.2345"),
        amount1Desired=Decimal("500.0"),
        amount0Min=Decimal("1.2"),
        amount1Min=Decimal("499"),
        recipient="0xRecipientAddress",
        deadline=1234567890
    )

    # Test with 18 decimals for token0 and 6 decimals for token1
    token0_decimals = 18
    token1_decimals = 6
    expected_amount0_desired_wei = int(Decimal("1.2345") * (10**token0_decimals))
    expected_amount1_desired_wei = int(Decimal("500.0") * (10**token1_decimals))
    expected_amount0_min_wei = int(Decimal("1.2") * (10**token0_decimals))
    expected_amount1_min_wei = int(Decimal("499") * (10**token1_decimals))

    expected_tuple = (
        "0xToken0Address",
        "0xToken1Address",
        3000,
        -1000,
        1000,
        expected_amount0_desired_wei,
        expected_amount1_desired_wei,
        expected_amount0_min_wei,
        expected_amount1_min_wei,
        "0xRecipientAddress",
        1234567890
    )

    assert params.to_contract_tuple(token0_decimals, token1_decimals) == expected_tuple

    # Test with default decimals (18 for both)
    default_expected_amount0_desired_wei = int(Decimal("1.2345") * (10**18))
    default_expected_amount1_desired_wei = int(Decimal("500.0") * (10**18))
    default_expected_amount0_min_wei = int(Decimal("1.2") * (10**18))
    default_expected_amount1_min_wei = int(Decimal("499") * (10**18))

    default_expected_tuple = (
        "0xToken0Address",
        "0xToken1Address",
        3000,
        -1000,
        1000,
        default_expected_amount0_desired_wei,
        default_expected_amount1_desired_wei,
        default_expected_amount0_min_wei,
        default_expected_amount1_min_wei,
        "0xRecipientAddress",
        1234567890
    )
    assert params.to_contract_tuple() == default_expected_tuple


def test_swap_info_to_contract_tuple():
    """Test SwapInfo.to_contract_tuple for correct type conversion and structure."""
    params = SwapInfo(
        tokenIn="0xTokenInAddress",
        tokenOut="0xTokenOutAddress",
        fee=3000,
        amountIn=Decimal("10.5"),
        amountOutMinimum=Decimal("20.0"),
        sqrtPriceLimitX96=12345678901234567890  # Example Q64.96 value
    )

    # Test with 18 decimals for token_in and 6 decimals for token_out
    token_in_decimals = 18
    token_out_decimals = 6
    expected_amount_in_wei = int(Decimal("10.5") * (10**token_in_decimals))
    expected_amount_out_minimum_wei = int(Decimal("20.0") * (10**token_out_decimals))

    expected_tuple = (
        "0xTokenInAddress",
        "0xTokenOutAddress",
        3000,
        expected_amount_in_wei,
        expected_amount_out_minimum_wei,
        12345678901234567890
    )

    assert params.to_contract_tuple(token_in_decimals, token_out_decimals) == expected_tuple

    # Test with default decimals (18 for both)
    default_expected_amount_in_wei = int(Decimal("10.5") * (10**18))
    default_expected_amount_out_minimum_wei = int(Decimal("20.0") * (10**18))

    default_expected_tuple = (
        "0xTokenInAddress",
        "0xTokenOutAddress",
        3000,
        default_expected_amount_in_wei,
        default_expected_amount_out_minimum_wei,
        12345678901234567890
    )
    assert params.to_contract_tuple() == default_expected_tuple


def test_multicall_params_to_contract_tuple():
    """Test MulticallParams.to_contract_tuple for correct structure."""
    params = MulticallParams(
        swapperIds=[1, 2, 3],
        actions=[b'\x01\x02\x03\x04', b'\x05\x06\x07\x08'],
        data=[b'\xaa\xbb', b'\xcc\xdd']
    )

    expected_tuple = (
        [1, 2, 3],
        [b'\x01\x02\x03\x04', b'\x05\x06\x07\x08'],
        [b'\xaa\xbb', b'\xcc\xdd']
    )

    assert params.to_contract_tuple() == expected_tuple


def test_position_id_encoding_decoding():
    """Test encoding and decoding of NFT position IDs."""
    test_cases = [
        {
            "owner": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            "tick_lower": -887272,
            "tick_upper": 887272,
            "description": "Coinbase wallet example with wide ticks"
        },
        {
            "owner": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            "tick_lower": -100,
            "tick_upper": 100,
            "description": "Another address with narrow ticks"
        },
        {
            "owner": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
            "tick_lower": 0,
            "tick_upper": 1,
            "description": "Ticks at zero and one"
        },
        {
            "owner": "0x90F79bf6EB2c4f870365E785982E1f101E93b906",
            "tick_lower": -1,
            "tick_upper": 0,
            "description": "Ticks at negative one and zero"
        },
        {
            "owner": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A6C",
            "tick_lower": -200000,
            "tick_upper": -100000,
            "description": "Both ticks negative"
        },
        {
            # Max tick values based on 24-bit signed int range approx.
            # Max positive: (2^23 - 1) = 8388607
            # Min negative: -(2^23) = -8388608
            "owner": "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc",
            "tick_lower": -8388608, # Min 24-bit signed int
            "tick_upper": 8388607,  # Max 24-bit signed int
            "description": "Min and Max tick values for 24-bit signed integers"
        },
         {
            "owner": "0x976EA74026E726554dB657fA54763abd0C3a0aa9",
            "tick_lower": 100000,
            "tick_upper": 200000,
            "description": "Both ticks positive"
        },
        {
            "owner": "0x0000000000000000000000000000000000000000",
            "tick_lower": 0,
            "tick_upper": 0,
            "description": "Zero address and zero ticks"
        },
    ]

    for case in test_cases:
        original_owner = case["owner"]
        original_tick_lower = case["tick_lower"]
        original_tick_upper = case["tick_upper"]

        position_id = encode_position_id(original_owner, original_tick_lower, original_tick_upper)
        decoded_owner, decoded_tick_lower, decoded_tick_upper = decode_position_id(position_id)

        assert decoded_owner.lower() == original_owner.lower(), f"Owner mismatch for {case['description']}"
        assert decoded_tick_lower == original_tick_lower, f"Tick lower mismatch for {case['description']}"
        assert decoded_tick_upper == original_tick_upper, f"Tick upper mismatch for {case['description']}"
