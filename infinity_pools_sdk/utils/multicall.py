"""Multicall."""

import logging
import re
import time
import traceback
from typing import Type

from multicall import Call, Multicall
from web3 import Web3
from web3.contract import Contract


# FIXME: Return handlers. This will not work for functions with multiple outputs
def batch_multicall(web3: Web3, contract_address: str | list[str], function_signature: str | list[str], args_list: list, batch_size=None, require_success=True):
    """Execute multiple contract calls in a single multicall to improve efficiency.

    Parameters
    ----------
    web3 : Web3
        Web3 instance
    contract_address : str or list
        Address of the contract to call, or list of addresses (one per call in args_list)
    function_signature : str or list
        Function signature with return type, e.g., 'getActiveMarketAddress(uint256)(address)'
    args_list : list
        List of arguments to pass to each function call
    batch_size : int, optional
        Size of batches to process. If None, all calls will be processed in a single batch.
        Use this for very large numbers of calls to avoid hitting gas limits.
    require_success : bool, optional
        Whether to require all calls to succeed. If False, failed calls will return None.

    Returns
    -------
    list
        List of results in the same order as args_list
    """
    # If no batch size is specified, process all calls at once
    if batch_size is None:
        calls = []
        # Convert contract_address to list if it's a string
        addresses = contract_address if isinstance(contract_address, list) else [contract_address] * len(args_list)

        # Convert function_signature to list if it's a string
        signatures = function_signature if isinstance(function_signature, list) else [function_signature] * len(args_list)

        for idx, args in enumerate(args_list):
            # Handle both single arguments and lists of arguments
            call_args = [args] if not isinstance(args, (list, tuple)) else list(args)
            # Get the appropriate contract address
            target_address = addresses[idx] if idx < len(addresses) else addresses[0]
            calls.append(Call(
                target_address,
                [signatures[idx]] + call_args,
                [[str(idx), None]],  # Use the index as the key
            ))

        # Execute the multicall
        results = Multicall(calls, _w3=web3, require_success=require_success)()

        # Extract results in order
        ordered_results = []
        for idx in range(len(args_list)):
            if str(idx) in results:
                ordered_results.append(results[str(idx)])
            else:
                ordered_results.append(None)  # Handle missing results

        return ordered_results

    # Process in batches if batch_size is specified
    all_results = []
    for batch_start in range(0, len(args_list), batch_size):
        batch_end = min(batch_start + batch_size, len(args_list))
        batch_args = args_list[batch_start:batch_end]

        # Process this batch
        batch_results = batch_multicall(web3, contract_address, function_signature, batch_args, None, require_success)
        all_results.extend(batch_results)

    return all_results