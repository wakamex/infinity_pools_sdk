"""Chain fixtures for integration testing."""

import logging
import os
import time
from decimal import Decimal
from pathlib import Path
from typing import Iterator, Optional, Dict, Any

import pytest
from web3 import Web3

from infinity_pools_sdk.core.connector import InfinityPoolsConnector
from .tenderly_fork import TenderlyFork


class LocalChain:
    """A simplified local chain implementation for testing."""

    def __init__(self, chain_port=8545):
        """Initialize a connection to a local chain.
        
        Args:
            chain_port: The port the local chain is running on.
        """
        self.chain_port = chain_port
        self.web3 = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{chain_port}"))
        # Note: In newer web3.py versions, geth_poa_middleware is not needed or has been moved
        # If you need POA middleware, you might need to install the eth-middleware package
        
        # Check connection
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to local chain at port {chain_port}")
        
        # Default accounts
        self.accounts = self.web3.eth.accounts
        self.deployer = self.accounts[0]
        
        logging.info(f"Connected to local chain at port {chain_port}")
        logging.info(f"Chain ID: {self.web3.eth.chain_id}")
        logging.info(f"Block number: {self.web3.eth.block_number}")

    def get_connector(self, account_index=0):
        """Get an InfinityPoolsConnector for the specified account.
        
        Args:
            account_index: Index of the account to use.
            
        Returns:
            InfinityPoolsConnector: A connector configured for the local chain.
        """
        # For local chains like Anvil, the private keys are deterministic
        # This is the private key for the first account in Anvil
        private_keys = [
            "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",  # account 0
            "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",  # account 1
            "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",  # account 2
            # Add more if needed
        ]
        
        if account_index >= len(private_keys):
            raise ValueError(f"Account index {account_index} out of range")
        
        return InfinityPoolsConnector(
            web3=self.web3,
            private_key=private_keys[account_index],
            default_gas_limit=3000000,
            default_tx_timeout_seconds=60
        )

    def mine_blocks(self, num_blocks=1):
        """Mine a specified number of blocks.
        
        Args:
            num_blocks: Number of blocks to mine.
        """
        for _ in range(num_blocks):
            # Different RPC methods depending on the node type
            try:
                # Anvil/Hardhat
                self.web3.provider.make_request("evm_mine", [])
            except:
                # Ganache
                self.web3.provider.make_request("miner_mine", [])
    
    def advance_time(self, seconds):
        """Advance the blockchain time.
        
        Args:
            seconds: Number of seconds to advance.
        """
        # Different RPC methods depending on the node type
        try:
            # Anvil/Hardhat
            self.web3.provider.make_request("evm_increaseTime", [seconds])
            self.mine_blocks(1)
        except:
            # Ganache
            self.web3.provider.make_request("evm_increaseTime", [seconds])
            self.mine_blocks(1)


@pytest.fixture(scope="session")
def local_chain():
    """Fixture for a local chain connection.
    
    Returns:
        LocalChain: A connection to the local chain.
    """
    # Check if we're running in CI or have a local node
    chain_port = int(os.environ.get("CHAIN_PORT", 8545))
    
    try:
        chain = LocalChain(chain_port=chain_port)
        yield chain
    except ConnectionError as e:
        pytest.skip(f"Could not connect to local chain: {e}")


@pytest.fixture(scope="function")
def tenderly_fork():
    """Fixture for a Tenderly fork.
    
    This fixture creates a Tenderly fork of the specified network at the specified block number.
    The fork is automatically deleted after the test completes.
    
    Returns:
        TenderlyFork: A Tenderly fork manager.
    """
    # Skip if Tenderly credentials are not set
    if not os.environ.get("TENDERLY_ACCESS_KEY"):
        pytest.skip("Tenderly credentials not set. Set TENDERLY_ACCESS_KEY, TENDERLY_ACCOUNT_SLUG, and TENDERLY_PROJECT_SLUG env vars.")
    
    # Create the fork
    fork = TenderlyFork()
    try:
        yield fork
    finally:
        # Clean up the fork after the test
        if fork.fork_id:
            fork.delete_fork()


@pytest.fixture(scope="function")
def infinity_pools_connector(local_chain):
    """Fixture for an InfinityPoolsConnector using a local chain.
    
    Args:
        local_chain: The local chain fixture.
        
    Returns:
        InfinityPoolsConnector: A connector for the Infinity Pools SDK.
    """
    return local_chain.get_connector(account_index=0)


@pytest.fixture(scope="function")
def user_connector(local_chain):
    """Fixture for a user's InfinityPoolsConnector using a local chain.
    
    Args:
        local_chain: The local chain fixture.
        
    Returns:
        InfinityPoolsConnector: A connector for a user account.
    """
    return local_chain.get_connector(account_index=1)


