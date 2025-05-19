import time
import json
from decimal import Decimal

import pytest
from web3 import Web3 # For to_checksum_address
from web3.exceptions import ContractLogicError

from infinity_pools_sdk.sdk import InfinityPoolsSDK
from infinity_pools_sdk.models.data_models import PositionType
from infinity_pools_sdk.constants import BaseTokens, FeeTiers # Import for specific tokens/fees

# Original defaults - will be overridden in the test for specific tokens
_DEFAULT_POOL_FEE = 3000
_DEFAULT_TICK_LOWER = -1000
_DEFAULT_TICK_UPPER = 1000
_DEFAULT_AMOUNT_DESIRED = Decimal('1') # e.g., 1 full token unit

class TestGetPositionsFunctional:

    def test_get_single_position_after_creation(
        self,
        sdk: InfinityPoolsSDK, 
        impersonated_account_address: str,
        # test_token0_address and test_token1_address from fixture are no longer directly used for pool creation params
        # but kept in signature if fixtures depend on them for setup (e.g. ensuring balance for specific test tokens)
        test_token0_address: str, 
        test_token1_address: str
    ):
        """Test retrieving a single position after its creation via add_liquidity."""
        # 1. Define parameters for add_liquidity using known good values
        actual_token0_address = Web3.to_checksum_address(BaseTokens.wstETH)
        actual_token1_address = Web3.to_checksum_address(BaseTokens.sUSDe)
        # fee = FeeTiers.FEE_0_3 # This is 3000, same as DEFAULT_POOL_FEE, sdk.add_liquidity doesn't take fee param directly for pool selection
        
        # For 0.3% fee, tick spacing is typically 60
        tick_spacing = 60 
        num_tick_spaces_range = 10 # Define a range of 10 tick spaces on either side of a hypothetical center
        tick_lower = - (num_tick_spaces_range * tick_spacing) # e.g., -600
        tick_upper = num_tick_spaces_range * tick_spacing    # e.g., 600

        amount_desired = Decimal('0.01') # Use a smaller, more realistic amount

        token0_decimals = sdk._get_erc20_helper().decimals(actual_token0_address)
        token1_decimals = sdk._get_erc20_helper().decimals(actual_token1_address)

        # Approve tokens (sdk.add_liquidity might handle this if auto_approve=True, 
        # but explicit approval can be clearer in tests or if auto_approve is off)
        # For simplicity, assuming auto_approve=True in sdk.add_liquidity or approvals are handled by fixtures/setup
        # sdk._get_erc20_helper().approve(test_token0_address, sdk.periphery_address, amount0_desired_wei, owner_account_address)
        # sdk._get_erc20_helper().approve(test_token1_address, sdk.periphery_address, amount1_desired_wei, owner_account_address)

        # <<< START DEBUG CHECKS >>>
        print(f"\nDEBUG: --- Pre-add_liquidity Checks for Account: {impersonated_account_address} ---")
        erc20_helper = sdk._get_erc20_helper()
        periphery_contract_address = sdk.periphery_contract.address

        # Token0 (wstETH)
        balance0_decimal = erc20_helper.balance_of(actual_token0_address, impersonated_account_address)
        allowance0_decimal = erc20_helper.allowance(actual_token0_address, impersonated_account_address, periphery_contract_address)
        print(f"DEBUG: Token0 ({BaseTokens.wstETH} @ {actual_token0_address})")
        print(f"DEBUG:   Balance: {balance0_decimal} (Desired for tx: {amount_desired})")
        print(f"DEBUG:   Allowance for Spender ({periphery_contract_address}): {allowance0_decimal} (Desired for tx: {amount_desired})")
        if balance0_decimal < amount_desired:
            print(f"WARNING: Insufficient Token0 balance. Has {balance0_decimal}, needs {amount_desired}")

        # Token1 (sUSDe)
        balance1_decimal = erc20_helper.balance_of(actual_token1_address, impersonated_account_address)
        allowance1_decimal = erc20_helper.allowance(actual_token1_address, impersonated_account_address, periphery_contract_address)
        print(f"DEBUG: Token1 ({BaseTokens.sUSDe} @ {actual_token1_address})")
        print(f"DEBUG:   Balance: {balance1_decimal} (Desired for tx: {amount_desired})")
        print(f"DEBUG:   Allowance for Spender ({periphery_contract_address}): {allowance1_decimal} (Desired for tx: {amount_desired})")
        if balance1_decimal < amount_desired:
            print(f"WARNING: Insufficient Token1 balance. Has {balance1_decimal}, needs {amount_desired}")
        
        print(f"DEBUG: Note: sdk.add_liquidity called with auto_approve=True in this test.")
        print(f"DEBUG: --- End Pre-add_liquidity Checks ---\n")
        # <<< END DEBUG CHECKS >>>

        deadline = int(time.time()) + 60 * 20  # 20 minutes from now

        # 2. Add liquidity to create a new position
        tx_receipt = None
        add_liquidity_result = None
        try:
            add_liquidity_result = sdk.add_liquidity(
                token0_address=actual_token0_address,
                token1_address=actual_token1_address,
                use_vault_deposit=False,
                tick_lower=tick_lower,  
                tick_upper=tick_upper,  
                amount0_desired=amount_desired,
                amount1_desired=amount_desired,
                amount0_min=Decimal('0'),
                amount1_min=Decimal('0'),
                token0_decimals=token0_decimals,
                token1_decimals=token1_decimals,
                auto_approve=True
            )
            print(f"Raw add_liquidity_result: {add_liquidity_result}") # DEBUG: Print raw result
            if add_liquidity_result and 'receipt' in add_liquidity_result:
                tx_receipt = add_liquidity_result['receipt']
            else:
                pytest.fail(f"add_liquidity did not return a valid result or receipt. Result: {add_liquidity_result}")

        except ContractLogicError as e:
            print(f"add_liquidity call raised ContractLogicError: {e}")
            pytest.fail(f"add_liquidity call reverted with ContractLogicError: {e}. Raw result if available: {add_liquidity_result}")
        except Exception as e:
            print(f"An unexpected error of type {type(e).__name__} occurred during add_liquidity: {e}")
            pytest.fail(f"Unexpected error of type {type(e).__name__} during add_liquidity: {e}. Raw result if available: {add_liquidity_result}")

        assert tx_receipt is not None, "Transaction receipt was not properly assigned."
        # Check status after receipt is confirmed to be present
        if tx_receipt.get('status') == 0:
            pytest.fail(f"add_liquidity transaction reverted. Receipt: {tx_receipt}")

        # 3. Extract the tokenId from the Transfer event in the transaction receipt
        # The Periphery contract (which is also the ERC721 NFT contract) emits the Transfer event.
        transfer_event_signature_check = sdk.periphery_contract.events.Transfer().abi['name']
        assert transfer_event_signature_check == 'Transfer', "Periphery ABI for Transfer event name might be incorrect"

        emitted_token_id = None
        print(f"Transaction Receipt for Add Liquidity: {tx_receipt}") # DEBUG: Print the receipt

        # Process all Transfer events from the Periphery contract in the transaction receipt
        try:
            processed_transfer_events = sdk.periphery_contract.events.Transfer().process_receipt(tx_receipt)
        except Exception as e:
            print(f"Error processing Transfer events from Periphery contract receipt: {e}")
            processed_transfer_events = []
        
        print(f"Processed Transfer Events from Periphery contract: {processed_transfer_events}") # DEBUG: Print processed events

        for pe in processed_transfer_events:
            # Ensure 'args' exists and contains all necessary fields
            if 'args' in pe and \
               all(key in pe['args'] for key in ['to', 'from', 'tokenId']):
                
                # Check for the mint event: from the zero address to our impersonated account
                if pe['args']['to'].lower() == impersonated_account_address.lower() and \
                   pe['args']['from'].lower() == '0x0000000000000000000000000000000000000000': # Standard ERC721 mint
                    emitted_token_id = pe['args']['tokenId']
                    print(f"Found Transfer event: tokenId={emitted_token_id}, from={pe['args']['from']}, to={pe['args']['to']}")
                    break # Found the relevant mint event
            else:
                print(f"Processed event missing 'args' or required keys: {pe}")
        
        assert emitted_token_id is not None, "Failed to find ERC721 Transfer event (from zero address to recipient) or extract tokenId for the new position."
        print(f"Newly minted position tokenId: {emitted_token_id}")

        # 4. Call get_positions for the owner
        # Give some time for node to sync if tests run too fast
        # time.sleep(1) # Optional: if facing issues with immediate event availability
        
        # Determine from_block. For functional tests against a fork, 'earliest' might be too broad.
        # Using the block of the transaction receipt can narrow it down.
        tx_block_number = tx_receipt['blockNumber']
        
        positions = sdk.get_positions(
            owner_address=impersonated_account_address,
            from_block=tx_block_number -1, # Start from one block before tx to be safe
            to_block=tx_block_number
        )

        # 5. Assertions
        assert len(positions) > 0, "No positions returned for the owner."

        found_position = None
        for pos in positions:
            if pos.token_id == emitted_token_id:
                found_position = pos
                break
        
        assert found_position is not None, f"Newly created position with tokenId {emitted_token_id} not found."
        
        assert found_position.owner.lower() == impersonated_account_address.lower(), "Position owner mismatch."
        assert found_position.position_type == PositionType.LP, "Position type mismatch, expected LP."
        
        # Pool address check might require knowing how test_token0_address, test_token1_address, and fee map to a pool address
        # For now, we'll assert it's a valid address if decoded.
        assert sdk.connector.w3.is_address(found_position.pool_address), "Decoded pool_address is not a valid address."

        # Further assertions based on known token parameters
        # The pool address depends on token0, token1, and fee. We can't easily precompute it here without pool_key logic.
        # However, we can check the decoded position's tokens match what we put in.
        # The get_positions method decodes the tokenId to get pool components.
        assert found_position.token0.lower() == actual_token0_address.lower(), f"Position token0 {found_position.token0} does not match expected {actual_token0_address}"
        assert found_position.token1.lower() == actual_token1_address.lower(), f"Position token1 {found_position.token1} does not match expected {actual_token1_address}"
        # Fee assertion might require decoding from pool_address or tokenId structure if available in Position object.
        # For now, focus on getting the add_liquidity to pass and position to be found.
        
        print(f"Successfully retrieved and verified position: {found_position}")
