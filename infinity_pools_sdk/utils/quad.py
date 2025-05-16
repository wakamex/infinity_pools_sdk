from decimal import Decimal

# It's good practice to set the precision for Decimal operations globally
# to avoid unexpected rounding issues, though for these specific functions,
# direct scaling and division should be fine.
# from decimal import getcontext
# getcontext().prec = 50 # Example: Set precision to 50 decimal places

QUAD_PRECISION = 18  # Number of decimal places in Quad type

def decimal_to_quad(value: Decimal) -> int:
    """Convert a Python Decimal to a Quad fixed-point integer representation.
    
    Note: Solidity's fixed-point types are usually signed integers.
    This function assumes the input Decimal can be negative.
    Rounding is towards zero (truncate) to match typical integer conversion.
    """
    # To ensure truncation (rounding towards zero) like int(),
    # we can use quantize with ROUND_DOWN for positive and ROUND_UP for negative,
    # or rely on int() behavior after scaling.
    # For positive numbers, int(x.y) truncates. For negative -int(x.y) truncates.
    # decimal.quantize is more explicit for financial math.
    # Example: Decimal('3.141592653589793238') * (10**18)
    # However, int() directly on the scaled Decimal should behave as truncate.
    scaled_value = value * (Decimal(10) ** QUAD_PRECISION)
    return int(scaled_value)

def quad_to_decimal(value: int) -> Decimal:
    """Convert a Quad fixed-point integer to a Python Decimal."""
    return Decimal(value) / (Decimal(10) ** QUAD_PRECISION)

def format_quad_for_display(value: int, display_decimals: int = 6) -> str:
    """Format a Quad value for human-readable display with specified precision.
    
    Args:
        value: The Quad fixed-point integer.
        display_decimals: The number of decimal places to show in the output string.
    """
    decimal_value = quad_to_decimal(value)
    # Ensure the output string has the correct number of decimal places,
    # even if they are trailing zeros.
    return f"{decimal_value:.{display_decimals}f}"
