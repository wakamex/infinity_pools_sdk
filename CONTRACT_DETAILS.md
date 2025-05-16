## InfinityPoolsProxy Contract (`proxy.sol`)

*(Protocol Importance: 4/10)*

`InfinityPoolsProxy` is an EIP-1967 compliant upgradeable proxy, providing a stable protocol address while enabling logic updates. It manages the implementation address via `ERC1967Utils` (at the standard EIP-1967 slot) and is initialized at deployment.

## InfinityPoolsPeriphery Contract (`InfinityPoolsPeriphery.sol`)

*(Protocol Importance: 9/10)*

The `InfinityPoolsPeriphery` contract is the main entry point for users and external systems interacting with the Infinity Pools protocol. It serves as a sophisticated facade, abstracting away the intricate mechanics of the core pool contracts and providing a user-friendly interface for managing DeFi positions and collateral. It simplifies common workflows, bundles complex atomic operations, and standardizes position representation through Non-Fungible Tokens (NFTs).

Key functionalities include:

*   **Position Management as NFTs (ERC721):** A cornerstone of the Periphery contract is its management of user Liquidity Provider (LP) and "Swapper" positions as ERC721 Non-Fungible Tokens. This approach provides users with clear ownership and transferability of their financial stakes.
    *   **Lifecycle & Minting:** NFTs are minted to users when they successfully execute operations that establish a new position. For instance, calling `addLiquidity` results in an LP NFT, while `newLoanWithSwap` (if it creates a Swapper position) mints a Swapper NFT.
    *   **Token ID Structure:** Each `tokenId` is not a simple counter but a structured identifier meticulously crafted by the `EncodeIdHelper` library. It encodes vital information:
        *   **Position Type:** Whether it's an LP or a Swapper position.
        *   **Pool Address:** The specific Infinity Pool contract address where the position resides.
        *   **Position Number:** A unique serial number for that position type within that particular pool (e.g., the 5th LP in pool X).
        This structured ID allows the Periphery and potentially external tools to quickly understand the nature and location of any given position NFT. (See `EncodeIdHelper.sol` documentation for precise encoding details).
    *   **Ownership & Transferability:** As standard ERC721 tokens, ownership of an NFT equates to ownership of the underlying DeFi position. Users can freely trade or transfer their position NFTs, thereby transferring the associated financial rights and obligations, subject to any protocol-specific conditions.
    *   **Metadata URI (`_baseURI`):** The contract implements `_baseURI()` to provide a base for constructing the `tokenURI` for each NFT. This typically points to an off-chain service that delivers JSON metadata (name, description, image, attributes) for display in wallets and marketplaces, dynamically generated based on the `block.chainid` and the `tokenId`.
*   **Liquidity Operations (For LP Positions):** The Periphery contract provides a suite of functions for managing Liquidity Provider (LP) positions. These operations are NFT-gated, meaning the caller typically needs to own or be approved for the relevant LP position NFT.
    *   **`addLiquidity(IInfinityPoolsPeriphery.AddLiquidityParams calldata params)`:** This is the primary function for users to provide liquidity to an Infinity Pool.
        *   **Parameters (`AddLiquidityParams`):** This struct includes crucial details such as `tokenA` and `tokenB` addresses, the desired `amountA` and `amountB` of each token to provide, `minAmountA` and `minAmountB` to protect against slippage, a `deadline` for the transaction, and the `earnEra` from which the LP wishes their liquidity to start earning fees.
        *   **Outcome:** If successful, the specified amounts of tokens are transferred from the user to the pool, and a new LP NFT is minted to the `msg.sender`, representing their share and terms. The function internally calls `PeripheryActions.addLiquidity` which orchestrates the interaction with the target pool.
        *   An `PeripheryLiquidityAdded` event is emitted upon success.
    *   **`collect(uint256 tokenId, address receiver)`:** Allows an LP to claim any accrued fees or rewards from their active position without removing the underlying liquidity.
        *   **Parameters:** Takes the `tokenId` of the LP NFT and a `receiver` address for the claimed assets.
        *   **Process:** The function decodes the `tokenId` to identify the specific pool and LP number, then calls the `collect` function on the respective `IInfinityPool` instance. The pool contract calculates and transfers the owed assets.
        *   The NFT owner or an approved operator must call this.
    *   **`drain(uint256 tokenId, address receiver)`:** Enables an LP to withdraw their entire liquidity position, including any accrued fees and rewards.
        *   **Parameters:** Similar to `collect`, it requires the `tokenId` and a `receiver` address.
        *   **Outcome:** All liquidity associated with the LP position is removed from the pool and transferred to the `receiver`. The LP NFT continues to exist but now represents an empty or closed position. Future interactions with this NFT for liquidity operations would likely fail or be no-ops until/unless new liquidity is added under a new position.
        *   The NFT owner or an approved operator must call this.
    *   **`tap(uint256 tokenId)`:** A more specialized function that allows an LP to "tap" their position. 
        *   **Purpose:** This generally triggers specific actions or updates related to the LP position within the core pool logic, such as checkpointing earnings or other internal state updates, without necessarily withdrawing assets. The exact behavior is defined by the `tap` implementation in the `IInfinityPool` contract.
        *   The NFT owner or an approved operator must call this.
*   **Swap Integration & Internal Collateral Management:** The Periphery contract streamlines token swaps and manages internal collateral balances for users, leveraging its `PeripheryPayment` inheritance and integration with external swap routers.
    *   **`swapDeposit(address user, IERC20 fromToken, uint256 fromTokenAmount, IERC20 toToken, uint256 minTokenAmountOut, SwapInfo memory swapInfo)`:** This function allows a user to swap a specified `fromTokenAmount` of `fromToken` for `toToken`, with the resulting `toToken` (and any unspent `fromToken`) being deposited into the `user`'s internal collateral account within the Periphery contract's vault system (managed by `PeripheryPayment`).
        *   **Process Flow:** 
            1.  The contract first withdraws `fromTokenAmount` from the `user` (or `msg.sender` if they are the same, checking allowances via `_withdrawERC20Capped`).
            2.  It then calls `PeripheryActions.handleSwap`. This internal function consults the `swapForwarders` mapping (which can be managed by the factory owner via `addOrRemoveSwapForwarder`) to select an appropriate external swap router (e.g., `GeneralSwapForwarder` or other registered forwarders) to execute the actual trade based on the provided `swapInfo`.
            3.  The `minTokenAmountOut` parameter protects the user against excessive slippage during the swap.
            4.  Any `toToken` received from the swap, along with any `fromToken` that wasn't fully spent (e.g., due to partial fills or dust), is then deposited into the `user`'s internal collateral balance using `_depositERC20`. These balances are held by the Periphery contract on behalf of the user and can be utilized in other Periphery operations or withdrawn.
    *   **`withdrawCollaterals(address token0, address token1, address user, bool token, uint256 amount)`:** Enables users to withdraw tokens from their internal collateral balance previously accumulated through `swapDeposit` or other means (like direct payments or callback settlements).
        *   **Parameters:** 
            *   `token0` and `token1`: Define the token pair context for the collateral. This is important as collateral might be tracked per pair.
            *   `user`: The address whose collateral is being withdrawn.
            *   `token`: A boolean (Z/I) indicating which token of the pair (`token0` if Z, `token1` if I) is to be withdrawn.
            *   `amount`: The quantity to withdraw. Can be `type(uint256).max` to withdraw the entire available balance for that specific token in that pair context.
        *   **Security:** If `msg.sender` is not the `user`, it checks if `msg.sender` is an approved operator for the `user`'s assets via `isApprovedForAll` (standard ERC721/1155 approval concept, adapted here for collateral).
        *   **Process:** The function verifies sufficient balance, decreases the internal collateral record using `_decreaseCollateral` (from `PeripheryPayment`), and then transfers the `amount` of the specified token to the `user` using `_depositERC20` (which, despite its name, here effectively means 'send token to user').
*   **Complex DeFi Actions (Primarily for Swapper Positions):** The Periphery contract offers powerful, atomic functions for managing sophisticated "Swapper" NFT positions, which represent more dynamic, loan-like interactions with Infinity Pools. These often involve the `PeripheryActions` library for orchestrating calls to the core pool contracts.
    *   **`newLoanWithSwap(address token0, address token1, int256 splits, address onBehalfOf, NewLoan.NewLoanParams calldata newLoanParams, Spot.SpotSwapParams calldata infinityPoolSpotSwapParams, SwapInfo calldata swap)`:** This versatile function allows a user to atomically: 
        1.  Create a new Swapper position in a specified pool (identified by `token0`, `token1`, `splits`).
        2.  Optionally perform an initial spot swap via the core Infinity Pool's spot market (`infinityPoolSpotSwapParams`) or an external swap (`swapInfo`) to acquire the necessary assets for the loan or to shape the initial position.
        3.  Define the terms of the new loan/Swapper position through `newLoanParams` (e.g., amounts to borrow/lend, collateral details, `deadEra` or maturity, `tokenMix`).
        *   **Outcome:** A new Swapper NFT is minted to the `onBehalfOf` address. The `msg.sender` must either be `onBehalfOf` or have approval via `isApprovedForAll`.
        *   This function essentially wraps `PeripheryActions.batchActionsOnSwappers` for a single, new position setup.
    *   **`batchActionsOnSwappers(IInfinityPoolsPeriphery.BatchActionsParams memory params)`:** Enables users to perform a series of actions on one or multiple existing Swapper positions they own, all within a single transaction. This is highly gas-efficient for active position management.
        *   **Parameters (`BatchActionsParams`):** This struct contains arrays detailing the target `swapperId`(s) and corresponding actions such as adjusting collateral (`deltaCollateral`), borrowing more (`borrow`), changing the `tokenMix`, extending the `deadEra`, or setting a `twapUntil` period for TWAP-based actions. It can also include parameters for new loans to be created in the batch.
        *   **Process:** It iterates through the requested actions, calling `PeripheryActions.batchActionsOnSwappers` which then translates these into lower-level calls to the appropriate `IInfinityPool` contract (e.g., `borrow`, `repay`, `reflowState`).
        *   The `infinityPoolPaymentCallback` is used to settle any resulting fund movements (e.g., borrowed amounts being credited).
        *   The `NoOpSwapperIds` event may be emitted if certain specified `swapperId`s were skipped (e.g., due to invalid parameters or state).
    *   **`reflow(IInfinityPoolsPeriphery.ReflowParams memory params, SwapInfo calldata swap)`:** Allows for the modification or "reflowing" of parameters for a single, existing Swapper position, identified by `params.tokenId`.
        *   **Parameters (`ReflowParams`):** Includes the `tokenId` of the Swapper NFT, and new desired parameters like `tokenMix`, `fixedToken`, and `twapUntil`.
        *   **Auxiliary Swap:** Can be combined with an external `swap` (defined by `SwapInfo`) if the reflow operation requires acquiring or disposing of tokens to meet the new parameters.
        *   **Process:** It uses `PeripheryActions.handleSwapper` to prepare callback data and then calls `IInfinityPool(poolAddress).reflow(...)` on the target pool. The `infinityPoolPaymentCallback` handles any resultant fund movements.
*   **Callback Handling (`infinityPoolPaymentCallback`):** The Periphery contract implements the `IInfinityPoolPaymentCallback` interface, specifically the `infinityPoolPaymentCallback(int256 amount0, int256 amount1, bytes calldata _data)` function. This is crucial for asynchronous operations and settlement of funds.
    *   **Trigger:** This function is designed to be called by an Infinity Pool contract *after* an interaction initiated by the Periphery contract (e.g., following a `batchActionsOnSwappers` or `reflow` operation that results in funds being owed to or from a user).
    *   **Purpose:** Its primary role is to securely receive token amounts (`amount0`, `amount1`) from the calling pool and credit them to the appropriate user's internal collateral balance within the Periphery contract. This ensures that funds resulting from pool interactions are correctly attributed and made available to the user via `PeripheryPayment`'s vault system.
    *   **`CallbackData`:** The `_data` parameter is abi-decoded into a `CallbackData` struct. This struct, defined within `PeripheryPayment`, typically contains:
        *   `user`: The address of the end-user on whose behalf the operation was performed and who should receive the funds.
        *   `paymentType`: An enum indicating how the funds should be handled (e.g., direct deposit, conversion to WETH before deposit).
        *   `tokenToPay`: Which token (token0, token1, or both) the callback pertains to.
    *   **Security:** A critical security measure is that `msg.sender` for this callback *must* be a legitimate Infinity Pool contract that the Periphery contract has previously interacted with. The `CallbackValidation` library's `validateCallback` (used within `PeripheryPayment`) typically enforces this by checking if `msg.sender` is a known/valid pool, often one associated with the `user` or transaction context stored during the initial outgoing call. Unauthorized calls would be rejected.
