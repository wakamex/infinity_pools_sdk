"""Temporary file to hold the fixed get_positions method."""

from typing import Any, Dict, List, Optional
import time
import signal
from contextlib import contextmanager

def get_positions(self, owner_address: Optional[str] = None, max_tokens: int = 100) -> List[Dict[str, Any]]:
    """Get all positions owned by the specified address.
    
    Args:
        owner_address: The address to check. If None, uses the connected account address.
        max_tokens: Maximum number of tokens to check to prevent excessive API calls.
        
    Returns:
        List[Dict[str, Any]]: List of position details.
    """
    @contextmanager
    def timeout(seconds):
        def handler(signum, frame):
            raise TimeoutError(f"Function call timed out after {seconds} seconds")
        
        # Set the timeout handler
        original_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(seconds)
        
        try:
            yield
        finally:
            # Restore the original handler and cancel the alarm
            signal.alarm(0)
            signal.signal(signal.SIGALRM, original_handler)
    
    if not owner_address and not self.connector.account:
        raise ValueError("No owner address provided and no account loaded.")
        
    actual_owner = owner_address if owner_address else self.connector.account.address
    print(f"Looking for positions owned by {actual_owner}")
    
    # Initialize the list to store positions
    positions = []
    token_ids_to_check = []
    
    # Step 1: Try to get the balance with a timeout
    try:
        with timeout(10):  # 10-second timeout for balanceOf call
            balance = self.periphery_contract.functions.balanceOf(actual_owner).call()
            print(f"Found balance of {balance} tokens for address {actual_owner}")
    except Exception as e:
        print(f"Error getting balance: {e}")
        balance = 0
    
    # Step 2: Since tokenOfOwnerByIndex might not be available in the ABI,
    # we'll use a more robust approach to find token IDs
    
    # If balance > 0, we know the user has tokens but we need to find them
    if balance and balance > 0:
        # Approach 1: Try a wider range of token IDs
        # This is more reliable than relying on tokenOfOwnerByIndex
        max_id_to_check = max(100, balance * 10)  # Check more IDs than the balance suggests
        print(f"Checking token IDs from 1 to {max_id_to_check}")
        
        # We'll check token IDs in batches to avoid timeouts
        batch_size = 20
        for batch_start in range(1, max_id_to_check, batch_size):
            batch_end = min(batch_start + batch_size, max_id_to_check + 1)
            print(f"Checking batch of token IDs from {batch_start} to {batch_end-1}")
            
            for token_id in range(batch_start, batch_end):
                try:
                    with timeout(3):  # 3-second timeout for each ownerOf call
                        try:
                            owner = self.periphery_contract.functions.ownerOf(token_id).call()
                            if owner.lower() == actual_owner.lower():
                                token_ids_to_check.append(token_id)
                                print(f"Found token ID {token_id} owned by {actual_owner}")
                                
                                # If we've found enough tokens matching the balance, we can stop
                                if len(token_ids_to_check) >= balance:
                                    print(f"Found all {balance} tokens, stopping search")
                                    break
                        except Exception:
                            # This token ID might not exist, just continue
                            pass
                except TimeoutError:
                    print(f"Timeout checking token ID {token_id}, continuing")
                    continue
            
            # If we've found all tokens matching the balance, we can stop
            if len(token_ids_to_check) >= balance:
                break
    
    # If we still haven't found any tokens, try some known token ID ranges
    if not token_ids_to_check:
        print("No tokens found. Trying fallback token ID ranges...")
        # Try some common ranges where tokens might exist
        fallback_ranges = [(1, 20), (100, 120), (1000, 1020), (10000, 10020)]
        
        for start, end in fallback_ranges:
            print(f"Checking fallback range {start}-{end}")
            for token_id in range(start, end):
                try:
                    with timeout(3):
                        try:
                            owner = self.periphery_contract.functions.ownerOf(token_id).call()
                            if owner.lower() == actual_owner.lower():
                                token_ids_to_check.append(token_id)
                                print(f"Found token ID {token_id} owned by {actual_owner} in fallback range")
                        except Exception:
                            # This token ID might not exist, just continue
                            pass
                except TimeoutError:
                    continue
    
    # Step 3: Process each token ID to get position details
    print(f"Processing {len(token_ids_to_check)} token IDs: {token_ids_to_check}")
    for token_id in token_ids_to_check:
        try:
            # Get position details with timeout
            with timeout(5):  # 5-second timeout for positions call
                position_data = self.periphery_contract.functions.positions(token_id).call()
            
            # Handle different data structures that might be returned
            if isinstance(position_data, (list, tuple)):
                if len(position_data) > 0 and isinstance(position_data[0], (list, tuple)):
                    # It's a tuple of tuples, use the inner tuple
                    position_data = position_data[0]
                
                # Format the position data
                if len(position_data) >= 12:
                    position = {
                        "token_id": token_id,
                        "token0": position_data[2],  # token0 address
                        "token1": position_data[3],  # token1 address
                        "fee": position_data[4],     # fee tier
                        "tickLower": position_data[5],  # lower tick
                        "tickUpper": position_data[6],  # upper tick
                        "liquidity": position_data[7],  # liquidity
                        "tokensOwed0": position_data[10],  # tokensOwed0
                        "tokensOwed1": position_data[11]   # tokensOwed1
                    }
                    positions.append(position)
                    print(f"Added position for token ID {token_id}")
        except Exception as e:
            print(f"Error getting position data for token ID {token_id}: {e}")
            # Continue to the next token ID
            continue
    
    return positions
