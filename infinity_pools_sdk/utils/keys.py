"""Manage keys."""

import os

from eth_keys import keys
from eth_utils.conversions import to_bytes
from eth_utils.crypto import keccak
from eth_utils.curried import text_if_str
from hexbytes import HexBytes
from web3 import Web3


def make_private_key(extra_entropy: bytes | str | None = None) -> str:
    """Make a private key.

    Arguments
    ---------
    extra_entropy: bytes | str | None, optional
        Additional entropy to mix with the random bytes.
        If None, additional random bytes will be used.

    Returns
    -------
    str
        The private key.
    """
    if extra_entropy is None:
        # Just use more random bytes for additional entropy
        extra_entropy = os.urandom(16)  # 16 more random bytes
    extra_key_bytes = text_if_str(to_bytes, extra_entropy)
    key_bytes = keccak(os.urandom(32) + extra_key_bytes)
    return HexBytes(key_bytes).hex()

def get_public_key_from_private_key(private_key: str) -> str:
    """Get the public key from a private key.

    Arguments
    ---------
    private_key: str
        The private key in hex format

    Returns
    -------
    str
        The public key in hex format
    """
    # For Ethereum, we need to derive the public key from the private key
    # using the eth-keys library which is used internally by Web3
    try:
        # Remove '0x' prefix if present
        if private_key.startswith('0x'):
            private_key = private_key[2:]

        # Create a PrivateKey object
        private_key_bytes = bytes.fromhex(private_key)
        private_key_obj = keys.PrivateKey(private_key_bytes)

        # Get the public key
        public_key = private_key_obj.public_key

        # Just return the public key in hex format
        return public_key.to_hex()
    except ImportError:
        # Fallback method if eth_keys is not available
        web3 = Web3()
        account = web3.eth.account.from_key(private_key)
        # Use the address as a fallback (not the actual public key)
        return f"Error: eth_keys library not available. Address: {account.address}"
