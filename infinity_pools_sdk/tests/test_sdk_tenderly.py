"""Integration tests for the Infinity Pools SDK using Tenderly forks."""

import os
import time
from decimal import Decimal

import pytest

from infinity_pools_sdk.sdk import InfinityPoolsSDK
from infinity_pools_sdk.models.data_models import AddLiquidityParams, RemoveLiquidityParams

# Import our Tenderly fork fixtures
from .chain_fixtures import tenderly_fork, tenderly_connector, tenderly_user_connector


# Contract addresses - these should be set to the actual addresses on the forked network
# You can set these via environment variables or hardcode them for specific tests
PERIPHERY_ADDRESS = os.environ.get("PERIPHERY_ADDRESS", "0xPeripheryContractAddress")
TOKEN0_ADDRESS = os.environ.get("TOKEN0_ADDRESS", "0xToken0Address")
TOKEN1_ADDRESS = os.environ.get("TOKEN1_ADDRESS", "0xToken1Address")

# Test parameters
FEE = 3000
TICK_LOWER = -100
TICK_UPPER = 100
AMOUNT0_DESIRED = Decimal("100")
AMOUNT1_DESIRED = Decimal("200")
AMOUNT0_MIN = Decimal("99")
AMOUNT1_MIN = Decimal("198")


class TestInfinityPoolsSDKTenderly:
    """Integration tests for the Infinity Pools SDK using Tenderly forks."""

    @pytest.mark.integration
    def test_add_liquidity_success(self, tenderly_fork, tenderly_connector):
        """Test add_liquidity successfully with a Tenderly fork."""
        # Skip this test if we don't have contract addresses yet
        if PERIPHERY_ADDRESS == "0xPeripheryContractAddress":
            pytest.skip("Periphery contract address not configured")
            
        # Setup
        sdk = InfinityPoolsSDK(
            connector=tenderly_connector,
            periphery_address=PERIPHERY_ADDRESS
        )
        
        # Set deadline to 1 hour from now
        deadline = int(time.time()) + 3600
        
        # Execute add_liquidity
        result = sdk.add_liquidity(
            token0_address=TOKEN0_ADDRESS,
            token1_address=TOKEN1_ADDRESS,
            fee=FEE,
            tick_lower=TICK_LOWER,
            tick_upper=TICK_UPPER,
            amount0_desired=AMOUNT0_DESIRED,
            amount1_desired=AMOUNT1_DESIRED,
            amount0_min=AMOUNT0_MIN,
            amount1_min=AMOUNT1_MIN,
            recipient=tenderly_connector.account.address,
            deadline=deadline,
            auto_approve=True
        )
        
        # Verify transaction was successful
        assert result["receipt"]["status"] == 1
        
        # Verify position was created
        # This would need to extract the token_id from the transaction receipt events
        # For now, we'll just verify the transaction was successful

    @pytest.mark.integration
    def test_remove_liquidity_success(self, tenderly_fork, tenderly_connector):
        """Test remove_liquidity successfully with a Tenderly fork."""
        # Skip this test if we don't have contract addresses yet
        if PERIPHERY_ADDRESS == "0xPeripheryContractAddress":
            pytest.skip("Periphery contract address not configured")
            
        # Setup
        sdk = InfinityPoolsSDK(
            connector=tenderly_connector,
            periphery_address=PERIPHERY_ADDRESS
        )
        
        # First add liquidity to get a position
        deadline = int(time.time()) + 3600
        add_result = sdk.add_liquidity(
            token0_address=TOKEN0_ADDRESS,
            token1_address=TOKEN1_ADDRESS,
            fee=FEE,
            tick_lower=TICK_LOWER,
            tick_upper=TICK_UPPER,
            amount0_desired=AMOUNT0_DESIRED,
            amount1_desired=AMOUNT1_DESIRED,
            amount0_min=AMOUNT0_MIN,
            amount1_min=AMOUNT1_MIN,
            recipient=tenderly_connector.account.address,
            deadline=deadline,
            auto_approve=True
        )
        
        # Extract the token ID from the transaction receipt
        # This would need to parse the events from the receipt
        # For demonstration, we'll use a helper method (to be implemented)
        token_id = self._extract_token_id_from_receipt(add_result["receipt"])
        
        # If we couldn't extract the token ID, skip the rest of the test
        if token_id is None:
            pytest.skip("Could not extract token ID from receipt")
        
        # Execute remove_liquidity
        remove_result = sdk.remove_liquidity(
            token_id=token_id,
            liquidity_percentage=Decimal("1"),  # Remove 100%
            recipient=tenderly_connector.account.address,
            deadline=deadline
        )
        
        # Verify transaction was successful
        assert remove_result["receipt"]["status"] == 1

    @pytest.mark.integration
    def test_multi_user_interaction(self, tenderly_fork, tenderly_connector, tenderly_user_connector):
        """Test interactions between multiple users."""
        # Skip this test if we don't have contract addresses yet
        if PERIPHERY_ADDRESS == "0xPeripheryContractAddress":
            pytest.skip("Periphery contract address not configured")
            
        # Setup SDKs for both users
        deployer_sdk = InfinityPoolsSDK(
            connector=tenderly_connector,
            periphery_address=PERIPHERY_ADDRESS
        )
        
        user_sdk = InfinityPoolsSDK(
            connector=tenderly_user_connector,
            periphery_address=PERIPHERY_ADDRESS
        )
        
        # Verify we have different addresses
        assert deployer_sdk.connector.account.address != user_sdk.connector.account.address
        
        # For a complete test, we would:
        # 1. Have deployer add liquidity
        # 2. Transfer the position to the user
        # 3. Have the user remove liquidity
        # 
        # This would require implementing position transfer functionality
        # For now, we'll just verify the accounts are different
        
        # Example of what this might look like:
        # deadline = int(time.time()) + 3600
        # add_result = deployer_sdk.add_liquidity(...)
        # token_id = self._extract_token_id_from_receipt(add_result["receipt"])
        # transfer_result = deployer_sdk.transfer_position(token_id, user_sdk.connector.account.address)
        # remove_result = user_sdk.remove_liquidity(token_id, ...)
        
        pytest.skip("Full multi-user test not implemented yet")

    def _extract_token_id_from_receipt(self, receipt):
        """Helper method to extract token ID from transaction receipt.
        
        This would need to parse the events from the receipt to find the token ID.
        For now, we'll return a placeholder.
        
        Args:
            receipt: The transaction receipt.
            
        Returns:
            int: The token ID, or None if it couldn't be extracted.
        """
        # In a real implementation, we would:
        # 1. Get the ABI for the periphery contract
        # 2. Create a contract instance
        # 3. Parse the logs using the contract's events
        # 4. Extract the token ID from the relevant event
        
        # For now, just return a placeholder
        return 1  # Placeholder token ID
