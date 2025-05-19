# Infinity Pools SDK - User-Facing Functions To-Do List

Concise overview of planned SDK functions and their status.

## Mapping of UI action to Solidity function

* **Withdraw from closing position**: `collect(token_id, address)`
* **Create a new position**: 

## Liquidity Provider (LP) Position Management

*   **`add_liquidity(params)`**: Add liquidity. Mints LP NFT. - *Status: Implemented*
*   **`remove_liquidity(token_id, percentage)`**: Remove % of liquidity. - *Status: Implemented*
*   **`collect_fees(token_id)`**: Claim fees from LP position. - *Status: Pending*
*   **`tap_position(token_id)`**: Trigger pool-internal actions for LP position. - *Status: Pending*

## Swapper Position Management (Loan/Leverage)

*   **`new_loan_with_swap(params, swap_info)`**: Create Swapper position with initial swap. Mints NFT. - *Status: Pending*
*   **`reset_swapper_position(params, swap_info)`**: Comprehensively update Swapper parameters. - *Status: Pending*
*   **`reflow_swapper_position(params, swap_info)`**: Modify Swapper parameters (optimized). - *Status: Pending*
*   **`close_swapper_position(token_id, swap_info)`**: Close Swapper position. - *Status: Pending*
*   **`batch_actions_on_swappers(params_array, swap_array)`**: Batch operations on Swappers. - *Status: Pending*

## Direct Token Swaps

*   **`swap_exact_input(...)`**: Swap exact input tokens for min output. - *Status: Pending*
*   **`swap_exact_output(...)`**: Swap max input tokens for exact output. - *Status: Pending*

## Flash Loans

*   **`flash_loan(...)`**: Execute a flash loan. - *Status: Pending*

## Token Approvals & Allowance Management

*   **`approve_token(...)`** (ERC20): Approve ERC20 spending. - *Status: Implemented*
*   **`approve_nft_position(...)`** (ERC721): Approve specific NFT management. - *Status: Implemented*
*   **`approve_nft_for_all(...)`** (ERC721): Grant/revoke operator for all NFTs in collection. - *Status: Implemented*

## Vault Interactions

*   **`deposit_to_vault(...)`**: Deposit ERC20s to Vault. - *Status: Pending*
*   **`withdraw_from_vault(...)`**: Withdraw ERC20s from Vault. - *Status: Pending*
*   **`add_collateral_to_vault(...)`**: Add collateral for a pool. - *Status: Pending*
*   **`withdraw_collateral_from_vault(...)`**: Withdraw collateral from a pool. - *Status: Pending*

## Utility / Read-Only Functions

*   **`get_lp_position_details(token_id)`**: Get LP NFT details. - *Status: Partially Implemented*
*   **`get_swapper_position_details(token_id)`**: Get Swapper NFT details. - *Status: Pending*
*   **`get_user_lp_positions(user_address, pool_optional)`**: Get user's LP NFTs. - *Status: Implemented (Off-chain API)*
*   **`get_user_swapper_positions(user_address, pool_optional)`**: Get user's Swapper NFTs. - *Status: Pending/Partially Implemented (Off-chain API)*
*   **`decode_token_id(token_id)`**: Decode structured `tokenId`. - *Status: Pending*
*   **`get_pool_address(token_a, token_b)`**: Get pool address from Factory. - *Status: Pending*

---

**Note:** This list is dynamic. Status reflects current development progress.
