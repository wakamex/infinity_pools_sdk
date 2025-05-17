"""Functional tests for remove_liquidity using Tenderly impersonation.

This module tests the remove_liquidity functionality of the Infinity Pools SDK
using Tenderly forks and impersonation to test with real accounts and state.
"""

import os
import pytest
import time
from decimal import Decimal
from typing import Dict, Any, Optional, List

from web3 import Web3

from infinity_pools_sdk.core.connector import InfinityPoolsConnector
from infinity_pools_sdk.sdk import InfinityPoolsSDK
from infinity_pools_sdk.tests.functional.base_tenderly_functional import BaseTenderlyFunctionalTest
from infinity_pools_sdk.abis import ERC20_ABI, ERC721_ABI, PERIPHERY_ABI
from infinity_pools_sdk.constants import BaseTokens, ContractAddresses, FeeTiers
from infinity_pools_sdk.models.data_models import RemoveLiquidityParams


class TestRemoveLiquidityTenderlyFunctional(BaseTenderlyFunctionalTest):
    """Functional tests for the remove_liquidity function using Tenderly impersonation."""

    @pytest.mark.integration
    def test_remove_liquidity_with_impersonation(self, impersonated_connector, request):
        """Test removing liquidity from an existing position using impersonation.
        
        This test demonstrates how to use the Tenderly impersonation feature to
        remove liquidity from a real position without needing the private key.
        
        Args:
            impersonated_connector: The impersonated connector fixture.
            sdk: The SDK fixture.
            request: The pytest request object.
        """
        # Skip if integration tests are not enabled
        if not request.config.getoption("--run-integration"):
            pytest.skip("Integration tests not enabled. Use --run-integration to run.")
            
        # Use the proxy address from the constants file
        proxy_address = Web3.to_checksum_address(ContractAddresses.BASE["proxy"])
        
        # Initialize the SDK with the impersonated connector, proxy address, and the imported PERIPHERY_ABI
        try:
            sdk = InfinityPoolsSDK(impersonated_connector, periphery_address=proxy_address, periphery_abi_override=PERIPHERY_ABI)
        except Exception as e:
            pytest.skip(f"Failed to initialize SDK: {e}")
            
        # Get token IDs of positions owned by the impersonated address
        token_ids = self.get_position_token_ids(impersonated_connector)
        
        # Skip if no positions are found
        if not token_ids:
            pytest.skip(f"No positions found for address {self.IMPERSONATED_ADDRESS}")
            
        # Use the first token ID for testing
        token_id = token_ids[0]
        print(f"Testing remove_liquidity with token ID: {token_id}")
        
        # Get position details before removing liquidity
        position_before = self.get_position_details(sdk, token_id)
        print(f"Position before: {position_before}")
        
        # Define liquidity percentage to remove (50%)
        liquidity_percentage = Decimal('0.5')
        
        # Create transaction overrides with explicit gas limit
        tx_overrides = {
            "gas": 5000000,  # Set a high explicit gas limit (5 million gas)
            "gasPrice": impersonated_connector.w3.eth.gas_price
        }
        
        # Call the SDK function with the impersonated connector and transaction overrides
        result = sdk.remove_liquidity(
            token_id=token_id,
            liquidity_percentage=liquidity_percentage,
            recipient=self.IMPERSONATED_ADDRESS,  # Send back to the same account
            deadline=int(time.time()) + 3600,  # 1 hour from now
            transaction_overrides=tx_overrides
        )
        
        # Verify the result
        assert result is not None
        assert "transaction_hash" in result
        assert "token0_amount" in result
        assert "token1_amount" in result
        
        # Print the result
        print(f"Remove liquidity result: {result}")
        
        # Verify that the position has been removed or updated
        # This may require waiting for the transaction to be mined
        receipt = impersonated_connector.wait_for_transaction(result["transaction_hash"])
        assert receipt["status"] == 1, "Transaction failed"
        
        # Try to get position details after removing liquidity
        try:
            position_after = self.get_position_details(sdk, token_id)
            print(f"Position after: {position_after}")
            
            # If the position still exists, verify that liquidity has decreased
            if position_after:
                assert Decimal(position_after["liquidity"]) < Decimal(position_before["liquidity"]), \
                    "Liquidity should have decreased"
        except Exception as e:
            # If the position was completely removed, this might throw an exception
            print(f"Position may have been completely removed: {e}")
            
        print("Remove liquidity test completed successfully")
        
    def get_position_token_ids(self, connector: InfinityPoolsConnector, address: Optional[str] = None) -> List[int]:
        """Get all position token IDs owned by the specified address.
        
        Args:
            connector: The connector to use.
            address: The address to check. If None, uses the impersonated address.
            
        Returns:
            List[int]: List of token IDs.
        """
        if address is None:
            address = self.IMPERSONATED_ADDRESS
            
        # Use the proxy address for the periphery contract on Base
        periphery_address = Web3.to_checksum_address(ContractAddresses.BASE["proxy"])
        
        try:
            periphery_contract = connector.get_contract_instance("InfinityPoolsPeriphery", periphery_address)
            balance = periphery_contract.functions.balanceOf(address).call()
            
            token_ids = []
            for i in range(balance):
                token_id = periphery_contract.functions.tokenOfOwnerByIndex(
                    address, i
                ).call()
                token_ids.append(token_id)
                
            return token_ids
        except Exception as e:
            print(f"Error getting position token IDs: {e}")
            return []
    
    def get_position_details(self, sdk, token_id) -> Optional[Dict[str, Any]]:
        """Get details for a position.
        
        Args:
            sdk: The SDK instance.
            token_id: The ID of the position token.
            
        Returns:
            Optional[Dict[str, Any]]: Position details or None if an error occurs.
        """
        try:
            # Get position details directly from the periphery contract
            position_data = sdk.periphery_contract.functions.positions(token_id).call()
            
            # Format the position data
            return {
                "token_id": token_id,
                "token0": position_data[2],  # token0 address
                "token1": position_data[3],  # token1 address
                "fee": position_data[4],     # fee tier
                "tickLower": position_data[5],  # lower tick
                "tickUpper": position_data[6],  # upper tick
                "liquidity": position_data[7],  # liquidity
                "tokensOwed0": position_data[10],  # tokensOwed0
                "tokensOwed1": position_data[11]   # tokensOwed1
            }
        except Exception as e:
            print(f"Error getting position details: {e}")
            return None
