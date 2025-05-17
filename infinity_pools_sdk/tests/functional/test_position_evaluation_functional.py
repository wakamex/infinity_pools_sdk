"""Functional test for evaluating positions using Tenderly impersonation.

This module provides a focused test to verify that we can evaluate existing
LP positions using Tenderly impersonation without needing private keys.
"""

import pytest
import os
from decimal import Decimal
from typing import Dict, Any, List

from web3 import Web3
from web3.contract import Contract

from infinity_pools_sdk.tests.functional.base_tenderly_functional import BaseTenderlyFunctionalTest


class TestPositionEvaluationFunctional(BaseTenderlyFunctionalTest):
    """Functional tests for evaluating positions with Tenderly impersonation."""

    @pytest.mark.integration
    def test_evaluate_existing_positions(self, impersonated_connector, request):
        """Test evaluating existing positions using impersonation.
        
        This test demonstrates how to use Tenderly impersonation to evaluate
        existing LP positions without needing the private key of the account.
        
        Args:
            impersonated_connector: The impersonated connector fixture.
            request: The pytest request object.
        """
        # Skip if integration tests are not enabled
        if not request.config.getoption("--run-integration"):
            pytest.skip("Integration tests not enabled. Use --run-integration to run.")
            
        # For testing with Uniswap V3 positions, we'll use the NonfungiblePositionManager contract
        # This is the Uniswap V3 NonfungiblePositionManager address on mainnet
        nft_manager_address = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
        
        # Create a contract instance for the NonfungiblePositionManager
        nft_contract = self._create_nft_manager_contract(impersonated_connector, nft_manager_address)
        
        # Get the positions owned by the impersonated address
        token_ids = self._get_position_token_ids(impersonated_connector, nft_contract)
        print(f"Found {len(token_ids)} LP positions for address {self.IMPERSONATED_ADDRESS}")
        
        # If there are positions, evaluate the first one
        if token_ids:
            token_id = token_ids[0]
            print(f"Evaluating position with token ID: {token_id}")
            
            # Get position details
            position_details = self._get_position_details(impersonated_connector, nft_contract, token_id)
            print(f"Position details: {position_details}")
            
            # Verify that we can get position details
            assert position_details is not None, "Failed to get position details"
            assert "token0" in position_details, "Position details missing token0"
            assert "token1" in position_details, "Position details missing token1"
            assert "fee" in position_details, "Position details missing fee"
            assert "liquidity" in position_details, "Position details missing liquidity"
            
            # Get token information
            token0_info = self._get_token_info(impersonated_connector, position_details["token0"])
            token1_info = self._get_token_info(impersonated_connector, position_details["token1"])
            
            print(f"Token0: {token0_info['symbol']} ({position_details['token0']})")
            print(f"Token1: {token1_info['symbol']} ({position_details['token1']})")
            print(f"Fee: {position_details['fee'] / 10000}%")
            print(f"Liquidity: {position_details['liquidity']}")
            print(f"Tick range: {position_details['tickLower']} to {position_details['tickUpper']}")
            
            # Calculate position value (simplified)
            token0_amount = position_details.get("amount0", 0)
            token1_amount = position_details.get("amount1", 0)
            
            token0_value = token0_amount / (10 ** token0_info["decimals"])
            token1_value = token1_amount / (10 ** token1_info["decimals"])
            
            print(f"Token0 amount: {token0_value} {token0_info['symbol']}")
            print(f"Token1 amount: {token1_value} {token1_info['symbol']}")
            
            # Calculate fees earned (if available)
            token0_fees = position_details.get("tokensOwed0", 0)
            token1_fees = position_details.get("tokensOwed1", 0)
            
            token0_fees_value = token0_fees / (10 ** token0_info["decimals"])
            token1_fees_value = token1_fees / (10 ** token1_info["decimals"])
            
            print(f"Token0 fees earned: {token0_fees_value} {token0_info['symbol']}")
            print(f"Token1 fees earned: {token1_fees_value} {token1_info['symbol']}")
            
            print("Position evaluation completed successfully")
        else:
            print(f"No LP positions found for address {self.IMPERSONATED_ADDRESS}")
            pytest.skip("No LP positions found for testing")
    
    def _create_nft_manager_contract(self, connector, address: str) -> Contract:
        """Create a contract instance for the NonfungiblePositionManager.
        
        Args:
            connector: The connector to use.
            address: The address of the NonfungiblePositionManager contract.
            
        Returns:
            Contract: The contract instance.
        """
        # Minimal ABI for the functions we need
        abi = [
            {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "payable": False, "stateMutability": "view", "type": "function"},
            {"constant": True, "inputs": [{"name": "owner", "type": "address"}, {"name": "index", "type": "uint256"}], "name": "tokenOfOwnerByIndex", "outputs": [{"name": "", "type": "uint256"}], "payable": False, "stateMutability": "view", "type": "function"},
            {"constant": True, "inputs": [{"name": "tokenId", "type": "uint256"}], "name": "ownerOf", "outputs": [{"name": "", "type": "address"}], "payable": False, "stateMutability": "view", "type": "function"},
            {"constant": True, "inputs": [{"name": "tokenId", "type": "uint256"}], "name": "positions", "outputs": [{"components": [{"name": "nonce", "type": "uint96"}, {"name": "operator", "type": "address"}, {"name": "token0", "type": "address"}, {"name": "token1", "type": "address"}, {"name": "fee", "type": "uint24"}, {"name": "tickLower", "type": "int24"}, {"name": "tickUpper", "type": "int24"}, {"name": "liquidity", "type": "uint128"}, {"name": "feeGrowthInside0LastX128", "type": "uint256"}, {"name": "feeGrowthInside1LastX128", "type": "uint256"}, {"name": "tokensOwed0", "type": "uint128"}, {"name": "tokensOwed1", "type": "uint128"}], "name": "", "type": "tuple"}], "payable": False, "stateMutability": "view", "type": "function"}
        ]
        
        return connector.w3.eth.contract(address=address, abi=abi)
    
    def _get_position_token_ids(self, connector, nft_contract: Contract) -> List[int]:
        """Get the token IDs of all LP positions owned by the impersonated address.
        
        Args:
            connector: The connector to use.
            nft_contract: The NonfungiblePositionManager contract instance.
            
        Returns:
            List[int]: A list of token IDs.
        """
        # Get the balance (number of positions) owned by the address
        balance = nft_contract.functions.balanceOf(self.IMPERSONATED_ADDRESS).call()
        
        # Get all token IDs
        token_ids = []
        for i in range(balance):
            try:
                token_id = nft_contract.functions.tokenOfOwnerByIndex(self.IMPERSONATED_ADDRESS, i).call()
                token_ids.append(token_id)
            except Exception as e:
                print(f"Error getting token ID at index {i}: {e}")
                
        return token_ids
    
    def _get_position_details(self, connector, nft_contract: Contract, token_id: int) -> Dict[str, Any]:
        """Get details about a specific position.
        
        Args:
            connector: The connector to use.
            nft_contract: The NonfungiblePositionManager contract instance.
            token_id: The ID of the position.
            
        Returns:
            Dict[str, Any]: Position details.
        """
        # Get position details from the contract
        position = nft_contract.functions.positions(token_id).call()
        
        # Format the position data
        return {
            "token_id": token_id,
            "token0": position[2],
            "token1": position[3],
            "fee": position[4],
            "tickLower": position[5],
            "tickUpper": position[6],
            "liquidity": position[7],
            "tokensOwed0": position[10],
            "tokensOwed1": position[11]
        }
    
    def _get_token_info(self, connector, token_address: str) -> Dict[str, Any]:
        """Get information about a token.
        
        Args:
            connector: The connector to use.
            token_address: The address of the token.
            
        Returns:
            Dict[str, Any]: Token information.
        """
        # Minimal ERC20 ABI for the functions we need
        erc20_abi = [
            {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "payable": False, "stateMutability": "view", "type": "function"},
            {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "payable": False, "stateMutability": "view", "type": "function"},
            {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "payable": False, "stateMutability": "view", "type": "function"},
            {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "payable": False, "stateMutability": "view", "type": "function"}
        ]
        
        # Create a contract instance for the token
        token_contract = connector.w3.eth.contract(address=token_address, abi=erc20_abi)
        
        # Get token information
        try:
            symbol = token_contract.functions.symbol().call()
        except Exception:
            symbol = "UNKNOWN"
            
        try:
            name = token_contract.functions.name().call()
        except Exception:
            name = "Unknown Token"
            
        try:
            decimals = token_contract.functions.decimals().call()
        except Exception:
            decimals = 18
            
        return {
            "address": token_address,
            "symbol": symbol,
            "name": name,
            "decimals": decimals
        }
