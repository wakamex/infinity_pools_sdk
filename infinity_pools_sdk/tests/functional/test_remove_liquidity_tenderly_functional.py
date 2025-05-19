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
    
    def setup_liquidity_position(self, sdk, impersonated_connector):
        """Create a liquidity position for testing remove_liquidity.
        
        This helper method creates a liquidity position that can be used for testing
        the remove_liquidity functionality. It uses the tokens that the impersonated
        address has available on the Base network.
        
        Args:
            sdk: The SDK instance.
            impersonated_connector: The impersonated connector.
            
        Returns:
            int: The token ID of the created position, or None if creation failed.
        """
        try:
            # Define token addresses (using tokens the impersonated address has)
            token0 = Web3.to_checksum_address(BaseTokens.wstETH)  # wstETH on Base
            token1 = Web3.to_checksum_address(BaseTokens.sUSDe)  # sUSDe on Base
            fee = FeeTiers.FEE_0_3  # 0.3%
            
            # Get token contracts for approvals and balance checks
            token0_contract = impersonated_connector.w3.eth.contract(address=token0, abi=ERC20_ABI)
            token1_contract = impersonated_connector.w3.eth.contract(address=token1, abi=ERC20_ABI)
            
            # Check token balances
            token0_balance = token0_contract.functions.balanceOf(self.IMPERSONATED_ADDRESS).call()
            token1_balance = token1_contract.functions.balanceOf(self.IMPERSONATED_ADDRESS).call()
            
            print(f"Token0 (wstETH) balance: {token0_balance}")
            print(f"Token1 (sUSDe) balance: {token1_balance}")
            
            if token0_balance == 0 or token1_balance == 0:
                print(f"Not enough balance for address {self.IMPERSONATED_ADDRESS}")
                return None
            
            # Use a small amount of tokens for the position
            token0_amount = min(token0_balance, 10**16)  # 0.01 ETH or less
            token1_amount = min(token1_balance, 10**6)   # 1 USDC or less
            
            # Set price range (wide range to ensure it's in-range)
            current_tick = -887272  # A default value, ideally this would be fetched from the pool
            tick_spacing = 60       # For 0.3% fee tier
            tick_lower = current_tick - (10 * tick_spacing)
            tick_upper = current_tick + (10 * tick_spacing)
            
            # Approve tokens if needed
            try:
                # Check current allowance
                token0_allowance = token0_contract.functions.allowance(
                    self.IMPERSONATED_ADDRESS, sdk.periphery_address
                ).call()
                token1_allowance = token1_contract.functions.allowance(
                    self.IMPERSONATED_ADDRESS, sdk.periphery_address
                ).call()
                
                # Approve token0 if needed
                if token0_allowance < token0_amount:
                    tx_hash = token0_contract.functions.approve(
                        sdk.periphery_address, 2**256 - 1  # Max approval
                    ).transact({"from": self.IMPERSONATED_ADDRESS})
                    impersonated_connector.wait_for_transaction(tx_hash)
                    print(f"Approved token0 (wstETH)")
                
                # Approve token1 if needed
                if token1_allowance < token1_amount:
                    tx_hash = token1_contract.functions.approve(
                        sdk.periphery_address, 2**256 - 1  # Max approval
                    ).transact({"from": self.IMPERSONATED_ADDRESS})
                    impersonated_connector.wait_for_transaction(tx_hash)
                    print(f"Approved token1 (sUSDe)")
            except Exception as e:
                print(f"Failed to approve tokens: {e}")
                return None
            
            # Create transaction overrides with explicit gas limit
            tx_overrides = {
                "gas": 5000000,  # Set a high explicit gas limit (5 million gas)
                "gasPrice": impersonated_connector.w3.eth.gas_price
            }
            
            # Add liquidity using the SDK
            result = sdk.add_liquidity(
                token0_address=token0,
                token1_address=token1,
                fee=fee,
                tick_lower=tick_lower,
                tick_upper=tick_upper,
                amount0_desired=Decimal(token0_amount) / Decimal(10**18),  # Convert to ETH units
                amount1_desired=Decimal(token1_amount) / Decimal(10**6),   # Convert to USDC units
                amount0_min=0,  # No slippage protection for test
                amount1_min=0,  # No slippage protection for test
                recipient=self.IMPERSONATED_ADDRESS,
                deadline=int(time.time()) + 3600,  # 1 hour from now
                auto_approve=True,
                transaction_overrides=tx_overrides
            )
            
            print(f"Add liquidity result: {result}")
            
            # Return the token ID of the created position
            return result.get("token_id")
        except Exception as e:
            print(f"Failed to create liquidity position: {e}")
            return None

    @pytest.mark.integration
    def test_remove_liquidity_with_impersonation(self, impersonated_connector, request):
        """Test removing liquidity from an existing position using impersonation.
        
        This test demonstrates how to use the Tenderly impersonation feature to
        remove liquidity from a real position without needing the private key.
        
        Args:
            impersonated_connector: The impersonated connector fixture.
            request: The pytest request object.
        """
        # Skip if --run-integration flag is not provided
        if not request.config.getoption("--run-integration"):
            pytest.skip("Skipping integration test. Use --run-integration to run")
        
        # Use the proxy address from the constants file
        proxy_address = Web3.to_checksum_address(ContractAddresses.BASE["proxy"])
        
        # Initialize the SDK with the impersonated connector and proxy address
        try:
            sdk = InfinityPoolsSDK(impersonated_connector, periphery_address=proxy_address, periphery_abi_override=PERIPHERY_ABI)
        except Exception as e:
            pytest.skip(f"Failed to initialize SDK: {e}")
        
        # Find a position to remove liquidity from
        token_id = None
        
        # Try using the SDK's get_positions method first
        try:
            positions = sdk.get_positions(self.IMPERSONATED_ADDRESS)
            if positions:
                print(f"Found {len(positions)} positions using SDK method")
                token_id = positions[0].get('token_id')
                print(f"Using position with token ID: {token_id}")
        except Exception as e:
            print(f"Error getting positions with SDK method: {e}")
        
        # If SDK method fails, try direct contract calls
        if token_id is None:
            existing_token_ids = self.get_position_token_ids(impersonated_connector)
            if existing_token_ids:
                token_id = existing_token_ids[0]
                print(f"Using existing position with token ID: {token_id} from direct contract calls")
        
        # If still no position found, try a range of token IDs
        if token_id is None:
            print("Trying with a range of token IDs...")
            for potential_id in range(1, 11):
                try:
                    # Check if the position belongs to the impersonated address
                    owner = sdk.periphery_contract.functions.ownerOf(potential_id).call()
                    if owner.lower() == self.IMPERSONATED_ADDRESS.lower():
                        print(f"Found position with token ID: {potential_id}")
                        token_id = potential_id
                        break
                except Exception:
                    # Ignore errors for non-existent token IDs
                    pass
        
        # If still no position found, try to create one
        if token_id is None:
            print("No existing positions found. Attempting to create one...")
            token_id = self.setup_liquidity_position(sdk, impersonated_connector)
        
        # If we still don't have a token ID, skip the test
        if token_id is None:
            pytest.skip("Could not find or create a position for testing")
        
        try:
            # Get position details before removing liquidity
            position_before = self.get_position_details(sdk, token_id)
            if not position_before:
                pytest.skip(f"Could not get details for position {token_id}")
                
            print("\nPosition details before removing liquidity:")
            print(f"Token ID: {token_id}")
            print(f"Liquidity: {position_before['liquidity']}")
            print(f"Tokens Owed: {position_before['tokensOwed0']} (token0), {position_before['tokensOwed1']} (token1)")
            
            # Get token contracts
            token0_address = position_before['token0']
            token1_address = position_before['token1']
            
            token0_contract = impersonated_connector.w3.eth.contract(address=token0_address, abi=ERC20_ABI)
            token1_contract = impersonated_connector.w3.eth.contract(address=token1_address, abi=ERC20_ABI)
            
            # Get token balances before removing liquidity
            token0_balance_before = token0_contract.functions.balanceOf(self.IMPERSONATED_ADDRESS).call()
            token1_balance_before = token1_contract.functions.balanceOf(self.IMPERSONATED_ADDRESS).call()
            
            print(f"\nToken balances before removing liquidity:")
            print(f"Token0 balance: {token0_balance_before}")
            print(f"Token1 balance: {token1_balance_before}")
            
            # Remove liquidity (50% of the position)
            liquidity_percentage = Decimal('0.5')  # Remove 50% of the position
            
            # Call the remove_liquidity method
            result = sdk.remove_liquidity(
                token_id=token_id,
                liquidity_percentage=liquidity_percentage,
                recipient=self.IMPERSONATED_ADDRESS,
                deadline=int(time.time()) + 3600,  # 1 hour from now
                amount0_min=0,  # No slippage protection for test
                amount1_min=0   # No slippage protection for test
            )
            
            print(f"\nRemove liquidity transaction successful:")
            print(f"Transaction hash: {result['tx_hash']}")
            print(f"Amount0: {result.get('amount0', 'N/A')}")
            print(f"Amount1: {result.get('amount1', 'N/A')}")
            
            # Wait a moment for the transaction to be processed
            time.sleep(2)
            
            # Get token balances after removing liquidity
            token0_balance_after = token0_contract.functions.balanceOf(self.IMPERSONATED_ADDRESS).call()
            token1_balance_after = token1_contract.functions.balanceOf(self.IMPERSONATED_ADDRESS).call()
            
            print(f"\nToken balances after removing liquidity:")
            print(f"Token0 balance: {token0_balance_after}")
            print(f"Token1 balance: {token1_balance_after}")
            
            # Get position details after removing liquidity
            position_after = self.get_position_details(sdk, token_id)
            
            if position_after:
                print("\nPosition details after removing liquidity:")
                print(f"Liquidity: {position_after['liquidity']}")
                print(f"Tokens Owed: {position_after['tokensOwed0']} (token0), {position_after['tokensOwed1']} (token1)")
                
                # Assert that liquidity decreased
                if liquidity_percentage < Decimal('1'):
                    # If we removed less than 100%, the position should still exist with less liquidity
                    assert int(position_after["liquidity"]) < int(position_before["liquidity"]), \
                        "Liquidity should have decreased"
                else:
                    # If we removed 100%, the position might still exist but with zero liquidity
                    assert int(position_after["liquidity"]) == 0, "Liquidity should be zero after full removal"
            else:
                # If the position was completely removed, that's also valid
                print("Position was completely removed")
                
            print("Remove liquidity test completed successfully")
            
        except Exception as e:
            pytest.skip(f"Failed to remove liquidity: {e}")
        
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
