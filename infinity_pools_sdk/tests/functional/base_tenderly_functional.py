"""Base class for Tenderly functional tests.

This module provides a base class for functional tests that use Tenderly
forks and impersonation to test the Infinity Pools SDK with real accounts
and state on mainnet forks.
"""

import os
import pytest
import time
from typing import Dict, Any, Optional

from web3 import Web3

from infinity_pools_sdk.core.connector import InfinityPoolsConnector
from infinity_pools_sdk.sdk import InfinityPoolsSDK
from infinity_pools_sdk.tests.tenderly_fork import TenderlyFork


class BaseTenderlyFunctionalTest:
    """Base class for Tenderly functional tests."""
    
    # The address to impersonate for functional tests
    # This is an address that has available balance on Base
    # Must be in checksum format for web3.py
    # This address has 10.605 sUSDe / 0.148 wstETH available
    IMPERSONATED_ADDRESS = "0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207"
    
    @pytest.fixture(scope="function")
    def tenderly_fork(self, request):
        """Fixture for a Tenderly fork.
        
        Args:
            request: The pytest request object.
            
        Returns:
            TenderlyFork: A Tenderly fork manager.
        """
        # Skip if integration tests are not enabled
        if not request.config.getoption("--run-integration"):
            pytest.skip("Integration tests not enabled. Use --run-integration to run.")
            
        # Create a Tenderly fork
        fork = TenderlyFork()
        yield fork
        # Clean up the fork after the test
        fork.delete_fork()
    
    @pytest.fixture(scope="function")
    def impersonated_connector(self, tenderly_fork, request):
        """Fixture for an InfinityPoolsConnector that impersonates a specific address.
        
        This connector will impersonate the address specified in IMPERSONATED_ADDRESS,
        which is a real user account on mainnet. Tenderly allows us to impersonate this
        account without needing its private key.
        
        Args:
            tenderly_fork: The Tenderly fork fixture.
            request: The pytest request object.
            
        Returns:
            InfinityPoolsConnector: A connector that impersonates the specified address.
        """
        # Create the fork directly in this fixture
        network_id = os.environ.get("TENDERLY_NETWORK_ID", "1")  # Default to Ethereum mainnet
        block_number = os.environ.get("TENDERLY_BLOCK_NUMBER")  # Use latest block if not specified
        if block_number:
            block_number = int(block_number)
        
        fork_id, web3, test_accounts = tenderly_fork.create_fork(
            network_id=network_id,
            block_number=block_number,
            fork_name="Functional Test Fork"
        )
        
        # Store the fork ID for later use
        tenderly_fork.fork_id = fork_id
        tenderly_fork.web3 = web3
        
        # Set a high block gas limit to avoid gas estimation issues
        # 30,000,000 is a common value for local development chains
        tenderly_fork.set_block_gas_limit(30000000)
        
        # Create a connector using the fork's RPC URL with impersonation headers
        fork_rpc_url = f"https://rpc.tenderly.co/fork/{fork_id}"
        
        # Create headers for impersonation
        headers = {"X-Tenderly-Force-Root-Account": self.IMPERSONATED_ADDRESS}
        
        # Return a connector with impersonation
        return InfinityPoolsConnector(
            rpc_url=fork_rpc_url,
            network="mainnet",  # Use the network that was forked
            headers=headers
        )
    
    @pytest.fixture(scope="function")
    def sdk(self):
        """Fixture for the InfinityPoolsSDK.
        
        Returns:
            InfinityPoolsSDK: An instance of the SDK.
        """
        return InfinityPoolsSDK()
    
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
