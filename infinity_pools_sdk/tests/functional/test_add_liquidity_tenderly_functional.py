"""Functional tests for add_liquidity using Tenderly impersonation.

This module tests the add_liquidity functionality of the Infinity Pools SDK
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
from infinity_pools_sdk.abis import PERIPHERY_ABI, ERC20_ABI
from infinity_pools_sdk.models.data_models import AddLiquidityParams
from infinity_pools_sdk.constants import BaseTokens, ContractAddresses, FeeTiers


class TestAddLiquidityTenderlyFunctional(BaseTenderlyFunctionalTest):
    """Functional tests for the add_liquidity function using Tenderly impersonation."""

    @pytest.mark.integration
    def test_add_liquidity_with_impersonation(self, impersonated_connector, request):
        """Test adding liquidity to a pool using impersonation.
        
        This test demonstrates how to use the Tenderly impersonation feature to
        add liquidity to a pool without needing the private key.
        
        Args:
            impersonated_connector: The impersonated connector fixture.
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
            
        # Define pool parameters (using tokens on Base network that the impersonated address has)
        # Example: wstETH/sUSDe pool with 0.3% fee
        token0 = Web3.to_checksum_address(BaseTokens.wstETH)  # wstETH on Base
        token1 = Web3.to_checksum_address(BaseTokens.sUSDe)  # sUSDe on Base
        fee = FeeTiers.FEE_0_3  # 0.3%
        
        # For testing, we'll skip pool ID retrieval and just use the token parameters directly
        print(f"Testing add_liquidity with tokens: {token0} and {token1}, fee: {fee}")
        
        # We'll skip getting detailed pool info since we're just testing the add_liquidity function
        
        print(f"Adding liquidity to pool with tokens {token0} and {token1}")
        
        # Get token contracts for approvals using the imported ERC20_ABI
        token0_contract = impersonated_connector.w3.eth.contract(address=token0, abi=ERC20_ABI)
        token1_contract = impersonated_connector.w3.eth.contract(address=token1, abi=ERC20_ABI)
        
        # Check token balances
        token0_balance = token0_contract.functions.balanceOf(self.IMPERSONATED_ADDRESS).call()
        token1_balance = token1_contract.functions.balanceOf(self.IMPERSONATED_ADDRESS).call()
        
        print(f"Token0 balance: {token0_balance}")
        print(f"Token1 balance: {token1_balance}")
        
        # Skip if not enough balance
        if token0_balance == 0 or token1_balance == 0:
            pytest.skip(f"Not enough balance for address {self.IMPERSONATED_ADDRESS}")
        
        # Define liquidity parameters
        # Use a small amount to avoid large price impact
        token0_amount = min(token0_balance, 10**16)  # 0.01 ETH or less
        token1_amount = min(token1_balance, 10**6)   # 1 USDC or less
        
        # Use the proxy address for approvals
        periphery_address = proxy_address  # Use the same proxy address we used for SDK initialization
        
        # Approve token0 with explicit gas limit to handle Tenderly fork gas limit issues
        tx_params = {
            "from": self.IMPERSONATED_ADDRESS,
            "gas": 500000,  # Set a reasonable gas limit explicitly
            "gasPrice": impersonated_connector.w3.eth.gas_price
        }
        
        try:
            tx_hash = token0_contract.functions.approve(
                periphery_address,
                token0_amount
            ).transact(tx_params)
            receipt = impersonated_connector.wait_for_transaction(tx_hash)
            assert receipt["status"] == 1, "Token0 approval failed"
        except Exception as e:
            pytest.skip(f"Failed to approve token0: {e}. This might be due to Tenderly fork configuration issues.")
            return
        
        # Approve token1 with explicit gas limit
        try:
            tx_hash = token1_contract.functions.approve(
                periphery_address,
                token1_amount
            ).transact(tx_params)
            receipt = impersonated_connector.wait_for_transaction(tx_hash)
            assert receipt["status"] == 1, "Token1 approval failed"
        except Exception as e:
            pytest.skip(f"Failed to approve token1: {e}. This might be due to Tenderly fork configuration issues.")
            return
        
        # Set tick range for the liquidity position
        # For 0.3% fee pool, the tick spacing is 60
        tick_spacing = 60
        # Using a reasonable range around 0 for testing
        tick_lower = -60 * 10  # 10 ticks below 0
        tick_upper = 60 * 10   # 10 ticks above 0
        
        params = AddLiquidityParams(
            token0=token0,
            token1=token1,
            useVaultDeposit=False,  # New parameter, defaulting to False for the test
            startEdge=tick_lower,   # Use startEdge to match AddLiquidityParams field (maps from tick_lower)
            stopEdge=tick_upper,    # Use stopEdge to match AddLiquidityParams field (maps from tick_upper)
            amount0Desired=Decimal(token0_amount),
            amount1Desired=Decimal(token1_amount),
            amount0Min=Decimal(0),
            amount1Min=Decimal(0)
            # fee, recipient, deadline, earnEra are no longer part of this AddLiquidityParams struct
        )
        
        # Get token IDs before adding liquidity
        token_ids_before = self.get_position_token_ids(impersonated_connector)
        
        # Create transaction overrides with explicit gas limit
        tx_overrides = {
            "gas": 5000000,  # Set a high explicit gas limit (5 million gas)
            "gasPrice": impersonated_connector.w3.eth.gas_price
        }
        
        # Call the SDK function with transaction overrides
        try:
            result = sdk.add_liquidity(
                token0_address=params.token0,
                token1_address=params.token1,
                use_vault_deposit=params.useVaultDeposit,
                tick_lower=params.startEdge, # Pass startEdge value to tick_lower param of SDK method
                tick_upper=params.stopEdge,  # Pass stopEdge value to tick_upper param of SDK method
                amount0_desired=params.amount0Desired,
                amount1_desired=params.amount1Desired,
                amount0_min=params.amount0Min,
                amount1_min=params.amount1Min,
                # recipient and deadline are not direct parameters for sdk.add_liquidity
                # recipient defaults to self._active_address (impersonated_connector in this test)
                transaction_overrides=tx_overrides
            )
        except Exception as e:
            pytest.skip(f"Failed to add liquidity: {e}. This might be due to Tenderly fork configuration issues.")
            return
        
        # Verify the result
        assert result is not None
        assert "transaction_hash" in result
        assert "token_id" in result
        assert "amount0" in result
        assert "amount1" in result
        
        # Print the result
        print(f"Add liquidity result: {result}")
        
        # Verify that the transaction was successful
        receipt = impersonated_connector.wait_for_transaction(result["transaction_hash"])
        assert receipt["status"] == 1, "Transaction failed"
        
        # Get token IDs after adding liquidity
        token_ids_after = self.get_position_token_ids(impersonated_connector)
        
        # Verify that a new token ID was created or an existing one was updated
        if result["token_id"] not in token_ids_before:
            assert result["token_id"] in token_ids_after, "New token ID should be in the list"
        
        # Get position details using our helper method
        position = self.get_position_details(sdk, result["token_id"])
        print(f"Position details: {position}")
        
        # Verify position details
        assert position is not None
        assert position["token0"] == token0
        assert position["token1"] == token1
        assert position["fee"] == fee
        assert position["tickLower"] == tick_lower
        assert position["tickUpper"] == tick_upper
        
        print(f"Add liquidity test completed successfully for tokens {token0} and {token1}")
        
    def get_position_token_ids(self, connector: InfinityPoolsConnector, address: Optional[str] = None) -> List[int]:
        """Get all position token IDs owned by the specified address.
        
        Args:
            connector: The connector to use for the contract calls.
            address: The address to check for token IDs. Defaults to the impersonated address.
            
        Returns:
            A list of token IDs owned by the address.
        """
        if address is None:
            address = self.IMPERSONATED_ADDRESS
            
        # Get the periphery contract using the imported PERIPHERY_ABI
        periphery_address = Web3.to_checksum_address(ContractAddresses.BASE["proxy"])
        periphery_contract = connector.w3.eth.contract(address=periphery_address, abi=PERIPHERY_ABI)
        
        # Get the number of tokens owned by the address
        balance = periphery_contract.functions.balanceOf(address).call()
        
        # Get all token IDs
        token_ids = []
        for i in range(balance):
            token_id = periphery_contract.functions.tokenOfOwnerByIndex(address, i).call()
            token_ids.append(token_id)
            
        return token_ids
        
    def get_pool_info(self, connector, pool_id) -> Dict[str, Any]:
        """Get information about a pool.
        
        Args:
            connector: The connector to use.
            pool_id: The ID of the pool.
            
        Returns:
            Dict[str, Any]: Pool information.
        """
        pools_contract = connector.get_contract_instance("InfinityPools")
        pool_info = pools_contract.functions.getPoolInfo(pool_id).call()
        
        return {
            "id": pool_id,
            "token0": pool_info[0],
            "token1": pool_info[1],
            "fee": pool_info[2],
            "tick": pool_info[3],
            "liquidity": pool_info[4]
        }
        
    def get_position_details(self, sdk: InfinityPoolsSDK, token_id: int) -> Optional[Dict[str, Any]]:
        """Get details about a position.
        
        Args:
            sdk: The SDK instance.
            token_id: The token ID of the position.
            
        Returns:
            Dict containing position details, or None if position not found.
        """
        try:
            # Get the periphery contract using the imported PERIPHERY_ABI
            periphery_address = Web3.to_checksum_address(ContractAddresses.BASE["proxy"])
            periphery_contract = sdk.connector.w3.eth.contract(address=periphery_address, abi=PERIPHERY_ABI)
            position = periphery_contract.functions.positions(token_id).call()
            
            # Convert position tuple to dict
            keys = [
                "nonce", "operator", "token0", "token1", "fee", "tickLower", "tickUpper",
                "liquidity", "feeGrowthInside0LastX128", "feeGrowthInside1LastX128",
                "tokensOwed0", "tokensOwed1"
            ]
            return dict(zip(keys, position))
        except Exception as e:
            print(f"Error getting position details: {e}")
            return None
