from typing import Optional

from ..core.connector import InfinityPoolsConnector


class ERC721Helper:
    def __init__(self, connector: InfinityPoolsConnector):
        self.connector = connector
        self.w3 = connector.w3

    def get_contract(self, nft_address: str):
        """Get ERC721 contract instance for a specific NFT address."""
        # Assuming a generic ERC721 ABI is available via connector.config.get_abi('ERC721')
        return self.w3.eth.contract(address=nft_address, abi=self.connector.config.get_abi('ERC721'))

    def owner_of(self, nft_address: str, token_id: int) -> str:
        """Get owner of a specific NFT token."""
        contract = self.get_contract(nft_address)
        return contract.functions.ownerOf(token_id).call()

    def balance_of(self, nft_address: str, address: Optional[str] = None) -> int:
        """Get NFT balance for an address (defaults to loaded account)."""
        if address is None:
            if not self.connector.account:
                raise ValueError("No account loaded and no address provided")
            address = self.connector.account.address

        contract = self.get_contract(nft_address)
        return contract.functions.balanceOf(address).call()

    def get_approved(self, nft_address: str, token_id: int) -> str:
        """Get approved address for a token."""
        contract = self.get_contract(nft_address)
        return contract.functions.getApproved(token_id).call()

    def is_approved_for_all(self, nft_address: str, owner_address: str, operator_address: str) -> bool:
        """Check if an operator is approved for all NFTs of an owner."""
        contract = self.get_contract(nft_address)
        return contract.functions.isApprovedForAll(owner_address, operator_address).call()

    def name(self, nft_address: str) -> str:
        """Get the name of the NFT collection.

        Args:
            nft_address: The address of the ERC721 token contract.

        Returns:
            The name of the NFT collection.
        """
        contract = self.get_contract(nft_address)
        return contract.functions.name().call()

    def symbol(self, nft_address: str) -> str:
        """Get the symbol of the NFT collection.

        Args:
            nft_address: The address of the ERC721 token contract.

        Returns:
            The symbol of the NFT collection.
        """
        contract = self.get_contract(nft_address)
        return contract.functions.symbol().call()

    def token_uri(self, nft_address: str, token_id: int) -> str:
        """Get the URI for a specific token's metadata.

        Args:
            nft_address: The address of the ERC721 token contract.
            token_id: The ID of the token.

        Returns:
            The URI string for the token's metadata.
        """
        contract = self.get_contract(nft_address)
        return contract.functions.tokenURI(token_id).call()

    def approve(self, nft_address: str, to_address: str, token_id: int, tx_options: Optional[dict] = None) -> str:
        """Approve an address to transfer a specific NFT.

        Args:
            nft_address: The address of the ERC721 token contract.
            to_address: The address to be approved.
            token_id: The ID of the token to approve.
            tx_options: Optional dictionary of transaction parameters (e.g., gas, gasPrice).

        Returns:
            The transaction hash.

        Raises:
            ValueError: If no account is loaded in the connector.
        """
        if not self.connector.account:
            raise ValueError("No account loaded for transaction")

        contract = self.get_contract(nft_address)
        
        base_tx_params = {'from': self.connector.account.address}
        if tx_options:
            base_tx_params.update(tx_options)
            
        transaction = contract.functions.approve(to_address, token_id).build_transaction(base_tx_params)
        return self.connector.send_transaction(transaction)

    def set_approval_for_all(self, nft_address: str, operator_address: str, approved: bool) -> str:
        """Set or revoke approval for all NFTs for an operator."""
        if not self.connector.account:
            raise ValueError("No account loaded for transaction")

        contract = self.get_contract(nft_address)
        tx_params = {
            'from': self.connector.account.address,
        }
        transaction = contract.functions.setApprovalForAll(operator_address, approved).build_transaction(tx_params)
        return self.connector.send_transaction(transaction)

    def transfer_from(self, nft_address: str, from_address: str, to_address: str, token_id: int) -> str:
        """Transfer an NFT from one address to another."""
        if not self.connector.account:
            raise ValueError("No account loaded for transaction")

        contract = self.get_contract(nft_address)
        tx_params = {
            'from': self.connector.account.address,
        }
        # Note: Web3.py's contract.functions.transferFrom typically takes three args for ERC721
        # (from, to, tokenId). Some interfaces might vary.
        transaction = contract.functions.transferFrom(from_address, to_address, token_id).build_transaction(tx_params)
        return self.connector.send_transaction(transaction)

    def safe_transfer_from(self, nft_address: str, from_address: str, to_address: str, token_id: int, data: bytes = b'') -> str:
        """Safely transfer an NFT from one address to another."""
        if not self.connector.account:
            raise ValueError("No account loaded for transaction")

        contract = self.get_contract(nft_address)
        tx_params = {
            'from': self.connector.account.address,
        }
        if data:
            transaction = contract.functions.safeTransferFrom(from_address, to_address, token_id, data).build_transaction(tx_params)
        else:
            transaction = contract.functions.safeTransferFrom(from_address, to_address, token_id).build_transaction(tx_params)
        return self.connector.send_transaction(transaction)
