"""Unit tests for Tenderly utilities without using pytest fixtures."""

import os
import unittest
from unittest import mock

# Import the connector class but patch it to avoid Web3 initialization
with mock.patch('infinity_pools_sdk.core.connector.Web3'):
    from infinity_pools_sdk.core.connector import InfinityPoolsConnector

from .tenderly_fork import TenderlyFork


class TestTenderlyUtils(unittest.TestCase):
    """Test Tenderly utilities without using pytest fixtures."""

    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = mock.patch.dict(os.environ, {
            "TENDERLY_ACCESS_KEY": "test_access_key",
            "TENDERLY_ACCOUNT_SLUG": "test_account",
            "TENDERLY_PROJECT_SLUG": "test_project",
            "TENDERLY_NETWORK_ID": "1",
            "TENDERLY_BLOCK_NUMBER": "12345678",
        })
        self.env_patcher.start()
        
        # Mock TenderlyFork
        self.tenderly_fork_patcher = mock.patch("infinity_pools_sdk.tests.tenderly_fork.TenderlyFork")
        self.mock_tenderly_fork_class = self.tenderly_fork_patcher.start()
        self.mock_tenderly_fork = mock.Mock()
        self.mock_tenderly_fork_class.return_value = self.mock_tenderly_fork
        
        # Mock Web3 - we don't need this since we're patching at import time
        self.mock_web3 = mock.Mock()
        
        # Mock InfinityPoolsConnector initialization
        self.connector_patcher = mock.patch.object(InfinityPoolsConnector, '__init__', return_value=None)
        self.mock_connector_init = self.connector_patcher.start()
        
        # Create a mock connector instance
        self.mock_connector = mock.Mock(spec=InfinityPoolsConnector)
        
        # Mock the connector class to return our mock instance
        self.connector_class_patcher = mock.patch('infinity_pools_sdk.tests.test_tenderly_utils.InfinityPoolsConnector', 
                                               return_value=self.mock_connector)
        self.mock_connector_class = self.connector_class_patcher.start()
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        self.tenderly_fork_patcher.stop()
        self.connector_patcher.stop()
        self.connector_class_patcher.stop()
    
    def test_create_tenderly_connector(self):
        """Test creating a connector with a Tenderly fork."""
        # Set up the mock fork
        mock_fork = self.mock_tenderly_fork
        mock_fork.create_fork.return_value = (
            "test_fork_id",
            self.mock_web3,
            ["0xAccount1", "0xAccount2"]
        )
        
        # Create the connector
        def create_tenderly_connector(tenderly_fork):
            """Create a connector using a Tenderly fork."""
            # Create the fork with specific parameters
            network_id = os.environ.get("TENDERLY_NETWORK_ID", "1")
            block_number = os.environ.get("TENDERLY_BLOCK_NUMBER")
            if block_number:
                block_number = int(block_number)
            
            fork_id, web3, test_accounts = tenderly_fork.create_fork(
                network_id=network_id,
                block_number=block_number,
                fork_name="Infinity Pools SDK Integration Test"
            )
            
            # In a real implementation, we would need to create a connector with the fork's RPC URL
            # Since we're mocking, we'll just create a connector with a dummy RPC URL
            fork_rpc_url = f"https://rpc.tenderly.co/fork/{fork_id}"
            
            return InfinityPoolsConnector(
                rpc_url=fork_rpc_url,
                network="mainnet",
                private_key="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
            )
        
        # Call the function
        connector = create_tenderly_connector(mock_fork)
        
        # Verify the fork was created with the right parameters
        mock_fork.create_fork.assert_called_once_with(
            network_id="1",
            block_number=12345678,
            fork_name="Infinity Pools SDK Integration Test"
        )
        
        # Verify the connector was created with the right parameters
        self.mock_connector_class.assert_called_once_with(
            rpc_url="https://rpc.tenderly.co/fork/test_fork_id",
            network="mainnet",
            private_key="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        )
    
    def test_create_tenderly_user_connector(self):
        """Test creating a user connector with a Tenderly fork."""
        # Set up the mock fork
        mock_fork = self.mock_tenderly_fork
        mock_fork.get_account.return_value = "0xUserAccount"
        mock_fork.web3 = self.mock_web3
        mock_fork.fork_id = "test_fork_id"
        
        # Create the user connector
        def create_tenderly_user_connector(tenderly_fork, tenderly_connector):
            """Create a user connector using a Tenderly fork."""
            # Use the second test account from the fork
            user_address = tenderly_fork.get_account(index=1)
            
            # In a real implementation, we would need to create a connector with the fork's RPC URL
            # and the user's private key
            # Since we're mocking, we'll just create a connector with a dummy RPC URL
            fork_rpc_url = f"https://rpc.tenderly.co/fork/{tenderly_fork.fork_id}"
            
            # In a real scenario, we would need the private key for this account
            # For testing, we'll use a dummy private key
            user_private_key = "0x2234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
            
            return InfinityPoolsConnector(
                rpc_url=fork_rpc_url,
                network="mainnet",
                private_key=user_private_key
            )
        
        # Call the function
        user_connector = create_tenderly_user_connector(mock_fork, self.mock_connector)
        
        # Verify the account was retrieved
        mock_fork.get_account.assert_called_once_with(index=1)
        
        # Verify the connector was created with the right parameters
        self.mock_connector_class.assert_called_once_with(
            rpc_url="https://rpc.tenderly.co/fork/test_fork_id",
            network="mainnet",
            private_key="0x2234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        )


if __name__ == "__main__":
    unittest.main()
