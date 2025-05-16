import json
from pathlib import Path

import pytest

from infinity_pools_sdk.utils.config import DEFAULT_ADDRESSES, NETWORKS, ContractConfig


@pytest.fixture
def mock_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    abis_dir = data_dir / "abis"
    abis_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy ABI files
    with open(abis_dir / "SampleContract.json", "w") as f:
        json.dump([{"type": "function", "name": "sampleFunction"}], f)
    with open(abis_dir / "ERC20.json", "w") as f:
        json.dump([{"type": "function", "name": "balanceOf"}], f)

    # Create dummy address files
    with open(data_dir / "addresses_mainnet.json", "w") as f:
        json.dump({"SampleContract": "0xMainnetSampleAddress", "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"}, f)
    with open(data_dir / "addresses_goerli.json", "w") as f:
        json.dump({"SampleContract": "0xGoerliSampleAddress", "USDC": "0x07865c6E87B9F70255377e024ace6630C1Eaa37F"}, f)
    
    return data_dir

@pytest.fixture
def patch_config_paths(monkeypatch, mock_data_dir):
    """Patches ContractConfig to use the mock_data_dir."""
    def mock_get_data_dir(self):
        return mock_data_dir
    
    monkeypatch.setattr(ContractConfig, "_get_data_dir", mock_get_data_dir)

def test_contract_config_initialization_mainnet(patch_config_paths):
    config = ContractConfig(network_name='mainnet')
    assert config.network_name == 'mainnet'
    assert config.network_id == NETWORKS['mainnet']
    assert config.get_address('SampleContract') == "0xMainnetSampleAddress"
    assert config.get_abi('SampleContract') is not None
    assert len(config.get_abi('SampleContract')) > 0

def test_contract_config_initialization_goerli(patch_config_paths):
    config = ContractConfig(network_name='goerli')
    assert config.network_name == 'goerli'
    assert config.network_id == NETWORKS['goerli']
    assert config.get_address('SampleContract') == "0xGoerliSampleAddress"
    assert config.get_abi('ERC20') is not None

def test_contract_config_fallback_to_default_addresses(patch_config_paths, mock_data_dir):
    # Remove a specific address file to test fallback
    address_file_to_remove = mock_data_dir / "addresses_sepolia.json" # A network we haven't written a file for
    if address_file_to_remove.exists():
        address_file_to_remove.unlink()

    # Add a default address for sepolia to DEFAULT_ADDRESSES for this test
    original_sepolia_defaults = DEFAULT_ADDRESSES.get('sepolia')
    DEFAULT_ADDRESSES['sepolia'] = {"DefaultToken": "0xSepoliaDefaultAddress"}
    
    config = ContractConfig(network_name='sepolia')
    assert config.network_name == 'sepolia'
    assert config.get_address('DefaultToken') == "0xSepoliaDefaultAddress" 
    assert config.get_address('SampleContract') is None # This shouldn't be in defaults

    # Clean up / revert DEFAULT_ADDRESSES for other tests
    if original_sepolia_defaults is None:
        del DEFAULT_ADDRESSES['sepolia']
    else:
        DEFAULT_ADDRESSES['sepolia'] = original_sepolia_defaults

def test_contract_config_missing_abi_file(patch_config_paths):
    config = ContractConfig(network_name='mainnet')
    assert config.get_abi('NonExistentContract') is None

def test_contract_config_missing_address(patch_config_paths):
    config = ContractConfig(network_name='mainnet')
    assert config.get_address('NonExistentToken') is None

def test_contract_config_unknown_network(patch_config_paths):
    # Test fallback for network_id if network name is unknown
    config = ContractConfig(network_name='supercustomnetwork')
    assert config.network_name == 'supercustomnetwork'
    assert config.network_id == NETWORKS['mainnet'] # Falls back to mainnet ID
    # Addresses and ABIs should likely be empty or from mainnet defaults if those were defined for unknown networks
    # Based on current logic, it will try to load addresses_supercustomnetwork.json which won't exist,
    # then fall back to DEFAULT_ADDRESSES['supercustomnetwork'] which also won't exist.
    assert config.addresses == {}

def test_set_network_valid_network_change(patch_config_paths):
    config = ContractConfig(network_name='mainnet')
    assert config.get_address('SampleContract') == "0xMainnetSampleAddress"

    config.set_network('goerli')
    assert config.network_name == 'goerli'
    assert config.network_id == NETWORKS['goerli']
    assert config.get_address('SampleContract') == "0xGoerliSampleAddress" # Ensure addresses are reloaded
    assert config.get_abi('ERC20') is not None # ABIs should still be available

def test_set_network_invalid_network_no_change(patch_config_paths, capsys):
    config = ContractConfig(network_name='mainnet')
    initial_address = config.get_address('SampleContract')
    
    config.set_network('non_existent_network')
    
    assert config.network_name == 'mainnet' # Network should not change
    assert config.get_address('SampleContract') == initial_address # Addresses should remain for 'mainnet'
    captured = capsys.readouterr()
    assert "Warning: Network 'non_existent_network' not explicitly defined" in captured.out

def test_set_network_same_network_no_unnecessary_reload(patch_config_paths, mocker):
    config = ContractConfig(network_name='mainnet')
    
    # Spy on the internal load methods
    spy_load_addresses = mocker.spy(config, '_load_addresses')
    spy_load_abis = mocker.spy(config, '_load_abis')
    
    config.set_network('mainnet') # Set to the same network
    
    spy_load_addresses.assert_not_called() # Should not be called if network is the same
    spy_load_abis.assert_not_called() # Should not be called if network is the same
    assert config.network_name == 'mainnet'

# TODO: Add tests for:
# - JSONDecodeError in address files (when attempting to load after set_network)
# - JSONDecodeError in ABI files (when attempting to load after set_network)
# - ABI directory not existing (when attempting to load after set_network)
# - Handling of empty ABI/address files if that's a valid state yielding empty configs
