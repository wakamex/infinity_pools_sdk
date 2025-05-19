#!/usr/bin/env python
"""Script to check all Infinity Pools liquidity positions for a wallet address."""

import json
from infinity_pools_sdk.offchain.liquidity_positions import get_liquidity_positions_by_wallet

# Use the same test wallet address that's in our scripts
WALLET_ADDRESS = "0x9eAFc0c2b04D96a1C1edAdda8A474a4506752207"

def main():
    """Fetch and display all positions for the wallet."""
    print(f"Fetching all liquidity positions for wallet: {WALLET_ADDRESS}")
    positions = get_liquidity_positions_by_wallet(WALLET_ADDRESS)
    
    if positions is not None:
        print(f"\nFound {len(positions)} positions:")
        for i, position in enumerate(positions):
            print(f"\nPosition #{i+1}:")
            # Extract and display key information in a readable format
            print(f"  ID: {position.get('id')}")
            print(f"  LP Number: {position.get('lpNum')}")
            print(f"  Pool: {position.get('baseAsset')} / {position.get('quoteAsset')}")
            print(f"  Status: {position.get('status')}")
            print(f"  Price Range: {position.get('lowerPrice')} to {position.get('upperPrice')}")
            print(f"  Original Assets: {position.get('originalBaseSize')} base, {position.get('originalQuoteSize')} quote")
            print(f"  Current Assets: {position.get('availableBaseSize')} available base, {position.get('availableQuoteSize')} available quote")
            print(f"  Opened: {position.get('openedAt')}")
            if position.get('tickLower') is not None:
                print(f"  Ticks: {position.get('tickLower')} to {position.get('tickUpper')}")
    else:
        print("Failed to fetch positions.")

if __name__ == "__main__":
    main()
