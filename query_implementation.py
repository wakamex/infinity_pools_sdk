import os

from web3 import Web3


def load_env_vars(env_path=".env"):
    """Load specific environment variables (e.g., BASE_RPC_URL, ALCHEMY_API_KEY) from a .env file."""
    loaded_vars = []
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith("#") or "=" not in stripped_line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'\"")  # Remove potential quotes
                # Target specific keys we might use
                if key in ["BASE_RPC_URL", "ALCHEMY_API_KEY"]:
                    os.environ[key] = value
                    if key not in loaded_vars:
                        loaded_vars.append(key)
        if loaded_vars:
            print(f"Loaded {', '.join(loaded_vars)} from {env_path}")
    except FileNotFoundError:
        print(f"Warning: {env_path} file not found. Required variables (e.g., BASE_RPC_URL) should be set directly in your environment.")
    except Exception as e:
        print(f"Warning: Error reading {env_path}: {e}")


# Load environment variables from .env file (if it exists)
load_env_vars()

# --- Configuration ---
# ALCHEMY_API_KEY is loaded by load_env_vars if present in .env, but not directly used for RPC URL construction anymore.
# os.getenv("ALCHEMY_API_KEY") could be used if needed for other specific Alchemy features.

BASE_RPC_URL = os.getenv("BASE_RPC_URL")
if not BASE_RPC_URL:
    raise ValueError("BASE_RPC_URL not found in environment variables. Please set it in your .env file or ensure it's set directly in your environment.")

# Replace with the actual address of your deployed InfinityPoolsProxy contract
PROXY_CONTRACT_ADDRESS = "0xf8fad01b2902ff57460552c920233682c7c011a7"

# EIP-1967 Implementation slot (keccak256('eip1967.proxy.implementation') - 1)
IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"


def get_implementation_address(rpc_url: str, proxy_address: str, slot: str) -> str:
    """Query the storage slot of a proxy contract to find its implementation address."""
    if proxy_address == "YOUR_PROXY_CONTRACT_ADDRESS_HERE":
        print("Error: Please replace 'YOUR_PROXY_CONTRACT_ADDRESS_HERE' with the actual proxy contract address in the script.")
        return ""

    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to Ethereum node at {rpc_url}")

    # Ensure the proxy_address is checksummed before use with web3.py functions
    try:
        checksummed_proxy_address = w3.to_checksum_address(proxy_address)
    except ValueError:
        # This typically means the address string is not a valid hex address format
        print(f"Error: The provided proxy address '{proxy_address}' is not a valid Ethereum address format.")
        return ""

    print(f"Connected to Ethereum node: {w3.is_connected()}")
    print(f"Querying storage slot {slot} for proxy contract at {checksummed_proxy_address}...")

    try:
        # eth_getStorageAt returns 32 bytes (64 hex characters + '0x')
        # The slot should also be a hex string; IMPLEMENTATION_SLOT is already defined as such.
        slot_as_int: int = int(slot, 16)
        storage_value_bytes = w3.eth.get_storage_at(checksummed_proxy_address, slot_as_int)

        hex_value = w3.to_hex(storage_value_bytes)

        if len(hex_value) < 42:  # '0x' + 40 chars
            print(f"Warning: Storage value '{hex_value}' is shorter than expected for an address.")
            implementation_address_hex = f"0x{hex_value[2:].zfill(40)}"  # Pad if too short
        else:
            implementation_address_hex = f"0x{hex_value[-40:]}"

        # Check if it's a valid address (checksumming is optional here but good practice)
        if w3.is_address(implementation_address_hex):
            return w3.to_checksum_address(implementation_address_hex)
        else:
            # Handle cases where the slot might be empty or not an address
            if int(implementation_address_hex, 16) == 0:
                return "0x0000000000000000000000000000000000000000 (Zero Address - No implementation set or beacon is zero)"
            return f"Invalid address format: {implementation_address_hex}"
    except Exception as e:
        print(f"An error occurred: {e}")
        return ""


if __name__ == "__main__":
    print("--- Querying EIP-1967 Implementation Slot ---")

    implementation_addr = get_implementation_address(
        BASE_RPC_URL,
        PROXY_CONTRACT_ADDRESS, IMPLEMENTATION_SLOT)

    if implementation_addr:
        print(f"\nProxy Contract: {PROXY_CONTRACT_ADDRESS}")
        print(f"Implementation Slot: {IMPLEMENTATION_SLOT}")
        print(f"Current Implementation Address: {implementation_addr}")

    print("\n--- Instructions ---")
    print("1. Ensure you have Python and `uv` installed.")
    print("2. Create a `.env` file in this directory with your BASE_RPC_URL:")
    print("   BASE_RPC_URL='your_full_rpc_url_here' (e.g., https://base-mainnet.g.alchemy.com/v2/your_key_if_needed_by_provider_or_just_the_url)")
    print("   (Optional: ALCHEMY_API_KEY='your_api_key' if needed for other purposes or by other scripts)")
    print("   Ensure no extra spaces around the '=' and values are not unnecessarily quoted.")
    print("3. Ensure PROXY_CONTRACT_ADDRESS in this script is correct for the network specified by BASE_RPC_URL.")
    print("   (Currently set to: 0xf8fad01b2902ff57460552c920233682c7c011a7)")
    print("5. Create a virtual environment: `uv venv .venv`")
    print("6. Activate the virtual environment: `source .venv/bin/activate` (Linux/macOS) or `.venv\\Scripts\\activate` (Windows)")
    print("7. Install dependencies: `uv pip install -r requirements.txt`")
    print("8. Run the script: `python query_implementation.py`")
