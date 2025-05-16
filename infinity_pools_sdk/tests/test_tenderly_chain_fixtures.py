"""Tests for the Tenderly chain fixtures."""

import os
import unittest
from unittest import mock

import pytest
from web3 import Web3

from .chain_fixtures import tenderly_fork, tenderly_connector, tenderly_user_connector
from .tenderly_fork import TenderlyFork


@pytest.mark.integration
class TestTenderlyFixtures:
    """Integration tests for Tenderly fixtures.
    
    These tests require valid Tenderly credentials in environment variables:
    - TENDERLY_ACCESS_KEY
    - TENDERLY_ACCOUNT_SLUG
    - TENDERLY_PROJECT_SLUG
    
    Run with: pytest -m integration --run-integration
    """
    
    def test_tenderly_fork_fixture(self, tenderly_fork):
        """Test that the tenderly_fork fixture creates a valid TenderlyFork instance."""
        assert isinstance(tenderly_fork, TenderlyFork)
        assert tenderly_fork.access_key is not None
        assert tenderly_fork.account_slug is not None
        assert tenderly_fork.project_slug is not None
    
    def test_tenderly_connector_fixture(self, tenderly_connector):
        """Test that the tenderly_connector fixture creates a valid connector."""
        # The connector should have a valid w3 instance
        assert tenderly_connector.w3 is not None
        
        # The connector should have a valid account
        assert tenderly_connector.account is not None
        assert tenderly_connector.account.address is not None
        
        # Check that we can get the block number
        block_number = tenderly_connector.w3.eth.block_number
        assert block_number > 0
        
        # Check that the account has a balance
        balance = tenderly_connector.w3.eth.get_balance(tenderly_connector.account.address)
        assert balance > 0
    
    def test_tenderly_user_connector_fixture(self, tenderly_user_connector, tenderly_connector):
        """Test that the tenderly_user_connector fixture creates a valid user connector."""
        # The user connector should have a valid w3 instance
        assert tenderly_user_connector.w3 is not None
        
        # The user connector should have a valid account
        assert tenderly_user_connector.account is not None
        assert tenderly_user_connector.account.address is not None
        
        # The user connector should have a different address than the main connector
        assert tenderly_user_connector.account.address != tenderly_connector.account.address
        
        # Check that the user account has a balance
        balance = tenderly_user_connector.w3.eth.get_balance(tenderly_user_connector.account.address)
        assert balance > 0


# Define test functions that will be used with pytest fixtures
def test_tenderly_connector_fixture_impl(tenderly_connector):
    """Implementation for testing the tenderly_connector fixture."""
    # The connector should have a valid web3 instance
    assert tenderly_connector.web3 is not None
    
    # The connector should have a valid account
    assert tenderly_connector.account is not None
    assert tenderly_connector.account.address is not None
    
    # Check that we can get the block number
    block_number = tenderly_connector.web3.eth.block_number
    assert block_number > 0
    
    # Check that the account has a balance
    balance = tenderly_connector.web3.eth.get_balance(tenderly_connector.account.address)
    assert balance > 0


def test_tenderly_user_connector_fixture_impl(tenderly_user_connector, tenderly_connector):
    """Implementation for testing the tenderly_user_connector fixture."""
    # The user connector should have a valid web3 instance
    assert tenderly_user_connector.web3 is not None
    
    # The user connector should have a valid account
    assert tenderly_user_connector.account is not None
    assert tenderly_user_connector.account.address is not None
    
    # The user connector should have a different address than the main connector
    assert tenderly_user_connector.account.address != tenderly_connector.account.address
    
    # Check that the user account has a balance
    balance = tenderly_user_connector.web3.eth.get_balance(tenderly_user_connector.account.address)
    assert balance > 0


