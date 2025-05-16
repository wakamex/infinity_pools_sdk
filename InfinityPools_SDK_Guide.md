# Infinity Pools SDK Developer Guide

This guide provides essential information for developers looking to build an SDK or integrate directly with the Infinity Pools protocol. The primary point of interaction for most user-facing operations is the `InfinityPoolsPeriphery.sol` contract.

## Core Concepts

### 1. Position Management as NFTs (ERC721)
User Liquidity Provider (LP) and "Swapper" positions are represented as ERC721 Non-Fungible Tokens (NFTs). This provides clear ownership and transferability.

*   **Minting:** NFTs are minted upon successful creation of a new position (e.g., via `addLiquidity` or `newLoanWithSwap`).
*   **Token ID Structure:** `tokenId`s are not sequential. They are encoded by `EncodeIdHelper.sol` and contain:
    *   **Position Type:** LP or Swapper.
    *   **Pool Address:** The specific Infinity Pool contract address.
    *   **Position Number:** A unique serial number for that position type within that pool.
*   **Metadata URI:** The `_baseURI()` function provides the base for `tokenURI`, pointing to an off-chain service for NFT metadata.

### 2. Internal Collateral Management
The `InfinityPoolsPeriphery` contract (via `PeripheryPayment`) manages internal collateral balances for users. Users can deposit tokens (e.g., via `swapDeposit`) into this internal vault, and these funds can be used for subsequent operations or withdrawn.

### 3. `InfinityPoolsPeriphery.sol` as the Main Entry Point
This contract simplifies interactions, bundles atomic operations, and standardizes position representation.

## Key User-Facing Functions (`InfinityPoolsPeriphery.sol`)

### A. Position & ID Management

*   **`encodeId(EncodeIdHelper.PositionType enumValue, address poolAddress, uint88 lpOrSwapperNumber) external pure returns (uint256)`**
    *   **Description:** Encodes the constituent parts (position type, pool address, position number) into a standard `tokenId` for an NFT position.
    *   **Use Case:** Useful for off-chain systems or other contracts to predict or construct `tokenId`s.
    *   **SDK Utility:** Provide a helper function that wraps this, allowing users to easily generate `tokenId`s if they know the components.

### B. Liquidity Operations (LP Positions - NFT Gated)

*   **`addLiquidity(IInfinityPoolsPeriphery.AddLiquidityParams calldata params) external nonReentrant returns (uint256 tokenId, uint256 amount0, uint256 amount1)`**
    *   **Description:** Allows users to provide liquidity to an Infinity Pool. Mints a new LP NFT to `msg.sender`.
    *   **Parameters:** See `AddLiquidityParams` struct below.
    *   **SDK Utility:** Abstract the parameter construction. Handle token approvals if `params.useVaultDeposit` is false.

*   **`collect(uint256 tokenId, address receiver) external nonReentrant returns (uint256 amount0, uint256 amount1)`**
    *   **Description:** Claims accrued fees/rewards from an LP position without removing liquidity.
    *   **Parameters:** `tokenId` of the LP NFT, `receiver` for assets.
    *   **SDK Utility:** Requires NFT ownership. Decode `tokenId` to display pool info.

*   **`drain(uint256 tokenId, address receiver) external nonReentrant returns (uint256 amount0, uint256 amount1)`**
    *   **Description:** Withdraws entire liquidity position and accrued fees/rewards.
    *   **Parameters:** `tokenId` of the LP NFT, `receiver` for assets.
    *   **SDK Utility:** Requires NFT ownership. The NFT continues to exist but represents a closed position.

*   **`tap(uint256 tokenId) external nonReentrant`**
    *   **Description:** Triggers specific actions/updates for an LP position (e.g., checkpointing earnings) within the core pool logic without withdrawing assets.
    *   **Parameters:** `tokenId` of the LP NFT.
    *   **SDK Utility:** Requires NFT ownership.

### C. Swap Integration & Internal Collateral Management

