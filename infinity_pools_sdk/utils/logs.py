"""Get logs using direct JSON-RPC calls."""

import json
import logging
import os
import re
import time
import traceback
from typing import Any, List

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, RequestException, Timeout
from web3 import Web3
from web3.types import FilterParams, LogReceipt

from infinity_pools_sdk.constants import Web3Objects


class SuggestedRangeError(Exception):
    """Custom exception for when the RPC provider suggests a new block range."""

    def __init__(self, message, suggested_from_block, suggested_to_block, original_exception=None):
        super().__init__(message)
        self.suggested_from_block = suggested_from_block
        self.suggested_to_block = suggested_to_block
        self.original_exception = original_exception



BLOCK_CHUNK_SIZE = 500  # Constant for chunk size
RPC_TIMEOUT_SECONDS = 10 # Timeout for RPC requests


def _fetch_current_block_number_via_rpc(debug: bool = False) -> int:
    """Fetch the current latest block number via a direct JSON-RPC call."""
    rpc_url = os.getenv("BASE_RPC_URL")
    if not rpc_url:
        raise ValueError("BASE_RPC_URL environment variable not set.")

    payload = {
        "jsonrpc": "2.0",
        "id": 1, # Static ID for simplicity
        "method": "eth_blockNumber",
        "params": []
    }

    if debug:
        logging.debug(f"RPC Request (eth_blockNumber) to {rpc_url}: {payload}")

    try:
        response = requests.post(rpc_url, json=payload, timeout=RPC_TIMEOUT_SECONDS)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        response_json = response.json()
        if debug:
            logging.debug(f"RPC Response (eth_blockNumber): {response_json}")

        if "error" in response_json and response_json["error"]:
            error_details = response_json["error"]
            error_message = error_details.get("message", "Unknown RPC error")
            raise Exception(f"RPC Error (eth_blockNumber): {error_message} (Code: {error_details.get('code')})")

        if "result" in response_json:
            return int(response_json["result"], 16)
        else:
            raise Exception("RPC response (eth_blockNumber) did not contain 'result' field.")

    except Timeout:
        raise Exception(f"RPC request (eth_blockNumber) timed out after {RPC_TIMEOUT_SECONDS} seconds.")
    except RequestException as e:
        raise Exception(f"RPC request (eth_blockNumber) failed: {e}")


def parse_suggested_block_range(error_message: str) -> tuple[int | None, int | None]:
    """Extract suggested block range from RPC error message."""
    # Example Alchemy error: 'Log response size exceeded. Try with this block range [0x123, 0x456].'
    match = re.search(r'\[0x([a-fA-F0-9]+), 0x([a-fA-F0-9]+)\]', error_message)
    if match:
        start_block = int(match.group(1), 16)
        end_block = int(match.group(2), 16)
        return start_block, end_block
    return None, None


