import json
import os


def load_abi(filename: str) -> list:
    """Load ABI from JSON file in the data/abis directory.

    Args:
        filename: Name of the JSON file (e.g., "InfinityPoolsPeriphery.json" or just "InfinityPoolsPeriphery")

    Returns:
        The ABI as a list
    """
    if not filename.endswith('.json'):
        filename += '.json'

    # Path from this file (infinity_pools_sdk/abis/loader.py)
    # to the ABI directory (infinity_pools_sdk/data/abis/)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # current_dir = /code/infinitypools/infinity_pools_sdk/abis
    # abi_dir should be /code/infinitypools/infinity_pools_sdk/data/abis
    abi_dir = os.path.join(current_dir, '..', 'data', 'abis')
    abi_path = os.path.join(abi_dir, filename)

    try:
        with open(abi_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback for when tests might be run from a different working directory structure
        # or if the package structure isn't perfectly resolved in the test environment.
        # This attempts to go up two levels from loader.py (to infinity_pools_sdk), then down to data/abis.
        # A more robust solution might involve `pkg_resources` or `importlib.resources` if this were a distributed package.
        alt_base_dir = os.path.dirname(os.path.dirname(current_dir)) # Should be /code/infinitypools/infinity_pools_sdk
        alt_abi_path = os.path.join(alt_base_dir, 'data', 'abis', filename)
        try:
            with open(alt_abi_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
             # Final fallback if the expected structure is from project root (e.g. /code/infinitypools/infinity_pools_sdk/data/abis)
            project_root_abi_path = os.path.join(os.path.dirname(alt_base_dir), 'infinity_pools_sdk', 'data', 'abis', filename)
            try:
                with open(project_root_abi_path, 'r') as f:
                    return json.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(f"ABI file not found. Checked: {abi_path}, {alt_abi_path}, and {project_root_abi_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in ABI file ({abi_path} or alternatives tried): {e}")