*   **`swapDeposit(address user, IERC20 fromToken, uint256 fromTokenAmount, IERC20 toToken, uint256 minTokenAmountOut, SwapInfo memory swapInfo) external nonReentrant returns (uint256 amountOut, uint256 amountLeftOver)`**
    *   **Description:** Swaps `fromToken` to `toToken`, depositing the `toToken` (and any unspent `fromToken`) into the `user`'s internal collateral account within the Periphery contract.
    *   **Parameters:** `user` (beneficiary of collateral), `fromToken`, `fromTokenAmount`, `toToken`, `minTokenAmountOut` (slippage protection), `swapInfo` (details for external swap router).
    *   **SDK Utility:** Handle token approvals for `fromToken`. Assist in constructing `SwapInfo`.

*   **`withdrawCollaterals(address token0, address token1, address user, bool token, uint256 amount) external nonReentrant`**
    *   **Description:** Withdraws tokens from a `user`'s internal collateral balance.
    *   **Parameters:** `token0`, `token1` (pair context), `user` (owner of collateral), `token` (boolean: Z/I for token0/token1), `amount` (can be `type(uint256).max`).
    *   **SDK Utility:** Check `isApprovedForAll` if `msg.sender` is not `user`. Allow querying available collateral.

### D. Complex DeFi Actions (Primarily for Swapper Positions - NFT Gated)

*   **`newLoanWithSwap(address token0, address token1, int256 splits, address onBehalfOf, NewLoan.NewLoanParams calldata newLoanParams, Spot.SpotSwapParams calldata infinityPoolSpotSwapParams, SwapInfo calldata swap) external payable nonReentrant returns (uint256 tokenId)`**
    *   **Description:** Atomically creates a new Swapper position, optionally performing an initial spot swap (internal or external) and defining loan terms. Mints a new Swapper NFT.
    *   **Parameters:** Pool identifiers (`token0`, `token1`, `splits`), `onBehalfOf` (NFT recipient), `newLoanParams`, `infinityPoolSpotSwapParams` (for core pool swap), `swap` (for external swap via `SwapInfo`).
    *   **SDK Utility:** Complex parameter construction. Handle approvals.

*   **`batchActionsOnSwappers(IInfinityPoolsPeriphery.BatchActionsParams memory params) external payable nonReentrant`**
    *   **Description:** Performs a series of actions on one or multiple existing Swapper positions (or creates new ones) in a single transaction.
    *   **Parameters:** See `BatchActionsParams` struct below.
    *   **SDK Utility:** High-level interface to build `BatchActionsParams`. Crucial for active management.

*   **`reflow(IInfinityPoolsPeriphery.ReflowParams memory params, SwapInfo calldata swap) external payable nonReentrant`**
    *   **Description:** Modifies parameters of a single existing Swapper position (e.g., `tokenMix`, `twapUntil`), optionally with an auxiliary external swap.
    *   **Parameters:** `params` (see `ReflowParams` struct), `swap` (see `SwapInfo` struct for auxiliary swap).
    *   **SDK Utility:** Requires Swapper NFT ownership. Assist in parameter construction.

### E. Pool & Factory Discovery (View Functions)

*   **`getPoolAddress(address tokenA, address tokenB, int256 splits) external view returns (address poolAddress, address token0, address token1)`**
*   **`getPoolAddress(address tokenA, address tokenB) external view returns (address poolAddress, address token0, address token1)`**
    *   **Description:** Retrieves the address of an Infinity Pool instance and the canonical sorted token addresses.
    *   **Use Case:** Essential for finding the correct pool to interact with.
    *   **SDK Utility:** Cache results. Provide easy lookup.

*   **`getFactoryAddress() external view returns (address factoryAddress)`**
    *   **Description:** Returns the configured `IInfinityPoolFactory` address.
    *   **SDK Utility:** Useful for more advanced interactions or verification.

## Important Data Structures (Structs & Enums from `IInfinityPoolsPeriphery.sol`)

An SDK should provide clear ways to construct and understand these parameter objects.

*   **`struct AddLiquidityParams`**
    *   `token0 (address)`: First token address (sorted lower).
    *   `token1 (address)`: Second token address.
    *   `useVaultDeposit (bool)`: Use internal collateral or pull from wallet.
    *   `startEdge (int256)`: Lower bound of price range for concentrated liquidity.
    *   `stopEdge (int256)`: Upper bound of price range.
    *   `amount0Desired (uint256)`: Preferred amount of `token0`.
    *   `amount1Desired (uint256)`: Preferred amount of `token1`.
    *   `amount0Min (uint256)`: Min `token0` (slippage protection).
    *   `amount1Min (uint256)`: Min `token1` (slippage protection).

