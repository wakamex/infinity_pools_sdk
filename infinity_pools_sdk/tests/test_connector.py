from unittest.mock import MagicMock, patch  # Standard library

import pytest  # Third-party
from eth_account.signers.local import LocalAccount  # Third-party
from web3 import HTTPProvider, Web3  # Third-party

from infinity_pools_sdk.core.connector import InfinityPoolsConnector  # First-party
from infinity_pools_sdk.utils.config import NETWORKS, ContractConfig  # First-party

# Sample private key for testing (replace with a burner key if interacting with live testnets)
TEST_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80" # Default Hardhat/Anvil key
TEST_ACCOUNT_ADDRESS = Web3.to_checksum_address("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")

@pytest.fixture
def connector_config():
    """Provide a default ContractConfig instance for 'mainnet'."""
    return ContractConfig(network_name='mainnet')

@pytest.fixture
def mock_http_provider():
    """Mock the HTTPProvider class, ensuring its instance passes BaseProvider check."""
    with patch('infinity_pools_sdk.core.connector.HTTPProvider') as mock_provider_class:
        mock_instance = MagicMock(spec=HTTPProvider) # Ensure instance passes type checks
        mock_provider_class.return_value = mock_instance
        yield mock_provider_class # Yield the mocked class itself

@pytest.fixture
def connector(mock_http_provider, connector_config):
    """Provide an InfinityPoolsConnector instance with a mocked HTTPProvider and default config."""
    # Mock ContractConfig to avoid file system access during basic connector tests
    with patch('infinity_pools_sdk.core.connector.ContractConfig') as mock_contract_config:
        mock_contract_config.return_value = connector_config
        # Mock os.environ.get for default RPC URL
        with patch('os.environ.get') as mock_env_get:
            mock_env_get.return_value = "http://localhost:8545" # Dummy RPC URL
            conn = InfinityPoolsConnector(network='mainnet')
            # Manually assign the mocked w3 instance if needed for some tests, 
            # or ensure methods that use w3 are mocked
            conn.w3 = MagicMock(spec=Web3) # Replace real w3 with a full MagicMock
            conn.w3.eth = MagicMock()
            conn.w3.middleware_onion = MagicMock()
            conn.w3.middleware_onion.inject = MagicMock()
            return conn


def test_connector_initialization_default_rpc(connector):
    """Test basic connector initialization with default RPC."""
    assert connector.network == 'mainnet'
    assert connector.w3 is not None
    assert connector.account is None
    # Further check if HTTPProvider was called with the default RPC
    # This requires the mock_http_provider fixture to be enhanced or os.environ.get to be patched
    # For now, we assume the fixture setup handles this implicitly by allowing init.

def test_connector_initialization_custom_rpc(connector_config):
    """Test connector initialization with a custom RPC URL."""
    custom_rpc = "http://127.0.0.1:7545"
    with patch('os.environ.get', return_value="http://another-default:8545"):
        with patch('infinity_pools_sdk.core.connector.HTTPProvider') as mock_provider_class:
            mock_http_instance = MagicMock(spec=HTTPProvider)
            mock_provider_class.return_value = mock_http_instance
            with patch('infinity_pools_sdk.core.connector.ContractConfig') as mock_contract_config:
                mock_contract_config.return_value = connector_config
                conn = InfinityPoolsConnector(rpc_url=custom_rpc, network='mainnet')
                mock_provider_class.assert_called_once_with(custom_rpc)
                assert conn.w3 is not None
                # Ensure the Web3 instance within the connector used our mocked HTTPProvider instance
                assert conn.w3.provider == mock_http_instance

def test_load_account(connector):
    """Test loading an account from a private key."""
    account = connector.load_account(TEST_PRIVATE_KEY)
    assert isinstance(account, LocalAccount)
    assert account.address == TEST_ACCOUNT_ADDRESS
    assert connector.account is not None
    assert connector.account.address == TEST_ACCOUNT_ADDRESS

