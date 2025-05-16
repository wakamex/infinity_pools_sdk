# Product Requirements Document: Infinity Pools Python SDK

**Version:** 1.0
**Date:** 2025-05-16

## 1. Introduction

This document outlines the requirements for a Python Software Development Kit (SDK) designed to facilitate interaction with the Infinity Pools decentralized finance (DeFi) protocol. The Infinity Pools protocol, primarily accessed via the `InfinityPoolsPeriphery.sol` smart contract, offers functionalities for liquidity provision, token swaps, and management of complex financial positions as Non-Fungible Tokens (NFTs). This SDK aims to provide Python developers with a high-level, intuitive, and robust interface to integrate these protocol features into their applications, bots, and scripts.

## 2. Goals

*   **Simplify Integration:** Abstract away the complexities of direct smart contract interaction (ABI encoding/decoding, gas management, transaction signing) for common Infinity Pools operations.
*   **Improve Developer Experience:** Offer a Pythonic, well-documented, and easy-to-use library.
*   **Enhance Readability:** Provide clear methods and data structures that map logically to protocol concepts.
*   **Promote Robustness:** Include comprehensive error handling, type safety (where possible in Python), and thorough testing.
*   **Facilitate Common Workflows:** Streamline typical user actions such as adding/removing liquidity, performing swaps, managing NFT positions, and querying pool/position states.

## 3. Target Audience

*   **DeFi Application Developers:** Building custom frontends, dashboards, or analytics tools for Infinity Pools.
*   **Arbitrage Bot Developers:** Creating automated trading strategies that leverage Infinity Pools.
*   **Liquidity Management Script Writers:** Automating LP position management.
*   **Data Analysts & Researchers:** Querying protocol data and state for analysis.
*   **Technical Traders:** Executing protocol interactions programmatically.

## 4. Key Features & Requirements

The SDK will primarily wrap functionalities exposed by `InfinityPoolsPeriphery.sol` and related utility contracts/libraries.

### 4.1. Core Protocol Interactions

*   **Connection Management:**
    *   Ability to connect to an Ethereum node (e.g., via Web3.py using HTTP, WebSocket, or IPC).
    *   Configuration for different networks (mainnet, testnets).
*   **Contract Instances:**
    *   Easy instantiation of `InfinityPoolsPeriphery` and other relevant contract objects (e.g., `IInfinityPoolFactory`, ERC20, ERC721 for NFTs).
    *   Automatic loading of ABIs and contract addresses for supported networks.
*   **Account Management:**
    *   Support for using local private keys for signing transactions.
    *   Integration with wallet providers or hardware wallets (stretch goal).
*   **Position & ID Management (as per `InfinityPools_SDK_Guide.md`):
    *   `encodeId()`: Helper function to construct `tokenId`s.
    *   `decodeId()`: Helper function to parse `tokenId`s (if `EncodeIdHelper.decodeId` is exposed or re-implementable).
*   **Liquidity Operations (LP Positions - NFT Gated):
    *   `addLiquidity()`: Wrapper with Pythonic input for `AddLiquidityParams`.
    *   `collect()`: Wrapper function.
    *   `drain()`: Wrapper function.
    *   `tap()`: Wrapper function.
*   **Swap Integration & Internal Collateral Management:
    *   `swapDeposit()`: Wrapper with Pythonic input for `SwapInfo`.
    *   `withdrawCollaterals()`: Wrapper function.
*   **Complex DeFi Actions (Swapper Positions - NFT Gated):
    *   `newLoanWithSwap()`: Wrapper with Pythonic input for `NewLoan.NewLoanParams`, `Spot.SpotSwapParams`, and `SwapInfo`.
    *   `batchActionsOnSwappers()`: Wrapper with Pythonic input for `BatchActionsParams`.
    *   `reflow()`: Wrapper with Pythonic input for `ReflowParams` and `SwapInfo`.
*   **Pool & Factory Discovery (View Functions):
    *   `getPoolAddress()`: (both overloaded versions).
    *   `getFactoryAddress()`.
*   **ERC20/NFT Interactions:**
    *   Standard ERC20 functions (`approve`, `balanceOf`, `transfer`, etc.) for tokens involved.
    *   Standard ERC721 functions (`ownerOf`, `tokenURI`, `isApprovedForAll`, `approve`, `setApprovalForAll`, `transferFrom`) for position NFTs.

### 4.2. Data Handling & Utilities

*   **Parameter Structs:** Provide Python classes or dictionaries for easy construction of complex input parameters (e.g., `AddLiquidityParams`, `SwapInfo`, `BatchActionsParams`).
*   **`Quad` Type Handling:** Utilities to convert Python numbers (float, Decimal) to and from the `Quad` fixed-point format used by the protocol.
*   **Return Value Parsing:** Automatically parse and return transaction receipts and decoded event logs in a user-friendly format.
*   **Transaction Building & Sending:**
    *   Functions to build and sign transactions.
    *   Option to send transactions and wait for confirmation, with configurable timeouts.
    *   Estimation of gas fees.

