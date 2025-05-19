"""Get contract."""

import logging
import re
import time
import traceback
from typing import Type

from web3 import Web3
from web3.contract import Contract


def get_contract(web3: Web3, address: str, abi: list) -> Type[Contract]:
    """Get a web3 contract."""
    return web3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)
