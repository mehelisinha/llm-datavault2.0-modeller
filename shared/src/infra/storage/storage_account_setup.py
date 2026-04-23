from shared.src.auth.credentials import ResolvedCredentials
from shared.src.logger.default_logger import default_logger
from shared.src.singleton.multiton import MultitonMeta
from shared.utils.spark import spark


class StorageAccount(metaclass=MultitonMeta):
    def __init__(self, storage_account: str, credentials: ResolvedCredentials):
        """Contructor method for StorageAccount class used to set up the account credentials.

        Args:
            scope (string): used to retrive the service credentials from key vault
            storage_account (string): name of the storage account to be set up
            app_credentials (AppCredentials): used to retrive the service credentials from key vault
                contains:
                client_id, client_secret, tenant_id

        """
        self.storage_account = storage_account
        self.credentials = credentials
        self._configure_storage_credentials()

    def _configure_storage_credentials(self):
        """
        Configures Azure Data Lake Storage credentials in Spark using a service principal.

        Parameters:
        - scope: The Databricks secret scope containing the credentials.
        - storage_account: The name of the Azure Storage Account.
        - client_id_key: The key name for the service principal's client ID in the secret scope.
        - client_secret_key: The key name for the service principal's client secret in the secret scope.
        - tenant_id: The Azure Active Directory tenant ID.
        """
        # logger.debug(f"DEBUG SET UP STOTAGE. CREDENTIALS: {self.storage_account}")
        # Define Spark configurations in a dictionary
        spark_configs = {
            f"fs.azure.account.auth.type.{self.storage_account}.dfs.core.windows.net": "OAuth",
            f"fs.azure.account.oauth.provider.type.{self.storage_account}.dfs.core.windows.net": "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider",
            f"fs.azure.account.oauth2.client.id.{self.storage_account}.dfs.core.windows.net": self.credentials.client_id,
            f"fs.azure.account.oauth2.client.secret.{self.storage_account}.dfs.core.windows.net": self.credentials.client_secret,
            f"fs.azure.account.oauth2.client.endpoint.{self.storage_account}.dfs.core.windows.net": f"https://login.microsoftonline.com/{self.credentials.tenant_id}/oauth2/token",
        }

        # Apply Spark configurations
        for key, value in spark_configs.items():
            spark.conf.set(key, value)

        default_logger.info(
            f"🔒  Storage credentials successfully configured for account: {self.storage_account}"
        )
