# infinity_pools_sdk/sdk.py

# Standard library imports
import time
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Union

# Third-party imports
from eth_typing import ChecksumAddress
from web3.contract import Contract

# Local application/library specific imports
from .abis import PERIPHERY_ABI
from .core.connector import InfinityPoolsConnector
from .erc.erc20 import ERC20Helper
from .models.data_models import (
    AddLiquidityParams,
    PositionInfo,
    PositionType,
    RemoveLiquidityParams,
)

MAX_UINT128 = (1 << 128) - 1


# Helper dataclass for decoded token ID components
@dataclass
class _DecodedTokenIdComponents:
    position_type: PositionType
    pool_address: str
    lp_or_swapper_number: int


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

        self.periphery_contract: Contract = self.connector.w3.eth.contract(address=self.periphery_address, abi=current_abi)

    @property
    def _active_address(self) -> ChecksumAddress:
        """Returns the checksummed address to be used for transactions, prioritizing loaded account over impersonation."""
        address_to_use = None
        if self.connector.account:
            # LocalAccount.address should already be checksummed
            address_to_use = self.connector.account.address
        elif self.connector.impersonated_address:
            address_to_use = self.connector.impersonated_address

        if not address_to_use:
            # This case should ideally not be reached if the initial checks in methods are correct.
            raise ValueError("SDK Error: Neither account nor impersonated address is available.")

        # Ensure address is checksummed. Redundant if coming from LocalAccount, but safe.
        return self.connector.w3.to_checksum_address(address_to_use)

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
        use_vault_deposit: bool,
        tick_lower: int,  # The lower tick boundary for the liquidity position.
        tick_upper: int,  # The upper tick boundary for the liquidity position.
        amount0_desired: Decimal,
        amount1_desired: Decimal,
        amount0_min: Decimal,
        amount1_min: Decimal,
        # Parameters like fee, recipient, deadline, earn_era are not part of the ABI's AddLiquidityParams struct
        # for this specific contract function. Fee is typically implicit in the pool context (token0/token1/tick_spacing).
        # Recipient of LP NFT defaults to msg.sender (self._active_address).
        token0_decimals: Optional[int] = None,
        token1_decimals: Optional[int] = None,
        auto_approve: bool = True,
        transaction_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add liquidity to an Infinity Pool based on the IInfinityPoolsPeriphery.AddLiquidityParams struct.

        Args:
            token0_address: Address of the first token.
            token1_address: Address of the second token.
            use_vault_deposit: Whether to use funds from the vault.
            tick_lower: The lower tick boundary for the liquidity position.
            tick_upper: The upper tick boundary for the liquidity position.
            amount0_desired: Desired amount of token0 to add.
            amount1_desired: Desired amount of token1 to add.
            amount0_min: Minimum amount of token0 to add (for slippage protection).
            amount1_min: Minimum amount of token1 to add (for slippage protection).
            token0_decimals: Decimals for token0. If None, will be fetched.
            token1_decimals: Decimals for token1. If None, will be fetched.
            auto_approve: If True, SDK will attempt to approve necessary token amounts.
            transaction_overrides: Optional transaction overrides.

        Returns:
            A dictionary containing transaction details (e.g., hash, receipt).
        """
        if not self.connector.account and not self.connector.impersonated_address:
            raise ValueError("No account loaded and no impersonation address configured in InfinityPoolsConnector. Cannot send transactions.")

        if not self.periphery_contract.address:  # Check if address is available on the contract object
            raise ValueError("Periphery contract address not available.")

        # Fetch token decimals if not provided
        token0_helper = self._get_erc20_helper()
        token1_helper = self._get_erc20_helper()
        _token0_decimals = token0_decimals if token0_decimals is not None else token0_helper.decimals(token0_address)
        _token1_decimals = token1_decimals if token1_decimals is not None else token1_helper.decimals(token1_address)

        # Token Approvals
        if auto_approve:
            token0_helper.ensure_allowance(token_address=token0_address, spender_address=self.periphery_contract.address, required_amount_decimal=amount0_desired, owner_address=self._active_address)
            token1_helper.ensure_allowance(token_address=token1_address, spender_address=self.periphery_contract.address, required_amount_decimal=amount1_desired, owner_address=self._active_address)

        # Convert decimal amounts to wei
        amount0_desired_wei = int(amount0_desired * (Decimal("10") ** _token0_decimals))
        amount1_desired_wei = int(amount1_desired * (Decimal("10") ** _token1_decimals))
        amount0_min_wei = int(amount0_min * (Decimal("10") ** _token0_decimals))
        amount1_min_wei = int(amount1_min * (Decimal("10") ** _token1_decimals))

        params = AddLiquidityParams(
            token0=token0_address,
            token1=token1_address,
            useVaultDeposit=use_vault_deposit,
            startEdge=tick_lower,
            stopEdge=tick_upper,
            amount0Desired=amount0_desired,
            amount1Desired=amount1_desired,
            amount0Min=amount0_min,
            amount1Min=amount1_min,
        )

        contract_call_params = params.to_contract_tuple(_token0_decimals, _token1_decimals)

        periphery_contract = self.periphery_contract
        # Set up transaction parameters
        tx_params = {
            "from": self._active_address,
            "gas": 1000000,  # Default gas limit
        }

        # Add nonce if not on a local network
        if getattr(self.connector, "network_type", None) != "local" and getattr(self.connector.w3.eth, "chain_id", None) != 1337:
            tx_params["nonce"] = self.connector.w3.eth.get_transaction_count(self._active_address)

        # Apply any transaction overrides
        if transaction_overrides:
            tx_params.update(transaction_overrides)

        transaction = periphery_contract.functions.addLiquidity(contract_call_params).build_transaction(tx_params)

        tx_hash = self.connector.send_transaction(transaction)
        receipt = self.connector.wait_for_transaction(tx_hash)

        return {"tx_hash": tx_hash, "receipt": receipt}  # tx_hash is already a hex string from connector.send_transaction

    def get_positions(
        self, owner_address: Optional[str] = None, pool_address: Optional[str] = None, from_block: Optional[Union[int, str]] = "earliest", to_block: Optional[Union[int, str]] = "latest"
    ) -> List[PositionInfo]:
        """Get all positions owned by the specified address by querying Transfer events.

        Args:
            owner_address: The address to check. If None, uses the connected account address.
            pool_address: Optional filter to return positions only for this pool.
            from_block: The block number (or 'earliest') from which to start scanning for events.
            to_block: The block number (or 'latest') up to which to scan for events.

        Returns:
            List[PositionInfo]: List of position details.
        """
        if owner_address is None:
            if self.connector.account:
                owner_address = self.connector.account.address
            else:
                raise ValueError("owner_address must be provided if no account is connected.")

        if not self.connector.w3.is_address(owner_address):
            raise ValueError(f"Invalid owner_address: {owner_address}")

        if pool_address and not self.connector.w3.is_address(pool_address):
            raise ValueError(f"Invalid pool_address: {pool_address}")

        periphery_contract = self.periphery_contract
        currently_owned_token_ids: Set[int] = set()
        position_details: List[PositionInfo] = []

        try:
            # Get all tokens ever transferred to the owner_address
            transfer_to_event_filter = periphery_contract.events.Transfer.create_filter(from_block=from_block, toBlock=to_block, argument_filters={"to": owner_address})
            events_to_owner = transfer_to_event_filter.get_all_entries()
            for event in events_to_owner:
                currently_owned_token_ids.add(event.args.tokenId)
            if hasattr(transfer_to_event_filter, "filter_id") and transfer_to_event_filter.filter_id is not None:
                self.connector.w3.eth.uninstall_filter(transfer_to_event_filter.filter_id)
            print(f"Found {len(events_to_owner)} Transfer(to) events. {len(currently_owned_token_ids)} unique token IDs potentially received by {owner_address}.")

            # Get all tokens ever transferred from the owner_address
            transfer_from_event_filter = periphery_contract.events.Transfer.create_filter(from_block=from_block, toBlock=to_block, argument_filters={"from": owner_address})
            events_from_owner = transfer_from_event_filter.get_all_entries()
            tokens_transferred_away = 0
            for event in events_from_owner:
                if event.args.tokenId in currently_owned_token_ids:
                    currently_owned_token_ids.remove(event.args.tokenId)
                    tokens_transferred_away += 1
            if hasattr(transfer_from_event_filter, "filter_id") and transfer_from_event_filter.filter_id is not None:
                self.connector.w3.eth.uninstall_filter(transfer_from_event_filter.filter_id)
            print(f"Found {len(events_from_owner)} Transfer(from) events. {tokens_transferred_away} tokens transferred away. Net owned token IDs: {len(currently_owned_token_ids)}.")

        except Exception as e:
            print(f"Error querying Transfer events for {owner_address}: {e}")
            return []

        for token_id in currently_owned_token_ids:
            try:
                decoded_info = self._decode_token_id_locally(token_id)

                if not decoded_info or not hasattr(decoded_info, "pool_address") or not hasattr(decoded_info, "position_type"):
                    print(f"Warning: Skipping token ID {token_id} due to incomplete decoded info from _decode_token_id_locally.")
                    continue

                if pool_address and decoded_info.pool_address.lower() != pool_address.lower():
                    # print(f"Skipping token ID {token_id} for pool {decoded_info.pool_address}, not matching filter {pool_address}")
                    continue

                actual_token0_symbol = "UNKNOWN_T0"  # Placeholder
                actual_token1_symbol = "UNKNOWN_T1"  # Placeholder

                pi = PositionInfo(
                    token_id=token_id,
                    owner=owner_address,
                    pool_address=decoded_info.pool_address,
                    position_type=decoded_info.position_type,
                    token0=actual_token0_symbol,
                    token1=actual_token1_symbol,
                    lp_number=decoded_info.lp_or_swapper_number if hasattr(decoded_info, "lp_or_swapper_number") and decoded_info.position_type == PositionType.LP else None,
                    swapper_number=decoded_info.lp_or_swapper_number if hasattr(decoded_info, "lp_or_swapper_number") and decoded_info.position_type == PositionType.SWAPPER else None,
                    amount0_total=Decimal(0),  # Placeholder
                    amount1_total=Decimal(0),  # Placeholder
                    fees0_earned=Decimal(0),  # Placeholder
                    fees1_earned=Decimal(0),  # Placeholder
                    amount0_collected=Decimal(0),  # Placeholder
                    amount1_collected=Decimal(0),  # Placeholder
                    liquidity=0,  # Placeholder
                    start_edge=0,  # Placeholder
                    stop_edge=0,  # Placeholder
                    min_price=Decimal(0),  # Placeholder
                    max_price=Decimal(0),  # Placeholder
                )
                position_details.append(pi)

            except NotImplementedError:
                print(f"Skipping token ID {token_id} because '_decode_token_id_locally' is not implemented.")
                continue
            except Exception as e:
                print(f"Could not process token_id {token_id} after event discovery: {e}")
                continue

        print(f"Processed {len(position_details)} positions for address {owner_address}" + (f" in pool {pool_address}" if pool_address else ""))
        return position_details

    def _decode_token_id_locally(self, token_id: int) -> Optional[_DecodedTokenIdComponents]:
        """Decode a token ID into its constituent parts.

        The encoding scheme is expected to be:
        `uint256(uint8(positionType)) << 248 | (uint256(uint160(poolAddress)) << 88) | uint256(lpOrSwapperNumber)`
        where `lpOrSwapperNumber` is `uint88`.

        Args:
            token_id: The token ID to decode.

        Returns:
            A _DecodedTokenIdComponents object containing the position type,
            pool address, and LP/swapper number, or None if decoding fails.
        """
        position_type_int = -1  # Initialize to ensure it's defined for the except block
        try:
            # Extract lp_or_swapper_number (lower 88 bits)
            lp_or_swapper_number_mask = (1 << 88) - 1
            lp_or_swapper_number = token_id & lp_or_swapper_number_mask

            # Extract pool_address (next 160 bits)
            pool_address_shift = 88
            pool_address_mask = (1 << 160) - 1
            pool_address_int = (token_id >> pool_address_shift) & pool_address_mask
            # Ensure it's padded to 40 hex characters (20 bytes)
            pool_address_hex = f"0x{pool_address_int:040x}"
            pool_address = self.connector.w3.to_checksum_address(pool_address_hex)

            # Extract position_type (next 8 bits)
            position_type_shift = 248  # 88 (lp_or_swapper) + 160 (pool_address)
            position_type_mask = (1 << 8) - 1  # uint8
            position_type_int = (token_id >> position_type_shift) & position_type_mask

            position_type = PositionType(position_type_int)

            return _DecodedTokenIdComponents(position_type=position_type, pool_address=pool_address, lp_or_swapper_number=lp_or_swapper_number)
        except ValueError as e:
            # This can happen if position_type_int is not a valid PositionType enum value
            print(f"Error decoding token ID {token_id}: Invalid position type value {position_type_int}. Error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error decoding token ID {token_id}: {e}")
            return None

    def remove_liquidity(
        self,
        token_id: int,
        liquidity_percentage: Decimal = Decimal("1"),  
        recipient: Optional[str] = None,
        deadline: Optional[int] = None,  
        amount0_min: int = 0,  
        amount1_min: int = 0,  
        current_position_liquidity_raw: Optional[int] = None, 
        transaction_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Remove 100% of liquidity and fees from a position using the 'drain' function."""
        if not self.connector.account and not self.connector.impersonated_address:
            raise ValueError("No account loaded and no impersonation address configured for transaction.")

        # 'drain' implies 100% removal, so liquidity_percentage is informational here.
        if liquidity_percentage != Decimal("1"):
            print(f"Warning: 'drain' function removes 100% of liquidity; liquidity_percentage ({liquidity_percentage*100}%) is ignored for the on-chain call.")

        actual_recipient = recipient if recipient else self._active_address

        try:
            print(f"Preparing 'drain' transaction for token ID: {token_id} to recipient: {actual_recipient}")
            
            tx_params = self._prepare_transaction_params(transaction_overrides)
            
            # Prepare the 'drain' function call
            transaction = self.periphery_contract.functions.drain(
                token_id,
                actual_recipient
            ).build_transaction(tx_params)

            # Sign and send the transaction
            print(f"Signing and sending 'drain' transaction for token {token_id}...")
            signed_tx = self.connector.sign_transaction(transaction)
            tx_hash = self.connector.send_raw_transaction(signed_tx.rawTransaction)
            print(f"'drain' transaction sent. Hash: {tx_hash.hex()}. Waiting for receipt...")
            receipt = self.connector.wait_for_transaction_receipt(tx_hash)
            print(f"'drain' transaction mined. Receipt status: {receipt.get('status')}")

            return {"tx_hash": tx_hash.hex(), "receipt": receipt, "status": receipt.get("status")}
            tx_receipt = self.connector.wait_for_transaction(tx_hash)

            return {"tx_hash": tx_hash.hex() if hasattr(tx_hash, "hex") else tx_hash.decode("utf-8") if isinstance(tx_hash, bytes) else tx_hash, "receipt": tx_receipt}

        except Exception as e:
            raise RuntimeError(f"Failed to remove liquidity for token {token_id}: {e}")

    # Other high-level methods like remove_liquidity, swap_exact_input, etc., will follow.
