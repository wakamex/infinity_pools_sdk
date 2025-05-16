#!/usr/bin/env python3
"""Tests for the InfinityPoolsSDK class."""

import unittest
from unittest.mock import MagicMock, patch, call
from decimal import Decimal

import pytest

from infinity_pools_sdk.sdk import InfinityPoolsSDK, MINIMAL_PERIPHERY_ABI
from infinity_pools_sdk.core.connector import InfinityPoolsConnector
from infinity_pools_sdk.erc.erc20 import ERC20Helper
from infinity_pools_sdk.models.data_models import AddLiquidityParams


@pytest.fixture
def mock_connector():
    """Fixture for a mocked InfinityPoolsConnector."""
    connector = MagicMock(spec=InfinityPoolsConnector)
    connector.w3 = MagicMock()
    connector.account = MagicMock()
    connector.account.address = "0xTestAccountAddress"
    connector.load_contract = MagicMock()
    connector.send_transaction = MagicMock(return_value=b'tx_hash_bytes')
    connector.wait_for_transaction = MagicMock(return_value={'status': 1, 'blockNumber': 123})
    return connector

@pytest.fixture
def mock_erc20_helper():
    """Fixture for a mocked ERC20Helper."""
    helper = MagicMock(spec=ERC20Helper)
    helper.decimals = MagicMock(return_value=18)
    helper.ensure_allowance = MagicMock()
    return helper


class TestInfinityPoolsSDKAddLiquidity:
    """Test suite for the InfinityPoolsSDK.add_liquidity method."""

    PERIPHERY_ADDRESS = "0xPeripheryContractAddress"

    def test_add_liquidity_success_with_auto_approve(self, mock_connector, mock_erc20_helper):
        """Test add_liquidity successfully with auto_approve=True."""
        # Arrange
        sdk = InfinityPoolsSDK(connector=mock_connector, periphery_contract_address=self.PERIPHERY_ADDRESS)
        
        # Patch the ERC20Helper instantiation within the SDK
        with patch('infinity_pools_sdk.sdk.ERC20Helper', return_value=mock_erc20_helper) as PatchedERC20Helper:
            sdk = InfinityPoolsSDK(connector=mock_connector, periphery_contract_address=self.PERIPHERY_ADDRESS)
            PatchedERC20Helper.assert_called_once_with(mock_connector)

            mock_contract = MagicMock()
            mock_connector.load_contract.return_value = mock_contract

            token0_addr = "0xToken0Address"
            token1_addr = "0xToken1Address"
            amount0_desired = Decimal("100")
            amount1_desired = Decimal("200")

            add_liquidity_args = {
                'token0_address': token0_addr,
                'token1_address': token1_addr,
                'fee': 3000,
                'tick_lower': -100,
                'tick_upper': 100,
                'amount0_desired': amount0_desired,
                'amount1_desired': amount1_desired,
                'amount0_min': Decimal("99"),
                'amount1_min': Decimal("198"),
                'recipient': "0xRecipientAddress",
                'deadline': 1234567890,
                'earn_era': 1,
                'auto_approve': True
            }

            # Act
            result = sdk.add_liquidity(**add_liquidity_args)

            # Assert
            # Check ERC20Helper calls
            mock_erc20_helper.decimals.assert_has_calls([
                call(token0_addr),
                call(token1_addr)
            ], any_order=True)
            mock_erc20_helper.ensure_allowance.assert_has_calls([
                call(token_address=token0_addr, spender_address=self.PERIPHERY_ADDRESS, required_amount_decimal=amount0_desired, owner_address=mock_connector.account.address),
                call(token_address=token1_addr, spender_address=self.PERIPHERY_ADDRESS, required_amount_decimal=amount1_desired, owner_address=mock_connector.account.address)
            ], any_order=True)

            # Check contract loading
            mock_connector.load_contract.assert_called_once_with(MINIMAL_PERIPHERY_ABI, self.PERIPHERY_ADDRESS)
            
            # Check contract function call building
            # Expected contract_call_params need to be constructed based on AddLiquidityParams.to_contract_tuple
            # This requires knowing the decimals used (mocked as 18 here)
            expected_params_obj = AddLiquidityParams(
                token0=token0_addr, token1=token1_addr, fee=3000, tickLower=-100, tickUpper=100,
                amount0Desired=amount0_desired, amount1Desired=amount1_desired,
                amount0Min=Decimal("99"), amount1Min=Decimal("198"),
                recipient="0xRecipientAddress", deadline=1234567890, earnEra=1
            )
            expected_contract_tuple = expected_params_obj.to_contract_tuple(18, 18)
            
            mock_contract.functions.addLiquidity.assert_called_once_with(expected_contract_tuple)
            mock_contract.functions.addLiquidity(expected_contract_tuple).build_transaction.assert_called_once_with({'from': mock_connector.account.address})

            # Check transaction sending
            mock_connector.send_transaction.assert_called_once()
            mock_connector.wait_for_transaction.assert_called_once_with(b'tx_hash_bytes')

            # Check result
            assert result == {'tx_hash': '74785f686173685f6279746573', 'receipt': {'status': 1, 'blockNumber': 123}}

    # TODO: Add more tests:
    # - auto_approve = False
    # - token decimals provided
    # - connector.account is None
    # - periphery_contract_address is None
    # - ERC20Helper.decimals raises error
    # - ERC20Helper.ensure_allowance raises error
    # - connector.load_contract returns None or raises error
    # - contract interaction (build, send, wait) raises error
