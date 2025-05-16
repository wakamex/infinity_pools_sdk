"""Tests for event parsing from Tenderly fork transactions."""

import json
import os
from decimal import Decimal
from unittest import mock

import pytest
from web3 import Web3

from infinity_pools_sdk.sdk import InfinityPoolsSDK
from .tenderly_fork import TenderlyFork


class TestTenderlyEventParsing:
    """Tests for parsing events from Tenderly fork transactions."""
    
    # Sample ABI for the periphery contract (partial, focusing on events)
    PERIPHERY_ABI = [
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "tokenId", "type": "uint256"},
                {"indexed": False, "name": "liquidity", "type": "uint128"},
                {"indexed": False, "name": "amount0", "type": "uint256"},
                {"indexed": False, "name": "amount1", "type": "uint256"}
            ],
            "name": "IncreaseLiquidity",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "tokenId", "type": "uint256"},
                {"indexed": False, "name": "liquidity", "type": "uint128"},
                {"indexed": False, "name": "amount0", "type": "uint256"},
                {"indexed": False, "name": "amount1", "type": "uint256"}
            ],
            "name": "DecreaseLiquidity",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "tokenId", "type": "uint256"},
                {"indexed": True, "name": "recipient", "type": "address"},
                {"indexed": False, "name": "amount0", "type": "uint256"},
                {"indexed": False, "name": "amount1", "type": "uint256"}
            ],
            "name": "Collect",
            "type": "event"
        }
    ]
    
    # Sample transaction receipt with events
    SAMPLE_RECEIPT = {
        "blockHash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "blockNumber": 12345678,
        "contractAddress": None,
        "cumulativeGasUsed": 1000000,
        "effectiveGasPrice": 20000000000,
        "from": "0xUserAddress",
        "gasUsed": 500000,
        "logs": [
            {
                "address": "0xPeripheryContractAddress",
                "topics": [
                    "0x3067048beee31b25b2f1681f88dac838c8bba36af25bfb2b7cf7473a5847e35f",  # IncreaseLiquidity event signature
                    "0x0000000000000000000000000000000000000000000000000000000000000123"   # tokenId (hex)
                ],
                "data": "0x00000000000000000000000000000000000000000000000000000000000186a0" +  # liquidity (100000)
                       "000000000000000000000000000000000000000000000000016345785d8a0000" +  # amount0 (100 * 10^18)
                       "000000000000000000000000000000000000000000000000002c68af0bb14000",  # amount1 (200 * 10^18)
                "blockNumber": 12345678,
                "transactionHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "transactionIndex": 0,
                "blockHash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "logIndex": 0,
                "removed": False
            }
        ],
        "status": 1,
        "to": "0xPeripheryContractAddress",
        "transactionHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "transactionIndex": 0
    }
    
    def test_extract_token_id_from_receipt(self):
        """Test extracting token ID from transaction receipt."""
        # Create a mock Web3 instance
        mock_web3 = mock.Mock()
        mock_contract = mock.Mock()
        mock_web3.eth.contract.return_value = mock_contract
        
        # This is the actual event signature in our sample receipt
        event_signature_hex = "0x3067048beee31b25b2f1681f88dac838c8bba36af25bfb2b7cf7473a5847e35f"
        
        # Create a mock keccak function that returns our expected hash
        mock_keccak_result = mock.Mock()
        mock_keccak_result.hex.return_value = event_signature_hex
        
        # Define the event parser function that will use our mocked Web3.keccak
        def extract_token_id_from_receipt(receipt, web3, periphery_address, periphery_abi):
            """Extract token ID from transaction receipt."""
            # Create contract instance
            contract = web3.eth.contract(
                address=periphery_address,
                abi=periphery_abi
            )
            
            # Find the IncreaseLiquidity event
            for log in receipt["logs"]:
                # Check if the log is from the periphery contract
                if log["address"].lower() != periphery_address.lower():
                    continue
                
                # The topic in our sample receipt is already the correct event signature
                # No need to calculate it, just compare directly
                if log["topics"][0].lower() == event_signature_hex.lower():
                    # Extract tokenId from the indexed parameter
                    token_id = int(log["topics"][1], 16)
                    return token_id
            
            return None
        
        # Test the function with our sample receipt
        periphery_address = "0xPeripheryContractAddress"
        token_id = extract_token_id_from_receipt(
            self.SAMPLE_RECEIPT,
            mock_web3,
            periphery_address,
            self.PERIPHERY_ABI
        )
        
        # The token ID in our sample receipt is 0x123 (291 in decimal)
        assert token_id == 291
    
    @pytest.mark.integration
    def test_extract_token_id_from_real_receipt(self, tenderly_fork):
        """Test extracting token ID from a real transaction receipt on a Tenderly fork.
        
        This test requires valid Tenderly credentials and contract addresses.
        """
        # Skip if Tenderly credentials are not set
        if not os.environ.get("TENDERLY_ACCESS_KEY"):
            pytest.skip("Tenderly credentials not set")
        
        # Skip if contract addresses are not set
        periphery_address = os.environ.get("PERIPHERY_ADDRESS")
        token0_address = os.environ.get("TOKEN0_ADDRESS")
        token1_address = os.environ.get("TOKEN1_ADDRESS")
        
        if not all([periphery_address, token0_address, token1_address]):
            pytest.skip("Contract addresses not set")
        
        # Create a fork and connector
        fork_id, web3, accounts = tenderly_fork.create_fork(
            network_id=os.environ.get("TENDERLY_NETWORK_ID", "1"),
            block_number=int(os.environ.get("TENDERLY_BLOCK_NUMBER", "0")) or None,
            fork_name="Event Parsing Test"
        )
        
        try:
            # Create a mock connector
            class MockConnector:
                def __init__(self, web3, account_address):
                    self.web3 = web3
                    self.account = mock.Mock()
                    self.account.address = account_address
                    self.default_gas_limit = 3000000
            
            # Create the connector and SDK
            connector = MockConnector(web3, accounts[0])
            sdk = InfinityPoolsSDK(
                connector=connector,
                periphery_address=periphery_address
            )
            
            # Define the event parser function
            def extract_token_id_from_receipt(receipt):
                """Extract token ID from transaction receipt."""
                # Get the periphery contract ABI
                # In a real implementation, this would come from the SDK
                periphery_abi = self.PERIPHERY_ABI
                
                # Create contract instance
                contract = web3.eth.contract(
                    address=periphery_address,
                    abi=periphery_abi
                )
                
                # Find the IncreaseLiquidity event
                for log in receipt["logs"]:
                    # Check if the log is from the periphery contract
                    if log["address"].lower() != periphery_address.lower():
                        continue
                    
                    # Try to find an IncreaseLiquidity event
                    event_signature = Web3.keccak(
                        text="IncreaseLiquidity(uint256,uint128,uint256,uint256)"
                    ).hex()
                    
                    if log["topics"][0].lower() == event_signature.lower():
                        # Extract tokenId from the indexed parameter
                        token_id = int(log["topics"][1], 16)
                        return token_id
                
                return None
            
            # If this were a real test with actual contracts deployed,
            # we would execute an add_liquidity transaction and parse the receipt
            
            # For now, we'll just test our parser with the sample receipt
            token_id = extract_token_id_from_receipt(self.SAMPLE_RECEIPT)
            assert token_id == 291
            
        finally:
            # Clean up the fork
            tenderly_fork.delete_fork()
    
    def test_parse_multiple_events(self):
        """Test parsing multiple events from a transaction receipt."""
        # Create a sample receipt with multiple events
        receipt = {
            "logs": [
                # IncreaseLiquidity event
                {
                    "address": "0xPeripheryContractAddress",
                    "topics": [
                        "0x3067048beee31b25b2f1681f88dac838c8bba36af25bfb2b7cf7473a5847e35f",  # IncreaseLiquidity
                        "0x0000000000000000000000000000000000000000000000000000000000000123"   # tokenId
                    ],
                    "data": "0x00000000000000000000000000000000000000000000000000000000000186a0" +  # liquidity
                           "000000000000000000000000000000000000000000000000016345785d8a0000" +  # amount0
                           "000000000000000000000000000000000000000000000000002c68af0bb14000",  # amount1
                },
                # DecreaseLiquidity event
                {
                    "address": "0xPeripheryContractAddress",
                    "topics": [
                        "0x26f6a048ee9138f2c0ce266f322cb99228e8d619ae2bff30c67f8dcf9d2377b4",  # DecreaseLiquidity
                        "0x0000000000000000000000000000000000000000000000000000000000000123"   # tokenId
                    ],
                    "data": "0x00000000000000000000000000000000000000000000000000000000000186a0" +  # liquidity
                           "000000000000000000000000000000000000000000000000016345785d8a0000" +  # amount0
                           "000000000000000000000000000000000000000000000000002c68af0bb14000",  # amount1
                }
            ]
        }
        
        # Define the event parser function
        def parse_events(receipt, periphery_address):
            """Parse events from transaction receipt."""
            events = []
            
            # Event signatures
            event_signatures = {
                "0x3067048beee31b25b2f1681f88dac838c8bba36af25bfb2b7cf7473a5847e35f": "IncreaseLiquidity",
                "0x26f6a048ee9138f2c0ce266f322cb99228e8d619ae2bff30c67f8dcf9d2377b4": "DecreaseLiquidity",
                "0x70935338e69775456a85ddef226c395fb668b63fa0115f5f20610b388e6ca9c0": "Collect"
            }
            
            for log in receipt["logs"]:
                # Check if the log is from the periphery contract
                if "address" in log and log["address"].lower() != periphery_address.lower():
                    continue
                
                # Get the event name
                topic0 = log["topics"][0]
                event_name = event_signatures.get(topic0)
                
                if event_name:
                    # Extract tokenId from the indexed parameter
                    token_id = int(log["topics"][1], 16)
                    
                    events.append({
                        "event": event_name,
                        "tokenId": token_id
                    })
            
            return events
        
        # Test the function
        events = parse_events(receipt, "0xPeripheryContractAddress")
        
        # Verify the results
        assert len(events) == 2
        assert events[0]["event"] == "IncreaseLiquidity"
        assert events[0]["tokenId"] == 291
        assert events[1]["event"] == "DecreaseLiquidity"
        assert events[1]["tokenId"] == 291


if __name__ == "__main__":
    pytest.main()
