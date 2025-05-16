"""Tests for the Tenderly fork utilities."""

import os
import unittest
from unittest import mock

import pytest
import requests
from web3 import Web3

from .tenderly_fork import TenderlyFork


class TestTenderlyFork(unittest.TestCase):
    """Test cases for the TenderlyFork class."""

    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = mock.patch.dict(os.environ, {
            "TENDERLY_ACCESS_KEY": "test_access_key",
            "TENDERLY_ACCOUNT_SLUG": "test_account",
            "TENDERLY_PROJECT_SLUG": "test_project",
        })
        self.env_patcher.start()
        
        # Create a TenderlyFork instance
        self.fork = TenderlyFork()
        
        # Mock the requests module
        self.requests_patcher = mock.patch("requests.post")
        self.mock_post = self.requests_patcher.start()
        
        self.requests_delete_patcher = mock.patch("requests.delete")
        self.mock_delete = self.requests_delete_patcher.start()
        
        # Mock Web3
        self.web3_patcher = mock.patch("web3.Web3")
        self.mock_web3 = self.web3_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        self.requests_patcher.stop()
        self.requests_delete_patcher.stop()
        self.web3_patcher.stop()

    def test_init_with_env_vars(self):
        """Test initialization with environment variables."""
        fork = TenderlyFork()
        self.assertEqual(fork.access_key, "test_access_key")
        self.assertEqual(fork.account_slug, "test_account")
        self.assertEqual(fork.project_slug, "test_project")
        self.assertEqual(fork.base_url, "https://api.tenderly.co/api/v1")
        self.assertEqual(fork.project_url, "account/test_account/project/test_project")

    def test_init_with_params(self):
        """Test initialization with parameters."""
        fork = TenderlyFork(
            access_key="custom_key",
            account_slug="custom_account",
            project_slug="custom_project",
        )
        self.assertEqual(fork.access_key, "custom_key")
        self.assertEqual(fork.account_slug, "custom_account")
        self.assertEqual(fork.project_slug, "custom_project")

    def test_init_missing_access_key(self):
        """Test initialization with missing access key."""
        with mock.patch.dict(os.environ, {
            "TENDERLY_ACCESS_KEY": "",
            "TENDERLY_ACCOUNT_SLUG": "test_account",
            "TENDERLY_PROJECT_SLUG": "test_project",
        }):
            with self.assertRaises(ValueError):
                TenderlyFork()

    def test_create_fork_success(self):
        """Test successful fork creation."""
        # Mock the response from Tenderly API
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "simulation_fork": {
                "id": "test_fork_id",
                "accounts": {
                    "0xAccount1": "100000000000000000000",
                    "0xAccount2": "100000000000000000000",
                }
            }
        }
        mock_response.raise_for_status = mock.Mock()
        self.mock_post.return_value = mock_response
        
        # We need to test two things:
        # 1. That the API call is made correctly
        # 2. That the create_fork method returns the expected values
        
        # For the first part, we'll use a partial mock that only mocks the Web3 part
        # Import Web3 directly in the test to avoid global modification
        from web3 import Web3 as OriginalWeb3
        mock_web3_instance = mock.Mock()
        
        # Create a mock Web3 class that returns our mock instance
        mock_web3_class = mock.Mock()
        mock_web3_class.HTTPProvider = mock.Mock(return_value=mock.Mock())
        mock_web3_class.return_value = mock_web3_instance
        
        # Replace Web3 with our mock
        try:
            # Patch the Web3 import in the tenderly_fork module
            with mock.patch.object(self.fork, 'web3', None):
                # Call create_fork
                with mock.patch('infinity_pools_sdk.tests.tenderly_fork.Web3', mock_web3_class):
                    fork_id, web3, accounts = self.fork.create_fork(
                        network_id="1",
                        block_number=12345678,
                        fork_name="Test Fork"
                    )
                    
                    # Verify results
                    self.assertEqual(fork_id, "test_fork_id")
                    self.assertEqual(accounts, ["0xAccount1", "0xAccount2"])
                    
                    # Verify API call
                    self.mock_post.assert_called_once_with(
                        "https://api.tenderly.co/api/v1/account/test_account/project/test_project/fork",
                        headers={
                            "X-Access-Key": "test_access_key",
                            "Content-Type": "application/json",
                        },
                        json={
                            "network_id": "1",
                            "block_number": 12345678,
                            "description": "Test Fork"
                        }
                    )
        finally:
            # No need to restore Web3 since we're using a local import
            pass

    def test_create_fork_api_error(self):
        """Test fork creation with API error."""
        # Mock the response to raise an exception
        self.mock_post.side_effect = requests.exceptions.RequestException("API Error")
        
        # Call create_fork and expect an exception
        with self.assertRaises(requests.exceptions.RequestException):
            self.fork.create_fork()

    def test_delete_fork_success(self):
        """Test successful fork deletion."""
        # Set up fork_id
        self.fork.fork_id = "test_fork_id"
        
        # Mock the response
        mock_response = mock.Mock()
        mock_response.raise_for_status = mock.Mock()
        self.mock_delete.return_value = mock_response
        
        # Call delete_fork
        result = self.fork.delete_fork()
        
        # Verify results
        self.assertTrue(result)
        self.assertIsNone(self.fork.fork_id)
        
        # Verify API call
        self.mock_delete.assert_called_once_with(
            "https://api.tenderly.co/api/v1/account/test_account/project/test_project/fork/test_fork_id",
            headers={
                "X-Access-Key": "test_access_key",
                "Content-Type": "application/json",
            }
        )

    def test_delete_fork_no_fork_id(self):
        """Test delete_fork with no fork_id."""
        # Ensure fork_id is None
        self.fork.fork_id = None
        
        # Call delete_fork
        result = self.fork.delete_fork()
        
        # Verify results
        self.assertFalse(result)
        
        # Verify no API call was made
        self.mock_delete.assert_not_called()

    def test_delete_fork_api_error(self):
        """Test delete_fork with API error."""
        # Set up fork_id
        self.fork.fork_id = "test_fork_id"
        
        # Mock the response to raise an exception
        self.mock_delete.side_effect = requests.exceptions.RequestException("API Error")
        
        # Call delete_fork
        result = self.fork.delete_fork()
        
        # Verify results
        self.assertFalse(result)
        self.assertEqual(self.fork.fork_id, "test_fork_id")  # fork_id should not be cleared

    def test_get_account_success(self):
        """Test get_account success."""
        # Set up test accounts
        self.fork.test_accounts = ["0xAccount1", "0xAccount2", "0xAccount3"]
        
        # Call get_account
        account = self.fork.get_account(1)
        
        # Verify results
        self.assertEqual(account, "0xAccount2")

    def test_get_account_no_accounts(self):
        """Test get_account with no accounts."""
        # Ensure test_accounts is empty
        self.fork.test_accounts = []
        
        # Call get_account and expect an exception
        with self.assertRaises(ValueError):
            self.fork.get_account()

    def test_get_account_index_out_of_range(self):
        """Test get_account with index out of range."""
        # Set up test accounts
        self.fork.test_accounts = ["0xAccount1", "0xAccount2"]
        
        # Call get_account with invalid index and expect an exception
        with self.assertRaises(ValueError):
            self.fork.get_account(2)

    def test_context_manager(self):
        """Test using TenderlyFork as a context manager."""
        # Mock delete_fork
        self.fork.delete_fork = mock.Mock(return_value=True)
        
        # Set fork_id
        self.fork.fork_id = "test_fork_id"
        
        # Use as context manager
        with self.fork as fork:
            self.assertEqual(fork, self.fork)
        
        # Verify delete_fork was called
        self.fork.delete_fork.assert_called_once()


@pytest.mark.integration
class TestTenderlyForkIntegration:
    """Integration tests for TenderlyFork.
    
    These tests require valid Tenderly credentials in environment variables:
    - TENDERLY_ACCESS_KEY
    - TENDERLY_ACCOUNT_SLUG
    - TENDERLY_PROJECT_SLUG
    
    Run with: pytest -m integration --run-integration
    """
    
    def test_create_and_delete_fork(self):
        """Test creating and deleting a fork with real API calls."""
        # Skip if credentials are not set
        if not os.environ.get("TENDERLY_ACCESS_KEY"):
            pytest.skip("Tenderly credentials not set")
        
        # Create fork
        fork = TenderlyFork()
        fork_id, web3, accounts = fork.create_fork(
            network_id="1",  # Ethereum mainnet
            fork_name="Integration Test Fork"
        )
        
        try:
            # Verify fork was created
            assert fork_id is not None
            assert web3 is not None
            assert len(accounts) > 0
            
            # Check that we can get the block number
            block_number = web3.eth.block_number
            assert block_number > 0
            
            # Check that we can get an account balance
            balance = web3.eth.get_balance(accounts[0])
            assert balance > 0
            
        finally:
            # Clean up
            result = fork.delete_fork()
            assert result is True