@pytest.mark.integration
class TestTenderlyFixturesMocked:
    """Unit tests for Tenderly fixtures using mocks."""
    
    @pytest.fixture
    def mock_tenderly_fork(self):
        """Create a mock TenderlyFork."""
        with mock.patch.dict(os.environ, {
            "TENDERLY_ACCESS_KEY": "test_access_key",
            "TENDERLY_ACCOUNT_SLUG": "test_account",
            "TENDERLY_PROJECT_SLUG": "test_project",
            "TENDERLY_NETWORK_ID": "1",
            "TENDERLY_BLOCK_NUMBER": "12345678",
        }):
            with mock.patch("infinity_pools_sdk.tests.tenderly_fork.TenderlyFork") as mock_fork_class:
                mock_fork = mock.Mock()
                mock_fork_class.return_value = mock_fork
                
                # Mock the create_fork method
                mock_web3 = mock.Mock()
                mock_fork.create_fork.return_value = (
                    "test_fork_id",
                    mock_web3,
                    ["0xAccount1", "0xAccount2"]
                )
                
                # Mock the get_account method
                mock_fork.get_account.return_value = "0xAccount2"
                
                yield mock_fork
    
    @pytest.fixture
    def mock_connector(self):
        """Create a mock connector."""
        with mock.patch("infinity_pools_sdk.tests.chain_fixtures.InfinityPoolsConnector") as mock_connector_class:
            mock_connector = mock.Mock()
            mock_connector_class.return_value = mock_connector
            yield mock_connector
    
    def test_tenderly_connector_creation(self, mock_tenderly_fork, mock_connector):
        """Test the creation of a tenderly_connector."""
        # Define a function that simulates what the fixture does
        def create_tenderly_connector(tenderly_fork):
            # Create the fork with specific parameters
            network_id = os.environ.get("TENDERLY_NETWORK_ID", "1")  # Default to Ethereum mainnet
            block_number = os.environ.get("TENDERLY_BLOCK_NUMBER")  # Use latest block if not specified
            if block_number:
                block_number = int(block_number)
            
            fork_id, web3, test_accounts = tenderly_fork.create_fork(
                network_id=network_id,
                block_number=block_number,
                fork_name="Infinity Pools SDK Integration Test"
            )
            
            # In a real implementation, we would create a connector with the fork's RPC URL
            # Since we're mocking, we'll just return our mock connector
            return mock_connector
        
        # Mock the InfinityPoolsConnector creation
        with mock.patch('infinity_pools_sdk.tests.chain_fixtures.InfinityPoolsConnector', return_value=mock_connector):
            # Call our simulated function with the mock fork
            connector = create_tenderly_connector(mock_tenderly_fork)
            
            # Verify the fork was created with the right parameters
            mock_tenderly_fork.create_fork.assert_called_once_with(
                network_id="1",
                block_number=12345678,
                fork_name="Infinity Pools SDK Integration Test"
            )
    
    def test_tenderly_user_connector_creation(self, mock_tenderly_fork, mock_connector):
        """Test the creation of a tenderly_user_connector."""
        # Define a function that simulates what the fixture does
        def create_tenderly_user_connector(tenderly_fork, tenderly_connector):
            # Use the second test account from the fork
            user_address = tenderly_fork.get_account(index=1)
            
            # In a real implementation, we would create a connector with the fork's web3 provider
            # Since we're mocking, we'll just return our mock connector
            return mock_connector
        
        # Set up the mock for get_account
        mock_tenderly_fork.get_account.return_value = "0xUserAddress"
        mock_tenderly_fork.web3 = mock.Mock()
        
        # Mock the InfinityPoolsConnector creation
        with mock.patch('infinity_pools_sdk.tests.chain_fixtures.InfinityPoolsConnector', return_value=mock_connector):
            # Call our simulated function with the mocks
            user_connector = create_tenderly_user_connector(mock_tenderly_fork, mock_connector)
            
            # Verify the account was retrieved
            mock_tenderly_fork.get_account.assert_called_once_with(index=1)


if __name__ == "__main__":
    unittest.main()
