from shared.src.auth.credentials import (
    ResolvedCredentials,
    SecretReferenceConfig,
)
from shared.src.auth.databricks_secret_manager import DatabricksSecretManager


class SecretProvider:
    """
    Manages credentials by securely retrieving them from Databricks secrets.

    This class provides access to sensitive application credentials, such as `client_id` and
    `client_secret`, using the Databricks secret manager. It ensures that credentials are
    retrieved only when needed and are cached for subsequent access.

    Attributes:
        ***app_credential_config*** (AppCredentialConfigurations):
            Configuration object containing the scope and keys for retrieving credentials:
                - client_id_key
                - client_secret_key
                _ tenanat_id


    **Properties**:
        - client_id (str): Retrieves the client ID from Databricks secrets if not already cached.
        - client_secret (str): Retrieves the client secret from Databricks secrets if not already cached.
        - credentials (AppCredentials): Returns an `AppCredentials` object containing the
            ***client ID***, ***client secret***, and ***tenant ID***.

    **Example Usage**:
        ```python
        app_cred_manager = AppCredetialManager(app_credential_config)
        credentials = app_cred_manager.credentials
        print(credentials.client_id, credentials.client_secret)
        ```

    Raises:
        Exception: If there is an issue retrieving secrets from Databricks.
    """

    def __init__(self, app_credential_config: "SecretReferenceConfig") -> None:
        self.app_credential_config = app_credential_config
        self._client_id: str | None = None
        self._client_secret: str | None = None

    @property
    def client_id(self) -> str:
        """Retrieves the client ID from Databricks secrets if not already cached."""
        if not self._client_id:
            self._client_id = DatabricksSecretManager.get_secret(
                scope=self.app_credential_config.scope,
                key=self.app_credential_config.client_id_key,
            )
            if not self._client_id:
                raise ValueError("Client ID could not be retrieved.")
        return self._client_id

    @property
    def client_secret(self) -> str:
        """Retrieved the client secret from Databricks secrets if not already cached."""
        if not self._client_secret:
            self._client_secret = DatabricksSecretManager.get_secret(
                scope=self.app_credential_config.scope,
                key=self.app_credential_config.client_secret_key,
            )
            if not self._client_secret:
                raise ValueError("Client secret could not be retrieved.")
        return self._client_secret

    @property
    def resolved_credentials(self) -> "ResolvedCredentials":
        """
        Returns an `AppCredentials` object containing the client ID, client secret, and tenant ID.

        Returns:
            AppCredentials: An instance containing the authentication details.
        """
        return ResolvedCredentials(
            client_id=self.client_id,
            client_secret=self.client_secret,
            tenant_id=self.app_credential_config.tenant_id,
        )
