from typing import List, Optional

from dbruntime.dbutils import SecretMetadata  # type: ignore

from shared.logger.default_logger import default_logger
from shared.utils.spark import dbutils


class DatabricksSecretManager:
    """
    Fetches secrets securely from Databricks Secret Scope.
    """

    @staticmethod
    def get_secret(scope: str, key: str) -> str:
        """
        Fetch a secret from the Databricks secret scope.

        :param key: The key of the secret to fetch
        :return: The secret value as a string.
        """
        try:
            default_logger.debug(f"Fetching secret '{key}' from scope '{scope}'")
            return dbutils.secrets.get(scope=scope, key=key)
        except Exception as e:
            raise ConnectionError(
                f"Error fetching secret '{key}' from scope '{scope}': {str(e)}"
            )

    @staticmethod
    def list_secrets(scope: str) -> Optional[List[SecretMetadata]]:
        return dbutils.secrets.list(scope)