def _fetch_logs_via_rpc(
    address: str | list[str],
    from_block_hex: str,
    to_block_hex: str,
    topics: list,
    debug: bool = False
) -> list[dict[str, Any]]:
    """Fetch logs for a given block range using a direct JSON-RPC call."""
    rpc_url = os.getenv("BASE_RPC_URL")
    if not rpc_url:
        raise ValueError("BASE_RPC_URL environment variable not set.")

    params_obj = {
        "address": address,
        "fromBlock": from_block_hex,
        "toBlock": to_block_hex,
        "topics": topics
    }

    payload = {
        "jsonrpc": "2.0",
        "id": 2, # Static ID for simplicity, different from eth_blockNumber
        "method": "eth_getLogs",
        "params": [params_obj]
    }

    if debug:
        logging.debug(f"RPC Request (eth_getLogs) to {rpc_url}: {payload}")

    try:
        response = requests.post(rpc_url, json=payload, timeout=RPC_TIMEOUT_SECONDS)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        response_json = response.json()

        if debug:
            logging.debug(f"RPC Response (eth_getLogs): {response_json}")

        if "error" in response_json and response_json["error"]:
            error_details = response_json["error"]
            # Pass the raw error message for parsing by parse_suggested_block_range
            error_message = error_details.get("message", "Unknown RPC error") 
            raise Exception(f"RPC Error (eth_getLogs): {error_message} (Code: {error_details.get('code')})")

        if "result" in response_json:
            return response_json["result"]
        else:
            raise Exception("RPC response (eth_getLogs) did not contain 'result' field.")

    except HTTPError as http_err:
        logging.warning(f"HTTPError during RPC call: {http_err}")
        try:
            error_response_text = http_err.response.text
            logging.debug(f"RPC Error Response Body: {error_response_text}")
            error_data = json.loads(error_response_text)
            
            if http_err.response.status_code == 400 and \
               error_data.get("error", {}).get("code") == -32600:
                
                error_message = error_data.get("error", {}).get("message", "")
                match = re.search(r"this block range should work: \[(0x[0-9a-fA-F]+), (0x[0-9a-fA-F]+)\]", error_message)
                
                if match:
                    suggested_from_hex = match.group(1)
                    suggested_to_hex = match.group(2)
                    suggested_from_block = int(suggested_from_hex, 16)
                    suggested_to_block = int(suggested_to_hex, 16)
                    logging.info(f"Alchemy suggested new range: from {suggested_from_block} to {suggested_to_block}")
                    raise SuggestedRangeError(
                        message=f"Alchemy suggested new block range: {suggested_from_block}-{suggested_to_block}",
                        suggested_from_block=suggested_from_block,
                        suggested_to_block=suggested_to_block,
                        original_exception=http_err
                    )
        except json.JSONDecodeError:
            logging.warning(f"Failed to parse JSON from error response: {error_response_text}")
            # Fall through to generic error if JSON parsing fails
        except Exception as parse_err: # Catch any other error during parsing/regex
            logging.warning(f"Error parsing suggested range: {parse_err}")
            # Fall through to generic error

        # If not the specific suggested range error, or if parsing failed, raise generic HTTP error
        err_msg = f"RPC request (eth_getLogs) failed with HTTPError: {http_err}."
        if hasattr(http_err, 'response') and http_err.response is not None:
            err_msg += f" Response: {http_err.response.text}"
        raise Exception(err_msg)

    except Timeout:
        raise Exception(f"RPC request (eth_getLogs) timed out after {RPC_TIMEOUT_SECONDS} seconds.")
    except RequestException as e:
        # Covers network problems, etc.
        response_text = e.response.text if e.response is not None else "No response body available"
        raise Exception(f"RPC request (eth_getLogs) failed: {e}. Response: {response_text}")


