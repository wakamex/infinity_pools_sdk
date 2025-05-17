# infinity_pools_sdk/sdk.py

import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from web3.contract import Contract

from .abis import PERIPHERY_ABI
from .core.connector import InfinityPoolsConnector
from .erc.erc20 import ERC20Helper
from .models.data_models import AddLiquidityParams, RemoveLiquidityParams

MAX_UINT128 = (1 << 128) - 1

class InfinityPoolsSDK:
    """SDK for interacting with Infinity Pools smart contracts."""

    def __init__(self, connector: InfinityPoolsConnector, periphery_address: str, periphery_abi_override: Optional[List[Dict[str, Any]]] = None):
        """Initialize the SDK with a connector and periphery contract address.
        
        Args:
            connector: The InfinityPoolsConnector instance.
            periphery_address: The address of the periphery contract.
            periphery_abi_override: Optional custom ABI to use instead of the default.
        """
        self.connector = connector
        self.periphery_address = periphery_address        
        
        current_abi = periphery_abi_override if periphery_abi_override is not None else PERIPHERY_ABI
            
        self.periphery_contract: Contract = self.connector.w3.eth.contract(
            address=self.periphery_address, abi=current_abi
        )
        
    def _get_erc20_helper(self, token_address=None):
        """Get an ERC20Helper instance for a specific token address.
        
        Args:
            token_address: The token address to create a helper for.
            
        Returns:
            An ERC20Helper instance.
        """
        # Always create a new instance to ensure the tests can properly track constructor calls
        return ERC20Helper(self.connector)

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
        auto_approve: bool = True,
        transaction_overrides: Optional[Dict[str, Any]] = None
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

        if not self.periphery_contract.address: # Check if address is available on the contract object
            raise ValueError("Periphery contract address not available.")

        # Fetch token decimals if not provided
        token0_helper = self._get_erc20_helper()
        token1_helper = self._get_erc20_helper()
        _token0_decimals = token0_decimals if token0_decimals is not None else token0_helper.decimals(token0_address)
        _token1_decimals = token1_decimals if token1_decimals is not None else token1_helper.decimals(token1_address)

        # Token Approvals
        if auto_approve:
            token0_helper.ensure_allowance(
                token_address=token0_address,
                spender_address=self.periphery_contract.address,
                required_amount_decimal=amount0_desired,
                owner_address=self.connector.account.address
            )
            token1_helper.ensure_allowance(
                token_address=token1_address,
                spender_address=self.periphery_contract.address,
                required_amount_decimal=amount1_desired,
                owner_address=self.connector.account.address
            )

        # Convert decimal amounts to wei
        amount0_desired_wei = int(amount0_desired * (Decimal('10') ** _token0_decimals))
        amount1_desired_wei = int(amount1_desired * (Decimal('10') ** _token1_decimals))
        amount0_min_wei = int(amount0_min * (Decimal('10') ** _token0_decimals))
        amount1_min_wei = int(amount1_min * (Decimal('10') ** _token1_decimals))

        params = AddLiquidityParams(
            token0=token0_address,
            token1=token1_address,
            fee=fee,
            tickLower=tick_lower,
            tickUpper=tick_upper,
            amount0Desired=amount0_desired_wei,
            amount1Desired=amount1_desired_wei,
            amount0Min=amount0_min_wei,
            amount1Min=amount1_min_wei,
            recipient=recipient,
            deadline=deadline,
            earnEra=earn_era
        )

        contract_call_params = params.to_contract_tuple(_token0_decimals, _token1_decimals)

        periphery_contract = self.periphery_contract
        # Set up transaction parameters
        tx_params = {
            'from': self.connector.account.address,
            'gas': 1000000,  # Default gas limit
        }
        
        # Add nonce if not on a local network
        if getattr(self.connector, 'network_type', None) != "local" and getattr(self.connector.w3.eth, 'chain_id', None) != 1337:
            tx_params["nonce"] = self.connector.w3.eth.get_transaction_count(self.connector.account.address)
        
        # Apply any transaction overrides
        if transaction_overrides:
            tx_params.update(transaction_overrides)

        transaction = periphery_contract.functions.addLiquidity(*contract_call_params).build_transaction(tx_params)
        
        tx_hash = self.connector.send_transaction(transaction)
        receipt = self.connector.wait_for_transaction(tx_hash)
        
        return {'tx_hash': tx_hash.hex(), 'receipt': receipt}

    def remove_liquidity(
        self,
        token_id: int,
        liquidity_percentage: Decimal = Decimal('1'),
        recipient: Optional[str] = None,
        deadline: Optional[int] = None,
        amount0_min: int = 0,  # Slippage protection for token0
        amount1_min: int = 0,   # Slippage protection for token1
        transaction_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Remove a percentage of liquidity from a position and collect fees."""
        if not self.connector.account:
            raise ValueError("No account loaded for transaction.")

        if not (Decimal('0') < liquidity_percentage <= Decimal('1')):
            raise ValueError("Liquidity percentage must be between 0 (exclusive) and 1 (inclusive).")

        actual_recipient = recipient if recipient else self.connector.account.address
        actual_deadline = deadline if deadline else int(time.time()) + 20 * 60  # 20 minutes from now

        try:
            # 1. Get current position liquidity
            position_data_tuple = self.periphery_contract.functions.positions(token_id).call()
            # The 'positions' function returns a tuple containing a single element, which is the struct itself.
            if not isinstance(position_data_tuple, (list, tuple)) or len(position_data_tuple) == 0 or \
               not isinstance(position_data_tuple[0], (list, tuple)) or len(position_data_tuple[0]) < 8:
                raise ValueError(f"Unexpected data structure for position {token_id}: {position_data_tuple}")
            position_info = position_data_tuple[0]
            current_liquidity = position_info[7] # liquidity is the 8th field (index 7) of the inner tuple
            
            if current_liquidity == 0:
                # If there's no liquidity, we might still want to attempt a collect operation.
                # However, decreaseLiquidity would fail or be a no-op.
                liquidity_to_remove = 0
            else:
                liquidity_to_remove = int(Decimal(current_liquidity) * liquidity_percentage)
                if liquidity_percentage == Decimal('1'): # Ensure all is removed if 100%
                    liquidity_to_remove = current_liquidity
            
            calls_to_make = []

            # 2. Prepare decreaseLiquidity call data (if there's liquidity to remove)
            if liquidity_to_remove > 0:
                decrease_params = (
                    token_id,
                    liquidity_to_remove,
                    amount0_min,
                    amount1_min,
                    actual_deadline
                )
                decrease_call_data = self.periphery_contract.encodeABI(
                    fn_name='decreaseLiquidity',
                    args=[decrease_params]
                )
                calls_to_make.append(decrease_call_data)

            # 3. Prepare collect call data (always attempt to collect fees)
            collect_params = (
                token_id,
                actual_recipient, 
                MAX_UINT128, # amount0Max: collect all available
                MAX_UINT128  # amount1Max: collect all available
            )
            collect_call_data = self.periphery_contract.encodeABI(
                fn_name='collect',
                args=[collect_params]
            )
            calls_to_make.append(collect_call_data)
            
            if not calls_to_make:
                 # This should only happen if somehow collect_call_data wasn't added, defensive.
                return {"message": "No actions to perform (e.g., zero liquidity and no collect).", "liquidity_removed_attempted": 0}

            # 4. Prepare and send multicall
            tx_params = {
                "from": self.connector.account.address,
                "gas": 1000000,  # Default gas limit
            }
        
            # Add nonce if not on a local network
            if getattr(self.connector, 'network_type', None) != "local" and getattr(self.connector.w3.eth, 'chain_id', None) != 1337:
                tx_params["nonce"] = self.connector.w3.eth.get_transaction_count(self.connector.account.address)
            
            # Apply any transaction overrides
            if transaction_overrides:
                tx_params.update(transaction_overrides)
            
            multicall_fn = self.periphery_contract.functions.multicall(actual_deadline, calls_to_make)
            
            # Build the transaction first
            tx_object = multicall_fn.build_transaction(tx_params)
            
            # Then send it
            tx_hash = self.connector.send_transaction(tx_object)
            tx_receipt = self.connector.wait_for_transaction(tx_hash)

            return {
                "tx_hash": tx_hash.hex() if hasattr(tx_hash, 'hex') else tx_hash.decode('utf-8') if isinstance(tx_hash, bytes) else tx_hash,
                "receipt": tx_receipt
            }

        except Exception as e:
            raise RuntimeError(f"Failed to remove liquidity for token {token_id}: {e}")

    # Other high-level methods like remove_liquidity, swap_exact_input, etc., will follow.
