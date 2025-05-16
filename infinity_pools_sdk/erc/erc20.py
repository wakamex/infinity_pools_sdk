from decimal import Decimal
from typing import Optional

from ..core.connector import InfinityPoolsConnector


class ERC20Helper:
    def __init__(self, connector: InfinityPoolsConnector):
        self.connector = connector
        self.w3 = connector.w3

    def get_contract(self, token_address: str):
        """Get ERC20 contract instance for a specific token address."""
        # Assuming a generic ERC20 ABI is available via connector.config.get_abi('ERC20')
        return self.w3.eth.contract(address=token_address, abi=self.connector.config.get_abi('ERC20'))

    def balance_of(self, token_address: str, address: Optional[str] = None) -> Decimal:
        """Get token balance for an address (defaults to loaded account)."""
        if address is None:
            if not self.connector.account:
                raise ValueError("No account loaded and no address provided")
            address = self.connector.account.address

        contract = self.get_contract(token_address)
        balance_wei = contract.functions.balanceOf(address).call()
        decimals = contract.functions.decimals().call() # Standard ERC20, might need error handling if not present
        return Decimal(balance_wei) / (10 ** decimals)

    def allowance(self, token_address: str, owner_address: Optional[str] = None, spender_address: Optional[str] = None) -> Decimal:
        """Check allowance for a spender from an owner (defaults to loaded account for owner)."""
        if owner_address is None:
            if not self.connector.account:
                raise ValueError("No account loaded and no owner_address provided for allowance check")
            owner_address = self.connector.account.address

        if spender_address is None:
            # This usually doesn't make sense without a spender to check against.
            # Depending on the protocol, the 'spender' might be a specific contract (e.g., router).
            # For now, let's require it or use a configured default if available.
            # For this generic helper, let's assume spender_address needs to be provided by the caller.
            raise ValueError("Spender address must be provided for allowance check")

        contract = self.get_contract(token_address)
        allowance_wei = contract.functions.allowance(owner_address, spender_address).call()
        decimals = contract.functions.decimals().call()
        return Decimal(allowance_wei) / (10 ** decimals)

    def approve(self, token_address: str, spender_address: str, amount: Decimal) -> str:
        """Approve spender to use tokens."""
        if not self.connector.account:
            raise ValueError("No account loaded for transaction")

        contract = self.get_contract(token_address)
        decimals = contract.functions.decimals().call()
        amount_wei = int(amount * (10 ** decimals))

        tx_params = {
            'from': self.connector.account.address,
            # gas, gasPrice, nonce can be auto-filled by connector.send_transaction
        }

        transaction = contract.functions.approve(spender_address, amount_wei).build_transaction(tx_params)
        return self.connector.send_transaction(transaction)

    def transfer(self, token_address: str, recipient_address: str, amount: Decimal) -> str:
        """Transfer tokens to a recipient."""
        if not self.connector.account:
            raise ValueError("No account loaded for transaction")

        contract = self.get_contract(token_address)
        decimals = contract.functions.decimals().call()
        amount_wei = int(amount * (10 ** decimals))

        tx_params = {
            'from': self.connector.account.address,
        }
        transaction = contract.functions.transfer(recipient_address, amount_wei).build_transaction(tx_params)
        return self.connector.send_transaction(transaction)

    def transfer_from(self, token_address: str, from_address: str, recipient_address: str, amount: Decimal) -> str:
        """Transfer tokens from one address to another (requires allowance)."""
        if not self.connector.account:
            raise ValueError("No account loaded for transaction (acting as msg.sender for transferFrom)")

        contract = self.get_contract(token_address)
        decimals = contract.functions.decimals().call()
        amount_wei = int(amount * (10 ** decimals))

        tx_params = {
            'from': self.connector.account.address,
        }
        transaction = contract.functions.transferFrom(from_address, recipient_address, amount_wei).build_transaction(tx_params)
        return self.connector.send_transaction(transaction)

    def name(self, token_address: str) -> str:
        """Get the name of the token."""
        contract = self.get_contract(token_address)
        return contract.functions.name().call()

    def symbol(self, token_address: str) -> str:
        """Get the symbol of the token."""
        contract = self.get_contract(token_address)
        return contract.functions.symbol().call()

    def decimals(self, token_address: str) -> int:
        """Get the decimals of the token."""
        contract = self.get_contract(token_address)
        return contract.functions.decimals().call()

    @staticmethod
    def decimal_to_wei(amount_decimal: Decimal, num_decimals: int) -> int:
        """Convert a Decimal token amount to its smallest unit (wei/atomic).

        Args:
            amount_decimal: The amount in Decimal format.
            num_decimals: The number of decimals the token uses.

        Returns:
            The amount in its smallest unit (integer).
        """
        if amount_decimal < Decimal(0):
            raise ValueError("Amount cannot be negative.")
        return int(amount_decimal * (10 ** num_decimals))

    def ensure_allowance(
        self,
        token_address: str,
        spender_address: str,
        required_amount_decimal: Decimal,
        owner_address: Optional[str] = None,
        approve_multiplier: Decimal = Decimal("1.5") # Optional: approve slightly more to avoid re-approving for minor dust
    ) -> Optional[str]:
        """Ensure that the spender has sufficient allowance from the owner.

        If allowance is insufficient, it attempts to approve an amount equal to
        required_amount_decimal * approve_multiplier.

        Args:
            token_address: The ERC20 token contract address.
            spender_address: The address of the contract/account that needs the allowance.
            required_amount_decimal: The minimum required allowance amount in Decimal format.
            owner_address: The address of the token owner. Defaults to the loaded account.
            approve_multiplier: Factor by which to multiply required_amount if approval is needed.

        Returns:
            The transaction hash if an approval was sent, otherwise None.
        """
        if owner_address is None:
            if not self.connector.account:
                raise ValueError("No account loaded and no owner_address provided for ensure_allowance")
            owner_address = self.connector.account.address

        current_allowance_decimal = self.allowance(token_address, owner_address, spender_address)

        if current_allowance_decimal < required_amount_decimal:
            amount_to_approve = required_amount_decimal * approve_multiplier
            print( # For debugging purposes, can be removed or made a log
                f"Approving {amount_to_approve} of token {token_address} for spender {spender_address} from owner {owner_address}"
            )
            return self.approve(token_address, spender_address, amount_to_approve)
        return None

    def total_supply(self, token_address: str) -> Decimal:
        """Get the total supply of the token."""
        contract = self.get_contract(token_address)
        supply_wei = contract.functions.totalSupply().call()
        decimals = contract.functions.decimals().call()
        return Decimal(supply_wei) / (10 ** decimals)