def fetch_events_logs_with_retry(
    address: str | list[str],
    topics: list,
    from_block: int,
    to_block: int | str = "latest",
    retries: int = 3,
    delay: int = 2,
    label: str | None = None,
    debug: bool = False,
) -> list[dict[str, Any]]:
    """Fetch event logs with retry logic and fixed block range limits using web3py get_logs.

    Args:
        address: Contract address or list of addresses to get logs for.
        topics: List of topics to filter logs by (first topic is usually the event signature).
        from_block: Starting block number (inclusive).
        to_block: Ending block number (inclusive) or "latest".
        retries: Number of retry attempts for each block segment.
        delay: Delay between retries in seconds.
        label: Optional label for logging purposes.
        debug: Optional debug flag to print verbose RPC request/response info.

    Returns:
        List of log objects.

    Raises:
        ValueError: If to_block is invalid.
        Exception: If RPC calls fail after retries or other unhandled errors occur.
    """
    w3 = Web3Objects.BASE # Corrected access to w3 instance
    all_logs: list[dict[str, Any]] = [] 
    log_label = f"(Label: {label}) " if label else ""

    if debug:
        logging.debug(f"{log_label}Starting fetch_events_logs_with_retry (web3) for {address} from {from_block} to {to_block}")

    actual_to_block: int
    if to_block == "latest":
        try:
            actual_to_block = _fetch_current_block_number_via_rpc(debug=debug)
            if debug:
                logging.debug(f"{log_label}Resolved 'latest' to block {actual_to_block}")
        except Exception as e:
            logging.error(f"{log_label}Failed to fetch current block number: {e}")
            raise
    elif isinstance(to_block, int):
        actual_to_block = to_block
    else:
        raise ValueError(f"Invalid to_block value: {to_block}. Must be an int or 'latest'.")

    if from_block > actual_to_block:
        logging.warning(f"{log_label}from_block {from_block} is greater than to_block {actual_to_block}. No logs will be fetched.")
        return []

    current_block = from_block
    while current_block <= actual_to_block:
        chunk_to_block = min(current_block + BLOCK_CHUNK_SIZE - 1, actual_to_block)
        
        if debug:
            logging.debug(f"{log_label}Processing chunk: {current_block}-{chunk_to_block}")

        for attempt in range(retries):
            try:
                if debug:
                    logging.debug(f"{log_label}Attempt {attempt + 1}/{retries} for chunk {current_block}-{chunk_to_block}")
                
                # log_filter = {
                #     'fromBlock': current_block,
                #     'toBlock': chunk_to_block,
                #     'address': address,
                #     'topics': topics
                # }
                # class FilterParams(TypedDict, total=False):
                # address: Union[Address, ChecksumAddress, List[Address], List[ChecksumAddress]]
                # blockHash: HexBytes
                # fromBlock: BlockIdentifier
                # toBlock: BlockIdentifier
                # topics: Sequence[Optional[Union[_Hash32, Sequence[_Hash32]]]]
                log_filter: FilterParams = FilterParams(
                    fromBlock=current_block,
                    toBlock=chunk_to_block,
                    address=address,
                    topics=topics
                )
                chunk_logs: List[LogReceipt] = Web3Objects.BASE.eth.get_logs(log_filter)
                
                all_logs.extend(chunk_logs)
                if debug:
                    logging.debug(f"{log_label}Successfully fetched {len(chunk_logs)} logs for chunk {current_block}-{chunk_to_block}")
                break  # Success, exit retry loop
            except (Timeout, RequestsConnectionError) as net_err:
                logging.warning(f"{log_label}Network error on attempt {attempt + 1} for chunk {current_block}-{chunk_to_block}: {net_err}")
                if attempt == retries - 1:
                    logging.error(f"{log_label}Failed to fetch logs for chunk {current_block}-{chunk_to_block} after {retries} retries due to network errors.")
                    raise Exception(f"Failed to fetch logs for chunk {current_block}-{chunk_to_block} after {retries} retries: {net_err}") from net_err
                time.sleep(delay)
            except Exception as e:
                # Handle other potential errors from w3.eth.get_logs more broadly
                logging.error(f"{log_label}An unexpected error occurred on attempt {attempt + 1} for chunk {current_block}-{chunk_to_block}: {e}\n{traceback.format_exc()}")
                if attempt == retries - 1:
                    logging.error(f"{log_label}Failed to fetch logs for chunk {current_block}-{chunk_to_block} after {retries} retries due to an unexpected error.")
                    raise Exception(f"Failed to fetch logs for chunk {current_block}-{chunk_to_block} after {retries} retries: {e}") from e
                time.sleep(delay) # Optionally retry on other errors too, or re-raise immediately
        
        current_block = chunk_to_block + 1

    if debug:
        logging.debug(f"{log_label}Finished fetching logs. Total logs retrieved: {len(all_logs)}")
    return all_logs