*   **`struct CallbackData`** (Used internally by Periphery for pool callbacks)
    *   `token0 (address)`, `token1 (address)`
    *   `useVaultDeposit (bool)`
    *   `caller (address)`: Original `msg.sender` to Periphery.
    *   `payer (address)`: Account for crediting/debiting in vault.
    *   `paymentType (PaymentType)`: Enum (see below).
    *   `extraData (bytes)`: Additional context (e.g., signifies `newLoan`).

*   **`struct SwapInfo`**
    *   `swapForwarder (address)`: Address of the swap router (e.g., `GeneralSwapForwarder`).
    *   `tokenInSpender (address)`: Address approved to spend `tokenIn` (usually Periphery itself).
    *   `to (address)`: Recipient of swap output (usually Periphery for collateral deposit).
    *   `data (bytes)`: ABI-encoded calldata for the `swapForwarder`.

*   **`struct BatchActionsParams`**
    *   `unwindTokenIds (uint256[])`: Swapper NFTs to unwind.
    *   `reflowParams (ReflowParams[])`: Array of reflow operations.
    *   `resetParams (ResetParams[])`: Array of reset operations.
    *   `newLoanParams (NewLoan.NewLoanParams[])`: Array of new loan creations.
    *   `noOpIds (uint256[])`: TokenIDs to ignore.
    *   `infinityPoolSpotSwapParams (Spot.SpotSwapParams)`: Optional internal pool spot swap.
    *   `swap (SwapInfo)`: Optional external swap.

*   **`struct ReflowParams`**
    *   `tokenId (uint256)`: Swapper NFT to reflow.
    *   `tokenMix (Quad)`: New target token mix.
    *   `fixedToken (bool)`: Influences rebalancing logic.
    *   `twapUntil (int256)`: Deadline for TWAP execution for rebalancing.

*   **`struct ResetParams`**
    *   `tokenId (uint256)`: Swapper NFT to reset.
    *   `deadEra (int256)`: New dead era for the Swapper.
    *   `tokenMix (Quad)`: New target token mix post-reset.
    *   `fixedToken (bool)`: Influences rebalancing logic.
    *   `twapUntil (int256)`: Deadline for TWAP execution for rebalancing.

*   **`enum PaymentType`**
    *   `WALLET (0)`: Settle directly with user's external wallet.
    *   `COLLATERAL_SWAP (1)`: Route to/from user's internal collateral balance.

## Event Handling

The `InfinityPoolsPeriphery` contract emits events for significant actions (e.g., `PeripheryLiquidityAdded`, `NoOpSwapperIds`). An SDK should allow users to subscribe to and decode these events to monitor position changes and transaction outcomes.

## Error Handling

The `IInfinityPoolsPeriphery` interface defines custom errors (e.g., `InvalidTokenOrder`, `PoolDoesNotExist`, `PriceSlippageAmount0`). An SDK should parse these custom errors to provide meaningful feedback to the user.

## Notes for SDK Developers

*   **Token Approvals:** Many functions require ERC20 token approvals to the `InfinityPoolsPeriphery` contract if not using `useVaultDeposit` or if pulling funds for swaps. The SDK should manage or guide users through this.
*   **Gas Estimation:** For complex functions like `batchActionsOnSwappers`, provide accurate gas estimation.
*   **`Quad` Type:** Interactions involving `tokenMix` use the `Quad` type (128-bit fixed-point). The SDK will need to handle conversion to/from this type.
*   **Chain Specificity:** NFT metadata URIs and other elements might be chain-specific. The SDK should handle `block.chainid` considerations where relevant.
*   **Security:** Always fetch contract addresses (Periphery, Factory) from reliable sources. Be mindful of user funds when constructing transactions.

This guide provides a starting point. Refer to the full `IInfinityPoolsPeriphery.sol` interface and its implementation for complete details.
