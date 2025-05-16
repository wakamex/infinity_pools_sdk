# Standard library imports
from decimal import Decimal
from unittest.mock import MagicMock

# Third-party imports
import pytest
from web3 import Web3  # For Web3.to_checksum_address if needed, or constants

# Local application/library specific imports
from infinity_pools_sdk.core.connector import InfinityPoolsConnector
from infinity_pools_sdk.erc.erc20 import ERC20Helper
from infinity_pools_sdk.utils.config import ContractConfig

# Test constants
TEST_TOKEN_ADDRESS = Web3.to_checksum_address("0x123456789012345678901234567890123456789a")
TEST_ACCOUNT_ADDRESS = Web3.to_checksum_address("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab")
TEST_OWNER_ADDRESS = Web3.to_checksum_address("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbc")
TEST_SPENDER_ADDRESS = Web3.to_checksum_address("0xcccccccccccccccccccccccccccccccccccccccd")
TEST_RECIPIENT_ADDRESS = Web3.to_checksum_address("0xddddddddddddddddddddddddddddddddddddddde")
MOCK_TX_HASH = "0xabcdef1234567890"
DEFAULT_DECIMALS = 18
ERC20_ABI_NAME = 'ERC20' # Assuming this is how ABI is fetched

@pytest.fixture
def mock_w3():
    """Fixture for a mock Web3 instance."""
    w3 = MagicMock(spec=Web3)
    w3.eth = MagicMock()
    return w3

