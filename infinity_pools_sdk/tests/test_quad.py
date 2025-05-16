"""Test Quad type conversion utilities."""

from decimal import Decimal, getcontext

# It's good practice to control precision in tests
getcontext().prec = 100  # Set high precision for Decimal calculations

from infinity_pools_sdk.utils.quad import QUAD_PRECISION, decimal_to_quad, format_quad_for_display, quad_to_decimal

# Helper for creating Decimals from strings, ensures precision
D = Decimal


def test_zero_conversion():
    """Test converting zero."""
    assert decimal_to_quad(D("0")) == 0
    assert quad_to_decimal(0) == D("0")
    assert format_quad_for_display(0) == "0.000000"
    assert format_quad_for_display(0, display_decimals=2) == "0.00"


def test_positive_conversion_exact():
    """Test converting a positive whole number."""
    val_decimal = D("123")
    val_quad = 123 * (10**QUAD_PRECISION)
    assert decimal_to_quad(val_decimal) == val_quad
    assert quad_to_decimal(val_quad) == val_decimal
    assert format_quad_for_display(val_quad) == "123.000000"


def test_negative_conversion_exact():
    """Test converting a negative whole number."""
    val_decimal = D("-456")
    val_quad = -456 * (10**QUAD_PRECISION)
    assert decimal_to_quad(val_decimal) == val_quad
    assert quad_to_decimal(val_quad) == val_decimal
    assert format_quad_for_display(val_quad) == "-456.000000"


def test_decimal_fraction_conversion():
    """Test converting a number with fractional parts."""
    # Exact representation within QUAD_PRECISION
    val_decimal = D("123.456789")
    val_quad = 123456789 * (10 ** (QUAD_PRECISION - 6))  # 123.456789 * 10^18
    assert decimal_to_quad(val_decimal) == val_quad
    assert quad_to_decimal(val_quad) == val_decimal
    assert format_quad_for_display(val_quad, display_decimals=6) == "123.456789"
    assert format_quad_for_display(val_quad, display_decimals=8) == "123.45678900"  # Check padding


def test_smallest_fractional_unit():
    """Test converting the smallest representable fractional unit."""
    # 1 / 10^18
    val_decimal = D("1") / (D("10") ** QUAD_PRECISION)
    val_quad = 1
    assert decimal_to_quad(val_decimal) == val_quad
    assert quad_to_decimal(val_quad) == val_decimal

    # Check display formatting for very small numbers
    expected_display = "0." + "0" * (QUAD_PRECISION - 1) + "1"
    # For default 6 decimals it will be 0.000000
    assert format_quad_for_display(val_quad, display_decimals=QUAD_PRECISION) == expected_display
    assert format_quad_for_display(val_quad) == "0.000000"  # Default display_decimals=6


def test_conversion_roundtrip_precision():
    """Test roundtrip conversion for various precise Decimal values."""
    test_values = [
        D("0.000000000000000001"),  # 10^-18
        D("1.000000000000000000"),
        D("3.141592653589793238"),  # Pi to 18 decimal places
        D("123456789.987654321012345678"),
        D("-0.123456789012345678"),
        D("-1000000000.000000000000000001"),
    ]
    for original_decimal in test_values:
        # Ensure the test decimal itself doesn't exceed QUAD_PRECISION for exact roundtrip
        # Quantize to QUAD_PRECISION places, rounding down (truncate towards zero)
        quantizer = Decimal("1e-" + str(QUAD_PRECISION))
        truncated_decimal = original_decimal.quantize(quantizer, rounding="ROUND_DOWN")

        quad_val = decimal_to_quad(truncated_decimal)
        converted_decimal = quad_to_decimal(quad_val)
        assert converted_decimal == truncated_decimal, f"Roundtrip failed for {original_decimal}"


def test_large_number_conversion():
    """Test conversion of large numbers."""
    # Max uint256 approx 1.1579e77
    # If Quad implies Q128.18, then max whole part is roughly 10^(128/log2(10) - 18) = 10^(38 - 18) = 10^20
    # If Quad is standard int256, it can be larger. Let's test a large number.
    large_val_str = "12345678901234567890.123456789012345678"  # 20 digits before, 18 after
    large_decimal = D(large_val_str)

    quad_val = decimal_to_quad(large_decimal)
    # Expected quad is integer part scaled + fractional part scaled
    # 12345678901234567890 * 10^18 + 123456789012345678
    expected_quad = int(large_val_str.replace(".", ""))
    assert quad_val == expected_quad
    assert quad_to_decimal(quad_val) == large_decimal
    assert format_quad_for_display(quad_val, display_decimals=18) == large_val_str


def test_format_quad_for_display_various_decimals():
    """Test formatting with different display decimal counts."""
    val_quad = decimal_to_quad(D("123.456789123"))  # 123456789123 * 10^9
    assert format_quad_for_display(val_quad, display_decimals=0) == "123"
    assert format_quad_for_display(val_quad, display_decimals=2) == "123.46"  # Standard rounding
    assert format_quad_for_display(val_quad, display_decimals=6) == "123.456789"
    assert format_quad_for_display(val_quad, display_decimals=9) == "123.456789123"
    assert format_quad_for_display(val_quad, display_decimals=12) == "123.456789123000"  # Padding


def test_rounding_behavior_decimal_to_quad():
    """Test the truncation behavior of decimal_to_quad."""
    # Positive value, fraction greater than 0.5 of the smallest unit
    # For QUAD_PRECISION = 18, the smallest unit is 10^-18
    # So, 0.6 * 10^-18 should be truncated
    val_decimal_pos = D("1.0000000000000000006")  # 1 + 0.6 * 10^-18
    expected_quad_pos = 1 * (10**QUAD_PRECISION)  # Should be 1 * 10^18, as 0.6 is truncated
    assert decimal_to_quad(val_decimal_pos) == expected_quad_pos

    # Negative value, fraction greater than 0.5 of the smallest unit (in magnitude)
    val_decimal_neg = D("-1.0000000000000000006")  # -1 - 0.6 * 10^-18
    expected_quad_neg = -1 * (10**QUAD_PRECISION)  # Should be -1 * 10^18
    assert decimal_to_quad(val_decimal_neg) == expected_quad_neg

    # Value just below a whole number, positive
    val_decimal_pos_lt = D("0.999999999999999999")  # (10^18 - 1) / 10^18
    # Actually, with simple int() truncation, this will be 0.
    # Let's test int(0.999... * 10^18) = int(10^18-1) = 10^18-1
    val_scaled = val_decimal_pos_lt * (Decimal(10) ** QUAD_PRECISION)  # This becomes (10**18)-1
    assert decimal_to_quad(val_decimal_pos_lt) == int(val_scaled)

    # Value that requires truncation of many digits
    complex_decimal = D("123.1234567890123456789")  # 19 decimal places
    # Expected quad value after truncation: 123123456789012345678
    expected_complex_quad = 123123456789012345678
    assert decimal_to_quad(complex_decimal) == expected_complex_quad
    assert quad_to_decimal(expected_complex_quad) == D("123.123456789012345678")
