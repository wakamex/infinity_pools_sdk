"""Integration tests for the Infinity Pools SDK using a local chain."""

import time
from decimal import Decimal

import pytest
from web3 import Web3

from infinity_pools_sdk.sdk import InfinityPoolsSDK
from infinity_pools_sdk.models.data_models import AddLiquidityParams, RemoveLiquidityParams

# Import our local chain fixtures
from .chain_fixtures import local_chain, infinity_pools_connector, user_connector


# Constants for testing
PERIPHERY_ADDRESS = "0xPeripheryContractAddress"  # Replace with actual address when deployed
TOKEN0_ADDRESS = "0xToken0Address"  # Replace with actual address
TOKEN1_ADDRESS = "0xToken1Address"  # Replace with actual address
FEE = 3000
TICK_LOWER = -100
TICK_UPPER = 100
AMOUNT0_DESIRED = Decimal("100")
AMOUNT1_DESIRED = Decimal("200")
AMOUNT0_MIN = Decimal("99")
AMOUNT1_MIN = Decimal("198")


class TestInfinityPoolsSDKIntegration:
    """Integration tests for the Infinity Pools SDK."""

    @pytest.mark.integration
    def test_add_liquidity_success(self, local_chain, infinity_pools_connector):
        """Test add_liquidity successfully with a local chain."""
        # Skip this test if we don't have contract addresses yet
        if PERIPHERY_ADDRESS == "0xPeripheryContractAddress":
            pytest.skip("Periphery contract address not configured")
            
        # Setup
        sdk = InfinityPoolsSDK(
            connector=infinity_pools_connector,
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
            recipient=infinity_pools_connector.account.address,
            deadline=deadline,
            auto_approve=True
        )
        
        # Verify transaction was successful
        assert result["receipt"]["status"] == 1
        
        # Verify position was created (this would need the actual contract to verify)
        # token_id = result.get("token_id")
        # position = sdk.periphery_contract.functions.positions(token_id).call()
        # assert position[7] > 0  # Verify liquidity was added

    @pytest.mark.integration
    def test_remove_liquidity_success(self, local_chain, infinity_pools_connector):
        """Test remove_liquidity successfully with a local chain."""
        # Skip this test if we don't have contract addresses yet
        if PERIPHERY_ADDRESS == "0xPeripheryContractAddress":
            pytest.skip("Periphery contract address not configured")
            
        # Setup
        sdk = InfinityPoolsSDK(
            connector=infinity_pools_connector,
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
            recipient=infinity_pools_connector.account.address,
            deadline=deadline,
            auto_approve=True
        )
        
        # Get the token ID from the add_liquidity result
        # This would need to be extracted from the transaction receipt or events
        # For now, we'll just use a placeholder
        token_id = 1  # Replace with actual token ID extraction
        
        # Execute remove_liquidity
        remove_result = sdk.remove_liquidity(
            token_id=token_id,
            liquidity_percentage=Decimal("1"),  # Remove 100%
            recipient=infinity_pools_connector.account.address,
            deadline=deadline
        )
        
        # Verify transaction was successful
        assert remove_result["receipt"]["status"] == 1
        
        # Verify position was removed (this would need the actual contract to verify)
        # position = sdk.periphery_contract.functions.positions(token_id).call()
        # assert position[7] == 0  # Verify liquidity was removed

    @pytest.mark.integration
    def test_batch_actions(self, local_chain, infinity_pools_connector):
        """Test batch_actions for combining multiple operations."""
        # Skip this test if we don't have contract addresses yet
        if PERIPHERY_ADDRESS == "0xPeripheryContractAddress":
            pytest.skip("Periphery contract address not configured")
            
        # Setup
        sdk = InfinityPoolsSDK(
            connector=infinity_pools_connector,
            periphery_address=PERIPHERY_ADDRESS
        )
        
        # This test would implement the multicall/batch_actions pattern
        # mentioned in the memory about function selector `0xac9650d8`
        
        # For now, we'll just create a placeholder test
        # that would be filled in once the batch_actions method is implemented
        
        # Example of what this might look like:
        # actions = [
        #     sdk.build_approve_action(TOKEN0_ADDRESS, PERIPHERY_ADDRESS, AMOUNT0_DESIRED),
        #     sdk.build_approve_action(TOKEN1_ADDRESS, PERIPHERY_ADDRESS, AMOUNT1_DESIRED),
        #     sdk.build_add_liquidity_action(
        #         token0_address=TOKEN0_ADDRESS,
        #         token1_address=TOKEN1_ADDRESS,
        #         fee=FEE,
        #         tick_lower=TICK_LOWER,
        #         tick_upper=TICK_UPPER,
        #         amount0_desired=AMOUNT0_DESIRED,
        #         amount1_desired=AMOUNT1_DESIRED,
        #         amount0_min=AMOUNT0_MIN,
        #         amount1_min=AMOUNT1_MIN,
        #         recipient=infinity_pools_connector.account.address,
        #         deadline=int(time.time()) + 3600
        #     )
        # ]
        # result = sdk.batch_actions(actions)
        # assert result["receipt"]["status"] == 1
        
        # For now, just mark as skipped until implemented
        pytest.skip("batch_actions not yet implemented")


# Additional test classes could be added for other SDK functionality
class TestInfinityPoolsSDKMultiUserIntegration:
    """Integration tests involving multiple users."""
    
    @pytest.mark.integration
    def test_add_liquidity_and_transfer(self, local_chain, infinity_pools_connector, user_connector):
        """Test adding liquidity and then transferring the position to another user."""
        # Skip this test if we don't have contract addresses yet
        if PERIPHERY_ADDRESS == "0xPeripheryContractAddress":
            pytest.skip("Periphery contract address not configured")
            
        # Setup
        deployer_sdk = InfinityPoolsSDK(
            connector=infinity_pools_connector,
            periphery_address=PERIPHERY_ADDRESS
        )
        
        user_sdk = InfinityPoolsSDK(
            connector=user_connector,
            periphery_address=PERIPHERY_ADDRESS
        )
        
        # Add liquidity with deployer account
        deadline = int(time.time()) + 3600
        add_result = deployer_sdk.add_liquidity(
            token0_address=TOKEN0_ADDRESS,
            token1_address=TOKEN1_ADDRESS,
            fee=FEE,
            tick_lower=TICK_LOWER,
            tick_upper=TICK_UPPER,
            amount0_desired=AMOUNT0_DESIRED,
            amount1_desired=AMOUNT1_DESIRED,
            amount0_min=AMOUNT0_MIN,
            amount1_min=AMOUNT1_MIN,
            recipient=infinity_pools_connector.account.address,
            deadline=deadline,
            auto_approve=True
        )
        
        # Get the token ID
        token_id = 1  # Replace with actual token ID extraction
        
        # This would transfer the position NFT to the user
        # For now, we'll just skip as this would need the actual contract implementation
        pytest.skip("NFT transfer not yet implemented")
        
        # Example of what this might look like:
        # transfer_result = deployer_sdk.transfer_position(
        #     token_id=token_id,
        #     to_address=user_connector.account.address
        # )
        # assert transfer_result["receipt"]["status"] == 1
        
        # # Now user should be able to remove liquidity
        # remove_result = user_sdk.remove_liquidity(
        #     token_id=token_id,
        #     liquidity_percentage=Decimal("1"),
        #     recipient=user_connector.account.address,
        #     deadline=deadline
        # )
        # assert remove_result["receipt"]["status"] == 1
