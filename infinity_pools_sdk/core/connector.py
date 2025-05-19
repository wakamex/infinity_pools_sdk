from typing import Any, Dict, Optional  # Standard library

from eth_account import Account  # Third-party
from eth_account.signers.local import LocalAccount  # Third-party
from web3 import HTTPProvider, Web3  # Third-party
from web3.middleware import ExtraDataToPOAMiddleware  # Third-party

from ..utils.config import NETWORKS, ContractConfig  # First-party


class InfinityPoolsConnector:
    """Handles connection to an Ethereum node and account management."""
    
    def __init__(self, 
                 w3_instance: Web3,
                 network: str = 'mainnet', # network string is still useful for context
                 private_key: Optional[str] = None):
        """Initialize the connector with a Web3 instance and optional private key.
        
        Args:
            w3_instance: A pre-configured Web3 instance.
            network: The network name (e.g., 'mainnet', 'goerli'). Important for network-specific logic like POA middleware.
            private_key: Optional private key for signing transactions.
        """
        self.network = network
        self.config = ContractConfig(network) # ContractConfig might still use network string
        
        self.w3: Web3 = w3_instance
        self.impersonated_address: Optional[str] = None # If impersonation is done by configuring w3_instance provider, this might not be needed or set differently.

        # Inject POA middleware if a common POA network is detected
        # This check relies on the network name. 
        # If POA detection previously relied on rpc_url structure, this might need review.
        if self.network.lower() in ['polygon', 'mumbai', 'bsc', 'goerli', 'sepolia', 'base']:
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        # Setup account if private key provided
        self.account: Optional[LocalAccount] = None
        if private_key:
            self.load_account(private_key)
    
    def load_account(self, private_key: str):
        """Load an account from a private key."""
        if private_key.startswith('0x'):
            private_key = private_key[2:]
        self.account = Account.from_key(private_key)
        return self.account
    
    def get_contract_instance(self, contract_name: str, address: Optional[str] = None) -> Any: 
        """Get a Web3 contract instance."""
        if address is None:
            address = self.config.get_address(contract_name)
            if not address:
                raise ValueError(f"Address for {contract_name} not found in configuration for network {self.network}")
        
        abi = self.config.get_abi(contract_name)
        if not abi:
            raise ValueError(f"Contract {contract_name} not found in configuration")
        return self.w3.eth.contract(address=address, abi=abi)
    
    def send_transaction(self, tx_params: Dict[str, Any]) -> str:
        """Sign and send a transaction.
        
        If using an impersonated account with Tenderly, this will send the transaction
        directly without signing it (Tenderly handles the impersonation).
        """
        # Handle differently based on whether we're using impersonation or a local account
        if self.impersonated_address:
            # When using impersonation, we don't need to sign the transaction
            # Tenderly will handle that for us
            
            # Make sure the 'from' address is set to the impersonated address
            tx_params['from'] = self.impersonated_address
            
            # Ensure gas parameters are set
            if 'gas' not in tx_params:
                tx_params['gas'] = self.w3.eth.estimate_gas(tx_params)
            if 'gasPrice' not in tx_params and 'maxFeePerGas' not in tx_params:
                tx_params['gasPrice'] = self.w3.eth.gas_price
            
            # Send the transaction directly (no signing needed with impersonation)
            tx_hash = self.w3.eth.send_transaction(tx_params)
            return tx_hash.hex()
        else:
            # Standard flow using a local account with private key
            if not self.account:
                raise ValueError("No account loaded and no impersonation configured. Call load_account() first.")
            
            # Ensure gas parameters are set
            if 'gas' not in tx_params:
                # For 'gas', we need a from address if not already in tx_params
                if 'from' not in tx_params and self.account:
                    tx_params['from'] = self.account.address
                tx_params['gas'] = self.w3.eth.estimate_gas(tx_params)
            if 'gasPrice' not in tx_params and 'maxFeePerGas' not in tx_params:
                tx_params['gasPrice'] = self.w3.eth.gas_price
            
            # Set nonce if not provided
            if 'nonce' not in tx_params:
                tx_params['nonce'] = self.w3.eth.get_transaction_count(self.account.address)
            
            # Sign transaction
            signed_tx = self.account.sign_transaction(tx_params)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction) # Changed rawTransaction to raw_transaction
            return "0x" + tx_hash.hex()
    
    def wait_for_transaction(self, tx_hash: str, timeout: int = 120) -> Dict[str, Any]:
        """Wait for a transaction to be mined and return the receipt."""
        tx_hash_bytes = Web3.to_bytes(hexstr=tx_hash)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=timeout)
        return dict(receipt)
