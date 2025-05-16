# InfinityPools Project

This project contains an EIP-1967 compliant upgradeable proxy contract and a Python script to query its implementation address.

## Smart Contracts

For detailed information about the Solidity smart contracts, interfaces, and libraries in this project, please see [CONTRACT_DETAILS.md](./CONTRACT_DETAILS.md).

## Query Implementation Script (`query_implementation.py`)

This Python script queries the EIP-1967 storage slot of an Ethereum proxy contract to retrieve its current implementation address.

### Purpose

To allow users to easily find out which logic contract a given EIP-1967 proxy contract is currently pointing to on the blockchain.

### Requirements

*   Python 3.12+
*   `web3.py` library (installable via `requirements.txt`)

### Setup

1.  **Clone the repository (if applicable) or ensure you have `query_implementation.py` and `requirements.txt`.**
2.  **Create and activate a Python virtual environment:**
    ```bash
    # Using uv (recommended)
    uv venv .venv -p 3.12
    source .venv/bin/activate  # Linux/macOS
    # .venv\Scripts\activate    # Windows
    uv pip install -e .  # Local install for development
    ```

4.  **Create a `.env` file** in the same directory as the script with your Ethereum node's RPC URL:
    ```
    BASE_RPC_URL='your_full_rpc_url_here'
    ```
    *Example:* `BASE_RPC_URL='https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID'` or `BASE_RPC_URL='https://base-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_API_KEY'`

5.  **(Optional) Update Proxy Contract Address:**
    The script defaults to `PROXY_CONTRACT_ADDRESS = "0xf8fad01b2902ff57460552c920233682c7c011a7"`.
    If you need to query a different proxy contract, change this value directly in `query_implementation.py`.

### Usage

Once set up, run the script from your terminal:

```bash
python query_implementation.py
```

### Example Output

The script will output the connection status, the proxy and slot being queried, and the retrieved implementation address:

```
Loaded BASE_RPC_URL from .env
--- Querying EIP-1967 Implementation Slot ---
Connected to Ethereum node: True
Querying storage slot 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc for proxy contract at 0xF8FAD01B2902fF57460552C920233682c7c011a7...

Proxy Contract: 0xf8fad01b2902ff57460552c920233682c7c011a7
Implementation Slot: 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
Current Implementation Address: 0x6C711E6bbD9955449bBcc833636a9199DfA7cA65
```