def test_get_default_rpc_env_var_exists(connector):
    """Test _get_default_rpc when the environment variable is set."""
    expected_rpc = "http://test-rpc.com"
    with patch('os.environ.get') as mock_env_get:
        mock_env_get.return_value = expected_rpc
        rpc_url = connector._get_default_rpc()
        mock_env_get.assert_called_once_with(f"INFINITY_POOLS_RPC_{connector.network.upper()}")
        assert rpc_url == expected_rpc

def test_get_default_rpc_env_var_missing(connector):
    """Test _get_default_rpc when the environment variable is NOT set."""
    with patch('os.environ.get') as mock_env_get:
        mock_env_get.return_value = None
        with pytest.raises(ValueError, match="No RPC URL provided and no INFINITY_POOLS_RPC_MAINNET environment variable found"):
            connector._get_default_rpc()


def test_get_contract_instance_success(connector, connector_config):
    """Test successfully getting a contract instance when address and ABI are found."""
    contract_name = "TestContract"
    mock_address = "0x1234567890123456789012345678901234567890"
    mock_abi = [{"type": "function", "name": "testFunc"}]
    mock_contract_object = MagicMock()

    # Setup mocks on the config object held by the connector
    connector.config.get_address = MagicMock(return_value=mock_address)
    connector.config.get_abi = MagicMock(return_value=mock_abi)
    
    # Mock the w3.eth.contract call
    connector.w3.eth.contract = MagicMock(return_value=mock_contract_object)

    contract_instance = connector.get_contract_instance(contract_name)

    connector.config.get_address.assert_called_once_with(contract_name)
    connector.config.get_abi.assert_called_once_with(contract_name)
    connector.w3.eth.contract.assert_called_once_with(address=mock_address, abi=mock_abi)
    assert contract_instance == mock_contract_object

def test_get_contract_instance_custom_address(connector, connector_config):
    """Test getting a contract instance with a custom address."""
    contract_name = "TestContract"
    custom_address = "0xABCDEF0123456789ABCDEF0123456789ABCDEF01"
    mock_abi = [{"type": "function", "name": "testFunc"}]
    mock_contract_object = MagicMock()

    connector.config.get_abi = MagicMock(return_value=mock_abi)
    connector.config.get_address = MagicMock() # To ensure it's not called
    connector.w3.eth.contract = MagicMock(return_value=mock_contract_object)

    contract_instance = connector.get_contract_instance(contract_name, address=custom_address)

    connector.config.get_address.assert_not_called()
    connector.config.get_abi.assert_called_once_with(contract_name)
    connector.w3.eth.contract.assert_called_once_with(address=custom_address, abi=mock_abi)
    assert contract_instance == mock_contract_object

def test_get_contract_instance_address_not_found(connector, connector_config):
    """Test error when contract address is not found in config."""
    contract_name = "NonExistentContract"
    connector.config.get_address = MagicMock(return_value=None)

    with pytest.raises(ValueError, match=f"Address for {contract_name} not found in configuration for network {connector.network}"):
        connector.get_contract_instance(contract_name)

def test_get_contract_instance_abi_not_found(connector, connector_config):
    """Test error when contract ABI is not found in config."""
    contract_name = "NoAbiContract"
    mock_address = "0x1234567890123456789012345678901234567890"
    
    connector.config.get_address = MagicMock(return_value=mock_address)
    connector.config.get_abi = MagicMock(return_value=None)

    with pytest.raises(ValueError, match=f"Contract {contract_name} not found in configuration"):
        connector.get_contract_instance(contract_name)


