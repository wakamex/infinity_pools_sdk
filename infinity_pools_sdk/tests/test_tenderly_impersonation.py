"""Tests for Tenderly impersonation functionality."""

import os
import pytest
from web3 import Web3

from infinity_pools_sdk.core.connector import InfinityPoolsConnector
from infinity_pools_sdk.tests.chain_fixtures import (
    tenderly_fork,
    tenderly_connector,
    tenderly_impersonated_connector,
)


class TestTenderlyImpersonation:
    """Test the Tenderly impersonation functionality."""

    @pytest.mark.integration
    def test_impersonated_connector(self, tenderly_impersonated_connector, request):
        """Test that we can create a connector that impersonates a specific address.
        
        This test demonstrates how to use the Tenderly impersonation feature to
        act as a specific address without needing its private key.
        """
        # Skip if integration tests are not enabled
        if not request.config.getoption("--run-integration"):
            pytest.skip("Integration tests not enabled. Use --run-integration to run.")
            
        # The address we're impersonating
        impersonated_address = "0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207"
        
        # Verify that the connector is properly configured
        assert tenderly_impersonated_connector.impersonated_address == impersonated_address
        
        # Get the balance of the impersonated account
        balance = tenderly_impersonated_connector.w3.eth.get_balance(impersonated_address)
        print(f"Balance of impersonated account: {Web3.from_wei(balance, 'ether')} ETH")
        
        # You can now use this connector to perform transactions as the impersonated account
        # For example, you could call a contract method:
        # contract = tenderly_impersonated_connector.get_contract_instance("ContractName")
        # tx_hash = contract.functions.someMethod().transact({"from": impersonated_address})
        
        # The transaction will be sent as if it came from the impersonated address
        # without needing the private key
        
        # This is particularly useful for testing with real user accounts
        # or for testing with accounts that have specific permissions
        
        # Assert that we have a valid Web3 instance
        assert tenderly_impersonated_connector.w3 is not None
        
        # Assert that we can get the chain ID
        chain_id = tenderly_impersonated_connector.w3.eth.chain_id
        assert chain_id > 0
        print(f"Chain ID: {chain_id}")
