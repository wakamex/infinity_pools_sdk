# Infinity Pools SDK Integration Tests

This document explains how to run integration tests for the Infinity Pools SDK using both local chains and Tenderly forks.

## Testing Approaches

The SDK supports two integration testing approaches:

1. **Local Chain Testing**: Using a local blockchain node like Anvil, Hardhat, or Ganache
2. **Tenderly Fork Testing**: Using Tenderly's API to fork a real network from a specific block number

## Setting Up Tenderly Fork Testing

### 1. Create a Tenderly Account

If you don't already have one, sign up at [tenderly.co](https://tenderly.co).

### 2. Get Your API Credentials

You'll need:
- Access Key
- Account Slug
- Project Slug

These can be found in your Tenderly dashboard.

### 3. Set Environment Variables

```bash
# Tenderly API credentials
export TENDERLY_ACCESS_KEY="your_access_key"
export TENDERLY_ACCOUNT_SLUG="your_account_slug"
export TENDERLY_PROJECT_SLUG="your_project_slug"

# Network and block to fork from
export TENDERLY_NETWORK_ID="1"  # Ethereum mainnet
export TENDERLY_BLOCK_NUMBER="12345678"  # Block number where contracts are deployed

# Contract addresses on the forked network
export PERIPHERY_ADDRESS="0x123...abc"
export TOKEN0_ADDRESS="0x456...def"
export TOKEN1_ADDRESS="0x789...ghi"
```

## Running Integration Tests

### Running Local Chain Tests

1. Start your local blockchain node:
   ```bash
   anvil
   # or
   npx hardhat node
   # or
   ganache-cli
   ```

2. Run the tests with the integration flag:
   ```bash
   pytest -m integration --run-integration
   ```

### Running Tenderly Fork Tests

Run the Tenderly-specific tests:
```bash
pytest test_sdk_tenderly.py -v --run-integration
```

## Test Organization

- `test_sdk.py`: Unit tests with mocks
- `test_sdk_integration.py`: Integration tests using a local chain
- `test_sdk_tenderly.py`: Integration tests using Tenderly forks
- `chain_fixtures.py`: Fixtures for both local chain and Tenderly fork testing
- `tenderly_fork.py`: Utilities for working with Tenderly forks

## Extracting Event Data

The current implementation includes a placeholder for extracting token IDs from transaction receipts. To implement this properly:

```python
def extract_token_id_from_receipt(receipt, web3, periphery_abi):
    """Extract token ID from transaction receipt."""
    # Create contract instance
    contract = web3.eth.contract(
        address=receipt["to"],
        abi=periphery_abi
    )
    
    # Find the relevant event
    for log in receipt["logs"]:
        try:
            # Try to decode the log with the IncreaseLiquidity event signature
            event = contract.events.IncreaseLiquidity().processLog(log)
            return event["args"]["tokenId"]
        except:
            continue
    
    return None
```

## Benefits of Tenderly Fork Testing

1. **Real Contract State**: Tests run against actual deployed contracts
2. **No Local Deployment**: No need to deploy contracts locally
3. **Reproducible Environment**: Fork from a specific block number for consistent testing
4. **Multiple Test Accounts**: Tenderly provides 10 test accounts with 100 ETH each
5. **Debugging**: All transactions are visible in the Tenderly dashboard

## Best Practices

1. **Use Environment Variables**: Store sensitive information and contract addresses in environment variables
2. **Clean Up Forks**: Always delete forks after tests complete (handled by the fixtures)
3. **Skip Tests If Not Configured**: Use `pytest.skip()` if required environment variables are missing
4. **Separate Test Files**: Keep unit tests and integration tests in separate files
5. **Use Markers**: Use pytest markers to categorize tests (`@pytest.mark.integration`)
