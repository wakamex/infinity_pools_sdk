import datetime
import json
import os
import sys
import time
import uuid
from typing import Optional, Dict, Any

import requests
from infinity_pools_sdk.utils.env_loader import load_env_vars

# Load environment variables using utility function
load_env_vars(target_keys=["TENDERLY_ACCESS_KEY", "TENDERLY_ACCOUNT_SLUG", "TENDERLY_PROJECT_SLUG"])

# Simple logger substitute for standalone script
class SimpleLogger:
    def info(self, msg):
        print(f"INFO: {msg}")
    def debug(self, msg):
        print(f"DEBUG: {msg}")
    def error(self, msg):
        print(f"ERROR: {msg}")
    def warning(self, msg):
        print(f"WARNING: {msg}")

logger = SimpleLogger()

class TenderlyVirtualTestNetManager:
    def __init__(self, access_key: str, account_slug: str, project_slug: str, logger=None):
        self.access_key = access_key
        self.account_slug = account_slug
        self.project_slug = project_slug
        self.base_api_url = f"https://api.tenderly.co/api/v1/account/me/project/{self.project_slug}/vnets"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Access-Key": self.access_key,
        }
        self.created_vnet_details = None
        self.logger = logger if logger else SimpleLogger()

    def create_vnet(
        self,
        display_name: str,
        parent_network_id: int | str,
        vnet_chain_id: int,
        block_number: Optional[int] = None,
        enable_sync: bool = True,
    ) -> Optional[Dict[str, Any]]:
        timestamp = int(time.time())
        unique_slug = f"infinitypoolssdk-test-vnet-{timestamp}-{uuid.uuid4().hex[:8]}"
        formatted_display_name = f"InfinityPoolsSDK-Test-VNet ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"

        payload = {
            "slug": unique_slug,
            "display_name": formatted_display_name,
            "fork_config": {
                "network_id": int(parent_network_id),
                "block_number": "latest" if block_number is None else hex(block_number),
            },
            "virtual_network_config": {
                "chain_config": {
                    "chain_id": vnet_chain_id,
                }
            },
            "sync_state_config": {
                "enabled": enable_sync,
                "commitment_level": "latest",
            },
            "explorer_page_config": {
                "enabled": False,
                "verification_visibility": "bytecode",
            },
        }

        self.logger.info(f"Attempting to create Tenderly Virtual TestNet. Slug: {unique_slug}")
        self.logger.info(f"Request URL: {self.base_api_url}")
        self.logger.info(f"Request Payload: {json.dumps(payload, indent=2)}")
        print(f"DEBUG: Request URL: {self.base_api_url}")
        print(f"DEBUG: Request Payload: {json.dumps(payload, indent=2)}")

        try:
            response = requests.post(self.base_api_url, headers=self.headers, json=payload, timeout=30)
            self.logger.debug(f"VNet creation HTTP status: {response.status_code}. Raw response snippet (first 500 chars): {response.text[:500]}")
            print(f"DEBUG: VNet creation HTTP status: {response.status_code}. Raw response snippet (first 500 chars): {response.text[:500]}")

            if response.status_code in {200, 201}:
                vnet_data = response.json()
                self.logger.debug(f"Successfully parsed VNet creation response: {json.dumps(vnet_data, indent=2)}")
                print(f"DEBUG: Successfully parsed VNet creation response: {json.dumps(vnet_data, indent=2)}")
                
                # Extract Admin RPC URL from rpcs array
                admin_rpc_url = None
                for rpc in vnet_data.get('rpcs', []):
                    if rpc.get('name') == 'Admin RPC':
                        admin_rpc_url = rpc.get('url')
                        break
                
                # Store the details with the admin_rpc_url added
                self.created_vnet_details = vnet_data
                self.created_vnet_details['admin_rpc_url'] = admin_rpc_url
                
                self.logger.info(f"Success! VNet created: {json.dumps(self.created_vnet_details, indent=2)}")
                print(f"Success! VNet created: {json.dumps(self.created_vnet_details, indent=2)}")
                return self.created_vnet_details
            else:
                self.logger.error(f"HTTP error creating VNet: {response.status_code}. Response: {response.text[:1000]}")
                print(f"ERROR: HTTP error creating VNet: {response.status_code}. Response: {response.text[:1000]}")
                return None
        except requests.RequestException as e:
            self.logger.error(f"Network error creating VNet: {e}")
            print(f"ERROR: Network error creating VNet: {e}")
            return None
        except ValueError as e:
            self.logger.error(f"ValueError during VNet creation: {e}")
            print(f"ERROR: ValueError during VNet creation: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error creating VNet: {e}")
            print(f"ERROR: Unexpected error creating VNet: {e}")
            return None

if __name__ == "__main__":
    access_key = os.getenv("TENDERLY_ACCESS_KEY", "")
    account_slug = os.getenv("TENDERLY_ACCOUNT_SLUG", "")
    project_slug = os.getenv("TENDERLY_PROJECT_SLUG", "")

    if not all([access_key, account_slug, project_slug]):
        print("ERROR: Missing Tenderly credentials. Please set TENDERLY_ACCESS_KEY, TENDERLY_ACCOUNT_SLUG, and TENDERLY_PROJECT_SLUG environment variables.")
        sys.exit(1)

    manager = TenderlyVirtualTestNetManager(access_key, account_slug, project_slug, logger=logger)
    result = manager.create_vnet(
        display_name="InfinityPoolsSDK-Test-VNet",
        parent_network_id="8453",
        vnet_chain_id=84530,
        enable_sync=True
    )
    if result:
        print(f"Success! VNet created: {json.dumps(result, indent=2)}")
    else:
        print("Failed to create VNet. Check the error messages above.")
