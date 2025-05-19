# Infinity Pools Offchain Scripts

This directory contains a collection of Python scripts designed to interact with the Infinity Pools API for various offchain data retrieval tasks. Each script targets a specific API endpoint and demonstrates how to fetch and display relevant information.

## Scripts

Below is a list of the scripts available in this directory, along with a brief description of their purpose and the API endpoint they utilize.

### `alchemy.py`
-   **Purpose**: Fetches and displays historical price bar data (candlesticks) for a given liquidity pool.
-   **API Endpoint**: `/pool_price_bars`
-   **Key Functionality**: Retrieves time-series data for pool prices, useful for charting or historical analysis.

### `infinity.py`
-   **Purpose**: Fetches the current liquidity ratio for a specified pair of assets. This can be used to determine a suggested quote asset size for a given base asset size before providing liquidity.
-   **API Endpoint**: `/liquidityRatio/{token0}/{token1}/{param3}/{param4}`
-   **Key Functionality**: Provides an estimate for balancing liquidity provision.

### `liquidity_positions.py`
-   **Purpose**: Fetches and displays all existing liquidity positions for a specified wallet address.
-   **API Endpoint**: `/liquidity_positions`
-   **Key Functionality**: Allows users to view details of their current and past liquidity provisions, including status, size, and fee information.

### `markets.py`
-   **Purpose**: Fetches and displays general data for all available markets.
-   **API Endpoint**: `/markets`
-   **Key Functionality**: Provides a snapshot of all active markets, including token pairs, pricing, volume, TVL, and APR.

### `markets2.py`
-   **Purpose**: Fetches and displays data for all available markets, similar to `markets.py`, but includes the `adjustPrice=true` parameter in the API request.
-   **API Endpoint**: `/markets?adjustPrice=true`
-   **Key Functionality**: Retrieves market data, potentially with prices adjusted based on certain internal platform logic.

### `orders.py`
-   **Purpose**: Fetches and displays historical order data for a specified wallet address.
-   **API Endpoint**: `/orders`
-   **Key Functionality**: Allows users to review their past trading activity, including filled and cancelled orders.

### `system.py`
-   **Purpose**: Fetches and displays general system-wide information from the Infinity Pools API.
-   **API Endpoint**: `/system`
-   **Key Functionality**: Retrieves global platform parameters, such as current block number, contract addresses, and software release details.

### `trading_positions.py`
-   **Purpose**: Fetches and displays current or recent trading positions (e.g., leveraged positions, shorts) for a specified wallet address.
-   **API Endpoint**: `/trading_positions`
-   **Key Functionality**: Provides insight into a user's active trading exposures and history.

## Common Usage

Most scripts require environment variables to be set for API interaction (e.g., `BASE_RPC_URL`, `PRIVATE_KEY`, `BASE_PERIPHERY_CONTRACT_ADDRESS`), although for these read-only scripts, only an internet connection is typically needed as they query public API endpoints. Some scripts that interact via wallet address (e.g., `liquidity_positions.py`, `orders.py`, `trading_positions.py`) have a hardcoded test wallet address in their `Cookie` header for demonstration purposes. This should be changed to the desired wallet address for actual use.

To run any script:
```bash
python <script_name>.py
```
The output will typically be a JSON formatted response printed to the console.