### 4.3. Error Handling

*   Translate common blockchain errors (e.g., out of gas, reverted transaction) into Python exceptions.
*   Parse custom errors defined in the smart contracts (e.g., `InvalidTokenOrder`, `PoolDoesNotExist`) and raise specific Python exceptions.
*   Provide clear error messages.

### 4.4. Event Subscription & Handling

*   Ability to subscribe to and listen for events emitted by `InfinityPoolsPeriphery` and individual pool contracts.
*   Provide event decoders to parse event data into Python objects.
*   Support for event filtering.

### 4.5. Configuration

*   Mechanisms for configuring contract addresses for different networks (e.g., mainnet, Sepolia, local).
*   Configuration for RPC endpoints.
*   Default gas settings (price, limit) with override options.

### 4.6. Documentation

*   Comprehensive API documentation (e.g., using Sphinx/ReadTheDocs).
*   Tutorials and example usage for common workflows.
*   Clear installation and setup instructions.
*   A `README.md` with an overview, quick start, and contribution guidelines.

## 5. Testing Strategy

A robust testing suite is critical for the reliability and security of the SDK.

### 5.1. Unit Tests

*   **Scope:** Test individual functions, classes, and modules in isolation.
*   **Focus:** Logic for data type conversions (esp. `Quad`), parameter encoding, ABI interactions (mocked), error handling, and utility functions.
*   **Tools:** `pytest` framework.
*   **Mocking:** Use `unittest.mock` or similar to mock external dependencies like Web3.py calls and actual blockchain interactions.

### 5.2. Integration Tests

*   **Scope:** Test interactions between SDK components and actual smart contracts deployed on a test environment.
*   **Environment:** 
    *   Utilize a local development blockchain (e.g., Hardhat/Anvil node with forking capabilities from a testnet or mainnet if necessary).
    *   Deploy the Infinity Pools contracts (or use existing deployments on a public testnet like Sepolia).
*   **Focus:** End-to-end workflows such as adding liquidity, performing a swap, creating a loan, and then verifying state changes on the blockchain.
*   **Test Accounts:** Use pre-funded accounts on the local/test network.
*   **Assertions:** Verify transaction success, emitted events, and expected changes in contract state (e.g., balances, NFT ownership, pool parameters).

### 5.3. Test Coverage

*   **Goal:** Aim for >90% unit test coverage and significant coverage for critical integration test paths.
*   **Tools:** `pytest-cov` or similar to measure and report coverage.

### 5.4. Continuous Integration (CI)

*   **Setup:** Implement a CI pipeline (e.g., GitHub Actions).
*   **Triggers:** Run tests automatically on every push and pull request to main branches.
*   **Checks:** Include linting (e.g., Flake8, Black), type checking (e.g., MyPy), and test execution.
*   **Reporting:** Report test results and coverage in the CI environment.

### 5.5. Test Data & Fixtures

*   Use `pytest` fixtures to set up common test data, contract instances, and account states.
*   For integration tests, define scripts or fixtures to deploy/configure contracts and pre-fund accounts if using a fresh local node.

## 6. Non-Functional Requirements

*   **Performance:** SDK operations should be efficient and not introduce undue latency beyond normal blockchain interaction times.
*   **Security:** 
    *   Avoid introducing vulnerabilities (e.g., improper handling of private keys if managed by the SDK).
    *   Follow best practices for interacting with smart contracts.
    *   Dependencies should be vetted.
*   **Usability (Developer Experience):** The SDK should be intuitive, well-documented, and easy to integrate. Pythonic design is key.
*   **Maintainability:** Code should be well-structured, modular, and include inline comments where necessary. Follow PEP 8 guidelines.
*   **Reliability:** The SDK should be stable and behave predictably.
*   **Compatibility:** Specify compatible Python versions (e.g., Python 3.8+).

## 7. Future Considerations (Post V1.0)

*   Asynchronous support (e.g., using `async/await` with Web3.py's async features).
*   Support for Layer 2 solutions if Infinity Pools deploys there.
*   Advanced analytics helper functions.
*   More sophisticated gas price estimation strategies.
*   Integration with popular Python trading frameworks.
*   GUI or CLI tool built on top of the SDK for simple interactions.

## 8. Success Metrics

*   **Adoption:** Number of downloads/installs (e.g., from PyPI).
*   **Community Engagement:** Number of GitHub stars, forks, issues, and pull requests.
*   **Developer Satisfaction:** Feedback from users (e.g., via GitHub issues, community channels).
*   **Reliability:** Low rate of critical bugs reported post-release.
*   **Test Coverage:** Meeting or exceeding defined test coverage goals.

---
