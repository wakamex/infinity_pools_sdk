import logging
import traceback

logging.basicConfig(level=logging.DEBUG)  # Configure logging to show DEBUG messages

import time

from infinity_pools_sdk.constants import (
    BASE_DEPLOYMENT_BLOCK,
    ERC721_TRANSFER_EVENT_SIGNATURE,
    IMPERSONATEE,
    PROXY,
    Web3Objects,
)
from infinity_pools_sdk.utils.logs import (
    fetch_events_logs_with_retry,
    fetch_events_logs_with_retry_alchemy,
)

start_time = time.time()
try:
    logs = fetch_events_logs_with_retry_alchemy(
        address=PROXY,
        topics=[ERC721_TRANSFER_EVENT_SIGNATURE],
        from_block=30324733 - 2000,
        to_block=30324733,
        retries=1,
        debug=True,
    )
    print("Logs retrieved:")
    if logs:
        for log_entry in logs:
            print(log_entry)
        print(f"retrieved {len(logs)} logs in {time.time() - start_time} seconds")
    else:
        print("No logs found.")
except Exception as e:
    print("An error occurred during fetch_events_logs_with_retry:")
    print(str(e))
    print("--- Traceback ---")
    print(traceback.format_exc())
    print("-----------------")

# block = Web3Objects.BASE.eth.get_block(30324733)
# print(block)
