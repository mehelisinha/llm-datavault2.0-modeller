from logging import Logger
from typing import Any, Dict

import requests
from databricks.sdk import WorkspaceClient
from dbruntime.databricks_repl_context import get_context

from shared.src.auth.credentials import ResolvedCredentials
from shared.src.auth.workspace_identity import WorkspaceIdentity
from shared.src.logger.default_logger import default_logger


class TokenManager:
    """
    Manages the token for the service principal.
    """

    def __init__(self, logger: Logger = default_logger):
        self.logger = logger
        env_fetcher = WorkspaceIdentity()
        self.workspace_url = env_fetcher.workspace_url
        self.workspace_host = env_fetcher.workspace_host
        self._api_token: str = None
        self.api_version = "2.0"

    @property
    def api_token(self) -> str:
        if self._api_token is None:
            # self._api_token = (
            #     dbutils.notebook.entry_point.getDbutils()
            #     .notebook()
            #     .getContext()
            #     .apiToken()
            #     .get()
            # )
            self._api_token = self._get_api_token()
        return self._api_token

    def _get_api_token(self) -> str:
        """Retrieve the current API token using the Databricks SDK credential chain.

        Works on all cluster types including USER_ISOLATION shared clusters
        where dbutils.notebook.entry_point and get_context().apiToken return None.
        """
        # Primary: Databricks SDK (handles OAuth, PAT, managed identity, etc.)
        try:
            w = WorkspaceClient()
            headers: dict = {}
            w.config.authenticate(headers)
            auth = headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                return auth[7:]
        except Exception:
            pass

        # Fallback: dbruntime REPL context
        try:
            token = get_context().apiToken
            if token:
                return token
        except Exception:
            pass

        raise RuntimeError(
            "Could not retrieve API token from any available source. "
            "Ensure the code is running inside a Databricks notebook context."
        )

    def delete_token(self, token_id_to_delete: str):
        """
        Deletes the token with the given ID.
        """

        # Endpoint
        url = f"{self.workspace_url}/api/{self.api_version}/token/delete"

        # Headers
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        # Payload
        payload = {"token_id": token_id_to_delete}

        # Make the DELETE request
        response = requests.post(url, headers=headers, json=payload)

        # Output result
        if response.status_code == 200:
            print(f"✅ Token {token_id_to_delete} deleted successfully.")
        else:
            print(f"❌ Failed to delete token: {response.status_code}")
            print(response.text)

    def create_token(
        self, app_cred: ResolvedCredentials, comment: str, lifetime_seconds: int = 3650
    ):
        # Service Principal details
        tenant_id = app_cred.tenant_id
        client_id = app_cred.client_id
        client_secret = app_cred.client_secret

        # Get Azure AD Access Token
        azure_ad_url = (
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        )
        azure_ad_payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default",  # Scopes for Azure Databricks
            "grant_type": "client_credentials",
        }

        azure_response = requests.post(azure_ad_url, data=azure_ad_payload)
        azure_token = azure_response.json().get("access_token")

        # Get Databricks PAT using Azure AD token
        databricks_api = f"/api/{self.api_version}/token/create"
        databricks_headers = {
            "Authorization": f"Bearer {azure_token}",
            "Content-Type": "application/json",
        }
        databricks_body: Dict[str, Any] = {
            "lifetime_seconds": lifetime_seconds,
            "comment": comment,
        }

        databricks_response = requests.post(
            f"{self.workspace_url}{databricks_api}",
            headers=databricks_headers,
            json=databricks_body,
        )
        self.logger.info("Status code:", databricks_response.status_code)
        self.logger.info("Response text:", databricks_response.text)
        databricks_pat = databricks_response.json().get("token_value")
        self.logger.info(f"Generated Databricks PAT: {databricks_pat}")
        return databricks_pat

    def list_tokens(self):
        # Set the API endpoint to list tokens
        url = f"{self.workspace_url}/api/{self.api_version}/token/list"

        # Set the headers with the Service Principal access token (PAT or OAuth token)
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        # Make the GET request to list tokens
        response = requests.get(url, headers=headers)

        # Handle the response
        if response.status_code == 200:
            self.logger.info("Tokens List:")
            tokens = response.json().get("tokens", [])
            for token in tokens:
                self.logger.info(
                    f"Token ID: {token['token_id']}, Created At: {token['created_at']}, Expiration Time: {token.get('expiration_time', 'N/A')}"
                )
        else:
            self.logger.error(
                f"Error listing tokens: {response.status_code} - {response.text}"
            )
            raise Exception(
                f"Error listing tokens: {response.status_code} - {response.text}"
            )
        return response.json()

    def is_token_valid(self, token_id_to_check: str) -> bool:
        """Checks if the token is valid by making a request to the workspace URL.
        This method sends a GET request to the workspace URL with the provided token ID
        in the headers. If the response status code is 200, the token is considered valid.
        If the response status code is not 200, the token is considered invalid.
        The method returns a boolean value indicating the validity of the token.
        The method also logs the result of the token validity check.

        Args:
            token_id_to_check (str): The token ID to check for validity.

        Returns:
            bool: True if the token is valid, False otherwise.
        """
        headers = {"Authorization": f"Bearer {token_id_to_check}"}
        response = requests.get(
            f"{self.workspace_url}/api/{self.api_version}/workspace/list?path=/",
            headers=headers,
        )
        # Output result
        if response.status_code == 200:
            self.logger.info(f"✅ Token {token_id_to_check} is valid.")
        else:
            self.logger.info(f"❌ Failed to check token: {response.status_code}")
            self.logger.info(response.text)
        return response.status_code == 200