@pytest.fixture(scope="function")
def tenderly_connector(tenderly_fork):
    """Fixture for an InfinityPoolsConnector using a Tenderly fork.
    
    Args:
        tenderly_fork: The Tenderly fork fixture.
        
    Returns:
        InfinityPoolsConnector: A connector for the Infinity Pools SDK.
    """
    # Create the fork with specific parameters
    # You can customize these parameters based on your needs
    network_id = os.environ.get("TENDERLY_NETWORK_ID", "1")  # Default to Ethereum mainnet
    block_number = os.environ.get("TENDERLY_BLOCK_NUMBER")  # Use latest block if not specified
    if block_number:
        block_number = int(block_number)
    
    fork_id, web3, test_accounts = tenderly_fork.create_fork(
        network_id=network_id,
        block_number=block_number,
        fork_name="Infinity Pools SDK Integration Test"
    )
    
    # Store the web3 instance and test accounts on the fork for later use
    tenderly_fork.web3 = web3
    tenderly_fork.test_accounts = test_accounts
    tenderly_fork.fork_id = fork_id
    
    # Create a connector using the fork's RPC URL
    fork_rpc_url = f"https://rpc.tenderly.co/fork/{fork_id}"
    
    # Fund the first test account with 1 ETH
    admin_account = web3.eth.accounts[0]
    test_account = test_accounts[0]
    
    # Send 1 ETH from admin to test account
    tx_hash = web3.eth.send_transaction({
        'from': admin_account,
        'to': test_account,
        'value': web3.to_wei(1, 'ether')
    })
    web3.eth.wait_for_transaction_receipt(tx_hash)
    
    # Use the test account for the connector
    # For testing, we'll use a hardcoded private key
    # In a real application, you would use a secure way to manage private keys
    test_private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    
    return InfinityPoolsConnector(
        rpc_url=fork_rpc_url,
        network="mainnet",  # Use the network that was forked
        private_key=test_private_key
    )


@pytest.fixture(scope="function")
def tenderly_user_connector(tenderly_fork, tenderly_connector):
    """Fixture for a user's InfinityPoolsConnector using a Tenderly fork.
    
    Args:
        tenderly_fork: The Tenderly fork fixture.
        tenderly_connector: The main Tenderly connector fixture (needed to ensure fork is created).
        
    Returns:
        InfinityPoolsConnector: A connector for a user account.
    """
    # Use the second test account from the fork
    user_account = tenderly_fork.test_accounts[1] if len(tenderly_fork.test_accounts) > 1 else tenderly_fork.test_accounts[0]
    
    # Create a connector using the fork's RPC URL
    fork_rpc_url = f"https://rpc.tenderly.co/fork/{tenderly_fork.fork_id}"
    
    # Fund the user account with 1 ETH
    admin_account = tenderly_fork.web3.eth.accounts[0]
    
    # Send 1 ETH from admin to user account
    tx_hash = tenderly_fork.web3.eth.send_transaction({
        'from': admin_account,
        'to': user_account,
        'value': tenderly_fork.web3.to_wei(1, 'ether')
    })
    tenderly_fork.web3.eth.wait_for_transaction_receipt(tx_hash)
    
    # Use the user account for the connector
    # For testing, we'll use a hardcoded private key
    # In a real application, you would use a secure way to manage private keys
    user_private_key = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
    
    return InfinityPoolsConnector(
        rpc_url=fork_rpc_url,
        network="mainnet",  # Use the network that was forked
        private_key=user_private_key
    )


@pytest.fixture(scope="function")
def tenderly_impersonated_connector(tenderly_fork, request):
    """Fixture for an InfinityPoolsConnector that impersonates a specific address.
    
    This connector will impersonate the address 0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207,
    which is a real user account on mainnet. Tenderly allows us to impersonate this
    account without needing its private key.
    
    Args:
        tenderly_fork: The Tenderly fork fixture.
        request: The pytest request object.
        
    Returns:
        InfinityPoolsConnector: A connector that impersonates the specified address.
    """
    # Skip if integration tests are not enabled
    if not request.config.getoption("--run-integration"):
        pytest.skip("Integration tests not enabled. Use --run-integration to run.")
    
    # The address to impersonate
    impersonated_address = "0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207"
    
    # Create the fork directly in this fixture
    network_id = os.environ.get("TENDERLY_NETWORK_ID", "1")  # Default to Ethereum mainnet
    block_number = os.environ.get("TENDERLY_BLOCK_NUMBER")  # Use latest block if not specified
    if block_number:
        block_number = int(block_number)
    
    fork_id, web3, test_accounts = tenderly_fork.create_fork(
        network_id=network_id,
        block_number=block_number,
        fork_name="Impersonation Test Fork"
    )
    
    # Store the fork ID for later use
    tenderly_fork.fork_id = fork_id
    
    # Create a connector using the fork's RPC URL with impersonation headers
    fork_rpc_url = f"https://rpc.tenderly.co/fork/{fork_id}"
    
    # Create headers for impersonation
    headers = {"X-Tenderly-Force-Root-Account": impersonated_address}
    
    # Return a connector with impersonation
    return InfinityPoolsConnector(
        rpc_url=fork_rpc_url,
        network="mainnet",  # Use the network that was forked
        headers=headers
    )
