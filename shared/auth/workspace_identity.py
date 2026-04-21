import hashlib
from urllib.parse import urlparse

from shared.singleton.singleton import SingletonMeta
from shared.utils.spark import spark


class WorkspaceIdentity(metaclass=SingletonMeta):
    """
    Singleton managing the Databricks workspace identity.

    Responsibilities:
        - Retrieve workspace URL from Spark configs.
        - Extract workspace host.
        - Compute a SHA-256 hash of the host for secure identification.
    """

    def __init__(self):
        """Initializes the WorkspaceUrlFetcher by retrieving and hashing the workspace URL."""

        self.workspace_url = self.get_workspace_url()
        self.workspace_host = self.extract_workspace_host(self.workspace_url)

    # ---------Properties---------#
    @property
    def workspace_host_hash(self) -> str:
        """SHA-256 hash of the workspace host (used for config mapping)."""
        return self._hash_workspace_host()

    # ---------Methods---------#
    @staticmethod
    def get_workspace_url() -> str:
        """Retrieves the Databricks workspace URL from Spark configurations.

        Returns:
            str: The workspace URL as a string.
        """
        url = str(spark.conf.get("spark.databricks.workspaceUrl"))
        if "https://" not in url:
            url = f"https://{str(spark.conf.get('spark.databricks.workspaceUrl'))}"
        return url

    @staticmethod
    def extract_workspace_host(workspace_url: str) -> str:
        parsed = urlparse(workspace_url)
        return parsed.netloc

    # ---------Helper Methods---------#
    def _hash_workspace_host(self) -> str:
        """Computes the SHA-256 hash of the workspace URL."""
        return hashlib.sha256(self.workspace_host.encode()).hexdigest()
