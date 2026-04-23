from __future__ import annotations

from shared.src.auth.credentials import (
    ResolvedCredentials,
    SecretReferenceConfig,
    ServicePrincipalSecretRef,
)
from shared.src.auth.secret_provider import SecretProvider
from shared.src.logger.default_logger import default_logger
from shared.src.singleton.singleton import SingletonMeta


class CredentialManager(metaclass=SingletonMeta):
    """
    Reads connection configurations and retunrs ResolvedCredentials from scope with attributes:
        -  client_id
        -  client_secret
        -  tenant_id

    """

    def __init__(self) -> None:
        self._service_principal_secret_ref: ServicePrincipalSecretRef | None = None
        self._app_con: dict[str, str] | None = None

        self._resolved_cache: dict[str, ResolvedCredentials] = {}
        self.net_code = "unreg"
        self.env = "dev"
        self.edh_version = "is02"

    def clear_cache(self):
        """Clears the cached app credential configuration."""
        self._service_principal_secret_ref = None

    @property
    def app_conn(self) -> dict[str, str]:
        return {
            "client_secret": "SP-INTEGRATION-SECRET",
            "tenant_id": "REDACTED_TENANT",
            "client_id": "SP-INTEGRATION-APP-ID",
        }

    @property
    def service_principal_secret_ref(self) -> ServicePrincipalSecretRef:
        """Service Principal configurations.

        Args:
            secret_alias (str): The alias of the secret to retrieve.

        Raises:
            ValueError: _description_

        Returns:
            SecretReferenceConfig: The secret reference configurations with attributes:
                    -  client_id_key
                    -  tenant_id
                    -  scope
        """
        try:
            if not self._service_principal_secret_ref:
                app_conn = self.app_conn
                self._service_principal_secret_ref = ServicePrincipalSecretRef(
                    client_id_key=app_conn["client_id"],
                    tenant_id=app_conn["tenant_id"],
                    scope=f"kv-edh{self.net_code}-euw-{self.env}-{self.edh_version}",
                )
            return self._service_principal_secret_ref
        except Exception as e:
            default_logger.error("❌ Error getting service principal config")
            raise ValueError(e) from e

    def get_resolved_credentials(
        self, client_secret_key: str, clear_cache: bool = False
    ) -> ResolvedCredentials:
        """
        Resolves credentials for a secret key.
        Will retreave it from chache if already resolved.

        Args:
            client_secret_key: The key name in the Databricks secret scope.

        Returns:
            ResolvedCredentials
        """
        if clear_cache:
            self._resolved_cache = {}

        if client_secret_key in self._resolved_cache:
            return self._resolved_cache[client_secret_key]

        try:
            service_principal_secret_ref = self.service_principal_secret_ref
            secret_getter = SecretProvider(
                SecretReferenceConfig(
                    scope=service_principal_secret_ref.scope,
                    client_id_key=service_principal_secret_ref.client_id_key,
                    client_secret_key=client_secret_key,
                    tenant_id=service_principal_secret_ref.tenant_id,
                )
            )
            resolved_creds = secret_getter.resolved_credentials
            self._resolved_cache[client_secret_key] = resolved_creds  # store in cache
            return resolved_creds
        except Exception as e:
            default_logger.error(
                "❌ Error getting credentials for key '%s' through SecretProvider",
                client_secret_key,
            )
            raise ConnectionError(
                f"Failed to resolve credentials for '{client_secret_key}'"
            ) from e
