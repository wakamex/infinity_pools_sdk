import json
from pathlib import Path
from typing import Dict, Optional

NETWORKS: Dict[str, int] = {
    'mainnet': 1,
    'goerli': 5,
    'sepolia': 11155111,
    'arbitrum': 42161,
    'optimism': 10,
    'base': 8453,
    # Add other supported networks
}

# Placeholder for default addresses, to be populated or loaded if specific files are missing
DEFAULT_ADDRESSES: Dict[str, Dict[str, str]] = {
    'mainnet': {},
    'goerli': {},
    # Add other networks and their default contract addresses if needed
}

class ContractConfig:
    def __init__(self, network_name: str = 'mainnet'):
        self.network_name = network_name
        if self.network_name not in NETWORKS:
            # Fallback to mainnet if network_name is not recognized, or raise an error
            print(f"Warning: Network '{self.network_name}' not explicitly defined. Defaulting to 'mainnet' ID.")
            self.network_id = NETWORKS.get('mainnet', 1)
        else:
            self.network_id = NETWORKS[self.network_name]
        
        self.addresses: Dict[str, str] = {}
        self.abis: Dict[str, list] = {}
        self._load_addresses()
        self._load_abis()
    
    def _get_data_dir(self) -> Path:
        """Return the path to the 'data' directory within the SDK."""
        # Assumes this file (config.py) is in infinity_pools_sdk/utils/
        return Path(__file__).parent.parent / 'data'

    def _load_addresses(self):
        """Load contract addresses for the selected network."""
        data_dir = self._get_data_dir()
        addresses_file = data_dir / f'addresses_{self.network_name}.json'
        
        if addresses_file.exists():
            try:
                with open(addresses_file, 'r', encoding='utf-8') as f:
                    self.addresses = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not decode JSON from {addresses_file}. Using default addresses for {self.network_name}.")
                self.addresses = DEFAULT_ADDRESSES.get(self.network_name, {})
        else:
            print(f"Warning: Address file {addresses_file} not found. Using default addresses for {self.network_name}.")
            self.addresses = DEFAULT_ADDRESSES.get(self.network_name, {})
    
    def _load_abis(self):
        """Load contract ABIs."""
        data_dir = self._get_data_dir()
        abi_dir = data_dir / 'abis'
        self.abis = {}
        if abi_dir.exists() and abi_dir.is_dir():
            for abi_file in abi_dir.glob('*.json'):
                contract_name = abi_file.stem
                try:
                    with open(abi_file, 'r', encoding='utf-8') as f:
                        self.abis[contract_name] = json.load(f)
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON from ABI file {abi_file}.")
        else:
            print(f"Warning: ABI directory {abi_dir} not found or is not a directory.")

    def get_address(self, contract_name: str) -> Optional[str]:
        """Get address for a specific contract."""
        return self.addresses.get(contract_name)
    
    def get_abi(self, contract_name: str) -> Optional[list]:
        """Get ABI for a specific contract."""
        return self.abis.get(contract_name)

    def set_network(self, network_name: str):
        """Set a new network and reload its corresponding addresses and ABIs.

        If the network_name is not recognized, a warning is printed and the
        network is not changed.
        """
        if network_name not in NETWORKS:
            print(f"Warning: Network '{network_name}' not explicitly defined in NETWORKS. Network not changed from '{self.network_name}'.")
            return

        if self.network_name == network_name:
            # print(f"Info: Network is already set to '{network_name}'. No change made.") # Optional: if verbose logging is desired
            return

        self.network_name = network_name
        self.network_id = NETWORKS[self.network_name]
        # print(f"Info: Switched network to: {self.network_name}") # Optional: for debugging/logging
        self._load_addresses()  # Reload addresses for the new network
        self._load_abis()       # Reload all ABIs (ABIs are not network-specific in the current design but good practice to call)

# Example usage (optional, for testing purposes):
# if __name__ == '__main__':
#     config_mainnet = ContractConfig('mainnet')
#     print(f"Mainnet Config - Addresses: {config_mainnet.addresses}, ABIs: {list(config_mainnet.abis.keys())}")
#     periphery_abi_mainnet = config_mainnet.get_abi('InfinityPoolsPeriphery')
#     print(f"Periphery ABI on Mainnet: {'Found' if periphery_abi_mainnet else 'Not Found'}")

#     config_goerli = ContractConfig('goerli')
#     print(f"Goerli Config - Addresses: {config_goerli.addresses}, ABIs: {list(config_goerli.abis.keys())}")

#     config_unknown = ContractConfig('unknown_network') # Test fallback
#     print(f"Unknown Network Config - Addresses: {config_unknown.addresses}, ABIs: {list(config_unknown.abis.keys())}")
