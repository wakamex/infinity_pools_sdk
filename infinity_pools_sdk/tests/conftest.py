"""Pytest configuration for Infinity Pools SDK tests."""

import logging
import os
from pathlib import Path
from typing import cast

import pytest
from web3 import Web3
from web3.types import RPCEndpoint  # For RPCEndpoint casting

from infinity_pools_sdk.abis import PERIPHERY_ABI
from infinity_pools_sdk.constants import BaseTokens, ContractAddresses
from infinity_pools_sdk.core.connector import InfinityPoolsConnector
from infinity_pools_sdk.sdk import InfinityPoolsSDK
from infinity_pools_sdk.tests.virtual_testnet_manager import TenderlyVirtualTestNetManager
from infinity_pools_sdk.utils.env_loader import load_env_vars

# Setup basic logging for the test session
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s")
logger = logging.getLogger(__name__)


def pytest_sessionstart(session):
    """Configure logging at the start of the test session.

    Ensures that logs are visible, especially for setup and teardown phases.
    """
    logging.getLogger().setLevel(logging.INFO)  # Ensure root logger is at INFO
    # The following options help ensure logs are visible, especially for setup/teardown.
    # Pytest's default capturing can sometimes hide logs from fixtures if not configured.
    if hasattr(session.config, 'option'):
        # session.config.option.capture = 'no' # Uncomment if logs are still not showing
        session.config.option.log_cli = True
        session.config.option.log_cli_level = 'INFO'


def load_env_file(env_path):
    """Load environment variables from a .env file.

    Args:
        env_path: Path to the .env file
    """
    if not os.path.exists(env_path):
        logger.warning(f"Env file not found at {env_path}")
        return

    with open(env_path) as f:
        for line_content in f:
            line = line_content.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value
    logger.info(f"Loaded env file from {env_path}")


# Load environment variables from .env file
env_path = "/code/infinitypools/.env"
load_env_file(env_path)

IMPERSONATED_ADDRESS = Web3.to_checksum_address("0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207")


@pytest.fixture(scope="session")
def vtn_manager(request):
    """Manage the lifecycle of a Tenderly Virtual TestNet for the test session."""
    if not request.config.getoption("--run-integration"):
        pytest.skip("Integration tests not enabled. Use --run-integration to run.")

    load_env_vars(target_keys=["TENDERLY_ACCESS_KEY", "TENDERLY_ACCOUNT_SLUG", "TENDERLY_PROJECT_SLUG"])
    access_key = os.getenv("TENDERLY_ACCESS_KEY")
    account_slug = os.getenv("TENDERLY_ACCOUNT_SLUG")
    project_slug = os.getenv("TENDERLY_PROJECT_SLUG")

    if not all([access_key, account_slug, project_slug]):
        pytest.skip("Missing Tenderly credentials (TENDERLY_ACCESS_KEY, TENDERLY_ACCOUNT_SLUG, TENDERLY_PROJECT_SLUG). Skipping integration tests.")

    # Assertions for type checker after skip condition
    assert access_key is not None
    assert account_slug is not None
    assert project_slug is not None

    manager = TenderlyVirtualTestNetManager(access_key=access_key, account_slug=account_slug, project_slug=project_slug)

    logger.info("Creating Virtual TestNet for test session...")
    vnet_details = None
    try:
        vnet_details = manager.create_vnet(
            display_name="InfinityPoolsSDK-Pytest-VNet",
            parent_network_id="8453",  # Base
            vnet_chain_id=84530,  # Custom chain ID for VNet
            enable_sync=True,
        )
        print(f"CONFTES DEBUG: vnet_details received from manager.create_vnet: {vnet_details}") # Explicit print for raw visibility
    except Exception as e:
        print(f"CONFTES EXCEPTION during create_vnet: {type(e).__name__}: {e}") # Explicit print for visibility
        logger.error(f"Exception during vtn_manager.create_vnet: {e}", exc_info=True)
        # Attempt cleanup if manager exists and has details (though unlikely if create_vnet failed catastrophically)
        if manager and manager.created_vnet_details:
            try:
                logger.info(f"Attempting cleanup of partially created VNet: {manager.created_vnet_details.get('id')}")
                manager.delete_vnet()
            except Exception as delete_e:
                logger.error(f"Error during cleanup attempt: {delete_e}", exc_info=True)
        pytest.fail(f"Failed to initialize Tenderly Virtual TestNet due to EXCEPTION: {e}")


    if not vnet_details or not vnet_details.get("admin_rpc_url"):
        # This block will now also catch cases where vnet_details remained None due to an exception handled above
        # or if create_vnet returned successfully but without admin_rpc_url
        logger.error("Failed to create Virtual TestNet or obtain Admin RPC URL. vnet_details: %s", vnet_details)
        if manager and manager.created_vnet_details and (not vnet_details or vnet_details.get('id') != manager.created_vnet_details.get('id')):
            # If create_vnet returned something but it's not what's stored, or if vnet_details is None but something was stored
            logger.info(f"Attempting cleanup of VNet ID from manager state: {manager.created_vnet_details.get('id')}")
            manager.delete_vnet() # Try to delete based on manager's stored state
        elif vnet_details and vnet_details.get('id'):
             # If create_vnet returned details with an ID but it's deemed invalid (e.g. no admin_rpc_url)
            logger.info(f"Attempting cleanup of VNet ID from vnet_details: {vnet_details.get('id')}")
            manager.delete_vnet(vnet_details.get('id'))

        pytest.fail("Failed to initialize Tenderly Virtual TestNet for integration tests. Check logs for details.")

    # If we've reached here, vnet_details should be populated and valid
    if vnet_details: # Added check for robustness and to satisfy linter
        logger.info(f"Virtual TestNet created: ID={vnet_details.get('id')}, Admin RPC={vnet_details.get('admin_rpc_url')}")
    else:
        # This case should ideally be caught by the fail conditions above, but as a safeguard:
        logger.error("Reached post-creation logging but vnet_details is unexpectedly None.")
        pytest.fail("Internal error in vtn_manager fixture: vnet_details is None after creation checks.")

    def finalizer():
        logger.info("Deleting Virtual TestNet...")
        if not manager.delete_vnet():
            logger.error("Failed to delete Virtual TestNet during cleanup.")
        else:
            logger.info("Virtual TestNet deleted successfully.")

    request.addfinalizer(finalizer)
    return manager