@pytest.fixture
def mock_contract_config():
    """Fixture for a mock ContractConfig."""
    config = MagicMock(spec=ContractConfig)
    # Simulate a generic ERC20 ABI
    mock_erc20_abi = [
        {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},
        {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":False,"stateMutability":"view","type":"function"},
        {"constant":True,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"remaining","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},
        {"constant":False,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"success","type":"bool"}],"payable":False,"stateMutability":"nonpayable","type":"function"},
        {"constant":False,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"success","type":"bool"}],"payable":False,"stateMutability":"nonpayable","type":"function"},
        {"constant":False,"inputs":[{"name":"_from","type":"address"},{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transferFrom","outputs":[{"name":"success","type":"bool"}],"payable":False,"stateMutability":"nonpayable","type":"function"},
        {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"},
        {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"},
        {"constant":True,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},
    ]
    config.get_abi.return_value = mock_erc20_abi
    return config

@pytest.fixture
def mock_connector(mock_w3, mock_contract_config):
    """Fixture for a mock InfinityPoolsConnector."""
    connector = MagicMock(spec=InfinityPoolsConnector)
    connector.w3 = mock_w3
    connector.config = mock_contract_config
    connector.account = None
    
    connector.send_transaction = MagicMock(return_value=MOCK_TX_HASH)
    return connector

@pytest.fixture
def mock_erc20_contract():
    """Fixture for a mock ERC20 contract instance."""
    contract = MagicMock()
    contract.functions.balanceOf = MagicMock()
    contract.functions.decimals = MagicMock()
    contract.functions.allowance = MagicMock()
    contract.functions.approve = MagicMock()
    contract.functions.transfer = MagicMock()
    contract.functions.transferFrom = MagicMock()
    contract.functions.name = MagicMock()
    contract.functions.symbol = MagicMock()
    contract.functions.symbol.return_value.call.return_value = "MOCK"
    contract.functions.decimals.return_value.call.return_value = DEFAULT_DECIMALS
    contract.functions.totalSupply = MagicMock()

    return contract

@pytest.fixture
def erc20_helper(mock_connector):
    """Fixture for an ERC20Helper instance."""
    return ERC20Helper(mock_connector)

@pytest.fixture(autouse=True)
def setup_default_contract_mock(erc20_helper, mock_erc20_contract):
    """Ensure get_contract returns the mock_erc20_contract by default."""
    erc20_helper.connector.w3.eth.contract.return_value = mock_erc20_contract


class TestERC20HelperGetContract:
    def test_get_contract(self, erc20_helper, mock_erc20_contract):
        contract = erc20_helper.get_contract(TEST_TOKEN_ADDRESS)
        erc20_helper.connector.w3.eth.contract.assert_called_once_with(
            address=TEST_TOKEN_ADDRESS,
            abi=erc20_helper.connector.config.get_abi(ERC20_ABI_NAME)
        )
        assert contract == mock_erc20_contract

class TestERC20HelperBalanceOf:
    def test_balance_of_with_address(self, erc20_helper, mock_erc20_contract):
        mock_balance_wei = 1000 * (10**DEFAULT_DECIMALS)
        mock_erc20_contract.functions.balanceOf.return_value.call.return_value = mock_balance_wei
    
        balance = erc20_helper.balance_of(TEST_TOKEN_ADDRESS, TEST_OWNER_ADDRESS)
    
        assert balance == 1000
        mock_erc20_contract.functions.balanceOf.assert_called_once_with(TEST_OWNER_ADDRESS)
        mock_erc20_contract.functions.balanceOf(TEST_OWNER_ADDRESS).call.assert_called_once_with()
        mock_erc20_contract.functions.decimals.assert_called_once()
        assert balance == Decimal("1000.0")

    def test_balance_of_with_loaded_account(self, erc20_helper, mock_connector, mock_erc20_contract):
        mock_account = MagicMock()
        mock_account.address = TEST_ACCOUNT_ADDRESS
        mock_connector.account = mock_account
        
        mock_balance_wei = 500 * (10**DEFAULT_DECIMALS)
        mock_erc20_contract.functions.balanceOf.return_value.call.return_value = mock_balance_wei
    
        balance = erc20_helper.balance_of(TEST_TOKEN_ADDRESS)
    
        assert balance == 500
        mock_erc20_contract.functions.balanceOf.assert_called_once_with(TEST_ACCOUNT_ADDRESS)
        mock_erc20_contract.functions.balanceOf(TEST_ACCOUNT_ADDRESS).call.assert_called_once_with()
        assert balance == Decimal("500.0")

    def test_balance_of_no_address_no_account(self, erc20_helper, mock_connector):
        mock_connector.account = None
        with pytest.raises(ValueError, match="No account loaded and no address provided"):
            erc20_helper.balance_of(TEST_TOKEN_ADDRESS)

    def test_balance_of_different_decimals(self, erc20_helper, mock_erc20_contract):
        custom_decimals = 6
        mock_erc20_contract.functions.decimals().call.return_value = custom_decimals
        mock_balance_wei = 12345 * (10**custom_decimals)
        mock_erc20_contract.functions.balanceOf.return_value.call.return_value = mock_balance_wei
        
        balance = erc20_helper.balance_of(TEST_TOKEN_ADDRESS, TEST_OWNER_ADDRESS)
        assert balance == Decimal("12345.0")


class TestERC20HelperAllowance:
    def test_allowance_with_addresses(self, erc20_helper, mock_erc20_contract):
        mock_allowance_wei = 200 * (10**DEFAULT_DECIMALS)
        mock_erc20_contract.functions.allowance.return_value.call.return_value = mock_allowance_wei
    
        allowance = erc20_helper.allowance(TEST_TOKEN_ADDRESS, TEST_OWNER_ADDRESS, TEST_SPENDER_ADDRESS)
    
        assert allowance == 200
        mock_erc20_contract.functions.allowance.assert_called_once_with(TEST_OWNER_ADDRESS, TEST_SPENDER_ADDRESS)
        mock_erc20_contract.functions.allowance(TEST_OWNER_ADDRESS, TEST_SPENDER_ADDRESS).call.assert_called_once_with()
        mock_erc20_contract.functions.decimals.assert_called_once()
        assert allowance == Decimal("200.0")

    def test_allowance_with_loaded_account_for_owner(self, erc20_helper, mock_connector, mock_erc20_contract):
        mock_account = MagicMock()
        mock_account.address = TEST_ACCOUNT_ADDRESS
        mock_connector.account = mock_account

        mock_allowance_wei = 300 * (10**DEFAULT_DECIMALS)
        mock_erc20_contract.functions.allowance.return_value.call.return_value = mock_allowance_wei
    
        allowance = erc20_helper.allowance(TEST_TOKEN_ADDRESS, spender_address=TEST_SPENDER_ADDRESS)
    
        assert allowance == 300
        mock_erc20_contract.functions.allowance.assert_called_once_with(TEST_ACCOUNT_ADDRESS, TEST_SPENDER_ADDRESS)
        mock_erc20_contract.functions.allowance(TEST_ACCOUNT_ADDRESS, TEST_SPENDER_ADDRESS).call.assert_called_once_with()
        assert allowance == Decimal("300.0")

    def test_allowance_no_owner_no_account(self, erc20_helper, mock_connector):
        mock_connector.account = None
        with pytest.raises(ValueError, match="No account loaded and no owner_address provided for allowance check"):
            erc20_helper.allowance(TEST_TOKEN_ADDRESS, spender_address=TEST_SPENDER_ADDRESS)
            
    def test_allowance_no_spender(self, erc20_helper):
        with pytest.raises(ValueError, match="Spender address must be provided for allowance check"):
            erc20_helper.allowance(TEST_TOKEN_ADDRESS, owner_address=TEST_OWNER_ADDRESS)


class TestERC20HelperApprove:
    def test_approve_successful(self, erc20_helper, mock_connector, mock_erc20_contract):
        mock_account = MagicMock()
        mock_account.address = TEST_ACCOUNT_ADDRESS
        mock_connector.account = mock_account
        
        amount_to_approve = Decimal("100")
        amount_wei = int(amount_to_approve * (10**DEFAULT_DECIMALS))

        mock_tx_func = MagicMock()
        mock_erc20_contract.functions.approve.return_value = mock_tx_func
        mock_built_tx = {'data': '0x...', 'to': TEST_TOKEN_ADDRESS} # Simplified
        mock_tx_func.build_transaction.return_value = mock_built_tx

        tx_hash = erc20_helper.approve(TEST_TOKEN_ADDRESS, TEST_SPENDER_ADDRESS, amount_to_approve)

        mock_erc20_contract.functions.approve.assert_called_once_with(TEST_SPENDER_ADDRESS, amount_wei)
        expected_tx_params = {'from': TEST_ACCOUNT_ADDRESS}
        mock_tx_func.build_transaction.assert_called_once_with(expected_tx_params)
        mock_connector.send_transaction.assert_called_once_with(mock_built_tx)
        assert tx_hash == MOCK_TX_HASH

    def test_approve_no_account(self, erc20_helper, mock_connector):
        mock_connector.account = None
        with pytest.raises(ValueError, match="No account loaded for transaction"):
            erc20_helper.approve(TEST_TOKEN_ADDRESS, TEST_SPENDER_ADDRESS, Decimal("100"))


class TestERC20HelperTransfer:
    def test_transfer_successful(self, erc20_helper, mock_connector, mock_erc20_contract):
        mock_account = MagicMock()
        mock_account.address = TEST_ACCOUNT_ADDRESS
        mock_connector.account = mock_account
        
        amount_to_transfer = Decimal("50")
        amount_wei = int(amount_to_transfer * (10**DEFAULT_DECIMALS))

        mock_tx_func = MagicMock()
        mock_erc20_contract.functions.transfer.return_value = mock_tx_func
        mock_built_tx = {'data': '0x...', 'to': TEST_TOKEN_ADDRESS}
        mock_tx_func.build_transaction.return_value = mock_built_tx

        tx_hash = erc20_helper.transfer(TEST_TOKEN_ADDRESS, TEST_RECIPIENT_ADDRESS, amount_to_transfer)

        mock_erc20_contract.functions.transfer.assert_called_once_with(TEST_RECIPIENT_ADDRESS, amount_wei)
        expected_tx_params = {'from': TEST_ACCOUNT_ADDRESS}
        mock_tx_func.build_transaction.assert_called_once_with(expected_tx_params)
        mock_connector.send_transaction.assert_called_once_with(mock_built_tx)
        assert tx_hash == MOCK_TX_HASH

    def test_transfer_no_account(self, erc20_helper, mock_connector):
        mock_connector.account = None
        with pytest.raises(ValueError, match="No account loaded for transaction"):
            erc20_helper.transfer(TEST_TOKEN_ADDRESS, TEST_RECIPIENT_ADDRESS, Decimal("50"))

class TestERC20HelperTransferFrom:
    def test_transfer_from_successful(self, erc20_helper, mock_connector, mock_erc20_contract):
        mock_account = MagicMock() # This is msg.sender
        mock_account.address = TEST_SPENDER_ADDRESS # The one authorized to spend
        mock_connector.account = mock_account
        
        amount_to_transfer = Decimal("25")
        amount_wei = int(amount_to_transfer * (10**DEFAULT_DECIMALS))

        mock_tx_func = MagicMock()
        mock_erc20_contract.functions.transferFrom.return_value = mock_tx_func
        mock_built_tx = {'data': '0x...', 'to': TEST_TOKEN_ADDRESS}
        mock_tx_func.build_transaction.return_value = mock_built_tx

        tx_hash = erc20_helper.transfer_from(TEST_TOKEN_ADDRESS, TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS, amount_to_transfer)

        mock_erc20_contract.functions.transferFrom.assert_called_once_with(TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS, amount_wei)
        expected_tx_params = {'from': TEST_SPENDER_ADDRESS}
        mock_tx_func.build_transaction.assert_called_once_with(expected_tx_params)
        mock_connector.send_transaction.assert_called_once_with(mock_built_tx)
        assert tx_hash == MOCK_TX_HASH

    def test_transfer_from_no_account(self, erc20_helper, mock_connector):
        mock_connector.account = None
        with pytest.raises(ValueError, match="No account loaded for transaction"):
            erc20_helper.transfer_from(TEST_TOKEN_ADDRESS, TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS, Decimal("25"))

class TestERC20HelperReadMethods:
    def test_name(self, erc20_helper, mock_erc20_contract):
        expected_name = "Test Token"
        mock_erc20_contract.functions.name().call.return_value = expected_name
        name = erc20_helper.name(TEST_TOKEN_ADDRESS)
        mock_erc20_contract.functions.name().call.assert_called_once()
        assert name == expected_name

    def test_symbol(self, erc20_helper, mock_erc20_contract):
        expected_symbol = "TST"
        mock_erc20_contract.functions.symbol().call.return_value = expected_symbol
        symbol = erc20_helper.symbol(TEST_TOKEN_ADDRESS)
        mock_erc20_contract.functions.symbol().call.assert_called_once()
        assert symbol == expected_symbol

    def test_decimals(self, erc20_helper, mock_erc20_contract):
        # Default behavior is already set in mock_erc20_contract fixture
        decimals = erc20_helper.decimals(TEST_TOKEN_ADDRESS)
        mock_erc20_contract.functions.decimals().call.assert_called_once()
        assert decimals == DEFAULT_DECIMALS

    def test_total_supply(self, erc20_helper, mock_erc20_contract):
        mock_total_supply_wei = 1000000 * (10**DEFAULT_DECIMALS)
        mock_erc20_contract.functions.totalSupply().call.return_value = mock_total_supply_wei
        
        total_supply = erc20_helper.total_supply(TEST_TOKEN_ADDRESS)
        
        mock_erc20_contract.functions.totalSupply().call.assert_called_once()
        # decimals() will be called again here
        assert mock_erc20_contract.functions.decimals().call.call_count > 0 # Exact count depends on other tests
        assert total_supply == Decimal("1000000.0")