def test_send_transaction_success(connector):
    """Test successfully sending a transaction."""
    # Setup account on the connector
    connector.load_account(TEST_PRIVATE_KEY)
    assert connector.account is not None

    tx_params = {
        'to': '0x0000000000000000000000000000000000000000',
        'value': Web3.to_wei(1, 'ether'),
        # 'gas', 'gasPrice', 'nonce' will be auto-filled by the method
    }
    expected_tx_hash = "0x123abc"
    mock_signed_tx = MagicMock()
    mock_signed_tx.rawTransaction = b'raw_tx_bytes'

    # Mock eth client calls
    connector.w3.eth.estimate_gas = MagicMock(return_value=21000)
    connector.w3.eth.gas_price = Web3.to_wei(50, 'gwei') 
    connector.w3.eth.get_transaction_count = MagicMock(return_value=1)
    connector.w3.eth.send_raw_transaction = MagicMock(return_value=bytes.fromhex(expected_tx_hash[2:]))
    
    # Mock account signing
    connector.account.sign_transaction = MagicMock(return_value=mock_signed_tx)

    tx_hash = connector.send_transaction(tx_params)

    connector.w3.eth.estimate_gas.assert_called_once()
    connector.w3.eth.get_transaction_count.assert_called_once_with(TEST_ACCOUNT_ADDRESS)
    connector.account.sign_transaction.assert_called_once()
    # Check that nonce, gas, gasPrice were added to tx_params before signing
    signed_call_args = connector.account.sign_transaction.call_args[0][0]
    assert 'nonce' in signed_call_args
    assert signed_call_args['nonce'] == 1
    assert 'gas' in signed_call_args
    assert signed_call_args['gas'] == 21000
    assert 'gasPrice' in signed_call_args
    assert signed_call_args['gasPrice'] == Web3.to_wei(50, 'gwei')
    connector.w3.eth.send_raw_transaction.assert_called_once_with(mock_signed_tx.rawTransaction)
    assert tx_hash == expected_tx_hash

def test_send_transaction_no_account(connector):
    """Test error when trying to send transaction without a loaded account."""
    connector.account = None # Ensure no account is loaded
    with pytest.raises(ValueError, match=r"No account loaded\. Call load_account\(\) first\."):
        connector.send_transaction({})

def test_send_transaction_manual_gas_nonce(connector):
    """Test sending a transaction with manually specified gas, gasPrice, and nonce."""
    connector.load_account(TEST_PRIVATE_KEY)
    tx_params = {
        'to': '0x0000000000000000000000000000000000000000',
        'value': Web3.to_wei(1, 'ether'),
        'gas': 30000,
        'gasPrice': Web3.to_wei(60, 'gwei'),
        'nonce': 5
    }
    expected_tx_hash = "0x456def"
    mock_signed_tx = MagicMock()
    mock_signed_tx.rawTransaction = b'raw_tx_bytes_manual'

    connector.w3.eth.send_raw_transaction = MagicMock(return_value=bytes.fromhex(expected_tx_hash[2:]))
    connector.account.sign_transaction = MagicMock(return_value=mock_signed_tx)
    # Ensure estimate_gas, gas_price, get_transaction_count are NOT called
    connector.w3.eth.estimate_gas = MagicMock()
    connector.w3.eth.gas_price = Web3.to_wei(50, 'gwei') 
    connector.w3.eth.get_transaction_count = MagicMock()

    tx_hash = connector.send_transaction(tx_params)

    connector.w3.eth.estimate_gas.assert_not_called()
    connector.w3.eth.get_transaction_count.assert_not_called()
    connector.account.sign_transaction.assert_called_once_with(tx_params) # Ensure original params are used
    assert tx_hash == expected_tx_hash

def test_wait_for_transaction_success(connector):
    """Test successfully waiting for a transaction receipt."""
    tx_hash = "0x789abcdef0123456789abcdef0123456789abcdef0123456789abcdef01234567"
    expected_receipt = {'blockNumber': 123, 'status': 1}
    
    connector.w3.eth.wait_for_transaction_receipt = MagicMock(return_value=expected_receipt)

    receipt = connector.wait_for_transaction(tx_hash)

    connector.w3.eth.wait_for_transaction_receipt.assert_called_once_with(Web3.to_bytes(hexstr=tx_hash), timeout=120)
    assert receipt == expected_receipt

# Placeholder for more tests to come based on the strategy