@pytest.fixture(scope="session")
def impersonated_account_address():
    return IMPERSONATED_ADDRESS


@pytest.fixture(scope="session")
def impersonated_connector(vtn_manager: TenderlyVirtualTestNetManager, impersonated_account_address: str):
    """Fixture for an InfinityPoolsConnector using a VNet and impersonated account."""
    admin_rpc_url = vtn_manager.get_admin_rpc_url()
    if not admin_rpc_url:
        pytest.fail("Admin RPC URL not available from vtn_manager.")

    # Ensure created_vnet_details is available for type checking, though logic implies it should be
    assert vtn_manager.created_vnet_details is not None

    provider_kwargs = {"timeout": 30}
    admin_w3 = Web3(Web3.HTTPProvider(admin_rpc_url, request_kwargs=provider_kwargs))
    if not admin_w3.is_connected():
        pytest.fail(f"Failed to connect to Admin RPC: {admin_rpc_url}")

    eth_to_fund_wei = admin_w3.to_wei(100, "ether")
    logger.info(f"Funding {impersonated_account_address} with {admin_w3.from_wei(eth_to_fund_wei, 'ether')} ETH on VNet...")
    try:
        admin_w3.provider.make_request(method=cast(RPCEndpoint, "tenderly_setBalance"), params=[[impersonated_account_address], hex(eth_to_fund_wei)])
    except Exception as e:
        pytest.fail(f"Failed to set ETH balance via tenderly_setBalance: {e}")

    tokens_to_fund = {
        BaseTokens.WETH: 1000 * (10**18),
        BaseTokens.USDC: 500000 * (10**6),
        BaseTokens.wstETH: 1000 * (10**18),
        BaseTokens.sUSDe: 1000 * (10**18),
    }

    for token_address_str, amount_wei in tokens_to_fund.items():
        token_address = Web3.to_checksum_address(token_address_str)
        logger.info(f"Funding {impersonated_account_address} with token {token_address} amount {amount_wei} on VNet...")
        try:
            admin_w3.provider.make_request(method=cast(RPCEndpoint, "tenderly_setErc20Balance"), params=[token_address, impersonated_account_address, hex(amount_wei)])
        except Exception as e:
            logger.warning(f"Failed to set ERC20 balance for {token_address}: {e}. Continuing...")

    public_rpc_url_from_details = None
    if vtn_manager.created_vnet_details:  # Check if details exist before calling .get()
        public_rpc_url_from_details = vtn_manager.created_vnet_details.get("public_rpc_url")
    
    connector_rpc_url = public_rpc_url_from_details # connector_rpc_url can be None here
    if not connector_rpc_url or connector_rpc_url == admin_rpc_url:
        connector_rpc_url = admin_rpc_url
    logger.info(f"Using RPC URL for connector: {connector_rpc_url}")

    headers = {"X-Tenderly-Force-Root-Account": impersonated_account_address}

    return InfinityPoolsConnector(rpc_url=connector_rpc_url, network="base", headers=headers)


@pytest.fixture(scope="session")
def sdk(impersonated_connector):
    """Fixture for the InfinityPoolsSDK."""
    proxy_address = Web3.to_checksum_address(ContractAddresses.BASE["proxy"])
    return InfinityPoolsSDK(connector=impersonated_connector, periphery_address=proxy_address, periphery_abi_override=PERIPHERY_ABI)


@pytest.fixture(scope="session")
def test_token0_address():
    """Fixture for test token 0 address (e.g., wstETH)."""
    return Web3.to_checksum_address(BaseTokens.wstETH)  # Using BaseTokens constant


@pytest.fixture(scope="session")
def test_token1_address():
    """Fixture for test token 1 address (e.g., sUSDe)."""
    return Web3.to_checksum_address(BaseTokens.sUSDe)  # Using BaseTokens constant


def pytest_addoption(parser):
    """Add command-line options to pytest."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require a local blockchain",
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as requiring a local blockchain")


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --run-integration is specified."""
    if not config.getoption("--run-integration"):
        skip_integration = pytest.mark.skip(reason="Need --run-integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
