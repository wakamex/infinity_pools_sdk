import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import requests
from requests.exceptions import HTTPError, JSONDecodeError, RequestException

logger = logging.getLogger(__name__)


class TenderlyVirtualTestNetManager:
    """Manages the lifecycle of a Tenderly Virtual TestNet via REST API."""

    def __init__(self, access_key: str, account_slug: str, project_slug: str):
        if not all([access_key, account_slug, project_slug]):
            raise ValueError(
                "Tenderly access_key, account_slug, and project_slug must be provided."
            )
        self.access_key = access_key
        self.account_slug = account_slug
        self.project_slug = project_slug
        self.base_api_url = f"https://api.tenderly.co/api/v1/account/me/project/project/vnets"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Access-Key": self.access_key,
        }
        self.created_vnet_details: Dict[str, Any] = {}

    def create_vnet(
        self,
        display_name: str,
        parent_network_id: int | str,
        vnet_chain_id: int,
        block_number: Optional[int] = None,
        enable_sync: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Create a Tenderly Virtual TestNet.

        Args:
            display_name: A human-readable name for the VNet.
            parent_network_id: The ID of the network to fork from.
            vnet_chain_id: The custom chain ID for the VNet.
            block_number: The block number to fork from. Defaults to None.
            enable_sync: Whether to enable syncing. Defaults to True.

        Returns:
            A dictionary containing the VNet's details, with 'admin_rpc_url' promoted
            to the top level if found. Returns None if creation fails.
        """
        timestamp = int(time.time())
        unique_slug = f"infinitypoolssdk-test-vnet-{timestamp}-{uuid.uuid4().hex[:8]}"
        formatted_display_name = f"InfinityPoolsSDK-Test-VNet ({time.strftime('%Y-%m-%d %H:%M:%S')})"

        # Ensure the network_id is passed as an *integer* – the Tenderly API will reject a
        # string value (400 Bad Request). Allow callers to pass either `int` or a string of
        # digits for convenience.
        network_id_value: int | str
        if isinstance(parent_network_id, str) and parent_network_id.isdigit():
            network_id_value = int(parent_network_id)
        else:
            network_id_value = parent_network_id

        # Tenderly expects `block_number` to be either an integer or the string "latest" –
        # `null` is rejected with a 400 error. Convert `None` to "latest" automatically.
        block_number_value: int | str | None
        if block_number is None:
            block_number_value = "latest"
        else:
            block_number_value = block_number

        payload = {
            "slug": unique_slug,
            "display_name": formatted_display_name,
            "fork_config": {
                "network_id": network_id_value,
                "block_number": block_number_value,
            },
            "virtual_network_config": {"chain_config": {"chain_id": vnet_chain_id}},
            "sync_state_config": {"enabled": enable_sync, "commitment_level": "latest"},
            "explorer_page_config": {"enabled": False, "verification_visibility": "bytecode"},
        }

        logger.info(f"Attempting to create Tenderly Virtual TestNet. Slug: {unique_slug}")
        logger.info(f"Request URL: {self.base_api_url}")
        logger.info(f"Request Payload: {json.dumps(payload, indent=2)}")
        print(f"DEBUG: Request URL: {self.base_api_url}")
        print(f"DEBUG: Request Payload: {json.dumps(payload, indent=2)}")

        raw_response_text = "No response received (request did not complete)"
        try:
            response = requests.post(
                self.base_api_url, headers=self.headers, json=payload, timeout=60
            )
            raw_response_text = response.text
            logger.debug(
                f"VNet creation HTTP status: {response.status_code}. "
                f"Raw response snippet (first 500 chars): {raw_response_text[:500]}"
            )

            response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)

            parsed_response = response.json()
            logger.debug(
                f"Successfully parsed VNet creation response: {json.dumps(parsed_response, indent=2)}"
            )

            self.created_vnet_details = parsed_response

            # Extract Admin RPC URL from rpcs array
            admin_rpc_url = None
            for rpc in self.created_vnet_details.get('rpcs', []):
                if rpc.get('name') == 'Admin RPC':
                    admin_rpc_url = rpc.get('url')
                    break

            # Store the details with the admin_rpc_url added
            self.created_vnet_details['admin_rpc_url'] = admin_rpc_url

            # Extract key details for logging and ensure admin_rpc_url is top-level
            vnet_main_id = parsed_response.get("id")
            virtual_testnet_obj = parsed_response.get("virtual_testnet", {})
            vnet_nested_id = virtual_testnet_obj.get("id")
            final_vnet_id = vnet_main_id or vnet_nested_id

            if not final_vnet_id:
                logger.warning(
                    "VNet response missing 'id' (checked top-level and virtual_testnet.id)."
                )

            if not admin_rpc_url:
                logger.warning(
                    "VNet response missing 'admin_rpc_url' (checked top-level and virtual_testnet.admin_rpc_url)."
                )

            logger.info(
                f"VNet creation call processed. Final VNet ID: {final_vnet_id}. "
                f"Admin RPC URL present: {admin_rpc_url is not None}"
            )
            return self.created_vnet_details

        except HTTPError as http_err:
            logger.error(
                f"HTTP error creating VNet: {http_err.response.status_code}. "
                f"Response: {http_err.response.text if http_err.response else 'No response body'}",
                exc_info=True,
            )
            return None
        except JSONDecodeError:  # More specific exception from requests.exceptions
            logger.error(
                f"JSONDecodeError creating VNet. Raw response was: {raw_response_text}",
                exc_info=True,
            )
            return None
        except RequestException as req_err:  # Catches other requests-related errors
            logger.error(f"RequestException creating VNet: {req_err}", exc_info=True)
            return None
        except Exception as e:  # Catch-all for other unexpected errors
            logger.error(f"Unexpected error creating VNet: {e}", exc_info=True)
            return None

    def delete_vnet(self, vnet_id_or_slug: Optional[str] = None) -> bool:
        """Delete a Tenderly Virtual TestNet using its ID or slug.

        If no ID/slug is provided, attempts to delete the VNet whose details are stored.
        Tenderly API uses the VNet 'id' (UUID) or 'slug' for deletion.
        The 'id' is usually in `created_vnet_details.id` or `created_vnet_details.virtual_testnet.id`.
        The 'slug' is in `created_vnet_details.slug`.
        We prioritize the ID from `virtual_testnet.id` if available.
        """
        identifier_to_delete = vnet_id_or_slug

        if not identifier_to_delete and self.created_vnet_details:
            details = self.created_vnet_details
            nested_vnet_obj = details.get("virtual_testnet", {})
            identifier_to_delete = (
                nested_vnet_obj.get("id")
                or details.get("id")
                or details.get("slug")
            )
            logger.info(
                f"No vnet_id_or_slug provided for deletion. Using stored identifier: {identifier_to_delete}"
            )

        if not identifier_to_delete:
            logger.warning(
                "No VNet identifier (ID or slug) provided or found to delete."
            )
            return False

        delete_url = f"{self.base_api_url}/{identifier_to_delete}"
        logger.info(f"Attempting to delete Tenderly Virtual TestNet: {delete_url}")
        try:
            response = requests.delete(
                delete_url, headers=self.headers, timeout=30
            )
            if response.status_code == 204:
                logger.info(f"Successfully deleted VNet: {identifier_to_delete}")
                if self.created_vnet_details:
                    stored_id_check = (
                        self.created_vnet_details.get("virtual_testnet", {}).get("id")
                        or self.created_vnet_details.get("id")
                        or self.created_vnet_details.get("slug")
                    )
                    if stored_id_check == identifier_to_delete:
                        self.created_vnet_details = {}
                return True
            else:
                logger.error(
                    f"Failed to delete VNet {identifier_to_delete}. "
                    f"Status: {response.status_code}, Response: {response.text}"
                )
                return False
        except RequestException as e:
            logger.error(
                f"RequestException during VNet deletion {identifier_to_delete}: {e}",
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error during VNet deletion {identifier_to_delete}: {e}",
                exc_info=True,
            )
            return False

    def get_admin_rpc_url(self) -> Optional[str]:
        if not self.created_vnet_details:
            return None
        # Check top-level first (due to potential promotion in create_vnet), then nested
        admin_url = self.created_vnet_details.get("admin_rpc_url")
        if admin_url:
            return admin_url

        virtual_testnet_obj = self.created_vnet_details.get("virtual_testnet", {})
        return virtual_testnet_obj.get("admin_rpc_url")

    def get_chain_id(self) -> Optional[int]:
        if not self.created_vnet_details:
            return None
        # Chain ID is usually in virtual_testnet.chain_config.chain_id
        virtual_testnet_obj = self.created_vnet_details.get("virtual_testnet", {})
        chain_config_obj = virtual_testnet_obj.get("chain_config", {})
        return chain_config_obj.get("chain_id")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
    )

    access_key_env = os.getenv("TENDERLY_ACCESS_KEY")
    account_slug_env = os.getenv("TENDERLY_ACCOUNT_SLUG")
    project_slug_env = os.getenv("TENDERLY_PROJECT_SLUG")

    if not all([access_key_env, account_slug_env, project_slug_env]):
        print(
            "Missing Tenderly credentials. Set TENDERLY_ACCESS_KEY, "
            "TENDERLY_ACCOUNT_SLUG, and TENDERLY_PROJECT_SLUG."
        )
    else:
        # Assertions for type checker after skip condition
        assert access_key_env is not None, "TENDERLY_ACCESS_KEY must be set"
        assert account_slug_env is not None, "TENDERLY_ACCOUNT_SLUG must be set"
        assert project_slug_env is not None, "TENDERLY_PROJECT_SLUG must be set"

        manager = TenderlyVirtualTestNetManager(
            access_key_env, account_slug_env, project_slug_env
        )

        print("Attempting to create VNet...")
        created_vnet_details = manager.create_vnet(
            display_name="MyTestVNet-DirectScript",
            parent_network_id="8453",
            vnet_chain_id=84530,
        )
        if created_vnet_details:
            retrieved_id = (
                created_vnet_details.get("virtual_testnet", {}).get("id")
                or created_vnet_details.get("id")
            )
            print(f"VNet Created: ID = {retrieved_id}")
            print(f"Admin RPC URL from manager method: {manager.get_admin_rpc_url()}")
            
            public_rpc_url = None
            vt_obj = created_vnet_details.get('virtual_testnet', {})
            if isinstance(vt_obj.get('rpcs'), list):
                 for rpc_entry in vt_obj['rpcs']:
                     if rpc_entry.get('name') == 'Public RPC':
                         public_rpc_url = rpc_entry.get('url')
                         break
            if not public_rpc_url:
                 public_rpc_url = vt_obj.get('public_rpc_url') # Fallback if not in rpcs list
            print(f"Public RPC URL (example extraction): {public_rpc_url}")

            time.sleep(5) # Short wait

            print("Attempting to delete VNet...")
            if manager.delete_vnet(): # Uses stored details
                print("VNet deleted successfully using stored details.")
            else:
                print("Failed to delete VNet using stored details.")
        else:
            print("Failed to create VNet.")