def fetch_events_logs_with_retry_alchemy(
    address: str | list[str],
    topics: list,
    from_block: int,
    to_block: int | str = "latest",
    retries: int = 3,
    delay: int = 2,
    label: str | None = None,
    debug: bool = False,
) -> list[dict[str, Any]]:
    """Fetch event logs with retry logic and handling of block range limits using direct eth_getLogs RPC calls.

    Args:
        address: Contract address or list of addresses to get logs for.
        topics: List of topics to filter logs by (first topic is usually the event signature).
        from_block: Starting block number (inclusive).
        to_block: Ending block number (inclusive) or "latest".
        retries: Number of retry attempts for each block segment.
        delay: Delay between retries in seconds.
        label: Optional label for logging purposes.
        debug: Optional debug flag to print verbose RPC request/response info.

    Returns:
        List of log objects.

    Raises:
        ValueError: If to_block is invalid.
        Exception: If RPC calls fail after retries or other unhandled errors occur.
    """
    if isinstance(to_block, str) and to_block.lower() == "latest":
        try:
            actual_latest_block_num = _fetch_current_block_number_via_rpc(debug=debug)
            to_block_int_for_loop = actual_latest_block_num
            if debug:
                logging.debug(f"'latest' resolved to block {actual_latest_block_num}")
        except Exception as e_block_num:
            logging.error(f"Failed to fetch current block number when to_block='latest': {e_block_num}")
            raise
    elif isinstance(to_block, int):
        to_block_int_for_loop = to_block
    else:
        raise ValueError(f"'to_block' must be an integer or 'latest', got {type(to_block)}: {to_block}")

    if from_block > to_block_int_for_loop:
        logging.warning(
            f"from_block ({from_block}) is greater than to_block ({to_block_int_for_loop}). Returning empty list."
        )
        return []

    processing_block_start = from_block
    all_logs: list[dict[str, Any]] = []

    addresses_list = address if isinstance(address, list) else [address]
    formatted_addresses_list = [
        Web3.to_checksum_address(addr if addr.startswith("0x") else "0x" + addr)
        for addr in addresses_list
    ]

    formatted_topics = []
    for topic_item in topics:
        if topic_item is None:
            formatted_topics.append(None)
        elif isinstance(topic_item, list):
            formatted_topics.append([t if t.startswith("0x") else "0x" + t for t in topic_item])
        else:
            formatted_topics.append(topic_item if topic_item.startswith("0x") else "0x" + topic_item)

    while processing_block_start <= to_block_int_for_loop:
        target_chunk_from_block = processing_block_start
        target_chunk_to_block = min(target_chunk_from_block + BLOCK_CHUNK_SIZE - 1, to_block_int_for_loop)

        effective_rpc_from_block = target_chunk_from_block
        effective_rpc_to_block = target_chunk_to_block
        
        suggestion_applied_for_target_chunk = False
        last_exception_for_this_chunk = None

        for attempt in range(retries):
            if debug:
                logging.debug(
                    f"Attempt {attempt + 1}/{retries} for target chunk {target_chunk_from_block}-{target_chunk_to_block}, "
                    f"RPC call for {effective_rpc_from_block}-{effective_rpc_to_block}"
                )
            try:
                logs_for_current_attempt = _fetch_logs_via_rpc(
                    address=formatted_addresses_list,
                    from_block_hex=hex(effective_rpc_from_block),
                    to_block_hex=hex(effective_rpc_to_block),
                    topics=formatted_topics,
                    debug=debug
                )
                
                if debug:
                    logging.debug(f"Retrieved {len(logs_for_current_attempt)} logs for {effective_rpc_from_block}-{effective_rpc_to_block}")
                
                all_logs.extend(logs_for_current_attempt)
                processing_block_start = effective_rpc_to_block + 1
                last_exception_for_this_chunk = None # Clear error on success
                break  # Success for this target_chunk, exit retry loop

            except SuggestedRangeError as sre:
                last_exception_for_this_chunk = sre
                logging.info(f"Handling SuggestedRangeError for {effective_rpc_from_block}-{effective_rpc_to_block}: {str(sre)}")
                
                # Only apply suggestion if it's for the current 'from_block' we are attempting,
                # and if it suggests a smaller 'to_block', and we haven't tried a suggestion for this target_chunk yet.
                if not suggestion_applied_for_target_chunk and \
                   sre.suggested_from_block == effective_rpc_from_block and \
                   sre.suggested_to_block < effective_rpc_to_block and \
                   sre.suggested_to_block >= sre.suggested_from_block: # Sanity check on suggested range
                    
                    logging.info(f"Applying suggested range: from {sre.suggested_from_block} to {sre.suggested_to_block}")
                    effective_rpc_to_block = sre.suggested_to_block # Adapt the 'to_block' for the next retry
                    suggestion_applied_for_target_chunk = True
                    # Continue to the next attempt immediately with the new range
                    if attempt < retries - 1:
                        logging.info(f"Retrying immediately with suggested range (next attempt {attempt + 2}/{retries})")
                        continue # Skip sleep, try next attempt with new effective_rpc_to_block
                    else:
                        logging.warning("Suggested range received on last attempt, but no retries left to apply it.")
                        # Error will be raised after loop if this was the last_exception
                elif suggestion_applied_for_target_chunk:
                    logging.warning(f"Suggestion already applied for target chunk {target_chunk_from_block}-{target_chunk_to_block}. Ignoring further suggestion: {str(sre)}")
                else:
                    logging.warning(f"Suggested range not applicable or invalid. Original suggestion: {str(sre)}. Current effective: {effective_rpc_from_block}-{effective_rpc_to_block}")
                # Fall through to normal retry backoff if suggestion not applied or if it's the last attempt

            except (Timeout, RequestsConnectionError) as net_err:
                last_exception_for_this_chunk = net_err
                logging.warning(f"Network error on attempt {attempt + 1} for {effective_rpc_from_block}-{effective_rpc_to_block}: {net_err}")

            except Exception as e:
                last_exception_for_this_chunk = e
                logging.warning(f"Generic error on attempt {attempt + 1} for {effective_rpc_from_block}-{effective_rpc_to_block}: {e}")
                # Log full traceback for unexpected errors during debug
                if debug:
                    logging.debug(traceback.format_exc())
            
            # If an error occurred (and wasn't 'continue'd by SuggestedRangeError handling) and it's not the last attempt
            if attempt < retries - 1:
                logging.info(
                    f"Retrying chunk {target_chunk_from_block}-{target_chunk_to_block} (attempt {attempt + 2}/{retries} for {effective_rpc_from_block}-{effective_rpc_to_block}) in {delay}s..."
                )
                time.sleep(delay)
        
        # After all retries for the current target_chunk
        if last_exception_for_this_chunk is not None:
            label_text = f" for {label}" if label else ""
            # Determine the range that ultimately failed
            failed_range_from = effective_rpc_from_block 
            failed_range_to = effective_rpc_to_block
            if isinstance(last_exception_for_this_chunk, SuggestedRangeError) and suggestion_applied_for_target_chunk:
                 # If the last error was a SRE and we applied a suggestion, the 'failed_range' might be the suggested one.
                 # However, it's more informative to report the original target chunk that couldn't be fetched.
                 failed_range_from = target_chunk_from_block
                 failed_range_to = target_chunk_to_block

            full_error_message = (
                f"Failed to fetch logs{label_text} for block range {failed_range_from}-{failed_range_to} "
                f"(target chunk {target_chunk_from_block}-{target_chunk_to_block}) after {retries} attempts. \n"
                f"Last error: {last_exception_for_this_chunk}"
            )
            # Avoid re-printing traceback if original error in SRE already included it.
            # Also, format_exc() here would give traceback for *this* location, not where SRE was raised.
            # The __cause__ or original_exception in SRE should be used if needed.
            logging.error(full_error_message)
            if isinstance(last_exception_for_this_chunk, SuggestedRangeError) and last_exception_for_this_chunk.original_exception:
                raise Exception(full_error_message) from last_exception_for_this_chunk.original_exception
            else:
                raise Exception(full_error_message) from last_exception_for_this_chunk

    return all_logs
