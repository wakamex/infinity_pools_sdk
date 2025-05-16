from typing import Any, Dict, Optional  # Standard library

from eth_account import Account  # Third-party
from eth_account.signers.local import LocalAccount  # Third-party
from web3 import HTTPProvider, Web3  # Third-party
from web3.middleware import ExtraDataToPOAMiddleware  # Third-party

from ..utils.config import NETWORKS, ContractConfig  # First-party

class InfinityPoolsConnector:
    def __init__(self, 
                 rpc_url: Optional[str] = None,
                 network: str = 'mainnet',
                 private_key: Optional[str] = None):
        """Initialize the connector with RPC URL and optional private key."""
        self.network = network
        self.config = ContractConfig(network)
        
        # Setup Web3 connection
        if rpc_url is None:
            rpc_url = self._get_default_rpc()
        self.w3 = Web3(HTTPProvider(rpc_url))
        # Inject POA middleware if a common POA network is detected or if URL suggests it
        if self.network.lower() in ['polygon', 'mumbai', 'bsc', 'goerli', 'sepolia'] or \
           any(keyword in rpc_url.lower() for keyword in ['matic', 'bsc', 'bnb', 'poa', 'ankr']):
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        # Setup account if private key provided
        self.account: Optional[LocalAccount] = None
        if private_key:
            self.load_account(private_key)
    
    def _get_default_rpc(self) -> str:
        """Get default RPC URL from environment variables."""
        import os
        env_var = f"INFINITY_POOLS_RPC_{self.network.upper()}"
        rpc_url = os.environ.get(env_var)
        if not rpc_url:
            raise ValueError(f"No RPC URL provided and no {env_var} environment variable found")
        return rpc_url
    
    def load_account(self, private_key: str) -> LocalAccount:
        """Load an Ethereum account from a private key."""
        if private_key.startswith('0x'):
            private_key = private_key[2:]
        self.account = Account.from_key(private_key)
        return self.account
    
    def get_contract_instance(self, contract_name: str, address: Optional[str] = None) -> Any: # Changed from web3.contract.Contract to Any
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
        """Sign and send a transaction."""
        if not self.account:
            raise ValueError("No account loaded. Call load_account() first.")
        
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
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return "0x" + tx_hash.hex()
    
    def wait_for_transaction(self, tx_hash: str, timeout: int = 120) -> Dict[str, Any]:
        """Wait for a transaction to be mined and return the receipt."""
        tx_hash_bytes = Web3.to_bytes(hexstr=tx_hash)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=timeout)
        return dict(receipt)
