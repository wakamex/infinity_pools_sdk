"""Base class for Tenderly functional tests.

This module provides a base class for functional tests that use Tenderly
forks and impersonation to test the Infinity Pools SDK with real accounts
and state on mainnet forks.
"""

import os
import time
from typing import Any, Dict, Optional
import logging

import pytest

from infinity_pools_sdk.constants import ContractAddresses
from infinity_pools_sdk.core.connector import InfinityPoolsConnector
from infinity_pools_sdk.sdk import InfinityPoolsSDK


class BaseTenderlyFunctionalTest:
    """Base class for Tenderly functional tests."""
    
    # The address to impersonate for functional tests
    # This is an address that has available balance on Base
    # Must be in checksum format for web3.py
    # This address has 10.605 sUSDe / 0.148 wstETH available
    IMPERSONATED_ADDRESS = "0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207"
    
    def setUp(self):
        super().setUp()
        # Log fork details for debugging
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Using Tenderly fork ID: {self.tenderly_fork.fork_id}")
        self.logger.info(f"Fork RPC URL: {self.tenderly_connector.rpc_url}")
        # Check if key contracts are deployed
        periphery_address = os.environ.get("PERIPHERY_ADDRESS", "Not set")
        self.logger.info(f"Periphery contract address: {periphery_address}")
        if periphery_address != "Not set":
            try:
                code = self.tenderly_connector.w3.eth.get_code(periphery_address)
                self.logger.info(f"Periphery contract code length: {len(code)} bytes")
            except Exception as e:
                self.logger.error(f"Error checking periphery contract: {e}")
        else:
            self.logger.warning("PERIPHERY_ADDRESS not set in environment")
    
    @pytest.fixture(scope="function")
    def sdk(self, impersonated_connector: InfinityPoolsConnector):
        """Fixture for the InfinityPoolsSDK.

        Args:
            impersonated_connector: The connector fixture providing an impersonated connection.
            
        Returns:
            InfinityPoolsSDK: An instance of the SDK.
        """
        return InfinityPoolsSDK(
            connector=impersonated_connector,
            periphery_address=ContractAddresses.BASE["proxy"]
        )
    
    def get_position_token_ids(self, connector: InfinityPoolsConnector, address: Optional[str] = None) -> list:
        """Get the token IDs of all LP positions owned by the specified address.
        
        Args:
            connector: The connector to use.
            address: The address to check. If None, uses the impersonated address.
            
        Returns:
            list: A list of token IDs.
        """
        if address is None:
            address = self.IMPERSONATED_ADDRESS
            
        # Get the NFT contract instance
        nft_contract = connector.get_contract_instance("InfinityPoolsNFT")
        
        # Get the balance of the address
        balance = nft_contract.functions.balanceOf(address).call()
        
        # Get all token IDs
        token_ids = []
        for i in range(balance):
            token_id = nft_contract.functions.tokenOfOwnerByIndex(address, i).call()
            token_ids.append(token_id)
            
        return token_ids
    
    def get_pool_info(self, connector: InfinityPoolsConnector, pool_id: int) -> Dict[str, Any]:
        """Get information about a specific pool.
        
        Args:
            connector: The connector to use.
            pool_id: The ID of the pool.
            
        Returns:
            Dict[str, Any]: Pool information.
        """
        # Get the pool contract instance
        pools_contract = connector.get_contract_instance("InfinityPools")
        
        # Get pool info
        pool_info = pools_contract.functions.getPoolInfo(pool_id).call()
        
        # Format the result
        return {
            "pool_id": pool_id,
            "token0": pool_info[0],
            "token1": pool_info[1],
            "fee": pool_info[2],
            "liquidity": pool_info[3],
            "sqrt_price_x96": pool_info[4],
            "tick": pool_info[5],
        }