*   **Upgradeable & Secure:** The contract is built with security and future-proofing in mind.
    *   **UUPS Upgradeability:** It inherits from `UUPSUpgradeable`, implementing the Universal Upgradeable Proxy Standard (EIP-1822). This allows the contract's logic to be upgraded in place without requiring users to migrate their positions or change the contract address they interact with. The upgrade mechanism itself is part of the implementation contract.
    *   **Upgrade Authorization:** Upgrades are controlled via the `_authorizeUpgrade(address newImplementation)` internal function. In this contract, authorization is delegated to the owner of the `IInfinityPoolFactory` contract, ensuring that only a designated administrative address can propose and execute upgrades.
    *   **Reentrancy Protection:** Many critical state-changing functions (e.g., `addLiquidity`, `batchActionsOnSwappers`, `swapDeposit`, `withdrawCollaterals`) are protected by the `nonReentrant` modifier (from OpenZeppelin's `ReentrancyGuardUpgradeable`). This prevents malicious contracts from making recursive calls back into the function before the initial invocation is complete, a common attack vector.
    *   **Ownership & Approval Checks:** For functions that operate on specific NFT positions (e.g., `collect`, `drain`, `tap`, `reflow`), the contract employs robust checks:
        *   `_requireOwned(tokenId)`: An internal function (likely from ERC721Upgradeable) that ensures the `msg.sender` is the owner of the NFT.
        *   `_isAuthorized(address owner, address spender, uint256 tokenId)`: A more general check (likely from ERC721Upgradeable's `isApprovedOrOwner` or a similar mechanism) to verify if the `spender` (typically `msg.sender`) is either the `owner` of the `tokenId` or has been approved by the owner (e.g., via `approve` or `setApprovalForAll`). This pattern is used extensively to gate access to position-specific actions.
    *   **Error Handling:** The contract defines custom errors (e.g., `InvalidFundsSpent`, `Unauthorized`, `CallerNotApproved`, `InvalidID`) for clear and gas-efficient reversion reasons.
*   **ID Management (`EncodeIdHelper`):** The contract relies heavily on the `EncodeIdHelper` library for managing the `tokenId`s of the ERC721 position NFTs. This is not just for uniqueness but for embedding structural information within the ID itself.
    *   **Structured `tokenId`s:** As mentioned in "Position Management as NFTs", `tokenId`s are not arbitrary. They are carefully encoded to contain:
        *   `PositionType`: An enum distinguishing LP positions from Swapper positions.
        *   `poolAddress`: The address of the specific Infinity Pool where the position exists.
        *   `lpOrSwapperNumber`: A unique identifier (e.g., a serial number or counter) for that position within its type and pool.
    *   **`encodeId` Function:** The Periphery contract exposes a public pure function `encodeId(EncodeIdHelper.PositionType enumValue, address poolAddress, uint88 lpOrSwapperNumber)` that delegates to `EncodeIdHelper.encodeId`. This can be useful for off-chain systems or other contracts to predict or construct `tokenId`s if they know the constituent parts.
    *   **`decodeId` Usage:** Internally, when a function is called with a `tokenId` (e.g., `collect(tokenId, ...)`), the contract uses `EncodeIdHelper.decodeId(tokenId)` to unpack these constituent parts. This allows it to quickly determine if the ID refers to an LP or Swapper, which pool to interact with, and the specific position number, without needing to look up this information from storage individually, leading to gas savings and efficient routing of operations.
    *   **Importance:** This structured ID system is crucial for the Periphery contract's ability to manage diverse positions across potentially many pools with a unified interface. It simplifies logic and ensures that operations are routed to the correct underlying pool and position context.

*   **Key Dependencies & Interactions:** The `InfinityPoolsPeriphery` contract does not operate in isolation. Its functionality is deeply intertwined with several other key contracts and libraries:
    *   **`IInfinityPoolFactory.sol`:** Used to fetch the factory owner (for upgrade authorization) and potentially other global configuration.
    *   **`IInfinityPool.sol`:** The interface for individual Infinity Pool contracts. The Periphery contract routes many operations (e.g., `addLiquidity` (via `PeripheryActions`), `collect`, `drain`, `tap`, `batchActionsOnSwappers`, `reflow`) to the specific pool instance decoded from the `tokenId`.
    *   **`PeripheryActions.sol`:** A critical internal library that encapsulates complex logic for interacting with pool contracts, particularly for `addLiquidity`, `batchActionsOnSwappers`, `handleSwapper` (used by `reflow`), and `handleSwap`.
    *   **`PeripheryPayment.sol` (and its dependencies like `Vault.sol`, `CallbackValidation.sol`):** Inherited by `InfinityPoolsPeriphery` to manage user WETH balances, internal collateral deposits/withdrawals (`_depositERC20`, `_withdrawERC20Capped`, `_decreaseCollateral`), and process payment callbacks.
    *   **`EncodeIdHelper.sol`:** As detailed above, essential for creating and decoding the structured `tokenId`s for NFTs.
    *   **`ERC721Upgradeable.sol` (OpenZeppelin):** Provides the base ERC721 NFT functionality for position tokens.
    *   **`UUPSUpgradeable.sol` (OpenZeppelin):** Enables the upgradeability of the contract.
    *   **`ReentrancyGuardUpgradeable.sol` (OpenZeppelin):** Provides the `nonReentrant` modifier.
    *   **`SafeERC20.sol` (OpenZeppelin):** Used for safe `IERC20` token interactions.
    *   **Swap Forwarders (e.g., `GeneralSwapForwarder.sol`, contracts implementing `ISwapForwarder.sol`):** External contracts registered with the Periphery that are used to execute token swaps for `swapDeposit` and potentially other functions.
    *   **`IPermit2.sol`:** Interface for interacting with Uniswap's Permit2 contract, likely used by `PeripheryPayment` for gas-efficient token approvals.

## IInfinityPoolFactory Interface (`IInfinityPoolFactory.sol`)

*(Protocol Importance: 7/10)*

The `IInfinityPoolFactory` interface outlines the standard functions and events for a factory contract responsible for deploying and managing Infinity Pool instances.

Key features defined by the interface include:

*   **Pool Creation:**
    *   `createPool(address tokenA, address tokenB, int256 splits)`: A function to deploy new Infinity Pool contracts for specified token pairs and "splits" (which likely determine pool parameters such as fee tiers or liquidity concentration characteristics).
    *   Emits a `PoolCreated` event upon successful pool deployment, providing details about the created pool including the tokens involved, splits, the new pool's address, and the decimals of the tokens.
*   **Pool Discovery/Retrieval:**
    *   `getPool(address tokenA, address tokenB, int256 splits)`: Retrieves the address of an existing pool for a specific pair of tokens and splits.
    *   `getPool(address tokenA, address tokenB)`: An overloaded version to retrieve a pool address for a token pair, potentially a default or primary pool if splits are not specified.
*   **Ownership Information:**
    *   `owner()`: A view function that returns the address of the entity controlling the factory.
    *   `OwnerChanged` event: Signifies that the factory likely implements an ownable pattern, allowing for transfer of administrative control.

## Constants Library (`Constants.sol`)

*(Protocol Importance: 7/10)*

The `Constants.sol` library provides a suite of pre-calculated mathematical and financial constants, fundamental to the protocol's high-precision fixed-point arithmetic (using `Quad` type). These constants are not merely numerical values; they directly define and constrain key financial behaviors, risk parameters, and model characteristics within Infinity Pools.

Key aspects include:

*   **Core Function:** Serves as the immutable source for numerical values that underpin critical financial calculations, ensuring consistency, accuracy, and defining the operational boundaries of the protocol.
*   **Types of Constants:**
    *   **Deflator Steps:** (e.g., `DEFLATOR_STEP_0` to `DEFLATOR_STEP_12`) for time-based value adjustments or financial model stepping.
    *   **Logarithmic Values:** Natural logarithm constants like `LAMBDA` (for compounding/growth) and `LN2`.
    *   **Financial Parameters:** Critical thresholds and rates such as `MIN_RATE`, `UTILISATION_CAP` (e.g., 99%), and `TWAP_SPREAD_DEFAULT`, which directly influence lending, borrowing, and trading mechanics.
    *   **Approximation Coefficients:** (`PERIODIC_APPROX_CONSTANT_0` through `_7`) for series approximations of complex financial functions.
    *   **Special Values:** Includes `NAN` for exceptional numerical results.
*   **Data Type:** All constants are `Quad` (from `bytes16`), designed for a 128-bit fixed-point system.

## IInfinityPoolsPeriphery Interface (`IInfinityPoolsPeriphery.sol`)

*(Protocol Importance: 9/10)*

As the primary gateway for user and external contract interactions, the `IInfinityPoolsPeriphery` interface defines the complete external API for the `InfinityPoolsPeriphery.sol` contract. It meticulously specifies all functions, events (if any were defined beyond the snippet), data structures (structs), enumerations, and custom errors. Mastery of this interface is essential for any developer aiming to integrate with, build upon, or simply interact with the Infinity Pools ecosystem, as it governs access to the periphery's rich functionalities.

Key elements defined in this interface include:

*   **Parameter Structures (Structs):**
    *   `AddLiquidityParams`: This struct encapsulates all necessary parameters for an `addLiquidity` operation when interacting with the `InfinityPoolsPeriphery` contract. Each field plays a crucial role in defining the liquidity to be added:
        *   `token0 (address)`: The contract address of the first token in the liquidity pair. By convention, this should be the token with the lower sort order address compared to `token1`.
        *   `token1 (address)`: The contract address of the second token in the liquidity pair.
        *   `useVaultDeposit (bool)`: If `true`, the Periphery contract will attempt to use tokens from the caller's internal collateral balance (managed by `PeripheryPayment`'s vault system) to provide liquidity. If `false`, tokens will be pulled directly from the caller's wallet (requiring prior ERC20 approval to the Periphery contract).
        *   `startEdge (int256)`: Defines the lower bound of the price range for the concentrated liquidity position. The exact interpretation (e.g., as a tick or a specific price representation) is determined by the core Infinity Pool logic.
        *   `stopEdge (int256)`: Defines the upper bound of the price range for the concentrated liquidity position.
        *   `amount0Desired (uint256)`: The preferred amount of `token0` the user wishes to contribute to the liquidity position. The actual amount used may be less, depending on the pool's current price ratio and the specified `startEdge`/`stopEdge`.
        *   `amount1Desired (uint256)`: The preferred amount of `token1` the user wishes to contribute.
        *   `amount0Min (uint256)`: The minimum acceptable amount of `token0` that must be used for the liquidity provision. If the calculated amount of `token0` to be added (based on the range and desired amounts) falls below this value, the transaction will revert. This serves as a slippage protection mechanism.
        *   `amount1Min (uint256)`: The minimum acceptable amount of `token1` to be used, serving as slippage protection for `token1`.
    *   `CallbackData`: This struct is crucial for the `infinityPoolPaymentCallback` function in `InfinityPoolsPeriphery.sol`. It is ABI-encoded and passed as the `_data` argument during a callback from an Infinity Pool to the Periphery contract, providing context for the payment settlement.
        *   `token0 (address)`: The address of the first token involved in the transaction that triggered the callback.
        *   `token1 (address)`: The address of the second token involved.
        *   `useVaultDeposit (bool)`: Indicates if the original transaction intended to use funds from the user's vault/collateral balance. This helps the callback logic determine how to handle refunds or further collateral interactions.
        *   `caller (address)`: The original `msg.sender` of the Periphery contract call that initiated the interaction with the pool. This is often the EOA or contract that expects to ultimately benefit from the callback funds.
        *   `payer (address)`: The address from which tokens were taken for the initial operation, or the account in the Periphery's vault system that should be credited or debited. For operations like `newLoanWithSwap`, this would be the entity (`onBehalfOf`) receiving the loan or providing collateral.
        *   `paymentType (PaymentType)`: An enum value (see below) indicating the nature of the payment or the source/destination of funds, guiding the callback's settlement logic.
        *   `extraData (bytes)`: Arbitrary additional data that can be passed along. The comment in `IInfinityPoolsPeriphery.sol` notes that currently, its presence signifies a `newLoan` call. This field allows for future extensibility of callback contexts.
    *   `SwapInfo`: This struct provides all necessary details for the `InfinityPoolsPeriphery` contract to execute a token swap using an external swap router or forwarder. It's a crucial parameter for functions like `swapDeposit`, `newLoanWithSwap`, `batchActionsOnSwappers`, and `reflow` when an auxiliary swap is needed.
        *   `swapForwarder (address)`: The contract address of the specific swap forwarder (e.g., `GeneralSwapForwarder` or another contract implementing `ISwapForwarder`) that should be used to execute this particular swap. The Periphery contract maintains a list of approved swap forwarders.
        *   `tokenInSpender (address)`: The address that the `swapForwarder` should be approved to spend `tokenIn` from. Typically, this is the Periphery contract itself, which would have already received the tokens from the user or its internal vault.
        *   `to (address)`: The address that should ultimately receive the output tokens from the swap. In many Periphery operations, this will be the Periphery contract itself, which then deposits the tokens into the user's internal collateral balance.
        *   `data (bytes)`: The ABI-encoded call data specific to the chosen `swapForwarder`. This data instructs the forwarder on how to perform the swap (e.g., which tokens to swap, the amount, slippage parameters, and the path through underlying DEXs like Uniswap V3). The Periphery contract does not interpret this data itself but forwards it directly to the `swapForwarder`.
    *   `BatchActionsParams`: This powerful struct is the cornerstone of the `batchActionsOnSwappers` function in `InfinityPoolsPeriphery.sol`. It enables users to bundle a variety of operations on existing Swapper positions, or even create new ones, into a single, atomic transaction, offering significant gas savings and improved user experience for complex position management.
        *   `unwindTokenIds (uint256[])`: An array of `tokenId`s for existing Swapper NFT positions that are to be unwound (i.e., closed out, with collateral returned and debt settled). The specifics of unwinding are handled by the core pool logic.
        *   `reflowParams (ReflowParams[])`: An array of `ReflowParams` structs (see below). Each element in this array specifies a `tokenId` of an existing Swapper position and the new parameters (`tokenMix`, `fixedToken`, `twapUntil`) to which it should be reflowed.
        *   `resetParams (ResetParams[])`: An array of `ResetParams` structs (see below). Each element defines a `tokenId` for an existing Swapper position and the parameters for resetting its state, such as a new `deadEra`, `tokenMix`, `fixedToken`, or `twapUntil`.
        *   `newLoanParams (NewLoan.NewLoanParams[])`: An array of `NewLoan.NewLoanParams` structs (imported from `src/libraries/external/NewLoan.sol`). Each struct in this array defines all the necessary parameters to create a brand new Swapper position (loan). This allows for batch creation of multiple loans.
        *   `noOpIds (uint256[])`: An array of `tokenId`s that should be explicitly ignored or treated as no-operations within the batch. This can be useful for selectively skipping certain positions in a pre-compiled list without altering the other arrays.
        *   `infinityPoolSpotSwapParams (Spot.SpotSwapParams)`: Parameters (imported from `src/libraries/external/Spot.sol`) for an optional spot swap operation that can be performed via the *core Infinity Pool's internal spot market mechanism*. This swap is part of the batch and can be used, for example, to acquire an asset needed for one of the new loans or to rebalance after a reflow, before or after other actions in the batch. Note the distinction from the general `swap` field below.
        *   `swap (SwapInfo)`: A `SwapInfo` struct (see above) detailing an optional *external* swap to be performed via a registered `swapForwarder`. This swap is also part of the batch and provides flexibility for more complex trading needs alongside the primary Swapper actions. It can be used in conjunction with or independently of the `infinityPoolSpotSwapParams`.
    *   `ReflowParams`: This struct defines the parameters needed to adjust an existing Swapper (automated strategy/loan) position. A reflow typically involves changing the composition or target of the position without fully unwinding and recreating it.
        *   `tokenId (uint256)`: The NFT `tokenId` that uniquely identifies the Swapper position to be reflowed.
        *   `tokenMix (Quad)`: A high-precision fixed-point number (Quad type) representing the new target mix or ratio of the two tokens in the underlying Infinity Pool for this Swapper position. For example, this could define a new target allocation if the Swapper is managing a portfolio or a new leverage ratio if it's a leveraged position.
        *   `fixedToken (bool)`: A boolean flag that likely influences how the `tokenMix` is interpreted or how the reflow rebalances. If `true`, one of the tokens in the pair might be held constant while the other is adjusted to meet the new `tokenMix`. If `false`, both tokens might be adjusted. The exact mechanics are defined by the core pool's `reflow` logic.
        *   `twapUntil (int256)`: A timestamp indicating the deadline until which a Time-Weighted Average Price (TWAP) mechanism should be used for any swaps or rebalancing actions required during the reflow. Using a TWAP can help reduce price impact for large adjustments. A value of `0` or a past timestamp might imply an immediate (spot price) execution.
    *   `ResetParams`: This struct provides parameters to reset an existing Swapper position, potentially after a significant market event, a period of inactivity, or to adjust its fundamental strategy parameters. A reset can be more drastic than a reflow.
        *   `tokenId (uint256)`: The NFT `tokenId` of the Swapper position to be reset.
        *   `deadEra (int256)`: Specifies a new "dead era" for the Swapper. An era is a time-based or event-based counter in the pool. Setting a `deadEra` often implies that the Swapper position should become inactive or enter a specific state until that era is passed or some other condition related to the era is met. This can be a mechanism to pause or re-evaluate a strategy.
        *   `tokenMix (Quad)`: Similar to `ReflowParams`, this defines a new target token mix for the Swapper position post-reset.
        *   `fixedToken (bool)`: Similar to `ReflowParams`, this influences how the `tokenMix` is achieved during the reset.
        *   `twapUntil (int256)`: Similar to `ReflowParams`, this sets a deadline for using TWAP during any rebalancing involved in the reset operation.
*   **Enumerations (Enums):**
    *   `PaymentType (enum)`: This enumeration provides distinct categories for how payments or fund movements should be handled by the `infinityPoolPaymentCallback` logic in the `InfinityPoolsPeriphery` contract.
        *   `WALLET (0)`: Indicates that the funds involved in the callback (e.g., amounts received from a pool operation) should be settled directly with the user's external wallet. This might involve transferring tokens directly to the `payer` or `caller` address if they are being returned, or it might signify that the initial funds came directly from the user's wallet rather than an internal collateral balance.
        *   `COLLATERAL_SWAP (1)`: Suggests that the funds are related to a collateral swap operation or should be routed to/from the user's internal collateral balance managed by the Periphery contract's vault system. For example, proceeds from a swap executed during `swapDeposit` would likely use this type to be credited to the user's collateral.
*   **Custom Error Types:** The interface defines a set of custom errors (e.g., `InvalidTokenOrder()`, `NoTokensProvided()`, `PoolDoesNotExist()`, `NoLiquidity()`, `PriceSlippageAmount0()`, `PriceSlippageAmount1()`). By declaring these errors, the interface establishes a standardized way for implementations like `InfinityPoolsPeriphery.sol` to signal specific failure conditions. This greatly aids developers integrating with the protocol by providing more granular and gas-efficient error reporting than generic string reasons.
        *   `InvalidTokenOrder()`: Signifies that `tokenA` and `tokenB` were provided in an order that does not match the canonical ordering (usually `token0.address < token1.address`) expected by the pool or factory.
        *   `NoTokensProvided()`: Indicates that one or both token addresses were zero or otherwise invalid when trying to identify or interact with a pool.
        *   `PoolDoesNotExist()`: Returned when a lookup for a pool (e.g., via `getPoolAddress`) for the given parameters does not find a corresponding deployed pool.
        *   `NoTokensRequired()`: Suggests an operation was attempted that expected token inputs, but none were necessary or provided under the circumstances.
        *   `NoLiquidity()`: Indicates an attempt to perform an action (e.g., a swap or liquidity withdrawal) for which there is insufficient liquidity in the pool.
        *   `PriceSlippageAmount0()`, `PriceSlippageAmount1()`: These errors are triggered if the execution price for a swap or liquidity operation would result in an amount of `token0` or `token1` (respectively) that is worse than the minimum acceptable amount specified by the user (`amount0Min` or `amount1Min`).
*   **View Functions (Queries):**
    *   `getPoolAddress(address tokenA, address tokenB, int256 splits) external view returns (address poolAddress, address token0, address token1)`: Retrieves the address of an Infinity Pool instance based on two token addresses (`tokenA`, `tokenB`) and a `splits` parameter (which defines specific pool characteristics like fee tier or other structural properties). It also returns `token0` and `token1` which are the canonical, sorted addresses of the input tokens as recognized by the factory and the pool. This is useful for integrators to confirm the sorted pair.
    *   `getPoolAddress(address tokenA, address tokenB) external view returns (address poolAddress, address token0, address token1)`: An overloaded version of the above function that omits the `splits` parameter. This likely retrieves a default or primary pool for the given token pair if one exists, or if splits are not a primary differentiating factor for some pool types. It also returns the `poolAddress` and the sorted `token0`, `token1` addresses.
    *   `getFactoryAddress() external view returns (address factoryAddress)`: Returns the contract address of the `IInfinityPoolFactory` instance that the `InfinityPoolsPeriphery` contract is configured to use for creating and discovering Infinity Pool instances.
*   **Dependencies:** The interface imports types like `NewLoan.NewLoanParams` and `Spot.SpotSwapParams` from other library contracts, indicating its role in orchestrating calls that involve these external parameter sets, and `Quad` for fixed-point number representations in its structs.

## IInfinityPool Interface (`IInfinityPool.sol`)

*(Protocol Importance: 10/10)*

The `IInfinityPool` interface is arguably the most critical interface for understanding the low-level mechanics of the Infinity Pools protocol. It defines the complete external API for a single, individual Infinity Pool instance. All core DeFi operations—such as token swaps, liquidity provision and withdrawal, and the creation and management of "Swapper" (automated strategy/loan) positions—are initiated through the functions defined in this interface.

Key elements of the `IInfinityPool` interface include:

*   **`Action` Enumeration:**
    *   Defines a list of possible actions (`SWAP`, `NEW_LOAN`, `UNWIND`, `REFLOW`, `RESET`, `POUR`, `DRAIN`, `COLLECT`, `TAP`) that can be performed within a pool. This is particularly used by the `doActions` function to allow for batching multiple operations into a single transaction.

*   **Events:**
    *   The interface declares a comprehensive set of events that log all significant state changes and operations within the pool. These are crucial for off-chain monitoring and indexing of pool activities.
    *   Examples: `PoolInitialized`, `Borrowed` (for new swapper/loan creation), `LiquidityAdded`, `LiquidityTapped`, `LiquidityDrained`, `LiquidityCollected` (for LP management), `SwapperCreated`, `SwapperReset`, `SwapperReflow`, `SwapperUnwind` (for swapper lifecycle events), and `SwapperCreationEnabled`.

*   **Custom Error Types:**
    *   Includes specific errors like `InvalidLPNumber` (if an invalid liquidity position ID is used) and `OnlyFactoryIsAllowed` (for actions restricted to the pool's factory).

*   **Core DeFi Interaction Functions:**
    *   `newLoan(NewLoan.NewLoanParams memory params, bytes calldata data)`: Creates a new "Swapper" position, which typically represents a borrow or a leveraged strategy. It takes detailed parameters for the loan/swapper configuration.
    *   `swap(Spot.SpotSwapParams memory params, address receiver, bytes calldata data)`: Executes an immediate spot token swap within the pool based on the provided parameters.
    *   Liquidity Provision:
        *   `getPourQuantities(int256 startTub, int256 stopTub, Quad liquidity)`: A helper function to calculate the amounts of token0 and token1 required to provide a certain amount of `liquidity` within a specified range of "tubs" (price bins).
        *   `pour(int256 startTub, int256 stopTub, Quad liquidity, bytes calldata data)`: Adds liquidity to the pool within the specified range.
    *   Liquidity Position Management:
        *   `drain(uint256 lpNum, address receiver, bytes calldata data)`: Allows an LP to withdraw their provided liquidity and any accrued fees or interest from their position.
        *   `collect(uint256 lpNum, address receiver, bytes calldata data)`: Similar to `drain`, allows LPs to collect assets from their position.
        *   `tap(uint256 lpNum)`: Allows an LP to interact with their position, potentially to claim rewards or trigger other position-specific actions without necessarily removing liquidity.
    *   "Swapper" Position Management:
        *   `unwind(uint256 swapperId, address receiver, bytes calldata data)`: Closes an active "Swapper" position, settling any outstanding obligations and returning assets.
        *   `reflow(uint256 swapperId, Quad tokenMix, bool fixedToken, OptInt256 twapUntil, address receiver, bytes calldata data)`: Modifies the parameters of an existing "Swapper" position, such as its token mix or TWAP (Time-Weighted Average Price) settings.
        *   `reset(uint256 swapperId, OptInt256 deadEra, Quad tokenMix, bool fixedToken, OptInt256 twapUntil, address receiver, bytes calldata data)`: Resets a "Swapper" position, potentially due to specific conditions or triggers, adjusting its parameters.

*   **Batch Operations:**
    *   `doActions(Action[] calldata actions, bytes[] calldata actionDatas, address receiver, bytes calldata data)`: A powerful function that enables multiple distinct actions (from the `Action` enum) to be executed sequentially within a single transaction, improving gas efficiency and atomicity for complex strategies.

*   **State Query (Getter) Functions:**
    *   Provides a suite of view functions to retrieve information about the pool's current state:
        *   `getPoolPriceInfo()`: Returns detailed price-related data for the pool.
        *   `getPoolInfo()`: Returns basic pool configuration details (e.g., token addresses, splits).
        *   `getLpCount()`: Returns the total number of active liquidity positions.
        *   `getLiquidityPosition(uint256 lpNum)`: Retrieves comprehensive details for a specific liquidity position.
        *   `getSwappersCount()`: Returns the total number of active "Swapper" positions.
        *   `getBinLiquids(uint256 startBin, uint256 stopBin)`: Returns an array of liquidity amounts present in specified price bins, relevant for concentrated liquidity models.

*   **Administrative and Utility Functions:**
    *   `enableSwapperCreation()`: A function likely restricted to an administrative role (e.g., the factory) to enable or disable the creation of new "Swapper" positions in the pool.
    *   `advance()`: A function that may be called periodically or by keepers to advance time-dependent parameters within the pool, such as updating TWAP accumulators or internal pool clocks.

*   **Dependencies:**
    *   The interface relies on several imported types and libraries: `Quad` for fixed-point arithmetic, `NewLoan.NewLoanParams` and `Spot.SpotSwapParams` for parameter structures from external libraries, `OptInt256` for optional integer values, `Structs` for shared data structures like `PoolPriceInfo` and `LiquidityPosition`, and `SwapperInternal.Info` for swapper-related data.

## Shared Data Structures (`Structs.sol`)

*(Protocol Importance: 8/10)*

The `Structs.sol` file is a central repository for custom data types, defining a collection of Solidity structs used extensively throughout the Infinity Pools protocol. These structures are the backbone for organizing, passing, and returning complex data between different contracts, libraries, and off-chain consumers. A thorough understanding of these data structures is indispensable for interpreting function parameters, return values, event data, and the overall state representation within the system.

Key structures defined in `Structs.sol` include:

*   **Liquidity Position State Constants:**
    *   `LP_STATE_OPENED`: Indicates a liquidity position has been created but is not yet actively earning fees (e.g., liquidity is outside the current price range).
    *   `LP_STATE_ACTIVE`: Indicates the liquidity position is within the active price range and is earning fees.
    *   `LP_STATE_CLOSED`: Indicates the liquidity position has been fully withdrawn or closed.

*   **`PoolPriceInfo` Struct:**
    *   **Purpose:** Encapsulates key information about the current price state of an Infinity Pool.
    *   **Fields:**
        *   `splits`: The splits parameter determining bin granularity.
        *   `tickBin`: The current active tick or bin where the price lies.
        *   `binFrac`: A `Quad` value representing the fractional position within the `tickBin`, allowing for more precise price representation than just the discrete bin.
        *   `quadvar`: Likely a measure of price variance, spread, or a related volatility metric, represented as a `Quad`.
        *   `poolDate`: The internal timestamp or era of the pool, represented as a `Quad`.

*   **`LiquidityInfo` Struct:**
    *   **Purpose:** Provides a comprehensive snapshot of liquidity distribution across a specified range of "tubs" (price ranges or segments) within a pool.
    *   **Fields:**
        *   `startTub`, `stopTub`: Defines the range of tubs for which liquidity information is being provided.
        *   Blockchain Context: `chainId`, `blockNumber`, `blockHash`, `blockTimestamp` provide context about the state of the blockchain when this information was queried.
        *   Pool State Context: `splits`, `tickBin`, `binFrac`, `poolDate` mirror the `PoolPriceInfo` to give context to the liquidity distribution.
        *   `perTubInfos`: An array of `TubLiquidityInfo` structs, each detailing the liquidity within a specific tub in the queried range.

*   **`TubLiquidityInfo` Struct:**
    *   **Purpose:** Contains granular, per-tub details about liquidity and accrued assets.
    *   **Fields:**
        *   `tub`: The identifier for the specific tub.
        *   `accrued0`, `accrued1`: `Quad` values representing the amounts of token0 and token1 that have accrued within this tub (e.g., from fees or other mechanisms).
        *   `liquidity`: The amount of liquidity present in this tub, as a `Quad`.
        *   `utilization`: A `Quad` value likely representing how much of the liquidity in this tub is currently being utilized or is considered active.

*   **`LiquidityPosition` Struct:**
    *   **Purpose:** Represents a detailed view of an individual user's liquidity position within a pool.
    *   **Fields:**
        *   `lpNum`: A unique identifier for the liquidity position.
        *   `token0`, `token1`: Addresses of the two tokens in the pool.
        *   `lowerEdge`, `upperEdge`: Integer values defining the lower and upper price boundaries (edges) of the concentrated liquidity position.
        *   `earnEra`: The pool era from which this LP position started earning fees.
        *   Token Amounts (in native units):
            *   `lockedAmount0`, `lockedAmount1`: The amounts of token0 and token1 initially provided and locked in the position.
            *   `availableAmount0`, `availableAmount1`: The amounts of token0 and token1 that are currently available for withdrawal.
            *   `unclaimedFees0`, `unclaimedFees1`: The amounts of token0 and token1 fees that have been earned by this position but not yet collected by the user.
        *   `state`: An `int8` value indicating the current state of the LP position (using `LP_STATE_OPENED`, `LP_STATE_ACTIVE`, `LP_STATE_CLOSED`).

*   **Dependencies:**
    *   Imports `LP.sol` (contents not yet fully detailed, but likely related to LP management).
    *   Uses `Quad` from `src/types/ABDKMathQuad/Quad.sol` for high-precision fixed-point numbers.

## Pool State Interface (`IInfinityPoolState.sol`)

*(Protocol Importance: 10/10)*

The `IInfinityPoolState.sol` file defines the `PoolState` struct, which is the absolute core data structure representing the complete and detailed state of an individual Infinity Pool. While the interface `IInfinityPoolState` itself is empty, the `PoolState` struct it contains is paramount for understanding how a pool stores and manages all its financial and operational data. The comment within the struct definition highlights that the order and type of variables are meticulously arranged for gas efficiency, adhering to EVM storage packing rules. Understanding this struct is critical for anyone diving deep into the pool's internal mechanics, as all pool operations read from and write to this state.

Key elements of the `PoolState` struct include:

*   **Overall Pool Identifiers and Configuration:**
    *   `lpCount (uint256)`: A counter for the total number of unique Liquidity Provider (LP) positions ever created in this pool. Used for assigning new `lpNum` identifiers.
    *   `era (int32)`: The current operational "era" of the pool. Eras are time-based or event-based periods that can influence various mechanisms like fee calculations, swapper behavior, or other time-sensitive parameters.
    *   `tickBin (int32)`: Represents the current active price bin or tick where the pool's spot price resides. This is fundamental for concentrated liquidity, indicating the current discrete price range.
    *   `splits (int32)`: A parameter defining the granularity of the price bins (or "tubs"). A higher `splits` value means finer price distinctions and more numerous bins across the price curve.
    *   `factory (address)`: The address of the `IInfinityPoolFactory` contract that deployed this pool instance.
    *   `token0 (address)`: The contract address of the first token in the pair (canonically, the one with the lower address).
    *   `token1 (address)`: The contract address of the second token in the pair.
    *   `isPoolInitialized (bool)`: A flag indicating whether the pool has been fully initialized and is ready for operations. Typically set to `true` once initial parameters are configured after deployment.

*   **Cached Decimal and Core Financial Parameters (Quad type):**
    *   `tenToPowerDecimals0 (Quad)`: A cached value of 10 raised to the power of `token0`'s decimals. Used for fixed-point arithmetic to convert between base units and decimal-adjusted representations.
    *   `tenToPowerDecimals1 (Quad)`: Similar to `tenToPowerDecimals0`, but for `token1`.
    *   `fee (Quad)`: The base trading fee percentage for swaps in this pool, represented as a high-precision fixed-point number.
    *   `epsilon (Quad)`: A small constant value, likely used as a tolerance in floating-point comparisons or to prevent division-by-zero in certain calculations.
    *   `move2Var (Quad)`: Potentially related to a variance or a component used in dynamic fee calculations or risk modeling (e.g., "move squared variance").
    *   `twapSpread (Quad)`: The spread applied for Time-Weighted Average Price (TWAP) calculations or operations, influencing the effective price for TWAP-based swaps.
    *   `halfspread (Quad)`: Half of the `twapSpread`, likely cached for efficiency in TWAP calculations.

*   **Time, Deflation, and Price State Parameters (Quad type):**
    *   `date (Quad)`: The current internal "date" or timestamp of the pool, represented as a `Quad`. This internal clock might advance differently from `block.timestamp` based on pool activity or `advance()` calls.
    *   `deflator (Quad)`: A value representing the current cumulative deflation factor applied within the pool. This can be used to adjust liquidity values or other metrics over time, effectively reducing their nominal value.
    *   `entryDeflator (Quad)`: The value of the `deflator` at the time of the last significant pool event or the start of the current `era`.
    *   `binFrac (Quad)`: Represents the fractional position of the current spot price *within* the current `tickBin`. It provides a more precise price indication than `tickBin` alone (e.g., if `tickBin` is 100 and `binFrac` is 0.5, the price is halfway through bin 100).
    *   `surplus0 (Quad)`: The amount of `token0` held by the pool that is considered surplus, potentially collected from fees or other mechanisms and not directly backing active liquidity or loans.
    *   `surplus1 (Quad)`: Similar to `surplus0`, but for `token1`.

*   **Core Liquidity and Debt Tracking (Struct-based):**
    *   `minted (BoxcarTubFrame.Info)`: Tracks the total amount of liquidity minted or provided across different price bins/tubs. `BoxcarTubFrame.Info` is a data structure designed to manage and account for values (like liquidity) distributed across a series of discrete bins, allowing for efficient updates and queries over ranges.
    *   `lent (JumpyFallback.Info)`: Represents the total amount of liquidity currently lent out or utilized by Swapper positions. `JumpyFallback.Info` is a sophisticated accumulator that tracks a value that can change over time, potentially with jumps or non-linear adjustments, and includes fallback mechanisms for periods of no change.
    *   `lentEnd (DropFaberTotals.Info[2])`: An array (one element per token) likely tracking the total amount of lent liquidity that is scheduled to end or expire at specific future deadlines. `DropFaberTotals.Info` is a structure for managing sums of values that "drop" off or expire at set future points in time.
    *   `used (JumpyFallback.Info)`: Tracks the utilization ratio of the available liquidity, possibly represented as an inflated value (i.e., scaled for precision). This helps gauge how much of the pool's capital is actively engaged.
    *   `owed (JumpyFallback.Info)`: Represents the total amount of assets owed back to the pool by Swapper positions (i.e., outstanding debt), often referred to as "omega liquidity" and potentially inflated for internal calculations.
    *   `joinStaged (GapStagedFrame.Info)`: Manages liquidity that has been staged to join the pool but is not yet active, possibly awaiting certain conditions or an epoch change. `GapStagedFrame.Info` likely handles values that are added in stages or with gaps.
    *   `dayMove (BucketRolling.Info)`: Tracks liquidity movements or volume over a rolling daily period. `BucketRolling.Info` is a data structure for maintaining rolling sums or averages over fixed time buckets (e.g., daily buckets for a 30-day rolling volume).
    *   `expire (DeadlineSet.Info[2])`: An array (one element per token) managing deadlines for expiring liquidity or other time-sensitive positions. `DeadlineSet.Info` is designed to track a set of upcoming deadlines and associated values.

*   **Swapper Lifecycle, Flow, and Fee Management (Struct-based):**
    *   `resets (DeadlineFlag.Info)`: Manages flags or boolean states associated with deadlines, specifically for Swapper position resets. The comment indicates it's similar to `DeadlineJumps` but for boolean flags rather than `Quad` values. `DeadlineFlag.Info` tracks true/false states over time-based deadlines.
    *   `flowHat (JumpyAnchorFaber.Info[2])`: An array (one element per token) likely tracking the target or capped flow rates related to Swapper activities or fee distributions. `JumpyAnchorFaber.Info` is an advanced accumulator that might track a value anchored to a target but subject to jumps or Faber-system-like decay/growth.
    *   `flowDot (EraBoxcarMidSum.Info[2][2])`: A 2D array (token, then perhaps another dimension like borrow/lend) tracking the rate of change (derivative, or "dot" product in calculus terms) of flows, summed up per era across price bins. `EraBoxcarMidSum.Info` sums values within discrete eras and bins, focusing on mid-points or averages.
    *   `fees (GrowthSplitFrame.Info[2])`: An array (one element per token) that accumulates trading fees earned by the pool. `GrowthSplitFrame.Info` is a structure to track values that grow over time, potentially with splits or distributions across different categories or eras.
    *   `offRamp (BoxcarTubFrame.Info)`: Tracks liquidity that is designated for withdrawal or "off-ramping" from the pool, managed across price bins.

*   **Netting, Price Runoff, and Reserve Tracking (Struct-based):**
    *   `netting (NettingGrowth.Info[2])`: An array (one element per token) that handles the netting of internal obligations or flows, accumulating net growth. `NettingGrowth.Info` tracks a value that grows after accounting for positive and negative contributions.
    *   `priceRun (SparseFloat.Info[2])`: An array (one element per token) that likely tracks cumulative price movements or "runoff" over time, possibly for TWAP calculations or impermanent loss metrics. `SparseFloat.Info` is a structure to represent and manage sparsely populated floating-point-like data, useful when many potential values are zero.
    *   `reserveRun (SparseFloat.Info[2])`: Similar to `priceRun`, but likely tracks changes in token reserves over time.

*   **Dynamic Position Storage and Cappers (Arrays and Mapping):**
    *   `lps (LP.Info[])`: A dynamic array storing detailed information for each Liquidity Provider (LP) position in the pool. `LP.Info` (from `src/libraries/external/LP.sol`) typically includes details like the LP's range (`lowerEdge`, `upperEdge`), the amount of liquidity provided, earned fees, and current state (e.g., active, closed). This array allows iteration over all LPs, although direct access by index is more common for specific LP operations.
    *   `swappers (SwapperInternal.Info[])`: A dynamic array holding the state for each active Swapper position (loan or automated strategy). `SwapperInternal.Info` (from `src/libraries/external/Swapper.sol`) contains comprehensive data about the swapper, such as its collateral, debt, operating parameters, and current status.
    *   `capper (mapping(bytes32 => Capper.Info))`: A mapping used to implement cappers or limits on certain pool parameters, likely on a per-tick and per-token basis. The key is a `bytes32` hash, probably derived from `(tick, tokenAddress)` to uniquely identify the capper. `Capper.Info` (from `src/libraries/internal/Capper.sol`) would store the specific cap values and related state for that tick/token combination. This mechanism can be used to enforce risk limits, such as maximum exposure or concentration in a specific price range.

## Swapper Internals Library (`SwapperInternal.sol`)

*(Protocol Importance: 10/10)*

The `SwapperInternal.sol` file defines a crucial library responsible for managing the internal state, calculations, and lifecycle logic of individual "Swapper" positions within an Infinity Pool. Swappers represent automated strategies, loans, or other complex positions that interact with the pool's liquidity. This library does not define a contract itself but provides the `SwapperInternal.Info` struct and a suite of functions to operate on instances of this struct, typically in conjunction with the main `PoolState`.

The `SwapperInternal.Info` struct is stored within `PoolState.swappers[]` for each active swapper.

### `SwapperInternal.Info` Struct

This struct encapsulates all the necessary data for a single swapper position:

*   `twapUntil (OptInt256)`: An optional era marker. If defined, it signifies the end era for a Time-Weighted Average Price (TWAP) mechanism associated with this swapper. The swapper might have a fixed exposure to one token until this era.
*   `deadEra (OptInt256)`: An optional era marker. If defined, it indicates the era in which the swapper position expires or is considered "dead." Operations related to the swapper may be disallowed or behave differently after this era.
*   `tokenMix (Quad)`: A high-precision fixed-point number representing the swapper's current exposure or allocation mix between `token0` and `token1`. Its interpretation can change based on whether `twapUntil` is active.
    *   If no TWAP (`!twapUntil.isDefined()`): `tokenMix` usually represents the fraction of the swapper's value exposed to `token1` (e.g., `tokenMix = 0` means 100% `token0`, `tokenMix = 1` means 100% `token1`).
    *   If TWAP is active: `tokenMix` represents the fixed amount of the `self.token` the swapper is holding during the TWAP period.
*   `unlockDate (Quad)`: The internal pool "date" (timestamp) at which this swapper position becomes unlocked, allowing for modifications, closure, or other lifecycle events.
*   `oweLimit (Quad)`: The total limit of liquidity (in inflated units) that this swapper position owes. This is a key parameter established at creation and used in various calculations.
*   `lentCapacity0 (Quad)`: The capacity of the swapper in terms of `token0`, derived from the liquidity lent to it, expressed in inflated units. Cached for efficiency.
*   `lentCapacity1 (Quad)`: Similar to `lentCapacity0`, but for `token1`.
*   `owed (Quad[])`: A dynamic array where each element `owed[i]` stores the amount of liquidity owed by the swapper in the `i`-th price bin relative to `startBin`. These values are stored in "inflated" terms (i.e., adjusted by the inverse of the pool's deflator at the time of swapper creation) to make them time-independent within the struct.
*   `lent (Quad[])`: Similar to `owed`, this array stores the amount of liquidity lent to the swapper in each respective price bin, also in inflated, time-independent units.
*   `minted (Quad[])`: An array storing the amount of liquidity minted or provided by the swapper in each price bin, effectively representing its collateral contribution. These are also likely in inflated units.
*   `startBin (int32)`: The index of the starting price bin for this swapper's liquidity range.
*   `strikeBin (int32)`: The index of a specific "strike" price bin. This is particularly relevant for swappers that have option-like characteristics or for determining reference prices in TWAP calculations.
*   `owner (address)`: The Ethereum address of the account that owns and controls this swapper position.
*   `token (bool)`: A boolean flag indicating the "fixed token" when a TWAP is active. Typically, `false` (or `Z`) refers to `token0`, and `true` (or `I`) refers to `token1`. The swapper maintains a fixed exposure to this token during the TWAP period.

### Custom Error Types

The library defines several custom errors to provide specific feedback upon failure:

*   `SwapperExpired(int256 era, int256 deadEra)`: Thrown if an operation is attempted on a swapper that has already passed its `deadEra`.
*   `DeadlineDoesNotCoverLockInDate(int256 deadEra, Quad unlockDate)`: Thrown if the swapper's `deadEra` is earlier than its `unlockDate`, which is an invalid state.
*   `InvalidTokenMixFraction(Quad tokenMix)`: Thrown if the provided `tokenMix` is outside its valid range (e.g., less than 0 or greater than 1 when no TWAP is active, or exceeds capacity during TWAP).
*   `TWAPEndsBeforeDeadline(int256 depegEra, int256 deadEra)`: Thrown if the `twapUntil` era is set after the `deadEra`.
*   `FixedTokenExceedsCapacity(bool token, Quad tokenMix, Quad capacity)`: Thrown during TWAP validation if the specified `tokenMix` (amount of fixed token) exceeds the swapper's calculated capacity for that token.

### Key Library Functions

#### Initialization and Validation

*   **`init(Info memory self, PoolState storage pool) external view returns (Info memory)`**
    *   **Purpose:** Initializes a `SwapperInternal.Info` struct *in memory* based on provided initial `owed` and `lent` arrays (within `self`) and the current `pool` state. It does not modify blockchain state directly but prepares an `Info` struct.
    *   **Logic:**
        1.  Calculates an `inflator = POSITIVE_ONE / pool.deflator` to convert time-dependent values to time-independent (inflated) representations for storage within the `Info` struct.
        2.  Iterates through the `self.owed` array (assumed to be passed in with nominal values): inflates each `owed[i]` value and stores it back.
        3.  Calculates `sum0` (total `token0` equivalent) and `sum1` (total `token1` equivalent) from the inflated `owed` amounts across all bins, using `sqrtStrike` for conversion.
        4.  Sets `self.oweLimit = (sum0 * sum1).sqrt()`, representing the geometric mean of the total owed principal in terms of both tokens, in inflated units.
        5.  A similar process is followed for the `self.lent` array: inflates `lent[i]`, then sums up their `token0` and `token1` equivalents (`sum0_lent`, `sum1_lent`).
        6.  Sets `self.lentCapacity0 = pool.epsilon * sum0_lent` and `self.lentCapacity1 = pool.epsilon * sum1_lent`, representing the lent capacity in each token (inflated).
    *   **Returns:** The modified `Info memory self` struct with calculated fields populated.
    *   **Usage:** Typically used by external contracts or off-chain logic to construct a valid `SwapperInternal.Info` object before it's formally added to the `PoolState.swappers` array.

*   **`validate(Info storage self, PoolState storage pool) public`**
    *   **Purpose:** Performs comprehensive validation checks on a `SwapperInternal.Info` struct (usually one already in `storage`) to ensure its parameters are consistent and adhere to protocol rules. This is critical before creating a new swapper or after modifying an existing one.
    *   **Checks Performed:**
        1.  **Deadline vs. Unlock Date:** Ensures `self.deadEra` (if defined) is not earlier than `self.unlockDate`. Reverts with `DeadlineDoesNotCoverLockInDate` if invalid.
        2.  **Swapper Liveness:** Calls `checkAlive(self, pool)` to ensure the swapper isn't already expired if the context requires an active swapper.
        3.  **Token Mix Sanity (General):** `self.tokenMix` must be non-negative. Reverts with `InvalidTokenMixFraction` if negative.
        4.  **Token Mix (No TWAP):** If `!self.twapUntil.isDefined()`, `self.tokenMix` must be less than or equal to `POSITIVE_ONE`. Reverts with `InvalidTokenMixFraction` if it exceeds one.
        5.  **Token Mix (With TWAP):** If `self.twapUntil.isDefined()`:
            *   `self.twapUntil` (depegEra) must not occur after `self.deadEra` (if defined). Reverts with `TWAPEndsBeforeDeadline`.
            *   Calculates the swapper's `capacity` for the `self.token` (the fixed token during TWAP) at the `twapUntil` era. This capacity depends on whether the swapper expires, and if so, when it expires relative to the TWAP end.
            *   If `self.tokenMix` is `isInfinity`, it's capped at the calculated `capacity`.
            *   Otherwise, `self.tokenMix` (the amount of fixed token) must not exceed this `capacity`. Reverts with `FixedTokenExceedsCapacity` if it does.
    *   **Side Effects:** Reverts with specific errors if any validation check fails.

*   **`signed(bool enable, Quad amount) internal pure returns (Quad)`**
    *   **Purpose:** A simple utility function to conditionally negate a `Quad` value.
    *   **Logic:** Returns `amount` if `enable` is `true`, otherwise returns `-amount`.
    *   **Usage:** Used internally within other functions where a value might need to be treated as positive or negative based on a condition (e.g., direction of a trade or flow).

*   **`checkAlive(Info storage self, PoolState storage pool) internal view`**
    *   **Purpose:** Checks if the swapper position is currently considered "alive" (i.e., not expired).
    *   **Logic:** If `self.deadEra` is defined, it compares the current `pool.date` with the `eraDate(self.deadEra.get())`. If `pool.date` is greater than or equal to the swapper's death date, it means the swapper has expired.
    *   **Side Effects:** Reverts with `SwapperExpired(pool.era, self.deadEra.get())` if the swapper is found to be expired.

#### Value, Exposure, and Financial State Calculation

*   **`noTwap(Info memory self, PoolState storage pool, bool token, Quad tokenMix) internal view returns (Quad)`**
    *   **Purpose:** Calculates the backing value of the swapper for the specified `token` when no TWAP is active (either not defined or already expired). This is a sub-function, often called by `backing()`.
    *   **Logic:** Handles two main scenarios:
        1.  **Swapper Expires (`self.deadEra.isDefined()`):** The calculation involves an `expiryFraction` based on how close the current `pool.date` is to the `self.deadEra.get()`. The value is a blend of `pool.epsilon * self.oweLimit` (adjusted by strike price) and `self.lentCapacity` (for the respective token), scaled by `expiryFraction` and `tokenMix`, and finally multiplied by `pool.deflator`.
        2.  **Swapper Does Not Expire:** The value is calculated as `pool.epsilon * self.oweLimit` adjusted by `tokenMix` and the appropriate `sqrtStrike` for the chosen `token`, then multiplied by `pool.deflator`. This represents a fixed-term loan scenario without TWAP.
    *   **Returns:** The calculated backing value for the specified `token` in current (non-inflated) terms.

*   **`endTokenMix(Info storage self, PoolState storage pool) internal view returns (Quad res)`**
    *   **Purpose:** Computes the effective `tokenMix` of the swapper at the precise moment its TWAP period ends. This is important because the swapper's exposure strategy might change once the TWAP concludes.
    *   **Logic:**
        1.  If no TWAP is defined (`!self.twapUntil.isDefined()`), it simply returns the current `self.tokenMix`.
        2.  If a TWAP is defined: It determines the `fixedToken` (the token whose exposure is fixed during TWAP).
        3.  Calculates `twapDeflator` (pool's deflator at the `twapUntil` era).
        4.  Computes the `capacity` of the swapper for the `fixedToken` at the `twapUntil` era. This calculation is complex and considers:
            *   Whether the swapper itself expires (`self.deadEra.isDefined()`).
            *   If the swapper's expiration coincides with the TWAP end (`self.deadEra.get() == depegEra`).
            *   If they expire at different times, it involves `deadDeflator` (deflator at swapper's death) and a blend of `oweLimit` and `lentCapacity`.
            *   If the swapper never expires, capacity is based on `self.oweLimit` and `strikeBin`.
        5.  Calculates a `ratio = self.tokenMix / vars.capacity` (where `self.tokenMix` here is the *amount* of fixed token).
        6.  The final `res` (new `tokenMix` fraction) is derived from this `ratio`, ensuring it's clamped between 0 and 1.
    *   **Returns:** The new `tokenMix` (fractional exposure) effective after the TWAP period.

*   **`backing(Info memory self, PoolState storage pool, bool token) internal view returns (Quad)`**
    *   **Purpose:** Calculates the current backing value of the swapper position for the specified `token` (either `Z` for `token0` or `I` for `token1`). This is a key function to determine the swapper's gross value from one token's perspective.
    *   **Logic (inferred & based on `noTwap` and typical TWAP logic):**
        1.  Calls `checkAlive(self, pool)` to ensure the swapper hasn't expired.
        2.  Determines if a TWAP is currently active (`self.twapUntil.isDefined()` and `pool.date < eraDate(self.twapUntil.get())`).
        3.  **If TWAP is active:** The backing for the `self.token` (the fixed token) is `self.tokenMix` (amount of fixed token) multiplied by `pool.deflator`. For the other token (the variable one), it's more complex, likely involving `self.oweLimit` and the portion not allocated to the fixed token, adjusted by `strikeBin` and `pool.deflator`.
        4.  **If TWAP is not active (or expired):** Calls `noTwap(self, pool, token, self.tokenMix)` to get the backing.
    *   **Returns:** The current backing value of the swapper for the specified `token`.

*   **`collateral(Info memory self, PoolState storage pool, bool token) internal view returns (Quad)`**
    *   **Purpose:** Calculates the value of the collateral provided by the swapper for the specified `token`.
    *   **Logic (inferred):**
        1.  Calls `checkAlive(self, pool)`.
        2.  Likely iterates through the `self.minted` array (which holds the swapper's collateral contributions per bin in inflated units).
        3.  For each `minted[i]`, it would convert this amount to the equivalent value in the specified `token` using `sqrtStrike(pool.splits, self.startBin + i)`.
        4.  Sums these values and multiplies by `pool.deflator` to get the current collateral value.
    *   **Returns:** The total current value of the swapper's collateral in terms of the specified `token`.

*   **`interest(Info memory self, PoolState storage pool, bool token) internal view returns (Quad)`**
    *   **Purpose:** Calculates the interest owed by the swapper in terms of the specified `token`.
    *   **Logic (inferred):** This is complex and would involve comparing the current value of what the swapper *owes* (derived from `self.owed` array, adjusted for current `pool.deflator` and converted to the perspective of `token`) against the initial principal lent. The difference would be interest. It needs to account for the `strikeBin` and `tokenMix` to correctly attribute value.
        1.  Calls `checkAlive(self, pool)`.
        2.  Calculates total current value of `self.owed` in terms of `token` (deflated).
        3.  Calculates total current value of `self.lent` (initial principal) in terms of `token` (deflated).
        4.  Interest = (Current Value of Owed) - (Current Value of Lent). Clamped at zero if negative.
    *   **Returns:** The calculated interest owed by the swapper for the specified `token`.

*   **`net(Info memory self, PoolState storage pool, bool token) internal view returns (Quad)`**
    *   **Purpose:** Calculates the net value of the swapper position for the specified `token`. This is essentially (Collateral - Backing_of_Debt + Interest_Earned_If_Any_Or_Minus_Interest_Owed).
    *   **Logic (inferred):**
        1.  `currentCollateral = collateral(self, pool, token)`
        2.  `currentBackingOfDebt = backing(self, pool, token)` (where backing here refers to the value of the assets the swapper *borrowed* or is liable for).
        3.  Net Value = `currentCollateral - currentBackingOfDebt`. This might be further adjusted by accrued interest if the swapper also *earns* interest, but typically swappers are borrowers.
    *   **Returns:** The net value of the swapper position in terms of the specified `token`.

#### State Modification, Settlement, and Specific Queries

*   **`settle(Info storage self, PoolState storage pool, bool token, Quad amount) internal returns (Quad actualAmount, Quad remainingAmount)`** (Signature inferred)
    *   **Purpose:** Attempts to settle a portion or all of a swapper's debt or position using the provided `amount` of the specified `token`.
    *   **Logic (inferred):**
        1.  Calls `checkAlive(self, pool)`.
        2.  Determines the swapper's current liability in the specified `token` (e.g., by calling `backing(self, pool, token)` or a similar internal valuation).
        3.  Compares the provided `amount` with the liability.
        4.  `actualAmount` settled would be the minimum of `amount` and the liability.
        5.  Updates `self.owed`, `self.lent`, or other relevant fields in the `Info` struct to reflect the settlement. This would involve deflating `actualAmount` and adjusting the per-bin values in `self.owed` arrays, which is complex.
        6.  `remainingAmount` would be any portion of the input `amount` not used for settlement (if `amount` > liability), or zero.
    *   **Returns:** `actualAmount` (the amount effectively settled) and `remainingAmount` (any unused portion of the input).
    *   **Note:** Modifying `self.owed` and `self.lent` arrays directly is complex due to their inflated nature and per-bin distribution. Settlement likely involves more sophisticated internal bookkeeping or interaction with pool-level functions.

*   **`peek(Info memory self, PoolState storage pool, bool token, int256 era) internal view returns (Quad)`** (Signature inferred)
    *   **Purpose:** Allows \"peeking\" into the projected backing value of the swapper for a specified `token` at a future `era`.
    *   **Logic (inferred):**
        1.  Creates a temporary, modified `PoolState` or adjusts relevant parameters (like `pool.date` and `pool.deflator`) to simulate the state at the target `era`.
        2.  Calls `backing(self, /*modified_pool_state_for_era*/, token)` with this simulated future state.
    *   **Returns:** The projected backing value of the swapper at the specified future `era`.

*   **`flowing(Info storage self, bool token) internal view returns (Quad)`**
    *   **Purpose:** Determines the amount of a given `token` that is considered \"flowing\" from or to the swapper. The \"Ignore\" comment in the source code for this function suggests its role might be nuanced or for a very specific internal calculation.
    *   **Logic (as per visible code snippet):**
        1.  If `!self.twapUntil.isDefined()`: `res = self.oweLimit * ((token == Z) ? (POSITIVE_ONE - self.tokenMix) : self.tokenMix)`. This calculates the exposure to the token based on `oweLimit` and `tokenMix`.
        2.  If TWAP is defined (`self.twapUntil.isDefined()`):
            *   `fixedToken = self.token` (the token with fixed exposure during TWAP).
            *   If the queried `token` is the `fixedToken`, `res = POSITIVE_ZERO` (meaning the fixed portion isn't \"flowing\" in this context).
            *   If the queried `token` is the *other* token, `res = self.oweLimit`.
    *   **Returns:** The calculated \"flowing\" amount. The exact semantic meaning of \"flowing\" here requires deeper context, especially given the \"Ignore\" comment.

*   **`updateFees(Info storage self, PoolState storage pool, ...)`** (General Description)
    *   **Purpose:** Likely responsible for updating fee-related metrics within the `Info` struct or interacting with the pool's fee mechanisms based on swapper activity or passage of time.
    *   **Logic (inferred):** Could involve accruing fees owed by the swapper, or distributing fees earned by the swapper's collateral, interacting with `pool.fees` or similar global fee trackers.

*   **`updateDebtUponTrade(Info storage self, PoolState storage pool, ...)`** (General Description)
    *   **Purpose:** Adjusts the swapper's debt (e.g., `self.owed` arrays, `self.oweLimit`) after a trade occurs that involves the swapper's position or affects its valuation.
    *   **Logic (inferred):** When the pool's price (`tickBin`, `binFrac`) changes or when a swapper's position is directly involved in a swap, its liabilities can change. This function would update the `Info` struct to reflect these changes, ensuring debt is accurately tracked.

## Pool Helper (`PoolHelper.sol`)

*(Protocol Importance: 7/10)*

`PoolHelper.sol` provides a collection of utility and helper functions crucial for the Infinity Pools protocol's mathematical calculations and state interactions. It serves a dual role:
1.  It defines numerous `internal` and `pure` free-standing mathematical functions. These functions handle complex calculations related to price curves, binning logic, tick conversions, time/era management, and other core algorithmic components of the Infinity Pools system. They operate on primitive types and `Quad` fixed-point numbers, leveraging types and constants from `ABDKMathQuad.sol` and `Constants.sol`.
2.  It includes a `library PoolHelper` which offers convenient, state-aware helper functions that operate directly on `PoolState storage pool`. These library functions often wrap or utilize the free-standing mathematical functions to provide higher-level views or calculations based on the current state of a pool.

This file is essential for abstracting complex mathematical logic and providing reusable components for other contracts in the protocol. It makes extensive use of custom data structures for managing piecewise functions and frames, such as `BoxcarTubFrame`, `JumpyFallback`, `GrowthSplitFrame`, and `PiecewiseGrowthNew`, imported from their respective library files.

### Free-standing Utility Functions

These functions are generally `pure` or `view` (if they interact with storage structs passed as arguments, like `fluidAt`) and form the mathematical backbone for many pool operations.

#### 1. Bin, Split, and Tick Mathematics
These functions are fundamental for converting between different representations of price, discretizing price ranges into bins, and handling the "splits" parameter which determines the granularity of these bins.

*   **`subSplits(int256 splits) pure returns (int256)`**: Calculates `splits - MIN_SPLITS`. `MIN_SPLITS` is a constant defining the minimum number of splits.
*   **`logBin(int256 splits) pure returns (Quad)`**: Computes the logarithmic width of a single bin, derived from `LOG1PPC` (log(1+p_c)) and the number of sub-splits (`1 << (splits - MIN_SPLITS)`). This is a key parameter for price calculations.
*   **`h(int256 splits) pure returns (Quad)`**: Calculates `exp(logBin(splits) / 2)`. This factor is likely used in geometric mean calculations or square root price conversions related to bin width.
*   **`BINS(int256 splits) pure returns (int256)`**: Calculates the total number of bins for a given number of splits: `1 << splits`.
*   **`binStrike(int256 splits, int256 bin) pure returns (Quad)`**: Computes the strike price for a given `bin` index. It uses `logBin` and effectively calculates `exp(logBin(splits) * (bin_normalized_index))` where `bin_normalized_index` is `(fromInt256(bin) - (fromInt256(BINS(splits)) / POSITIVE_TWO) + HALF)`.
*   **`sqrtStrike(int256 splits, int256 bin) pure returns (Quad)`**: Computes the square root of the strike price for a given `bin`. `exp(logBin(splits)/2 * (bin_normalized_index))`.
*   **`mid(int256 splits, int256 tickBin) pure returns (Quad)`**: An alias for `binStrike(splits, tickBin)`, returning the strike price of the `tickBin`.
*   **`fracBin(int256 splits, Quad startPrice) pure returns (Quad)`**: Converts a given `startPrice` into a fractional bin index. This involves taking the logarithm of the price and normalizing by `logBin(splits)`, then adjusting relative to the center of the bin range.
*   **`fracPrice(int256 splits, int256 tickBin, Quad binFrac) pure returns (Quad)`**: The inverse of `fracBin`. Converts a `tickBin` and a fractional component `binFrac` back into a price.
*   **`tickBin(Quad fracBin) pure returns (int256)`**: Converts a fractional bin index `fracBin` into an integer `tickBin` by taking the floor (via `intoInt256`).
*   **`tickBin(int256 splits, Quad startPrice) pure returns (int256)`**: Overloaded function. Converts a `startPrice` directly to an integer `tickBin` by first calling `fracBin` and then `tickBin`.
*   **`binLowSqrt(int256 splits, int256 bin) pure returns (Quad)`**: Calculates the square root of the price at the lower edge of a given `bin`.
*   **`binLowTick(int256 splits, int256 bin) pure returns (int256)`**: Calculates the tick corresponding to the lower edge of a `bin`, adjusted by `TICK_SUB_SLITS`.
*   **`logTick() pure returns (Quad)`**: Computes the logarithmic width of a single tick, `LOG1PPC / (1 << TICK_SUB_SLITS)`. `TICK_SUB_SLITS` defines tick granularity.

#### 2. Tub Mathematics
"Tubs" appear to be coarser-grained aggregations or regions related to bins or edges, potentially used for range orders or broader liquidity management.

*   **`tubLowSqrt(int256 tub) pure returns (Quad)`**: Calculates the square root price at the lower edge of a "tub", using `edgeSqrtPrice(tub - TUBS / 2)`.
*   **`tubLowTick(int256 tub) pure returns (int256)`**: Calculates the tick corresponding to the lower edge of a "tub".
*   **`lowEdgeTub(int256 edge) pure returns (int256)`**: Converts an "edge" index to a "tub" index: `edge + TUBS / 2`.
*   **`tubLowEdge(int256 tub) pure returns (int256)`**: Inverse of `lowEdgeTub`. Converts a "tub" index to its corresponding lower "edge" index: `tub - TUBS / 2`.

#### 3. Price and Edge Mathematics
These functions deal with price calculations, often in logarithmic space or square root space, related to "edges" (likely boundaries of ticks or bins).

*   **`edgePrice(int256 edge) pure returns (Quad)`**: Calculates price from an "edge" index: `exp(LOG1PPC * edge)`.
*   **`edgeSqrtPrice(int256 edge) pure returns (Quad)`**: Calculates square root price from an "edge" index: `exp(LOG1PPC/2 * edge)`.
*   **`tickSqrtPrice(int256 tick) pure returns (Quad)`**: Calculates the square root price for a given `tick` using `logTick()`.

#### 4. Liquidity, Gamma, and Fee Calculations
These functions are more complex and often involve custom structs representing liquidity profiles or fee states.

*   **`exFee(Quad fees) pure returns (Quad)`**: Calculates `1 - fees`, representing the portion remaining after fees.
*   **`fluidAt(BoxcarTubFrame.Info storage self, int256 bin, int256 splits) view returns (Quad)`**: Retrieves the "fluid" value from a `BoxcarTubFrame.Info` struct at a specific (adjusted) `bin`. This represents a form of liquidity or density within the BoxcarTubFrame structure.
*   **`liquid(BoxcarTubFrame.Info storage self, int256 bin, int256 splits, Quad gamma, Quad deflator) view returns (Quad)`**: Calculates "liquid" amount by taking `fluidAt` and subtracting `gamma * deflator`, floored at zero. This seems to be an effective liquidity calculation after accounting for some gamma exposure and deflation factor.
*   **`gamma(JumpyFallback.Info storage lent, BoxcarTubFrame.Info storage offRamp, int256 poolEra, int256 splits, int256 tickBin) returns (Quad)`**: Calculates a `gamma` value. It involves querying `lent.nowAt(...)` (from `JumpyFallback`) and `offRamp.active(...)` (from `BoxcarTubFrame`), representing a difference between two dynamic values based on the current pool state. This is likely related to impermanent loss calculations or market risk exposure adjustment.
*   **`spotFee(GrowthSplitFrame.Info[2] storage fees, int256 splits, bool inToken, Quad accrual, Quad /* unused */)`**: Updates accrued fees within a `PiecewiseGrowthNew.Info` struct (obtained from `fees[inToken ? 1 : 0].live(splits)`). The last `Quad` parameter in the signature appears unused in the provided snippet.

#### 5. Time, Era, and Date Conversions
These functions handle conversions between different time units used by the protocol: block timestamps, "dates" (likely days or fractions of days as `Quad`), and "eras" (protocol-specific time steps, possibly related to `pool.era`).

*   **`eraDay(int256 era) pure returns (int256)`**: Converts an `era` to a day index (`era >> 11`).
*   **`dayEra(int256 day) pure returns (int256)`**: Converts a day index to an `era` (`day << 11`).
*   **`dayEras() pure returns (int256)`**: Returns the number of eras in one day (`1 << 11`).
*   **`dateEra(Quad date) pure returns (int256)`**: Converts a `Quad` date value (presumably in days) to an `era` by multiplying with `dayEras()` and taking the floor.
*   **`eraDate(int256 era) pure returns (Quad)`**: Converts an `era` to a `Quad` date value.
*   **`timestampDate(uint256 timestamp) pure returns (Quad)`**: Converts a Unix `timestamp` to a `Quad` date value, by subtracting `EPOCH` and dividing by the number of seconds in a day.

#### 6. General Math Utilities
Standard mathematical utilities for integer arithmetic.

*   **`floorMod(int256 x, int256 y) pure returns (int256)`**: Calculates `x mod y` ensuring the result has the same sign as `y` or is zero. Useful for consistent modulo operations with negative numbers.
*   **`floorDiv(int256 x, int256 y) pure returns (int256)`**: Calculates `floor(x / y)`, correctly handling negative numbers to ensure division rounds towards negative infinity.

#### 7. Deflator Step Utility
*   **`getDeflatorStep(uint256 index) pure returns (Quad)`**: Returns a pre-defined deflator step value (`DEFLATOR_STEP_0` through `DEFLATOR_STEP_12` from `Constants.sol`) based on an `index` (0-12). This is likely used for implementing a step-wise deflator mechanism in the pool.

### Library `PoolHelper`

This library provides functions that operate on `PoolState storage pool`, offering convenient access to derived values. Many of these functions wrap internal, file-level underscore-prefixed helper functions also defined in `PoolHelper.sol`.

*   **`epsilon_(PoolState storage pool) public view returns (Quad)`**:
    *   **Purpose:** Returns the `pool.epsilon` value directly from the `PoolState` struct.
    *   **Returns:** The `epsilon` value of the pool.

*   **`logBin(PoolState storage pool) public view returns (Quad)`**:
    *   **Purpose:** Calculates the logarithmic width of a single bin for the given pool's configuration.
    *   **Logic:** Calls the internal `_logBin(pool)`, which in turn calls the free-standing `logBin(pool.splits)` using the pool's current `splits` value.
    *   **Returns:** The `logBin` value for the pool's split configuration.

*   **`BINS(PoolState storage pool) public view returns (int256)`**:
    *   **Purpose:** Calculates the total number of bins for the given pool's configuration.
    *   **Logic:** Calls the internal `_BINS(pool)`, which in turn calls the free-standing `BINS(pool.splits)` using the pool's current `splits` value.
    *   **Returns:** The total number of bins for the pool's split configuration.

*   **`sqrtMid(PoolState storage pool) public view returns (Quad)`**:
    *   **Purpose:** Calculates the square root of the middle/strike price of the pool's current `tickBin`.
    *   **Logic:** Calls the internal `_sqrtMid(pool)`, which uses the free-standing `sqrtStrike(pool.splits, pool.tickBin)` with the pool's current `splits` and `tickBin`.
    *   **Returns:** The square root of the current mid-price.

*   **`mid(PoolState storage pool) public view returns (Quad)`**:
    *   **Purpose:** Calculates the middle/strike price of the pool's current `tickBin`.
    *   **Logic:** Calls the internal `_mid(pool)`, which uses the free-standing `mid(pool.splits, pool.tickBin)` with the pool's current `splits` and `tickBin`.
    *   **Returns:** The current mid-price.

*   **`liquid(PoolState storage pool) public returns (Quad)`**:
    *   **Purpose:** Calculates the current "liquid" amount in the pool. This is a complex calculation involving multiple components of the `PoolState`.
    *   **Logic:** Calls the internal `_liquid(pool)`.
        *   `_liquid` first calculates `gamma` by calling the free-standing `gamma(pool.lent, pool.offRamp, pool.era, pool.splits, pool.tickBin)` using various state variables from the pool.
        *   Then, it calls the free-standing `liquid(pool.minted, pool.tickBin, pool.splits, gamma, pool.deflator)` to get the final liquid value, using the calculated `gamma` and other pool state variables.
    *   **Returns:** The calculated liquid amount.

### Internal Underscore-Prefixed Helper Functions

These functions are `internal` (or `private` if not specified, default visibility for free functions) to the `PoolHelper.sol` file and are primarily called by the public functions in the `PoolHelper` library. They take `PoolState storage pool` as an argument and typically delegate to the free-standing mathematical functions.

*   **`_logBin(PoolState storage pool) view returns (Quad)`**: Retrieves `pool.splits` and calls the free-standing `logBin(splits)`.
*   **`_BINS(PoolState storage pool) view returns (int256)`**: Retrieves `pool.splits` and calls the free-standing `BINS(splits)`.
*   **`_sqrtMid(PoolState storage pool) view returns (Quad)`**: Retrieves `pool.splits` and `pool.tickBin` and calls `sqrtStrike(splits, tickBin)`.
*   **`_mid(PoolState storage pool) view returns (Quad)`**: Retrieves `pool.splits` and `pool.tickBin` and calls `mid(splits, tickBin)`.
*   **`_liquid(PoolState storage pool) returns (Quad)`**: Orchestrates the calculation of the pool's liquid amount by calling the free-standing `gamma(...)` and `liquid(...)` functions with appropriate parameters from `PoolState`.

## Payment Callback Interface (`IInfinityPoolPaymentCallback.sol`)

*(Protocol Importance: 6/10)*

The `IInfinityPoolPaymentCallback.sol` interface defines a standardized callback function for contracts that receive token transfers from an Infinity Pool and need to execute logic in response. This pattern is commonly used for operations like flash loans or more complex multi-step interactions where the pool sends tokens out and requires confirmation or subsequent actions from the recipient within the same transaction.

Key elements:

*   **`infinityPoolPaymentCallback(int256 amount0, int256 amount1, bytes calldata data)` Function:**
    *   **Purpose:** This is the sole function in the interface. It is designed to be called by an Infinity Pool *after* it has transferred `amount0` of token0 and `amount1` of token1 to the contract implementing this interface.
    *   **Parameters:**
        *   `amount0`: The net amount of token0 transferred from the pool to the callback contract.
        *   `amount1`: The net amount of token1 transferred from the pool to the callback contract.
        *   `data`: Arbitrary data that can be passed by the original initiator of the pool action. This allows the callback recipient to receive context or instructions specific to the transaction.
    *   **Usage Context:** A typical use case is a flash loan. A user requests a flash loan from the pool, specifying the callback contract (which implements this interface) and any `data`. The pool transfers the requested tokens to the callback contract and then calls `infinityPoolPaymentCallback` on it. The callback contract then executes its logic (e.g., arbitrage, liquidations) and, before the function (and transaction) ends, must return the borrowed tokens plus any required fees to the pool.

*   **Dependencies:** This interface is self-contained and does not import other contracts or libraries.

## NewLoan Library (`NewLoan.sol`)

*(Protocol Importance: 9/10)*

The `NewLoan.sol` library is a cornerstone of the Infinity Pools protocol, encapsulating the sophisticated financial engineering required to create new "Swapper" positions. Swappers are versatile on-chain instruments that can represent loans, leveraged positions, or other structured financial products. This library's `newLoan` function is the entry point for their origination.

Key functionalities and logic within `NewLoan.sol` include:

*   **`NewLoanParams` Struct (Input):**
    *   Defines the characteristics of the desired Swapper position. Fields include:
        *   `owedPotential`: An array of `Quad` values specifying the target value or "owed amount" across different price bins. This fundamentally shapes the Swapper's payoff profile.
        *   `startBin`, `strikeBin`: Integers defining the starting price bin and a central "strike" bin for the position. The strike bin is used in the "tilting" mechanism.
        *   `tokenMix`: A `Quad` indicating the desired proportional mix of the two pool tokens (token0 and token1) for the position.
        *   `lockinEnd`: A `Quad` representing the duration or maturity date of the Swapper's lock-in period.
        *   `deadEra`: An `OptInt256` (optional integer) that can specify an era at which the Swapper might be subject to special conditions or termination.
        *   `token`: A boolean likely indicating a primary token focus for the Swapper.
        *   `twapUntil`: An `OptInt256` for specifying an end time for Time-Weighted Average Price (TWAP) related conditions or calculations.

*   **Core Operational Logic:**
    1.  **Input Validation:** The `newLoan` function begins with extensive validation of the `NewLoanParams`. This includes checks for non-zero `owedPotential` values, valid price bin ranges (`startBin` to `stopBin`), sensible `lockinEnd` periods, correct alignment of the `strikeBin` relative to the position's range, prevention of NaN (Not a Number) inputs, and ensuring that Swapper creation is currently enabled in the target pool.
    2.  **Lend Token Determination:** The library determines which of the pool's two tokens (conceptually token Z and token I, likely mapping to token0 and token1) is considered to be "lent" by the pool to collateralize the new Swapper. This decision is based on whether the price range of the new Swapper (from `startBin` to `stopBin`) is entirely above or entirely below the pool's current active `tickBin` (market price). A Swapper's range cannot straddle the current market price.
    3.  **"Tilting" Mechanism:** If the `owedPotential` covers more than one price bin, an internal "tilting" mechanism adjusts the distribution of `owedPotential` values across these bins. It uses the `strikeBin` as a fulcrum. The `tilter` internal function calculates adjustment factors to rebalance the owed amounts. This ensures the overall value and risk profile are maintained while allowing for specific payoff shapes.
    4.  **Dynamic Lent Amount Calculation (via `computeLentAtIndex` internal helper):** This function is the financial core of `newLoan`, determining how much of the "lend token" the pool needs to allocate for each price bin covered by the new Swapper. It's called iteratively for each bin.
        *   **Inputs for each bin:**
            *   `owedPotentialAtIndex`: The target value for the Swapper in the current specific bin.
            *   `lockinEnd`: The duration of the Swapper's lock-in period.
            *   `logm`: The logarithmic distance of the current bin from the pool's active `tickBin` (current market price). This reflects how far "out of the money" the bin is.
            *   `q`: A risk factor derived from the pool's observed volatility (`quadVar`, which itself comes from `pool.dayMove`) and a protocol constant `LAMBDA`. A higher `q` generally implies higher perceived risk.
            *   `pool.deflator`: The pool's current deflator, used to calculate an `inflator` for value adjustments.
            *   `pool.used[bin]`: Existing utilization in the bin.
            *   `pool.minted[bin]`: Available fluid liquidity in the bin.
        *   **Calculation Steps per bin:**
            *   **Rate Calculation:** A dynamic lending/borrowing `rate` is first computed. This rate is highly sensitive to `q` and `logm`.
                *   The `lockinEnd` duration significantly influences how `logm` is adjusted before rate calculation. Finite, non-zero `lockinEnd` values (specifically those `<= POSITIVE_ONE`, representing up to one day for example) trigger a complex periodic approximation formula (using `PERIODIC_APPROX_CONSTANT_0` through `_7` and `quadVar`) to modify `logm`. This adjustment accounts for the time value and risk over shorter, defined periods.
                *   Effectively infinite lock-ins (represented by `POSITIVE_INFINITY`) or unsupported periods lead to different paths or reversions (e.g., `UnsupportedLockInPeriod`). The calculated base rate is also floored by `MIN_RATE`.
            *   **Theta and CR:** Using the calculated `rate`, intermediate terms `theta` (related to the Swapper's sensitivity to price changes) and `cr` (collateralization ratio component) are determined.
            *   **New Utilization (`newUsed`):** The required new utilization level for the bin is calculated. This depends on the `owedPotentialAtIndex`, `theta`, `cr`, and the `minted` liquidity in that bin. The calculation aims to ensure that the `minted` liquidity, when adjusted by `theta` and `cr`, can cover the `owedPotentialAtIndex`.
            *   **Utilization Cap Check:** The `newUsed` is capped by `UTILISATION_CAP`. If this cap would be breached, the transaction reverts (`UtilisationCapBreached`).
            *   **Lent Amount for Bin:** The final `lent` amount for the specific bin is `(newUsed - oldUsed) * minted * inflator`. This represents the additional "lend token" value the pool commits to this bin for this Swapper. `oldUsed` is the prior utilization of the bin, and `inflator` is the reciprocal of `pool.deflator`.
    5.  **Swapper Struct Instantiation:** A `SwapperInternal.Info` struct is populated with all user-defined parameters and internally calculated values (e.g., `owner` (msg.sender), `startBin`, `strikeBin`, `tokenMix`, `unlockDate`, `deadEra`, the (potentially tilted) `owedPotential` array, and the `lent` array detailing lent amounts per bin).
    6.  **Pool State Update:** The newly configured `SwapperInternal.Info` struct is initialized (using `SwapperInternal.init`) and then pushed into the `pool.swappers` array, officially creating the Swapper on-chain. A `swapper.created(pool)` hook (from `SwapperInternal.sol`) is called for any post-creation logic.
    7.  **Return Value:** The `newLoan` function returns a `UserPay.Info` struct. This struct informs the caller of the net amounts of token0 and token1 they need to pay into the pool (or will receive from the pool) to establish this new Swapper position. These amounts are derived from the Swapper's calculated backing assets minus its total lent capacity (adjusted by the `pool.deflator`).

*   **Dependencies:**
    *   Utilizes `Quad` fixed-point arithmetic extensively.
    *   Imports numerous constants from `Constants.sol` (e.g., `LAMBDA`, `MIN_RATE`, `UTILISATION_CAP`, periodic approximation constants).
    *   Reads from `PoolState` (via the `IInfinityPoolState.sol` interface) for critical pool data like `deflator`, `dayMove` (for `quadVar`), `used` (utilization per bin via `BucketRolling`), `minted` (liquidity per bin via `BoxcarTubFrame`), `tickBin`, and `splits`.
    *   Leverages helper functions from `PoolHelper.sol` (e.g., `logBin`, `BINS`, `sqrtStrike`, `binStrike`, `fluidAt`).
    *   Employs data structures and enums from `SwapperInternal.sol` (for Swapper representation) and `UserPay.sol` (for the return type).
    *   Uses `OptInt256` for optional integer parameters.

*   **Custom Errors:**
    *   `UnavailableLockInPeriod(Quad lockingEnd)`: Reverts if the provided `lockingEnd` is considered an unavailable or invalid period for creating a new loan. (Note: current code seems to mostly use `UnsupportedLockInPeriod`).
    *   `UnsupportedLockInPeriod(Quad lockingEnd)`: Reverts if the `lockingEnd` duration is not supported. For example, values between `POSITIVE_ONE` and `POSITIVE_INFINITY` (exclusive) are unsupported.
    *   `InvalidOwedPotential()`: Reverts if the `owedPotential` array is empty or contains invalid values (e.g., non-positive amounts where positive are expected).
    *   `InvalidBinRange(int256 startBin, int256 stopBin)`: Reverts if the specified `startBin` to `stopBin` range is invalid (e.g., `startBin` >= `stopBin`, or bins are out of acceptable protocol limits).
    *   `InvalidLendToken()`: Reverts internally if the determined `lendToken` (Z or I) is inconsistent with other parameters or an invalid state is reached.
    *   `UnalignableStrikeOutside(int256 strikeBin, int256 startBin, int256 stopBin)`: Reverts if the `strikeBin` is outside the range `(startBin, stopBin - 1)` when the Swapper covers multiple bins, making the tilting mechanism impossible.
    *   `UnalignedStrike(int256 strikeBin, int256 startBin)`: Reverts if `strikeBin` is not equal to `startBin` when the Swapper covers only a single bin.
    *   `StrikeAtBinZeroNotAllowed()`: Reverts if the `strikeBin` is zero, which is disallowed.
    *   `LiquidityRangeContainsPrice(Quad fracPrice)`: Reverts if the price range of the new Swapper (from `startBin` to `stopBin`) straddles the pool's current active `tickBin` (market price). A Swapper's range must be entirely above or entirely below the current market price.
    *   `NaNIsNotAllowed()`: Reverts if `tokenMix` or `lockinEnd` inputs are NaN (Not a Number).
    *   `SwapperCreationNotEnabledYet()`: Reverts if the `swapperCreationEnabled` flag in the pool state is false.
    *   `UtilisationCapBreached(Quad badUsed)`: Reverts if the calculated `newUsed` (new utilization level) for any bin exceeds the `UTILISATION_CAP`.

## GeneralSwapForwarder Contract (` GeneralSwapForwarder.sol`)

*(Protocol Importance: 7/10)*

The `GeneralSwapForwarder.sol` contract provides a standardized and reusable mechanism for executing token swaps by interacting with external Automated Market Makers (AMMs) or Decentralized Exchange (DEX) routers. It simplifies the process for other smart contracts (e.g., the Infinity Pools periphery) to perform swaps by handling token approvals, forwarding the swap execution call, managing the flow of tokens, and ensuring slippage protection.

The typical workflow involves:
1.  **Approval:** The forwarder approves an external contract (`tokenInSpender`, usually a DEX router) to spend the input tokens (`tokenIn`) that have been (or will be) transferred to this forwarder.
2.  **External Call Execution:** It makes a low-level `call` to a target address `to` (the external DEX or AMM contract) using `data` provided by the initiator. This `data` must be the correctly encoded function call for the desired swap operation on the target venue. The external swap must be configured so that output tokens are sent to this `GeneralSwapForwarder` contract's address.
3.  **Token Handling & Slippage:** After the external call:
    *   For `swapExactInput`: It measures the `tokenOut` received and checks against `minTokenAmountOut`.
    *   For `swapExactOutput`: It calculates `tokenIn` spent and checks against `maxTokenAmountIn`.
4.  **Forwarding:** Transfers received `tokenOut` to `msg.sender`. Any unspent `tokenIn` is also returned.
5.  **Approval Reset:** Resets approval for `tokenInSpender` to zero for security.

### Implemented Interface (`ISwapForwarder`)
The contract adheres to the `ISwapForwarder` interface, standardizing swap function signatures (`exactOutputSupported`, `swapExactInput`, `swapExactOutput`) for consistent integration within the Infinity Pools ecosystem.

### Public Functions
*   **`exactOutputSupported() external pure returns (bool)`:**
    *   Indicates whether the forwarder supports swaps where the exact output amount is specified.
    *   **Returns:** `true`, signifying that this forwarder can handle exact output swaps.

*   **`swapExactInput(IERC20 tokenIn, address tokenInSpender, uint256 tokenAmountIn, IERC20 tokenOut, uint256 minTokenAmountOut, address to, bytes calldata data) external returns (uint256 tokenOutAmount)`:**
    *   Facilitates swaps where a precise amount of input tokens (`tokenAmountIn`) is provided.
    *   **Parameters:**
        *   `tokenIn`: The `IERC20` token to be swapped.
        *   `tokenInSpender`: The address (typically an external DEX router) to approve for spending `tokenIn`.
        *   `tokenAmountIn`: The exact amount of `tokenIn` to be swapped.
        *   `tokenOut`: The `IERC20` token to be received.
        *   `minTokenAmountOut`: The minimum amount of `tokenOut` acceptable, providing slippage protection.
        *   `to`: The address of the external DEX or AMM contract to call.
        *   `data`: The abi-encoded call data for the swap function on the `to` contract.
    *   **Returns:** `tokenOutAmount` - The actual amount of `tokenOut` received.

*   **`swapExactOutput(IERC20 tokenIn, address tokenInSpender, uint256 maxTokenAmountIn, IERC20 tokenOut, uint256 tokenAmountOut, address to, bytes calldata data) external returns (uint256 tokenInAmount)`:**
    *   Facilitates swaps where a precise amount of output tokens (`tokenAmountOut`) is desired. Should ideally be used if `exactOutputSupported()` is `true`.
    *   **Parameters:**
        *   `tokenIn`: The `IERC20` token to be swapped.
        *   `tokenInSpender`: The address to approve for spending `tokenIn`.
        *   `maxTokenAmountIn`: The maximum amount of `tokenIn` that can be spent, providing slippage protection.
        *   `tokenOut`: The `IERC20` token to be received.
        *   `tokenAmountOut`: The exact amount of `tokenOut` desired.
        *   `to`: The address of the external DEX or AMM contract to call.
        *   `data`: The abi-encoded call data for the swap function on the `to` contract.
    *   **Returns:** `tokenInAmount` - The actual amount of `tokenIn` spent.

### Custom Errors
*   **`SwapFailed()`**: Reverts if the external call to the `to` address (the DEX/AMM) does not succeed.
*   **`InsufficientOutputAmount()`**: Reverts in `swapExactInput` if the actual `tokenOutAmount` received is less than the specified `minTokenAmountOut`.
    *   `ExcessiveInputAmount()`: Reverts if the actual `tokenInAmount` spent is more than the `maxTokenAmountIn` specified in `swapExactOutput`.

## LP Library (`LP.sol`)

*(Protocol Importance: 9/10)*

### Overall Description
The `LP.sol` library is a cornerstone of the Infinity Pools protocol, meticulously managing the entire lifecycle of individual Liquidity Provider (LP) positions. It provides the functionalities for users to supply liquidity to specified price ranges (tubs), tracks the fees accrued by these positions, handles the various operational stages of an LP position, and facilitates the collection of earned fees and the eventual withdrawal of liquidity. This library works in close conjunction with the main `PoolState` and numerous internal helper libraries to perform its complex accounting and state management tasks.

Key operations include:
*   **Adding Liquidity (`pour`):** Allows users to provide liquidity within a defined price range (startTub to stopTub). This involves calculating the required token amounts, updating pool-wide liquidity trackers (e.g., `pool.minted`), and creating or updating an `LP.Info` struct for the provider.
*   **Fee Accrual and Collection (`accrued`, `earn`, `collect`):** Tracks the fee growth relevant to an LP's specific range and allows LPs to claim their earned fees.
*   **State Transitions (`tap`):** Manages the progression of an LP position through its lifecycle stages, notably from an initial `Join` state to an active `Earn` state.
*   **Withdrawing Liquidity (`drain`):** Enables LPs to remove their liquidity from the pool. This process transitions the LP to an `Exit` stage and involves accounting for any final earned fees and updating pool liquidity trackers.

### Key Structs
*   **`LP.Info`**: The central data structure holding all pertinent information for a single LP position. Its fields include:
    *   `owner (address)`: The address of the liquidity provider.
    *   `liquidity (Quad)`: The amount of concentrated liquidity provided.
    *   `startTub (int32)`, `stopTub (int32)`: Define the price range of the liquidity position in terms of 'tubs'.
    *   `stage (Stage)`: The current operational stage of the LP position (Join, Earn, or Exit).
    *   `earnEra (int32)`: The pool era at which the position is eligible to start earning fees (transition from Join to Earn).
    *   `growPast0 (Quad)`, `growPast1 (Quad)`: Trackers for the cumulative fee growth (per unit of liquidity) for token0 and token1 respectively, up to the last point of collection or update. Used to calculate newly earned fees.
    *   `drainDate (Quad)`: The pool date when the draining process was initiated for this position.
    *   `lower0 (int128)`, `upper0 (int128)`, `lower1 (int128)`, `upper1 (int128)`: Parameters calculated during the `drain` process, related to the payoff for the collected liquidity, likely representing packed floating-point values for token amounts at different price points of the draining range.

*   **`LP.PourLocalVars`**: An internal, temporary struct used within the `pour` function to store intermediate variables during the complex calculations involved in adding liquidity. This includes bin ranges, token reserves, projected yields, tail era information, and flow adjustments.

*   **`LP.DrainLocalVars`**: An internal, temporary struct used within the `drain` function. It holds intermediate values for calculations like the current stage, tail era, exponent for payoff calculations, tick boundaries, and earned amounts for token0 and token1.

### Enums
*   **`LP.Stage`**: Defines the distinct operational states an LP position can be in:
    *   `Join`: The initial state when liquidity has been added but the position is not yet eligible to earn fees (i.e., `pool.era < lp.earnEra`).
    *   `Earn`: The active state where the LP position is accruing fees based on trading activity within its range.
    *   `Exit`: The state indicating that the LP has initiated the process of withdrawing their liquidity. Fees are typically finalized at the start of this stage, and the liquidity is scheduled for removal.

### Custom Errors
*   `InvalidPourArguments()`: Reverted if the arguments provided to the `pour` function (e.g., `startTub`, `stopTub`, `liquidity`) are out of valid ranges or inconsistent.
*   `MustWaitTillTailEraToStartDraining(int256 tailEra, int256 poolEra)`: Reverted by `drain` if an attempt is made to drain a position in the `Join` stage before its designated `earnEra` (referred to as `tailEra` in the `drain` context) is reached.
*   `MustWaitTillEarnEraToStartTapping(int256 earnEra, int256 poolEra)`: Reverted by `tap` if an attempt is made to transition a position from `Join` to `Earn` before its `earnEra`.
*   `LiquidityPositionAlreadyDraining()`: Reverted by `drain` if it's called on an LP position that is already in the `Exit` stage.
*   `StageNotJoined()`: Reverted by `tap` if the LP position is not currently in the `Join` stage.
*   `OnlyOwnerAllowed()`: Reverted by `drain` and `collect` if `msg.sender` is not the registered owner of the LP position.
*   `liquidityIsNaN()`: Reverted by `pour` if the input `liquidity` amount is Not-a-Number (NaN).
*   `GetPourQuantitiesResult(int256 pay0, int256 pay1)`: Used by the `getPourQuantitiesReverts` function to return the calculated token amounts by reverting with this error. This is a common pattern for off-chain data retrieval.

### Key Functions

#### External Functions
*   **`pour(PoolState storage pool, int256 startTub, int256 stopTub, Quad liquidity) external returns (UserPay.Info memory)`**: 
    *   The primary function for adding liquidity. Users specify a range (`startTub`, `stopTub`) and an amount of `liquidity`.
    *   It updates `pool.minted` (total active liquidity), `pool.joinStaged` (for fee accounting), and pool-wide flow trackers (`pool.flowHat`, `pool.owed`).
    *   Creates an `LP.Info` entry in `pool.lps` array, initially in the `Join` stage.
    *   Calculates and returns the amounts of `token0` and `token1` the caller needs to provide, considering both the base reserves for the range and projected future yield (`vars.yield0`, `vars.yield1` adjusted by `tailDeflator`).

*   **`getPourQuantities(PoolState storage pool, int256 startTub, int256 stopTub, Quad liquidity) public returns (UserPay.Info memory)`**: 
    *   A read-only (though it may update lazy-evaluation structs internally) function that simulates the `pour` operation's calculations.
    *   Determines the required `token0` and `token1` amounts for a given liquidity addition without actually modifying the pool state permanently.
    *   Useful for frontends or other contracts to estimate costs before executing a `pour`.

*   **`getPourQuantitiesReverts(PoolState storage pool, int256 startTub, int256 stopTub, Quad liquidity) external`**: 
    *   Calls `getPourQuantities` and then reverts with a `GetPourQuantitiesResult` error containing the calculated token amounts. Facilitates off-chain queries by allowing clients to catch the revert data.

*   **`drain(PoolState storage pool, uint256 lpNum) external returns (UserPay.Info memory)`**: 
    *   Allows the owner of an LP position (`lpNum`) to initiate liquidity withdrawal.
    *   Checks ownership and current stage (cannot drain if already `Exit` or if `Join` stage and `earnEra` not met).
    *   Updates `pool.minted` (subtracts liquidity) and `pool.offRamp` (adds to liquidity scheduled for removal).
    *   Calculates final earned fees using `earn(lp, pool, true)`.
    *   Transitions the LP position to `Stage.Exit` and records `drainDate` and payoff parameters (`lower0`, `upper0`, etc.) in `LP.Info`.
    *   Returns the earned fees to be paid out to the LP.

*   **`collect(PoolState storage pool, uint256 lpNum) external returns (UserPay.Info memory)`**: 
    *   Allows the LP owner to collect accrued fees.
    *   If `lp.stage == Stage.Earn`, it calls `earn(lp, pool, true)` to calculate and return new earnings, updating `growPast` trackers.
    *   If `lp.stage == Stage.Exit`, it calls `LPShed.shed(lp, pool, true)` to calculate and return amounts being shed from the draining position.
    *   Returns amounts to be paid out to the LP.

*   **`tap(PoolState storage pool, uint256 lpNum) external`**: 
    *   Allows an LP owner to transition their position from `Stage.Join` to `Stage.Earn`.
    *   Requires `pool.era >= lp.earnEra`.
    *   Updates `lp.stage` to `Stage.Earn` and initializes `lp.growPast0` and `lp.growPast1` based on current `accrued` fee levels, effectively setting the baseline for future `earn` calculations.

#### Notable Internal Functions
*   **`init(int256 startTub, int256 stopTub, Quad liquidity, Stage stage, int256 earnEra) internal view returns (Info memory)`**: 
    *   A helper function to create and initialize a new `LP.Info` struct with provided parameters and `msg.sender` as owner.

*   **`accrued(Info storage self, PoolState storage pool) internal returns (Quad, Quad)`**: 
    *   Calculates the total cumulative fee growth per unit of liquidity (`pool.fees[0].accruedRange` and `pool.fees[1].accruedRange`) for the specific tub range (`self.startTub`, `self.stopTub`) of the LP position.

*   **`earn(Info storage self, PoolState storage pool, bool flush) internal returns (Quad, Quad)`**: 
    *   Calculates the newly earned fees for an LP position in `Stage.Earn`.
    *   It finds the difference between the current `accrued` total fee growth and the `growPast` values stored in `LP.Info` (which represent the growth at the last collection/tap).
    *   Multiplies this differential growth by `self.liquidity`.
    *   If `flush` is true, it updates `self.growPast0` and `self.growPast1` to the new `accrued` values.

*   **`bins(int256 splits, int256 startTub, int256 stopTub) public pure returns (int256, int256)`**: 
    *   Converts a range defined by `startTub` and `stopTub` into the corresponding `startBin` and `stopBin` based on the pool's `splits` parameter.

*   **`reserves(PoolState storage pool, int256 startTub, int256 stopTub, int256 startBin, int256 stopBin) internal view returns (Quad, Quad)`**: 
    *   Calculates the notional amounts of `token0` and `token1` that correspond to one unit of liquidity within the specified tub/bin range, considering the current pool price (`pool.tickBin`, `pool.binFrac`). This is fundamental for determining how much of each token a new LP needs to provide.

*   **`lowSqrtBin(PoolState storage pool, int256 bin) internal view returns (Quad)`**: 
    *   A mathematical helper to calculate the square root of the price at the lower edge of a given `bin`.

### Key Dependencies
*   **`PoolState` (from `IInfinityPoolState.sol`)**: The central state struct of the pool, accessed extensively.
*   **`UserPay.sol`**: Used to structure the return values for token amounts to be paid to/from the user.
*   **`LPShed.sol`**: Used by `collect` when an LP is in the `Exit` stage to determine the amounts being shed.
*   **`ABDKMathQuad.sol`**: For `Quad` fixed-point arithmetic.
*   **`Constants.sol`**: For various protocol-wide constants (e.g., `TUBS`, `JUMPS`).
*   **Helper Libraries**: `PoolHelper.sol` (e.g., `eraDate`, `sqrtStrike`), `DeadlineHelper.sol` (e.g., `deadEra`).
*   **Internal Mechanics Libraries**: `GrowthSplitFrame.sol`, `JumpyAnchorFaber.sol`, `BoxcarTubFrame.sol`, `DeadlineFlag.sol`, `GapStagedFrame.sol`, `JumpyFallback.sol`, `EachPayoff.sol`, `Capper.sol`.

*   **Dependencies:**
    *   OpenZeppelin Contracts: `SafeERC20.sol` (for `safeTransfer` and `forceApprove`) and `IERC20.sol`.
    *   Infinity Pools Interfaces: `ISwapForwarder.sol` (which it implements) and `IUniswapV2Router02.sol` (imported, indicating a common target for the `data` payload, though not directly used in the forwarder's own logic).

This contract enhances composability by allowing the Infinity Pools system to seamlessly integrate with various external liquidity sources without requiring each part of the system to implement bespoke swap logic and approval management.

## Context Contract (`Context.sol` - OpenZeppelin Utility)

*(Protocol Importance: 2/10)*

`Context.sol` is a standard OpenZeppelin utility contract (v5.0.1) that provides an abstraction layer for `msg.sender` and `msg.data`. This is primarily to support meta-transactions (e.g., EIP-2771). Its inclusion is often a standard part of using OpenZeppelin's upgradeable contracts or other utilities, and it may not signify active use of meta-transactions within Infinity Pools unless otherwise specified.

## EncodeIdHelper Library (`EncodeIdHelper.sol`)

*(Protocol Importance: 6/10)*

The `EncodeIdHelper` library provides essential utility functions for encoding and decoding `uint256` token IDs used for Non-Fungible Tokens (NFTs) that represent user positions (Liquidity Provider or Swapper) within the Infinity Pools protocol. This library enables the protocol to store critical position information directly within the NFT's `tokenId`, making it easily parsable and reducing the need for additional storage lookups.

Key functionalities:

*   **`PositionType` Enum:**
    *   Defines the type of position: `LP` (Liquidity Provider) or `Swapper`.

*   **`encodeId(PositionType enumValue, address poolAddress, uint88 lpOrSwapperNumber)` Function:**
    *   Combines the `PositionType`, the `poolAddress` where the position exists, and a unique `lpOrSwapperNumber` (an 88-bit identifier for the specific LP or Swapper position within that pool) into a single `uint256` value.
    *   This is achieved through bitwise operations (shifts and ORs) to pack the data:
        *   The `PositionType` (1 bit) is placed in the most significant bits.
        *   The `poolAddress` (160 bits) is placed in the middle.
        *   The `lpOrSwapperNumber` (88 bits) is placed in the least significant bits.

*   **`decodeId(uint256 id)` Function:**
    *   Takes a `uint256` tokenId.
    *   Reverses the encoding process using bitwise shifts and masks to extract and return the original `PositionType`, `poolAddress`, and `lpOrSwapperNumber`.

This library is fundamental to the NFT-based position management strategy employed by `InfinityPoolsPeriphery.sol`, ensuring that each NFT tokenId is unique, self-descriptive, and efficiently links back to its specific on-chain context.

## PeripheryActions Library (`PeripheryActions.sol`)

*(Protocol Importance: 8/10)*

The `PeripheryActions.sol` library is a crucial internal component that encapsulates the core logic for many operations performed by the `InfinityPoolsPeriphery.sol` contract. It provides a suite of functions that orchestrate interactions with Infinity Pools, manage liquidity positions, create new loans (Swapper positions), handle token swaps via external forwarders, and manage NFT-related operations. By centralizing this logic, it promotes modularity and clarity within the periphery contract.

Key functionalities provided by this library include:

*   **Liquidity Provision (`addLiquidity`):**
    *   Validates parameters (token order, amounts).
    *   Retrieves the pool address from the factory.
    *   Calculates the optimal liquidity amount based on desired token inputs and current pool state.
    *   Calls the `pour` function on the target `IInfinityPool` instance, providing necessary callback data for payment handling.
    *   Encodes a unique LP NFT `tokenId` using `EncodeIdHelper.sol` upon successful liquidity addition.
    *   Emits a `PeripheryLiquidityAdded` event.

*   **New Loan Creation (`newLoan`):**
    *   Validates parameters and retrieves the pool address.
    *   Prepares callback data, including information for potential collateral swaps.
    *   Can bundle a `newLoan` action with a `SWAP` action on the `IInfinityPool` if `infinityPoolSpotSwapParams` are provided, executing them atomically.
    *   Otherwise, directly calls `newLoan` on the pool.
    *   Encodes a unique Swapper NFT `tokenId` using `EncodeIdHelper.sol` based on the new swapper count.

*   **Swap Execution (`handleSwap`):**
    *   Manages the execution of token swaps through a registered `ISwapForwarder`.
    *   Transfers the `fromToken` to the specified `swapForwarder`.
    *   Invokes either `swapExactOutput` or `swapExactInput` on the forwarder based on its capabilities and the `shouldExactOutput` parameter.
    *   Measures and returns the tokens received (`fromTokenReceived` if any unspent, `toTokenReceived`).
    *   Emits a `SpotSwap` event.

*   **Pool and NFT Utilities:**
    *   `getPoolAddress(address factory, address tokenA, address tokenB)`: Retrieves and validates the pool address for a given token pair.
    *   `isApprovedForAll(address owner, address operator)`, `isAuthorized(address owner, address spender, uint256 tokenId)`, `ownerOf(uint256 tokenId)`: Provides standard ERC721 view functions, implying the calling contract (periphery) is an NFT. These are used for access control and ownership checks.

*   **Events and Custom Errors:**
    *   Defines several events (`PeripheryLiquidityAdded`, `SpotSwap`, `NoOpSwapperIds`) for off-chain tracking.
    *   Includes a comprehensive list of custom errors (e.g., `IdenticalTokens`, `PoolDoesNotExist`, `PriceSlippageAmount0`, `InvalidSwapForwarder`) to provide specific reasons for transaction failures.

*   **Dependencies:**
    *   Interfaces: `IInfinityPoolFactory`, `IInfinityPool`, `IInfinityPoolsPeriphery`, `ISwapForwarder`, `IERC20`, `IERC721`.
    *   Libraries: `PoolHelper.sol`, `ABDKMathQuad`, `EncodeIdHelper.sol`, `Spot.sol`, `NewLoan.sol`, `VaultActions.sol`.
    *   Contracts: OpenZeppelin's `SafeCast`, `SafeERC20`.

This library is central to the operational logic of the Infinity Pools periphery, acting as the engine for user-initiated actions like adding liquidity and creating loans, while also managing the complexities of external swaps and NFT representations of positions.

## ISwapForwarder Interface (`ISwapForwarder.sol`)

*(Protocol Importance: 7/10)*

The `ISwapForwarder` interface defines a standardized contract for executing token swaps via external Automated Market Makers (AMMs) or Decentralized Exchange (DEX) aggregators. By abstracting the swap execution logic, this interface allows the Infinity Pools protocol (specifically `PeripheryActions.sol` and its consumers like `InfinityPoolsPeriphery.sol`) to interact with various external swapping venues in a consistent manner. Any contract designed to act as a swap intermediary for the protocol should implement this interface.

Key functions defined:

*   **`exactOutputSupported() external pure returns (bool)`:**
    *   A view function that indicates whether the implementing forwarder contract supports "exact output" swaps (i.e., swaps where the desired amount of `tokenOut` is specified, and the amount of `tokenIn` spent is variable up to a maximum).
    *   Returns `true` if exact output swaps are supported, `false` otherwise.

*   **`swapExactInput(...) external returns (uint256 tokenOutAmount)`:**
    *   Executes a swap where the amount of input tokens (`tokenAmountIn`) is precisely known.
    *   **Parameters:**
        *   `tokenIn`: The `IERC20` token to be swapped.
        *   `tokenInSpender`: The address (typically an external DEX router) that the forwarder needs to approve to spend `tokenIn` on its behalf.
        *   `tokenAmountIn`: The exact amount of `tokenIn` to be swapped.
        *   `tokenOut`: The `IERC20` token to be received.
        *   `minTokenAmountOut`: The minimum amount of `tokenOut` acceptable for the swap, providing slippage protection.
        *   `to`: The address of the external DEX or AMM contract to call for the swap.
        *   `data`: The abi-encoded call data for the specific swap function on the `to` contract (e.g., Uniswap's `swapExactTokensForTokens`). The external swap must be configured such that `tokenOut` is sent back to this `ISwapForwarder` contract.
    *   **Returns:** `tokenOutAmount` - The actual amount of `tokenOut` received by the forwarder from the swap.

*   **`swapExactOutput(...) external returns (uint256 tokenInAmount)`:**
    *   Executes a swap where the amount of output tokens (`tokenAmountOut`) is precisely known. This function should ideally only be called if `exactOutputSupported()` returns `true`.
    *   **Parameters:**
        *   `tokenIn`: The `IERC20` token to be swapped.
        *   `tokenInSpender`: The address (typically an external DEX router) that the forwarder needs to approve to spend `tokenIn`.
        *   `maxTokenAmountIn`: The maximum amount of `tokenIn` that can be spent to achieve the desired `tokenAmountOut`, providing slippage protection.
        *   `tokenOut`: The `IERC20` token to be received.
        *   `tokenAmountOut`: The exact amount of `tokenOut` desired from the swap.
        *   `to`: The address of the external DEX or AMM contract to call for the swap.
        *   `data`: The abi-encoded call data for the specific swap function on the `to` contract (e.g., Uniswap's `swapTokensForExactTokens`). The external swap must ensure `tokenOut` is sent to the forwarder.
    *   **Returns:** `tokenInAmount` - The actual amount of `tokenIn` spent by the forwarder in the swap.

This interface is crucial for the protocol's flexibility in integrating with the broader DeFi ecosystem for efficient token swapping. It allows `PeripheryActions.sol` to delegate swap operations without being tightly coupled to any single DEX's implementation details.

## Swapper Library (`Swapper.sol`)

*(Protocol Importance: 8/10)*

### Overall Description
`Swapper.sol` is a Solidity library that manages "swapper" positions. These positions allow users to effectively borrow one token against another within a specific price range (defined by `startBin` and the `lent` array structure within `SwapperInternal.Info`), often incorporating a time-weighted average price (TWAP) component. The library provides functionalities for the creation (typically initiated via `NewLoan.createSwapper`, which then calls `Swapper.created`), modification (`reset`, `reflow`), and closing (`unwind`) of these leveraged or strategic positions. It works in close conjunction with `SwapperInternal.sol`, which handles much of the detailed accounting, state management, and validation for swapper positions. The `enableSwapperCreation` function serves as a one-time initialization to activate the swapper system within a given pool.

### Key Data Structures
*   **`SwapperInternal.Info`** (defined in `SwapperInternal.sol` but is the primary state object manipulated by `Swapper.sol` functions):
    *   `owner (address)`: The address of the entity that owns and controls the swapper position.
    *   `tokenMix (Quad)`: A value representing the desired ratio or mix of the two underlying tokens in the position. This influences how the position behaves, particularly during swaps or rebalancing.
    *   `token (bool)`: A boolean flag indicating if the swapper position is defined in terms of a fixed amount of one specific token (`true`) or if its composition is more fluidly determined by the `tokenMix` (`false`).
    *   `unlockDate (Quad)`: The pool date (a Quad representation of time) at which the swapper position becomes eligible for modification or unwinding.
    *   `deadEra (OptInt256)`: An optional integer representing the pool era at which the swapper position expires or becomes inactive. If it's not defined (e.g., for a perpetual swapper or a fixed-term loan with different mechanics), certain operations like `unwind` might be restricted. A value of `NEVER_AGO` is used to mark a swapper as effectively closed after unwinding.
    *   `twapUntil (OptInt256)`: An optional era defining the end point for any Time-Weighted Average Price (TWAP) calculations relevant to this swapper position.
    *   `startBin (int32)`: The initial price bin that anchors the range of the swapper position.
    *   `lent (Quad[])`: An array of Quad values representing the distribution of the swapper's borrowed liquidity across different price bins relative to `startBin`.
    *   *Note: Other fields exist within `SwapperInternal.Info` for detailed internal accounting, managed primarily by `SwapperInternal.sol`.*

*   **`Swapper.UnwindLocalVars`**: A temporary struct used internally within the `unwind` function. It holds intermediate variables required for calculating the collateral amounts to be released to the owner when the position is closed, such as `release0`, `release1`, and `midIndex`.

### Enums
No enums are defined directly within `Swapper.sol`.

### Custom Errors
*   `OnlyOwnerAllowed()`: Reverted if a function that requires owner privileges (e.g., `reset`, `reflow`, `unwind`) is called by an address other than the swapper's owner.
*   `SwapperLocked(Quad currentDate, Quad unlockDate)`: Reverted by the `unwind` function if an attempt is made to unwind a swapper position before its designated `unlockDate` has been reached.
*   `CannotWithDrawFromFixedLoan()`: Reverted by `reset` and `unwind` if `deadEra` is not defined. This usually implies the swapper is a type of fixed loan with potentially different closing mechanisms or that it has already been unwound and its `deadEra` was cleared or set to an undefined state.
*   `TokenMixIsNaN()`: Reverted by `reset` and `reflow` if the `tokenMix` parameter provided is Not-a-Number (NaN), indicating invalid input.
*   `SwapperCreationIsAlreadyEnabled()`: Reverted by `enableSwapperCreation` if the `pool.swappers` array already contains entries, signifying that the swapper system has already been initialized for the pool and this function cannot be run again.

### Key Functions

#### External Functions
*   **`reset(SwapperInternal.Info storage self, PoolState storage pool, OptInt256 deadEra, Quad tokenMix, bool fixedToken, OptInt256 twapUntil) external returns (UserPay.Info memory)`**:
    *   Allows the owner of a swapper position to modify its core parameters, including its expiration time (`deadEra`), the target mix of underlying tokens (`tokenMix`), whether the position is fixed in terms of one token (`fixedToken`), and the duration for TWAP calculations (`twapUntil`).
    *   This function recalculates the necessary backing for the modified position and returns a `UserPay.Info` struct indicating the net change in token0 and token1 balances required from or due to the owner.

*   **`reflow(SwapperInternal.Info storage self, PoolState storage pool, Quad tokenMix, bool fixedToken, OptInt256 twapUntil) external returns (UserPay.Info memory)`**:
    *   A more gas-optimized version of `reset`, specifically designed for adjusting the `tokenMix`, `fixedToken` status, and `twapUntil` duration.
    *   Like `reset`, it returns the net change in token balances resulting from these adjustments.

*   **`created(SwapperInternal.Info storage self, PoolState storage pool) public returns (SwapperInternal.Info storage)`**:
    *   This function is typically called by `NewLoan.createSwapper` immediately after a new `SwapperInternal.Info` struct has been initialized and added to the pool's swapper array.
    *   It performs essential initial validation of the new swapper's parameters and updates the pool's borrow and flow accounting to reflect the new position.

*   **`unwind(SwapperInternal.Info storage self, PoolState storage pool) external returns (UserPay.Info memory)`**:
    *   Enables the owner to close out their swapper position.
    *   It calculates the amounts of token0 (`release0`) and token1 (`release1`) collateral to be returned to the owner, after accounting for the `lent` liquidity distributed across various price bins.
    *   It updates internal pool accounting (borrow and flow trackers via `SwapperInternal.borrow` and `SwapperInternal.flow`) and marks the swapper as inactive by setting its `deadEra` to `NEVER_AGO`.
    *   Returns a `UserPay.Info` struct with negative values, indicating the token amounts paid out from the pool to the user.

*   **`enableSwapperCreation(PoolState storage pool) external`**:
    *   A one-time setup function required to activate the swapper system for a specific Infinity Pool.
    *   It initializes the system by pushing a placeholder (empty) `SwapperInternal.Info` struct onto the `pool.swappers` array. Subsequent calls will fail due to `SwapperCreationIsAlreadyEnabled`.

### Key Dependencies
*   **`PoolState` (from `IInfinityPoolState.sol`)**: The central state struct of the pool, accessed and modified by swapper operations.
*   **`UserPay.sol`**: A library used to structure the return values representing token amounts to be paid to or by the user.
*   **`SwapperInternal.sol`**: Crucial for the `SwapperInternal.Info` struct definition and provides core logic for swapper accounting (`backing`, `borrow`, `flow`) and state validation (`checkAlive`, `validate`).
*   **`NewLoan.sol`**: While not a direct import, `NewLoan.sol` is the typical entry point for creating new swapper positions, which then calls `Swapper.created`.
*   **Math and Utility Libraries**: `ABDKMathQuad.sol` (for Quad fixed-point arithmetic), `OptInt256.sol` (for optional integer types), `Constants.sol` (for global constants like `Z`, `I`, `NEVER_AGO`), and `PoolHelper.sol` (for utility functions related to pool mechanics).

## Spot Library (`Spot.sol`)

*(Protocol Importance: 9/10)*

The `Spot.sol` library is a core component of the Infinity Pools protocol, containing the intricate logic for executing token swaps directly within an individual Infinity Pool. It operates on the pool's concentrated liquidity, managing bin transitions, calculating swap amounts, applying fees, and updating the pool's internal state. This library is fundamental to the Automated Market Maker (AMM) functionality of each pool.

Key functionalities:

*   **Internal Pool State Manipulation:**
    *   Directly reads from and writes to the `PoolState storage` variable of an Infinity Pool.
    *   Functions like `_uptick` and `_downtick` handle the transition between discrete price bins (`tickBin`), which involves flushing any staged liquidity (`joinStaged.flush`) into the new active bin and updating fee trackers (`updateFees`).
    *   Manages `binFrac` (the fractional position within the current `tickBin`) and `halfspread` (related to the dynamic spread/fees).

*   **`SpotSwapParams` Struct:**
    *   Defines the parameters for initiating a swap within the pool:
        *   `shove`: A `Quad` representing the quantity of tokens to be "pushed" into the pool (if positive) or the target quantity to be "pulled" from the pool (if negative, though the `swap` function's internal logic uses `abs(shove)` and the `token` boolean to determine direction).
        *   `ofToken`: A boolean indicating which token the `shove` amount refers to (`true` for `token1`, `false` for `token0`).
        *   `limitPrice`: An optional `OptQuad` specifying a price limit for the swap. The swap will not execute beyond this price.
        *   `remainingAmount`: An `OptQuad` that can specify a target remaining balance of the *other* token. This is used in more complex scenarios, like when a swap follows another action (e.g., creating a loan), to ensure the combined operations result in a specific net outcome for that token.

*   **Core `swap` Function:**
    *   The primary public function that executes a spot swap based on the `SpotSwapParams`.
    *   Iteratively processes the swap by traversing price bins.
    *   Calculates the amount of input token required or output token produced for each segment of liquidity encountered.
    *   Respects the `limitPrice` if provided.
    *   Applies dynamic spot fees using an internal `spotFee_` function, which considers factors like liquidity utilization.
    *   Updates the pool's variance tracker (`onSlip`) based on the price movement.
    *   Returns a `UserPay.Info` struct detailing the net amounts of `token0` and `token1` to be paid by or transferred to the user.

*   **Fee and State Updates:**
    *   `updateFees(PoolState storage self, bool isUp)`: Manages the movement and accrual of fees as the active price bin changes.
    *   `onSlip(PoolState storage pool, Quad qMove)`: Updates a daily price movement tracker, likely used for dynamic fee calculations or risk metrics.

*   **Event:**
    *   `SpotSwapEvent`: Emitted after a swap, logging the input parameters and the resulting token exchange.

*   **Dependencies:**
    *   Utilizes `PoolState` from `IInfinityPoolState.sol` and various types/functions from `ABDKMathQuad`, `OptQuad`, `Constants.sol`, and numerous internal helper libraries like `PoolHelper.sol`, `GapStagedFrame.sol`, `UserPay.sol`, etc., for complex mathematical calculations and state interactions.

The `Spot.sol` library is essential for the direct AMM functionality of Infinity Pools, embodying the complex mechanics of its concentrated liquidity design and dynamic fee structure.

## PeripheryPayment Contract (`PeripheryPayment.sol`)

*(Protocol Importance: 7/10)*

The `PeripheryPayment` contract is a utility contract responsible for facilitating token payments within the Infinity Pools periphery. It inherits from `Vault.sol`, enabling it to interact with user funds deposited into the vault system. The contract abstracts the complexities of token sourcing for payments, offering flexibility in how transfers are executed, and includes special handling for WETH.

Key functionalities:

*   **Inherits from `Vault`:** This allows `PeripheryPayment` to access and utilize tokens that users have deposited into the `Vault` contract, streamlining payments that can be sourced from these deposits.

*   **`pay(IERC20 token, address payer, address recipient, bool useVaultDeposit, uint256 value)` (internal):**
    *   The core internal function for executing token transfers.
    *   **WETH Handling:** If `token` is WETH and the `PeripheryPayment` contract holds sufficient ETH, it can wrap its ETH into WETH on-the-fly to make the payment. The `useVaultDeposit` flag cannot be true in this specific scenario.
    *   **Payment Sourcing Logic:**
        *   If `payer` is `address(this)` (i.e., the `PeripheryPayment` contract itself), it transfers tokens it already holds.
        *   If `useVaultDeposit` is `true`, it withdraws the `value` from the `payer`'s balance within the `Vault` system and then transfers it to the `recipient`.
        *   Otherwise, it performs a standard `SafeERC20.safeTransferFrom`, pulling tokens directly from the `payer`'s address (requiring prior approval).
    *   This function centralizes payment logic, allowing other periphery contracts to request payments without needing to manage the specific source of funds.

*   **`wrapAndDepositWETH(address to)` (external payable):**
    *   Allows users to send ETH to the `PeripheryPayment` contract.
    *   The contract then wraps its entire current ETH balance into WETH.
    *   This newly wrapped WETH is then deposited into the `Vault` system for the benefit of the `to` address.
    *   This provides a convenient way for users to convert ETH to WETH and deposit it into their vault in a single transaction.

*   **Error Handling:**
    *   `NotAllowedToUseVaultDeposit()`: Reverts if an attempt is made to use vault deposits when paying with WETH derived from the contract's own ETH balance.

*   **Dependencies:**
    *   `Vault.sol`: For interacting with user-deposited funds.
    *   OpenZeppelin's `SafeERC20.sol`: For safe ERC20 token transfers.
    *   `IWETH9.sol`: For interacting with the WETH9 contract (wrapping ETH).
    *   `IPermit2.sol`: (Imported, though direct usage isn't apparent in the snippet, suggesting potential integration for permit-based approvals, possibly within `Vault.sol` or for future enhancements).

The `PeripheryPayment` contract enhances the Infinity Pools ecosystem by providing a robust and flexible mechanism for handling token payments, particularly by integrating seamlessly with the `Vault` and offering WETH utility functions.

### `SwapperInternal.sol` - Library

*(Protocol Importance: 10/10)*

**Description:**
The `SwapperInternal.sol` library provides the core logic for managing "Swapper" positions within an Infinity Pool. Swapper positions are complex financial instruments that can involve Time-Weighted Average Price (TWAP) features, fixed-term loans, and specific token exposures. This library handles the lifecycle, accounting, and validation of these positions.

**Key Functionalities & Data Structures:**

*   **`Info` Struct:** This crucial struct holds the state of an individual Swapper position, including:
    *   `twapUntil`: Optional era until which a TWAP is active.
    *   `deadEra`: Optional era at which the Swapper position expires.
    *   `tokenMix`: Specifies the desired token exposure (e.g., fixed exposure to token0 or token1, or a mix).
    *   `unlockDate`: The date until which the Swapper position is locked.
    *   `oweLimit`: The total owed liquidity limit in inflated units.
    *   `lentCapacity0`, `lentCapacity1`: The capacity of liquidity lent out, in terms of token0 and token1 respectively (inflated).
    *   `owed`, `lent`, `minted`: Arrays tracking owed, lent, and minted liquidity across relevant bins (in inflated units where applicable).
    *   `startBin`, `strikeBin`: Define the range and strike price bin for the Swapper.
    *   `owner`: The address of the Swapper position's owner.
    *   `token`: Boolean indicating the token for fixed exposure if TWAP is active.

*   **Initialization & Validation:**
    *   `init()`: Initializes a new Swapper's `Info` struct, calculating `oweLimit` and `lentCapacity` based on provided liquidity arrays and current pool state (inflator).
    *   `validate()`: Performs critical checks on a Swapper's parameters to ensure logical consistency (e.g., deadlines, token mix against capacity). Reverts with errors like `DeadlineDoesNotCoverLockInDate`, `InvalidTokenMixFraction`, `TWAPEndsBeforeDeadline`, `FixedTokenExceedsCapacity`.
    *   `checkAlive()`: Ensures a Swapper position is not expired before allowing operations.

*   **Lifecycle Management & Accounting:**
    *   `borrow()`: Updates pool accounting for lent, used, and owed liquidity when a Swapper borrows. It also creates fee entries and flow entries for when liquidity returns.
    *   `flow()`: Calculates and creates payoff entries (`AnyPayoff.payoffCreate`, `AnyPayoff.payoffExtend`) and netting entries in the pool state based on the Swapper's configuration (TWAP, expiration). It also updates `expire` entries for lent capacity returning to the pool.
    *   `backing()`: Calculates the amount of a specific token required to back the Swapper position, considering TWAP status and expiration. This is crucial for ensuring solvency.
    *   `endTokenMix()`: Computes the effective token mix after a TWAP period has concluded.

*   **Fee Creation:**
    *   `feeCreate()`, `feeCreateOne()`: Internal functions to create fee entries in the pool's `fees` tracker based on the difference between owed and lent liquidity.

**Dependencies & Key Imports:**

*   `src/types/ABDKMathQuad/Quad.sol` (for `Quad` fixed-point math)
*   `src/types/Optional/OptInt256.sol`
*   `src/interfaces/IInfinityPoolState.sol` (for `PoolState`)
*   `src/Constants.sol`
*   OpenZeppelin's `SafeCast.sol`
*   Numerous internal libraries for pool mechanics and data structures: `DeadlineJumps.sol`, `PoolHelper.sol`, `GrowthSplitFrame.sol`, `JumpyFallback.sol`, `DropFaberTotals.sol`, `JumpyAnchorFaber.sol`, `UserPay.sol`, `Payoff.sol`, `GapStagedFrame.sol`, `NettingGrowth.sol`.

**Reasoning for Importance:**
`SwapperInternal.sol` is fundamental to one of the core, advanced functionalities of Infinity Pools. It encapsulates highly complex logic for managing these positions, including their financial mechanics, interactions with overall pool liquidity, and fee accounting. Understanding this library is critical for developers working on Swapper-related features or analyzing pool dynamics involving these instruments.

---

## UserPay Library (`UserPay.sol`)

*(Protocol Importance: 7/10)*

### Overall Description
`UserPay.sol` is a Solidity library dedicated to managing the mechanics of token payments (both token0 and token1) between the Infinity Pool contract and its users or other interacting contracts. A key function is the conversion of token amounts from `Quad` fixed-point values (which often represent human-readable decimal units in other parts of the system) into their `wei` equivalents (the base unit for ERC20 tokens). This conversion utilizes decimal information stored within the `PoolState` struct. The library is designed to handle payments robustly, supporting direct token transfers via `safeTransfer` and `safeTransferFrom`, as well as a more flexible callback pattern using the `IInfinityPoolPaymentCallback` interface. The callback is particularly useful for scenarios where users might need to source funds from external contracts or perform additional actions to fulfill their payment obligations. All rounding of fractional token amounts is done conservatively from the pool's perspective, meaning users will pay slightly more or receive slightly less in such cases.

### Key Data Structures
*   **`Info` (struct)**: This struct is the primary way token amounts are specified for payment operations.
    *   `token0 (Quad)`: The amount of token0 involved in the transaction, expressed as a `Quad` value. If this value is positive, it signifies that the user is expected to pay this amount of token0 to the pool. If it's negative, the user is expected to receive this amount of token0 from the pool.
    *   `token1 (Quad)`: The amount of token1 involved in the transaction, also as a `Quad`. Similar to `token0`, a positive value indicates a payment from the user to the pool, and a negative value indicates a payment from the pool to the user.

### Enums
No enums are defined directly within `UserPay.sol`.

### Custom Errors
*   `UserPayToken0Mismatch(int256 expectedToken0, int256 expectedToken1)`: This error is reverted if the `infinityPoolPaymentCallback` mechanism is used, and the actual amount of token0 received by the pool does not precisely match the `expectedToken0` that was calculated by the `translateQuantities` function. This ensures the pool receives the exact amount it's due.
*   `UserPayToken1Mismatch(int256 expectedToken0, int256 expectedToken1)`: Similar to `UserPayToken0Mismatch`, but for token1. It's reverted if the amount of token1 received via callback doesn't match the `expectedToken1`.

### Key Functions

#### Public Function
*   **`makeUserPay(Info memory amounts, PoolState storage pool, address to, bytes calldata data) public returns (int256 expectedToken0, int256 expectedToken1)`**:
    *   This is the main external-facing function for processing payments.
    *   It first calls `translateQuantities` to convert the `Quad` amounts in `amounts` to `int256` wei values (`expectedToken0`, `expectedToken1`).
    *   If `expectedToken0` or `expectedToken1` is negative (user receives), it uses `SafeERC20.safeTransfer` to send tokens to the `to` address.
    *   If payment is expected from the user (positive amounts) and `data` has a length greater than zero, it triggers the `IInfinityPoolPaymentCallback(msg.sender).infinityPoolPaymentCallback(...)`. After the callback returns, it checks if the pool's token balances have increased by the `expectedToken0` and `expectedToken1`. If not, it reverts with `UserPayToken0Mismatch` or `UserPayToken1Mismatch`.
    *   If payment is expected and `data` is empty, it attempts to pull tokens directly from `msg.sender` using `SafeERC20.safeTransferFrom`.

#### Internal Functions
*   **`makeUserPay(Info memory amounts, PoolState storage pool, bytes calldata data) internal returns (int256 expectedToken0, int256 expectedToken1)`**:
    *   An internal overload of the public `makeUserPay` function. It simplifies calls from within the same contract (or other libraries used by the core pool) by defaulting the recipient (`to`) of any outgoing funds (when `amounts` are negative) to `msg.sender`.

*   **`translateQuantities(Info memory amounts, PoolState storage pool) internal view returns (int256, int256)`**:
    *   A helper function that converts the `Quad` values for `token0` and `token1` from the `amounts` struct into their `int256` wei representations. It achieves this by multiplying the `Quad` amounts by the respective `pool.tenToPowerDecimals0` and `pool.tenToPowerDecimals1` scaling factors (which account for the number of decimals in each token) and then applying the `round` function.

*   **`round(Quad amount) internal pure returns (int256)`**:
    *   A utility function that takes a `Quad` amount and rounds it to an `int256` by calling `ceil(amount)`. The comment in the code, "always round to +infinity so that user pay more and receive less," clarifies that this rounding method is chosen to be conservative and slightly favor the pool in cases of fractional amounts.

### Key Dependencies
*   **`PoolState` (from `src/interfaces/IInfinityPoolState.sol`)**: Essential for accessing the addresses of `token0` and `token1`, and their respective decimal scaling factors (`tenToPowerDecimals0`, `tenToPowerDecimals1`) which are crucial for `translateQuantities`.
*   **`ABDKMathQuad/Quad.sol`** and **`ABDKMathQuad/Math.sol`**: These provide the `Quad` fixed-point arithmetic type and mathematical functions like `ceil` used in `round`.
*   **OpenZeppelin `SafeERC20.sol`** and **`IERC20.sol`**: Used for executing ERC20 token transfers securely (`safeTransfer`, `safeTransferFrom`) and for interacting with token contracts to check balances.
*   **`IInfinityPoolPaymentCallback.sol`**: This interface defines the `infinityPoolPaymentCallback` function that allows for a flexible payment mechanism, where the `msg.sender` (typically the contract initiating the payment flow, like `PeripheryActions`) can implement custom logic to source the required funds.

---

### `IInfinityPoolState.sol` - Interface & Struct

*(Protocol Importance: 10/10)*

**Description:**
While `IInfinityPoolState.sol` defines an empty interface `IInfinityPoolState`, its primary significance comes from the `PoolState` struct it declares. The `PoolState` struct is a comprehensive data structure that holds all the state variables for an Infinity Pool. It serves as the single source of truth for the pool's current operational status, parameters, and tracked financial data.

**Key Functionalities & Data Points:**

*   **Core Pool Parameters:** Includes `era`, `tickBin`, `splits`, token addresses (`token0`, `token1`), `factory` address, and initialization status (`isPoolInitialized`).
*   **Decimal Precision Cache:** `tenToPowerDecimals0` and `tenToPowerDecimals1` for efficient calculations.
*   **Fee and Spread Parameters:** `fee`, `epsilon`, `twapSpread`, `halfspread`.
*   **Time-Related State:** `date`, `deflator`, `entryDeflator`, `binFrac` (fraction of current bin elapsed).
*   **Surplus Tracking:** `surplus0` and `surplus1` to account for excess tokens.
*   **Liquidity Tracking:**
    *   `minted`: Total minted liquidity across bins (using `BoxcarTubFrame.Info`).
    *   `lent`: Total lent liquidity (using `JumpyFallback.Info`).
    *   `lentEnd`: Tracks end of lending periods (using `DropFaberTotals.Info`).
    *   `used`: Liquidity utilization ratio (using `JumpyFallback.Info`).
    *   `owed`: Owed liquidity (using `JumpyFallback.Info`).
    *   `joinStaged`: Staged liquidity for joining pools (using `GapStagedFrame.Info`).
*   **Price and Movement Tracking:**
    *   `dayMove`: Daily price movement (using `BucketRolling.Info`).
    *   `priceRun` & `reserveRun`: SparseFloat structures for tracking price and reserve movements.
*   **Expiration and Resets:**
    *   `expire`: Manages expiring liquidity/positions (using `DeadlineSet.Info`, part of `DropsGroup`).
    *   `resets`: Tracks deadline-based boolean flags (using `DeadlineFlag.Info`).
*   **Flow and Fee Management:**
    *   `flowHat`: Tracks anticipated flows (using `JumpyAnchorFaber.Info`).
    *   `flowDot`: Tracks realized flows (using `EraBoxcarMidSum.Info`).
    *   `fees`: Manages fee accrual and distribution (using `GrowthSplitFrame.Info`).
    *   `offRamp`: Manages liquidity exiting the pool (using `BoxcarTubFrame.Info`).
    *   `netting`: Manages netting of obligations (using `NettingGrowth.Info`).
*   **LP and Swapper Positions:**
    *   `lps`: An array storing information about Liquidity Provider positions (`LP.Info[]`).
    *   `swappers`: An array storing information about Swapper positions (`SwapperInternal.Info[]`).
*   **Capping Mechanism:**
    *   `capper`: A mapping to `Capper.Info` to manage position caps, keyed by a hash of `(tick, token)`.

**Dependencies & Key Imports:**

*   `src/types/ABDKMathQuad/Quad.sol` (for `Quad` fixed-point math)
*   Various internal libraries for specific data structures and accounting logic:
    *   `JumpyAnchorFaber.sol`
    *   `BoxcarTubFrame.sol`
    *   `JumpyFallback.sol`
    *   `DropFaberTotals.sol`
    *   `DeadlineJumps.sol` (including `DropsGroup`, `DeadlineSet`)
    *   `EraBoxcarMidSum.sol`
    *   `GrowthSplitFrame.sol`
    *   `GapStagedFrame.sol`
    *   `BucketRolling.sol`
    *   `DeadlineFlag.sol`
    *   `NettingGrowth.sol`
    *   `Capper.sol`
    *   `SparseFloat.sol`
*   External libraries for position types:
    *   `src/libraries/external/LP.sol`
    *   `src/libraries/external/Swapper.sol` (for `SwapperInternal.Info`)

**Importance Rating:** **10/10**

**Reasoning for Importance:**
The `PoolState` struct is the heart of each Infinity Pool, containing all critical data required for its operation. Understanding its structure and the meaning of its fields is fundamental for interacting with and developing on top of the Infinity Pools protocol. Any operation that reads or modifies pool state will interact with this struct.

## VaultActions Library (`VaultActions.sol`)

*(Protocol Importance: 8/10)*

### Overall Description
The `VaultActions.sol` library provides a suite of functions for managing user assets within a system that interacts with Infinity Pools, likely a vault or a periphery contract. It handles ERC20 token deposits (including those via Permit2), withdrawals, collateral management for Infinity Pools, and ERC20 allowance Pnmechanisms. It acts as a centralized point for these common actions, ensuring consistent handling of user funds and interactions with underlying pool mechanics.

### Key Data Structures (Storage Mappings)
The library primarily operates on storage mappings passed in as arguments by the calling contract. These are crucial for its stateful operations:
*   **`deposits`: `mapping(address => mapping(address => uint256))`**
    *   Stores the balance of each ERC20 token (`address token`) for each user (`address user`).
*   **`collaterals`: `mapping(address user => mapping(address token0 => mapping(address token1 => mapping(bool isToken0 => uint256))))`**
    *   Tracks the amount of collateral a `user` has for a specific Infinity Pool (identified by `token0` and `token1`), distinguishing between token0 (`isToken0 = true`) and token1 (`isToken0 = false`).
*   **`allowance`: `mapping(address user => mapping(address token => mapping(address spender => uint256)))`**
    *   Manages ERC20 allowances granted by a `user` (owner) to a `spender` for a specific `token`.

### Events
*   **`Deposit(address indexed token, address indexed to, uint256 amount)`**: Emitted when a user deposits ERC20 tokens.
*   **`Withdraw(address indexed token, address indexed from, uint256 amount)`**: Emitted when a user withdraws ERC20 tokens.
*   **`DepositCollateral(address indexed user, address indexed poolAddress, bool token, uint8 decimals, address source, uint256 amount)`**: Emitted when collateral is added for a user in an Infinity Pool.
*   **`WithdrawCollateral(address indexed user, address indexed poolAddress, bool token, uint8 decimals, address destination, uint256 amount)`**: Emitted when collateral is withdrawn for a user from an Infinity Pool.

### Custom Errors
*   **`NonExistentToken()`**: Reverts if an operation is attempted on an ERC20 token address that has no deployed code (used in Permit2 flow).
*   **`VaultERC20InsufficientAllowance(address token, address owner, address spender, uint256 allowance, uint256 needed)`**: Reverts if a spender attempts to use more tokens than allowed by the owner.
*   **`NotEnoughDeposit()`**: Reverts if a user attempts to withdraw more tokens than they have deposited.
*   **`InvalidToken()`**: Reverts if a token provided is not one of the two tokens (token0 or token1) of a specified Infinity Pool pair.
*   **`ETHTransferFailed()`**: (Note: Defined in the provided snippet but not directly used by the functions shown. Typically for failed native ETH transfers).

### Key Functions

#### 1. Deposit Management
*   **`depositERC20(deposits, permit2, token, to, amount, isPermit2, nonce, deadline, signature)`**:
    *   Handles ERC20 token deposits into the vault system.
    *   Supports standard `transferFrom` and EIP-2612 style permits via `IPermit2` for gasless approvals.
    *   If `isPermit2` is true, it uses `permit2.permitTransferFrom` to pull tokens.
    *   Otherwise, it uses `SafeERC20.safeTransferFrom`.
    *   Calls the internal `_depositERC20` to update the user's balance.
*   **`_depositERC20(deposits, token, to, amount)`**:
    *   Internal function to increment the deposit balance of `token` for user `to` by `amount`.
    *   Emits a `Deposit` event.

#### 2. Withdrawal Management
*   **`_withdrawERC20Capped(deposits, allowance, token, onBehalfOf, to, amount)`**:
    *   Handles ERC20 withdrawals.
    *   Allows withdrawing up to the user's full deposit (`type(uint256).max` for `amount`).
    *   If `msg.sender` is not `onBehalfOf`, it first spends the allowance via `_spendAllowance`.
    *   Calls `_withdrawERC20WithoutCheckingForAllowance` to perform the actual withdrawal.
    *   Returns the amount withdrawn.
*   **`_withdrawERC20WithoutCheckingForAllowance(deposits, token, onBehalfOf, to, amount)`**:
    *   Internal function that performs the core withdrawal logic.
    *   Checks for sufficient deposit (`NotEnoughDeposit`).
    *   Decrements the user's deposit balance.
    *   Transfers the tokens to the `to` address using `SafeERC20.safeTransfer` (if `to` is not the contract itself).
    *   Emits a `Withdraw` event.

#### 3. Collateral Management (for Infinity Pools)
*   **`addCollateralCapped(deposits, collaterals, allowance, factory, tokenA, tokenB, token, user, amount)`**:
    *   Allows a `user` to add `token` (which must be `tokenA` or `tokenB`) as collateral for the Infinity Pool defined by `tokenA` and `tokenB`.
    *   First withdraws the `amount` from the user's deposits in the vault using `_withdrawERC20Capped`.
    *   Then calls `_increaseCollateral` to update the collateral record.
    *   Returns the amount of collateral added.
*   **`_increaseCollateral(collaterals, factory, token0, token1, token, user, source, amount)`**:
    *   Internal function to increase a `user`'s collateral for the pool (`token0`, `token1`).
    *   Determines if `token` is `token0` or `token1` for the pool using `_getToken`.
    *   Increments the corresponding collateral balance.
    *   Emits a `DepositCollateral` event, including pool address and token decimals.
*   **`_decreaseCollateral(collaterals, factory, token0, token1, token, user, destination, amount)`**:
    *   Internal function to decrease a `user`'s collateral.
    *   Determines if `token` is `token0` or `token1`.
    *   Decrements the collateral balance.
    *   Emits a `WithdrawCollateral` event.
*   **`_getToken(address token0, address token1, address token) pure returns (bool)`**:
    *   Helper function to determine if a given `token` is `token0` (returns `Z` from `Constants.sol`, typically false) or `token1` (returns `I`, typically true) of a pool. Reverts with `InvalidToken` if it's neither.

#### 4. ERC20 Allowance Management
*   **`_spendAllowance(allowance, token, owner, spender, value)`**:
    *   Internal function to decrease the allowance granted by `owner` to `spender` for `token` by `value`.
    *   Reverts with `VaultERC20InsufficientAllowance` if `value` exceeds current allowance.
*   **`approveERC20(allowance, token, spender, amount)`**:
    *   Allows `msg.sender` to set an ERC20 `allowance` for `spender` on `token` to a specific `amount`.
*   **`increaseAllowanceERC20(allowance, token, spender, amount)`**:
    *   Allows `msg.sender` to increase their ERC20 `allowance` for `spender` on `token` by `amount`.

### Dependencies
*   **OpenZeppelin Contracts:**
    *   `@openzeppelin/contracts/utils/Address.sol` (for `Address` library utilities).
    *   `@openzeppelin/contracts/token/ERC20/IERC20.sol` (standard ERC20 interface).
    *   `@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol` (for safe ERC20 token transfers).
    *   `@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol` (to get token decimals).
*   **Infinity Pools Protocol & Periphery:**
    *   `src/periphery/interfaces/external/IPermit2.sol` (interface for Uniswap's Permit2 contract).
    *   `src/interfaces/IInfinityPoolFactory.sol` (to get pool addresses from token pairs).
    *   `src/Constants.sol` (for `Z` and `I` constants representing token0 and token1 flags).