"""Tenderly fork utilities for integration testing.

This module provides utilities for creating and managing Tenderly forks
for integration testing with the Infinity Pools SDK.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple, Union, Any, Callable

import requests
from web3 import Web3
from web3.providers import HTTPProvider


class TenderlyFork:
    """Tenderly fork manager for integration testing."""

    def __init__(
        self,
        access_key: Optional[str] = None,
        account_slug: Optional[str] = None,
        project_slug: Optional[str] = None,
    ):
        """Initialize the Tenderly fork manager.
        
        Args:
            access_key: Tenderly access key. If not provided, will use TENDERLY_ACCESS_KEY env var.
            account_slug: Tenderly account slug. If not provided, will use TENDERLY_ACCOUNT_SLUG env var.
            project_slug: Tenderly project slug. If not provided, will use TENDERLY_PROJECT_SLUG env var.
        """
        self.access_key = access_key or os.environ.get("TENDERLY_ACCESS_KEY")
        self.account_slug = account_slug or os.environ.get("TENDERLY_ACCOUNT_SLUG")
        self.project_slug = project_slug or os.environ.get("TENDERLY_PROJECT_SLUG")
        
        if not self.access_key:
            raise ValueError("Tenderly access key not provided. Set TENDERLY_ACCESS_KEY env var.")
        if not self.account_slug:
            raise ValueError("Tenderly account slug not provided. Set TENDERLY_ACCOUNT_SLUG env var.")
        if not self.project_slug:
            raise ValueError("Tenderly project slug not provided. Set TENDERLY_PROJECT_SLUG env var.")
        
        self.base_url = "https://api.tenderly.co/api/v1"
        self.project_url = f"account/{self.account_slug}/project/{self.project_slug}"
        self.fork_id = None
        self.web3 = None
        self.test_accounts = []
    
    def create_fork(
        self,
        network_id: str = "1",  # Ethereum mainnet by default
        block_number: Optional[int] = None,
        fork_name: Optional[str] = None,
    ) -> Tuple[str, Web3, List[str]]:
        """Create a Tenderly fork.
        
        Args:
            network_id: Network ID to fork. Default is "1" (Ethereum mainnet).
                See Tenderly docs for supported networks.
            block_number: Block number to fork from. If None, uses latest block.
            fork_name: Optional name for the fork.
            
        Returns:
            Tuple of (fork_id, web3_provider, test_accounts)
        """
        headers = {
            "X-Access-Key": self.access_key,
            "Content-Type": "application/json",
        }
        
        fork_data = {
            "network_id": network_id,
        }
        
        if block_number is not None:
            fork_data["block_number"] = block_number
            
        if fork_name is not None:
            fork_data["description"] = fork_name
        
        try:
            response = requests.post(
                f"{self.base_url}/{self.project_url}/fork",
                headers=headers,
                json=fork_data,
            )
            response.raise_for_status()
            
            fork_response = response.json()
            self.fork_id = fork_response["simulation_fork"]["id"]
            
            # Extract test accounts
            self.test_accounts = list(fork_response["simulation_fork"]["accounts"].keys())
            
            # Create Web3 provider
            fork_rpc_url = f"https://rpc.tenderly.co/fork/{self.fork_id}"
            # Create a custom HTTP provider that can be configured for impersonation
            provider = Web3.HTTPProvider(fork_rpc_url)
            web3 = Web3(provider)
            # Note: In newer web3.py versions, geth_poa_middleware is not needed or has been moved
            # If you need POA middleware, you might need to install the eth-middleware package
            self.web3 = web3
            self.fork_rpc_url = fork_rpc_url
            
            logging.info(f"Created Tenderly fork with ID: {self.fork_id}")
            logging.info(f"Fork RPC URL: {fork_rpc_url}")
            logging.info(f"Test accounts: {self.test_accounts}")
            
            return self.fork_id, self.web3, self.test_accounts
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to create Tenderly fork: {e}")
            if hasattr(e, "response") and e.response is not None:
                logging.error(f"Response: {e.response.text}")
            raise
    
    def set_block_gas_limit(self, gas_limit: int) -> bool:
        """Set the block gas limit on the Tenderly fork.
        
        Args:
            gas_limit: The gas limit to set for blocks on the fork.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        if not self.fork_id:
            logging.warning("No fork to modify")
            return False
            
        # Use the Tenderly API to set the block gas limit
        # This is a custom JSON-RPC method provided by Tenderly
        payload = {
            "jsonrpc": "2.0",
            "method": "tenderly_setBlockGasLimit",
            "params": [gas_limit],
            "id": 1
        }
        
        try:
            response = requests.post(
                self.fork_rpc_url,
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logging.error(f"Failed to set block gas limit: {result['error']}")
                return False
                
            logging.info(f"Set block gas limit to {gas_limit} on fork {self.fork_id}")
            return True
            
        except requests.RequestException as e:
            logging.error(f"Failed to set block gas limit on Tenderly fork: {e}")
            if hasattr(e, "response") and e.response is not None:
                logging.error(f"Response: {e.response.text}")
            return False
    
    def delete_fork(self) -> bool:
        """Delete the Tenderly fork.
        
        Returns:
            True if successful, False otherwise.
        """
        if not self.fork_id:
            logging.warning("No fork to delete")
            return False
        
        headers = {
            "X-Access-Key": self.access_key,
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.delete(
                f"{self.base_url}/{self.project_url}/fork/{self.fork_id}",
                headers=headers,
            )
            response.raise_for_status()
            
            logging.info(f"Deleted Tenderly fork with ID: {self.fork_id}")
            self.fork_id = None
            self.web3 = None
            self.test_accounts = []
            
            return True
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to delete Tenderly fork: {e}")
            if hasattr(e, "response") and e.response is not None:
                logging.error(f"Response: {e.response.text}")
            return False
    
    def get_account(self, index: int = 0) -> str:
        """Get a test account address.
        
        Args:
            index: Index of the account to get. Default is 0.
            
        Returns:
            Account address.
        """
        if not self.test_accounts:
            raise ValueError("No test accounts available. Create a fork first.")
        
        if index < 0 or index >= len(self.test_accounts):
            raise ValueError(f"Account index {index} out of range. Available: 0-{len(self.test_accounts)-1}")
        
        return self.test_accounts[index]
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def impersonate_account(self, address: str) -> Web3:
        """Create a Web3 instance that impersonates a specific address.
        
        This allows you to make transactions as if you were this address,
        without needing the private key. This is useful for testing with
        real user accounts.
        
        Args:
            address: The Ethereum address to impersonate
            
        Returns:
            A Web3 instance configured to impersonate the address
        """
        if not self.fork_id:
            raise ValueError("No fork created yet. Call create_fork() first.")
            
        # Create a new provider with the impersonation header
        provider = HTTPProvider(
            self.fork_rpc_url,
            request_kwargs={
                "headers": {
                    "X-Tenderly-Force-Root-Account": address
                }
            }
        )
        
        # Create a new Web3 instance with this provider
        impersonated_web3 = Web3(provider)
        
        logging.info(f"Created impersonated Web3 instance for address: {address}")
        return impersonated_web3
        
    def create_impersonated_connector(self, address: str, connector_class: Any, **kwargs) -> Any:
        """Create a connector instance that impersonates a specific address.
        
        Args:
            address: The Ethereum address to impersonate
            connector_class: The connector class to instantiate
            **kwargs: Additional arguments to pass to the connector constructor
            
        Returns:
            An instance of the connector class configured to impersonate the address
        """
        if not self.fork_id:
            raise ValueError("No fork created yet. Call create_fork() first.")
            
        # Create a connector using the fork's RPC URL with impersonation
        return connector_class(
            rpc_url=self.fork_rpc_url,
            network="mainnet",  # Use the network that was forked
            headers={"X-Tenderly-Force-Root-Account": address},
            **kwargs
        )
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit. Deletes the fork."""
        if self.fork_id:
            self.delete_fork()
