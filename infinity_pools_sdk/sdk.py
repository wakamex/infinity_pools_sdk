# infinity_pools_sdk/sdk.py

from decimal import Decimal
from typing import Any, Dict, Optional

from web3.contract import Contract  # For type hinting self.periphery_contract

from .core.connector import InfinityPoolsConnector
from .erc.erc20 import ERC20Helper
from .models.data_models import AddLiquidityParams

# from ..constants import PERIPHERY_ABI, PERIPHERY_CONTRACT_ADDRESS # To be defined/used later

MINIMAL_PERIPHERY_ABI = [
    {
        "name": "addLiquidity",
        "type": "function",
        "stateMutability": "nonpayable", # Assuming non-payable based on function's nature
        "inputs": [
            {
                "name": "params",
                "type": "tuple",
                "components": [
                    {"name": "token0", "type": "address"},
                    {"name": "token1", "type": "address"},
                    {"name": "fee", "type": "uint24"},
                    {"name": "tickLower", "type": "int24"},
                    {"name": "tickUpper", "type": "int24"},
                    {"name": "amount0Desired", "type": "uint256"},
                    {"name": "amount1Desired", "type": "uint256"},
                    {"name": "amount0Min", "type": "uint256"},
                    {"name": "amount1Min", "type": "uint256"},
                    {"name": "recipient", "type": "address"},
                    {"name": "deadline", "type": "uint256"},
                    {"name": "earnEra", "type": "uint256"}
                ]
            }
        ],
        "outputs": [] # Assuming no direct return value needed for SDK interaction beyond tx receipt
    }
]


class InfinityPoolsSDK:
    """Main SDK class for interacting with the Infinity Pools protocol."""

    def __init__(self, connector: InfinityPoolsConnector, periphery_contract_address: Optional[str] = None):
        """Initialize the SDK with a contract connector and periphery contract address.

        Args:
            connector: An instance of InfinityPoolsConnector.
            periphery_contract_address: Address of the InfinityPoolsPeriphery contract.
        """
        self.connector = connector
        self.w3 = connector.w3
        self.erc20_helper = ERC20Helper(connector)
        self._periphery_contract_address: Optional[str] = periphery_contract_address
        self.periphery_contract: Optional[Contract] = None

        # TODO: Define PERIPHERY_ABI, likely in constants.py
        # For now, we'll defer actual contract loading or make it on-demand in methods.
        # if self._periphery_contract_address and PERIPHERY_ABI:
        #     self.periphery_contract = self.connector.load_contract(
        #         PERIPHERY_ABI, self._periphery_contract_address
        #     )

    def _get_loaded_periphery_contract(self) -> Contract:
        """Ensure the periphery contract is loaded and return it."""
        if self.periphery_contract is None:
            if not self._periphery_contract_address:
                raise ValueError("Periphery contract address not set.")
            self.periphery_contract = self.connector.load_contract(
                 MINIMAL_PERIPHERY_ABI, self._periphery_contract_address
            )
            if self.periphery_contract is None: # Should not happen if load_contract works or raises
                 raise ConnectionError("Failed to load periphery contract.")
        return self.periphery_contract

    def add_liquidity(
        self,
        token0_address: str,
        token1_address: str,
        fee: int,
        tick_lower: int,
        tick_upper: int,
        amount0_desired: Decimal,
        amount1_desired: Decimal,
        amount0_min: Decimal,
        amount1_min: Decimal,
        recipient: str,
        deadline: int,
        earn_era: int = 0,
        token0_decimals: Optional[int] = None,
        token1_decimals: Optional[int] = None,
        auto_approve: bool = True
    ) -> Dict[str, Any]:
        """Add liquidity to an Infinity Pool.

        Args:
            token0_address: Address of the first token.
            token1_address: Address of the second token.
            fee: The fee tier of the pool.
            tick_lower: The lower tick of the liquidity range.
            tick_upper: The upper tick of the liquidity range.
            amount0_desired: Desired amount of token0 to add.
            amount1_desired: Desired amount of token1 to add.
            amount0_min: Minimum amount of token0 to add (for slippage protection).
            amount1_min: Minimum amount of token1 to add (for slippage protection).
            recipient: Address to receive the position NFT.
            deadline: Unix timestamp for transaction deadline.
            earn_era: The era from which the liquidity should start earning fees.
            token0_decimals: Decimals for token0. If None, will be fetched.
            token1_decimals: Decimals for token1. If None, will be fetched.
            auto_approve: If True, SDK will attempt to approve necessary token amounts.

        Returns:
            A dictionary containing transaction details (e.g., hash, receipt).
        """
        if not self.connector.account:
            raise ValueError("No account loaded in InfinityPoolsConnector. Cannot send transactions.")

        if not self._periphery_contract_address:
            raise ValueError("Periphery contract address not configured for the SDK.")

        # Fetch token decimals if not provided
        _token0_decimals = token0_decimals if token0_decimals is not None else self.erc20_helper.decimals(token0_address)
        _token1_decimals = token1_decimals if token1_decimals is not None else self.erc20_helper.decimals(token1_address)

        # Token Approvals
        if auto_approve:
            self.erc20_helper.ensure_allowance(
                token_address=token0_address,
                spender_address=self._periphery_contract_address,
                required_amount_decimal=amount0_desired,
                owner_address=self.connector.account.address
            )
            self.erc20_helper.ensure_allowance(
                token_address=token1_address,
                spender_address=self._periphery_contract_address,
                required_amount_decimal=amount1_desired,
                owner_address=self.connector.account.address
            )

        params = AddLiquidityParams(
            token0=token0_address,
            token1=token1_address,
            fee=fee,
            tickLower=tick_lower,
            tickUpper=tick_upper,
            amount0Desired=amount0_desired,
            amount1Desired=amount1_desired,
            amount0Min=amount0_min,
            amount1Min=amount1_min,
            recipient=recipient,
            deadline=deadline,
            earnEra=earn_era
        )

        contract_call_params = params.to_contract_tuple(_token0_decimals, _token1_decimals)

        periphery_contract = self._get_loaded_periphery_contract()
        tx_params = {'from': self.connector.account.address}
        # Add other necessary tx_params like gas, gasPrice, or nonce if not handled by connector

        transaction = periphery_contract.functions.addLiquidity(contract_call_params).build_transaction(tx_params)
        
        tx_hash = self.connector.send_transaction(transaction)
        receipt = self.connector.wait_for_transaction(tx_hash)
        
        return {'tx_hash': tx_hash.hex(), 'receipt': receipt}

    # Other high-level methods like remove_liquidity, swap_exact_input, etc., will follow.
