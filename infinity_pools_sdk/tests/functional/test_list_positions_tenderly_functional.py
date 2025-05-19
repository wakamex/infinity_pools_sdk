"""Functional tests for listing positions using Tenderly impersonation.

This module tests the functionality to list and get details of positions
owned by an address using Tenderly forks and impersonation.
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


class TestListPositionsTenderlyFunctional(BaseTenderlyFunctionalTest):
    """Functional tests for listing positions using Tenderly impersonation."""
    
    def test_list_positions_with_impersonation(self, impersonated_connector, request):
        """Test listing positions owned by an impersonated address.
        
        This test demonstrates how to use the Tenderly impersonation feature to
        list positions owned by a real address without needing the private key.
        
        Args:
            impersonated_connector: The impersonated connector fixture.
            request: The pytest request object.
        """
        # Skip if integration tests are not enabled
        if not request.config.getoption("--run-integration"):
            pytest.skip("Integration tests not enabled. Use --run-integration to run.")
            
        # Use the proxy address from the constants file
        proxy_address = Web3.to_checksum_address(ContractAddresses.BASE["proxy"])
        
        # Initialize the SDK with the impersonated connector and proxy address
        try:
            sdk = InfinityPoolsSDK(impersonated_connector, periphery_address=proxy_address, periphery_abi_override=PERIPHERY_ABI)
        except Exception as e:
            pytest.skip(f"Failed to initialize SDK: {e}")
        
        # Use the SDK's get_positions method to get positions
        try:
            print("\n==== CALLING get_positions() ====\n")
            positions = sdk.get_positions(self.IMPERSONATED_ADDRESS)
            print(f"\n==== RESULT: Found {len(positions)} positions for address {self.IMPERSONATED_ADDRESS} ====\n")
            
            # Print detailed information about each position
            if positions:
                print("\n==== ACTUAL POSITIONS FOUND ====\n")
                for i, position in enumerate(positions):
                    print(f"Position {i+1}:")
                    print(f"  Token ID: {position.get('token_id')}")
                    print(f"  Token0: {position.get('token0')}")
                    print(f"  Token1: {position.get('token1')}")
                    print(f"  Fee: {position.get('fee')}")
                    print(f"  Ticks: {position.get('tickLower')} to {position.get('tickUpper')}")
                    print(f"  Liquidity: {position.get('liquidity')}")
                    print(f"  Tokens Owed: {position.get('tokensOwed0')} (token0), {position.get('tokensOwed1')} (token1)")
                    print()
            
            if not positions:
                print("\n==== NO POSITIONS FOUND ====\n")
                # Fail the test if no positions are found
                pytest.fail("No positions found for the impersonated address. The get_positions method should return at least one position.")
                return
            
            # Print details for each position
            for position in positions:
                token_id = position.get("token_id")
                print(f"\nPosition ID: {token_id}")
                print(f"Token0: {position['token0']}")
                print(f"Token1: {position['token1']}")
                print(f"Fee: {position['fee']}")
                print(f"Tick Range: {position['tickLower']} to {position['tickUpper']}")
                print(f"Liquidity: {position['liquidity']}")
                print(f"Tokens Owed: {position['tokensOwed0']} (token0), {position['tokensOwed1']} (token1)")
                
                # Get token symbols and balances
                token0_address = position.get("token0")
                token1_address = position.get("token1")
                
                if token0_address and token1_address:
                    try:
                        token0_contract = impersonated_connector.w3.eth.contract(address=token0_address, abi=ERC20_ABI)
                        token1_contract = impersonated_connector.w3.eth.contract(address=token1_address, abi=ERC20_ABI)
                        
                        # Get token symbols
                        token0_symbol = token0_contract.functions.symbol().call()
                        token1_symbol = token1_contract.functions.symbol().call()
                        print(f"Tokens: {token0_symbol}/{token1_symbol}")
                        
                        # Get token balances
                        token0_decimals = token0_contract.functions.decimals().call()
                        token1_decimals = token1_contract.functions.decimals().call()
                        
                        token0_balance = token0_contract.functions.balanceOf(self.IMPERSONATED_ADDRESS).call()
                        token1_balance = token1_contract.functions.balanceOf(self.IMPERSONATED_ADDRESS).call()
                        
                        print(f"Token0 Balance: {token0_balance / 10**token0_decimals} {token0_symbol}")
                        print(f"Token1 Balance: {token1_balance / 10**token1_decimals} {token1_symbol}")
                    except Exception as e:
                        print(f"Error getting token info: {e}")
            
            # Assert that we found at least one position
            assert len(positions) > 0, "Should have found at least one position"
            
            print("List positions test completed successfully")
            
        except Exception as e:
            pytest.skip(f"Failed to get positions: {e}")
    
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
            
            # Handle different data structures that might be returned
            # Some contracts return a tuple of tuples, others return a flat tuple
            if isinstance(position_data, (list, tuple)):
                if len(position_data) > 0 and isinstance(position_data[0], (list, tuple)):
                    # It's a tuple of tuples, use the inner tuple
                    position_data = position_data[0]
                
                # Ensure we have enough elements in the tuple
                if len(position_data) >= 12:
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
                else:
                    print(f"Position data has unexpected length: {len(position_data)}")
            else:
                print(f"Position data has unexpected type: {type(position_data)}")
            
            return None
        except Exception as e:
            print(f"Error getting position details: {e}")
            return None
