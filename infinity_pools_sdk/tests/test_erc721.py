# Standard library imports
from unittest.mock import MagicMock

# Third-party imports
import pytest
from web3 import Web3

# Local application/library specific imports
from infinity_pools_sdk.core.connector import InfinityPoolsConnector
from infinity_pools_sdk.erc.erc721 import ERC721Helper
from infinity_pools_sdk.utils.config import ContractConfig  # Assuming used by connector

# Test constants
TEST_NFT_ADDRESS = Web3.to_checksum_address("0x123456789012345678901234567890123456789a")
TEST_ACCOUNT_ADDRESS = Web3.to_checksum_address("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab")
TEST_OWNER_ADDRESS = Web3.to_checksum_address("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbc")
TEST_OPERATOR_ADDRESS = Web3.to_checksum_address("0xcccccccccccccccccccccccccccccccccccccccd")
TEST_RECIPIENT_ADDRESS = Web3.to_checksum_address("0xddddddddddddddddddddddddddddddddddddddde")
TEST_TOKEN_ID_1 = 1
TEST_TOKEN_ID_2 = 2
MOCK_TX_HASH = "0xabcdef1234567890"
ERC721_ABI_NAME = 'ERC721' # Assuming this is how ABI is fetched

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
    # Simulate a generic ERC721 ABI
    mock_erc721_abi = [
        {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},
        {"constant":True,"inputs":[{"name":"_tokenId","type":"uint256"}],"name":"ownerOf","outputs":[{"name":"owner","type":"address"}],"payable":False,"stateMutability":"view","type":"function"},
        {"constant":False,"inputs":[{"name":"_to","type":"address"},{"name":"_tokenId","type":"uint256"}],"name":"approve","outputs":[],"payable":False,"stateMutability":"nonpayable","type":"function"},
        {"constant":True,"inputs":[{"name":"_tokenId","type":"uint256"}],"name":"getApproved","outputs":[{"name":"operator","type":"address"}],"payable":False,"stateMutability":"view","type":"function"},
        {"constant":False,"inputs":[{"name":"_operator","type":"address"},{"name":"_approved","type":"bool"}],"name":"setApprovalForAll","outputs":[],"payable":False,"stateMutability":"nonpayable","type":"function"},
        {"constant":True,"inputs":[{"name":"_owner","type":"address"},{"name":"_operator","type":"address"}],"name":"isApprovedForAll","outputs":[{"name":"","type":"bool"}],"payable":False,"stateMutability":"view","type":"function"},
        {"constant":False,"inputs":[{"name":"_from","type":"address"},{"name":"_to","type":"address"},{"name":"_tokenId","type":"uint256"}],"name":"transferFrom","outputs":[],"payable":False,"stateMutability":"nonpayable","type":"function"},
        {"constant":False,"inputs":[{"name":"_from","type":"address"},{"name":"_to","type":"address"},{"name":"_tokenId","type":"uint256"},{"name":"_data","type":"bytes"}],"name":"safeTransferFrom","outputs":[],"payable":False,"stateMutability":"nonpayable","type":"function"},
        {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"},
        {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"},
        {"constant":True,"inputs":[{"name":"_tokenId","type":"uint256"}],"name":"tokenURI","outputs":[{"name":"","type":"string"}],"payable":False,"stateMutability":"view","type":"function"},
    ]
    config.get_abi.return_value = mock_erc721_abi
    return config

@pytest.fixture
def mock_connector(mock_w3, mock_contract_config):
    """Fixture for a mock InfinityPoolsConnector."""
    connector = MagicMock(spec=InfinityPoolsConnector)
    connector.w3 = mock_w3
    connector.config = mock_contract_config
    connector.account = None # Default to no account loaded
    connector.send_transaction = MagicMock(return_value=MOCK_TX_HASH)
    return connector

@pytest.fixture
def mock_erc721_contract():
    """Fixture for a mock ERC721 contract instance."""
    contract = MagicMock()
    # Define all expected functions as MagicMock attributes
    contract.functions.balanceOf = MagicMock()
    contract.functions.ownerOf = MagicMock()
    contract.functions.approve = MagicMock()
    contract.functions.getApproved = MagicMock()
    contract.functions.setApprovalForAll = MagicMock()
    contract.functions.isApprovedForAll = MagicMock()
    contract.functions.transferFrom = MagicMock()
    contract.functions.safeTransferFrom = MagicMock()
    contract.functions.name = MagicMock()
    contract.functions.symbol = MagicMock()
    contract.functions.tokenURI = MagicMock()
    return contract

@pytest.fixture
def erc721_helper(mock_connector):
    """Fixture for an ERC721Helper instance."""
    return ERC721Helper(mock_connector)

@pytest.fixture(autouse=True)
def setup_default_contract_mock(erc721_helper, mock_erc721_contract):
    """Ensure get_contract returns the mock_erc721_contract by default."""
    erc721_helper.connector.w3.eth.contract.return_value = mock_erc721_contract

class TestERC721HelperGetContract:
    def test_get_contract(self, erc721_helper, mock_erc721_contract):
        """Test that get_contract correctly calls w3.eth.contract and returns the contract."""
        contract = erc721_helper.get_contract(TEST_NFT_ADDRESS)
        erc721_helper.connector.w3.eth.contract.assert_called_once_with(
            address=TEST_NFT_ADDRESS,
            abi=erc721_helper.connector.config.get_abi(ERC721_ABI_NAME)
        )
        assert contract == mock_erc721_contract

class TestERC721HelperBalanceOf:
    def test_balance_of_with_address(self, erc721_helper, mock_erc721_contract):
        """Test balance_of with an explicitly provided owner address."""
        mock_erc721_contract.functions.balanceOf.return_value.call.return_value = 5
        balance = erc721_helper.balance_of(TEST_NFT_ADDRESS, TEST_OWNER_ADDRESS)
        assert balance == 5
        mock_erc721_contract.functions.balanceOf.assert_called_once_with(TEST_OWNER_ADDRESS)
        mock_erc721_contract.functions.balanceOf(TEST_OWNER_ADDRESS).call.assert_called_once_with()
        assert balance == 5

    def test_balance_of_with_loaded_account(self, erc721_helper, mock_connector, mock_erc721_contract):
        """Test balance_of when an account is loaded in the connector."""
        mock_account = MagicMock()
        mock_account.address = TEST_ACCOUNT_ADDRESS
        mock_connector.account = mock_account
        mock_erc721_contract.functions.balanceOf.return_value.call.return_value = 3
        balance = erc721_helper.balance_of(TEST_NFT_ADDRESS)
        assert balance == 3
        mock_erc721_contract.functions.balanceOf.assert_called_once_with(TEST_ACCOUNT_ADDRESS)
        mock_erc721_contract.functions.balanceOf(TEST_ACCOUNT_ADDRESS).call.assert_called_once_with()
        assert balance == 3

    def test_balance_of_no_address_no_account(self, erc721_helper, mock_connector):
        """Test balance_of raises ValueError when no address or loaded account is available."""
        mock_connector.account = None
        with pytest.raises(ValueError, match="No account loaded and no address provided"):
            erc721_helper.balance_of(TEST_NFT_ADDRESS)

class TestERC721HelperOwnerOf:
    def test_owner_of(self, erc721_helper, mock_erc721_contract):
        """Test owner_of returns the correct owner for a token ID."""
        mock_erc721_contract.functions.ownerOf.return_value.call.return_value = TEST_OWNER_ADDRESS
        owner = erc721_helper.owner_of(TEST_NFT_ADDRESS, TEST_TOKEN_ID_1)
        assert owner == TEST_OWNER_ADDRESS
        mock_erc721_contract.functions.ownerOf.assert_called_once_with(TEST_TOKEN_ID_1)
        mock_erc721_contract.functions.ownerOf(TEST_TOKEN_ID_1).call.assert_called_once_with()
        assert owner == TEST_OWNER_ADDRESS

class TestERC721HelperApprove:
    def test_approve_successful(self, erc721_helper, mock_connector, mock_erc721_contract):
        """Test approve successfully builds and sends a transaction."""
        mock_account = MagicMock()
        mock_account.address = TEST_ACCOUNT_ADDRESS
        mock_connector.account = mock_account
        mock_tx_func = MagicMock()
        mock_erc721_contract.functions.approve.return_value = mock_tx_func
        mock_built_tx = {'data': '0x...', 'to': TEST_NFT_ADDRESS}
        mock_tx_func.build_transaction.return_value = mock_built_tx

        tx_hash = erc721_helper.approve(TEST_NFT_ADDRESS, TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1)

        mock_erc721_contract.functions.approve.assert_called_once_with(TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1)
        expected_tx_params = {'from': TEST_ACCOUNT_ADDRESS}
        mock_tx_func.build_transaction.assert_called_once_with(expected_tx_params)
        mock_connector.send_transaction.assert_called_once_with(mock_built_tx)
        assert tx_hash == MOCK_TX_HASH

    def test_approve_with_tx_options(self, erc721_helper, mock_connector, mock_erc721_contract):
        """Test approve with custom transaction options."""
        mock_account = MagicMock()
        mock_account.address = TEST_ACCOUNT_ADDRESS
        mock_connector.account = mock_account
        tx_options = {'gas': 100000, 'gasPrice': Web3.to_wei(10, 'gwei')}
        mock_tx_func = MagicMock()
        mock_erc721_contract.functions.approve.return_value = mock_tx_func
        mock_built_tx = {'data': '0x...', 'to': TEST_NFT_ADDRESS}
        mock_tx_func.build_transaction.return_value = mock_built_tx

        erc721_helper.approve(TEST_NFT_ADDRESS, TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1, tx_options=tx_options)
        
        expected_tx_params = {'from': TEST_ACCOUNT_ADDRESS, **tx_options}
        mock_tx_func.build_transaction.assert_called_once_with(expected_tx_params)

    def test_approve_no_account(self, erc721_helper, mock_connector):
        """Test approve raises ValueError if no account is loaded."""
        mock_connector.account = None
        with pytest.raises(ValueError, match="No account loaded for transaction"):
            erc721_helper.approve(TEST_NFT_ADDRESS, TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1)

class TestERC721HelperGetApproved:
    def test_get_approved(self, erc721_helper, mock_erc721_contract):
        """Test get_approved returns the approved address for a token."""
        mock_erc721_contract.functions.getApproved.return_value.call.return_value = TEST_OPERATOR_ADDRESS
        approved_address = erc721_helper.get_approved(TEST_NFT_ADDRESS, TEST_TOKEN_ID_1)
        assert approved_address == TEST_OPERATOR_ADDRESS
        mock_erc721_contract.functions.getApproved.assert_called_once_with(TEST_TOKEN_ID_1)
        mock_erc721_contract.functions.getApproved(TEST_TOKEN_ID_1).call.assert_called_once_with()
        assert approved_address == TEST_OPERATOR_ADDRESS

    def test_get_approved_no_approval(self, erc721_helper, mock_erc721_contract):
        """Test get_approved returns the zero address if no specific approval."""
        zero_address = Web3.to_checksum_address("0x0000000000000000000000000000000000000000")
        mock_erc721_contract.functions.getApproved.return_value.call.return_value = zero_address
        approved_address = erc721_helper.get_approved(TEST_NFT_ADDRESS, TEST_TOKEN_ID_2)
        assert approved_address == zero_address

class TestERC721HelperSetApprovalForAll:
    def test_set_approval_for_all_successful(self, erc721_helper, mock_connector, mock_erc721_contract):
        """Test set_approval_for_all successfully builds and sends a transaction."""
        mock_account = MagicMock()
        mock_account.address = TEST_ACCOUNT_ADDRESS
        mock_connector.account = mock_account
        mock_tx_func = MagicMock()
        mock_erc721_contract.functions.setApprovalForAll.return_value = mock_tx_func
        mock_built_tx = {'data': '0x...', 'to': TEST_NFT_ADDRESS}
        mock_tx_func.build_transaction.return_value = mock_built_tx

        tx_hash = erc721_helper.set_approval_for_all(TEST_NFT_ADDRESS, TEST_OPERATOR_ADDRESS, True)

        mock_erc721_contract.functions.setApprovalForAll.assert_called_once_with(TEST_OPERATOR_ADDRESS, True)
        expected_tx_params = {'from': TEST_ACCOUNT_ADDRESS}
        mock_tx_func.build_transaction.assert_called_once_with(expected_tx_params)
        mock_connector.send_transaction.assert_called_once_with(mock_built_tx)
        assert tx_hash == MOCK_TX_HASH

    def test_set_approval_for_all_no_account(self, erc721_helper, mock_connector):
        """Test set_approval_for_all raises ValueError if no account is loaded."""
        mock_connector.account = None
        with pytest.raises(ValueError, match="No account loaded for transaction"):
            erc721_helper.set_approval_for_all(TEST_NFT_ADDRESS, TEST_OPERATOR_ADDRESS, True)

class TestERC721HelperIsApprovedForAll:
    def test_is_approved_for_all_true(self, erc721_helper, mock_erc721_contract):
        """Test is_approved_for_all returns True when an operator is approved."""
        mock_erc721_contract.functions.isApprovedForAll.return_value.call.return_value = True
        is_approved = erc721_helper.is_approved_for_all(TEST_NFT_ADDRESS, TEST_OWNER_ADDRESS, TEST_OPERATOR_ADDRESS)
        assert is_approved is True
        mock_erc721_contract.functions.isApprovedForAll.assert_called_once_with(TEST_OWNER_ADDRESS, TEST_OPERATOR_ADDRESS)
        mock_erc721_contract.functions.isApprovedForAll(TEST_OWNER_ADDRESS, TEST_OPERATOR_ADDRESS).call.assert_called_once_with()
        assert is_approved is True

    def test_is_approved_for_all_false(self, erc721_helper, mock_erc721_contract):
        """Test is_approved_for_all returns False when an operator is not approved."""
        mock_erc721_contract.functions.isApprovedForAll.return_value.call.return_value = False
        is_approved = erc721_helper.is_approved_for_all(TEST_NFT_ADDRESS, TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS)
        assert is_approved is False

class TestERC721HelperTransferFrom:
    def test_transfer_from_successful(self, erc721_helper, mock_connector, mock_erc721_contract):
        """Test transfer_from successfully builds and sends a transaction."""
        mock_account = MagicMock()
        mock_account.address = TEST_ACCOUNT_ADDRESS # This account is the sender of the tx
        mock_connector.account = mock_account
        mock_tx_func = MagicMock()
        mock_erc721_contract.functions.transferFrom.return_value = mock_tx_func
        mock_built_tx = {'data': '0x...', 'to': TEST_NFT_ADDRESS}
        mock_tx_func.build_transaction.return_value = mock_built_tx

        tx_hash = erc721_helper.transfer_from(TEST_NFT_ADDRESS, TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1)

        mock_erc721_contract.functions.transferFrom.assert_called_once_with(TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1)
        expected_tx_params = {'from': TEST_ACCOUNT_ADDRESS}
        mock_tx_func.build_transaction.assert_called_once_with(expected_tx_params)
        mock_connector.send_transaction.assert_called_once_with(mock_built_tx)
        assert tx_hash == MOCK_TX_HASH

    def test_transfer_from_no_account(self, erc721_helper, mock_connector):
        """Test transfer_from raises ValueError if no account is loaded."""
        mock_connector.account = None
        with pytest.raises(ValueError, match="No account loaded for transaction"):
            erc721_helper.transfer_from(TEST_NFT_ADDRESS, TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1)

class TestERC721HelperSafeTransferFrom:
    def test_safe_transfer_from_successful(self, erc721_helper, mock_connector, mock_erc721_contract):
        """Test safe_transfer_from (no data) successfully builds and sends a transaction."""
        mock_account = MagicMock()
        mock_account.address = TEST_ACCOUNT_ADDRESS
        mock_connector.account = mock_account
        mock_tx_func = MagicMock()
        mock_erc721_contract.functions.safeTransferFrom.return_value = mock_tx_func
        mock_built_tx = {'data': '0x...', 'to': TEST_NFT_ADDRESS}
        mock_tx_func.build_transaction.return_value = mock_built_tx

        tx_hash = erc721_helper.safe_transfer_from(TEST_NFT_ADDRESS, TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1)

        mock_erc721_contract.functions.safeTransferFrom.assert_called_once_with(TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1)
        expected_tx_params = {'from': TEST_ACCOUNT_ADDRESS}
        mock_tx_func.build_transaction.assert_called_once_with(expected_tx_params)
        mock_connector.send_transaction.assert_called_once_with(mock_built_tx)
        assert tx_hash == MOCK_TX_HASH

    def test_safe_transfer_from_with_data_successful(self, erc721_helper, mock_connector, mock_erc721_contract):
        """Test safe_transfer_from (with data) successfully builds and sends a transaction."""
        mock_account = MagicMock()
        mock_account.address = TEST_ACCOUNT_ADDRESS
        mock_connector.account = mock_account
        test_data = b'\x12\x34'
        mock_tx_func = MagicMock()
        mock_erc721_contract.functions.safeTransferFrom.return_value = mock_tx_func
        mock_built_tx = {'data': '0x...', 'to': TEST_NFT_ADDRESS}
        mock_tx_func.build_transaction.return_value = mock_built_tx

        tx_hash = erc721_helper.safe_transfer_from(TEST_NFT_ADDRESS, TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1, data=test_data)

        mock_erc721_contract.functions.safeTransferFrom.assert_called_once_with(TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1, test_data)
        expected_tx_params = {'from': TEST_ACCOUNT_ADDRESS}
        mock_tx_func.build_transaction.assert_called_once_with(expected_tx_params)
        mock_connector.send_transaction.assert_called_once_with(mock_built_tx)
        assert tx_hash == MOCK_TX_HASH

    def test_safe_transfer_from_no_account(self, erc721_helper, mock_connector):
        """Test safe_transfer_from raises ValueError if no account is loaded."""
        mock_connector.account = None
        with pytest.raises(ValueError, match="No account loaded for transaction"):
            erc721_helper.safe_transfer_from(TEST_NFT_ADDRESS, TEST_OWNER_ADDRESS, TEST_RECIPIENT_ADDRESS, TEST_TOKEN_ID_1)

class TestERC721HelperMetadata:
    def test_name(self, erc721_helper, mock_erc721_contract):
        """Test name returns the correct collection name."""
        mock_erc721_contract.functions.name.return_value.call.return_value = "TestNFT"
        name = erc721_helper.name(TEST_NFT_ADDRESS)
        assert name == "TestNFT"
        mock_erc721_contract.functions.name.assert_called_once_with()
        mock_erc721_contract.functions.name().call.assert_called_once_with()
        assert name == "TestNFT"

    def test_symbol(self, erc721_helper, mock_erc721_contract):
        """Test symbol returns the correct collection symbol."""
        mock_erc721_contract.functions.symbol.return_value.call.return_value = "TNFT"
        symbol = erc721_helper.symbol(TEST_NFT_ADDRESS)
        assert symbol == "TNFT"
        mock_erc721_contract.functions.symbol.assert_called_once_with()
        mock_erc721_contract.functions.symbol().call.assert_called_once_with()
        assert symbol == "TNFT"

    def test_token_uri(self, erc721_helper, mock_erc721_contract):
        """Test token_uri returns the correct URI for a token ID."""
        mock_uri = "https://example.com/nft/1"
        mock_erc721_contract.functions.tokenURI.return_value.call.return_value = mock_uri
        uri = erc721_helper.token_uri(TEST_NFT_ADDRESS, TEST_TOKEN_ID_1)
        assert uri == mock_uri
        mock_erc721_contract.functions.tokenURI.assert_called_once_with(TEST_TOKEN_ID_1)
        mock_erc721_contract.functions.tokenURI(TEST_TOKEN_ID_1).call.assert_called_once_with()
        assert uri == mock_uri
