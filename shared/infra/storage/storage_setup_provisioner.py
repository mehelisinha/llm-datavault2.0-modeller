from shared.auth.credential_manager import (
    CredentialManager,
)
from shared.infra.storage.storage_account_setup import StorageAccount


class StorageSetupProvisioner:
    @staticmethod
    def provisiona_storage_set_up(
        storage_account: str,
        client_secret_key: str = "SP-INTEGRATION-SECRET",
    ) -> None:
        credential_manager = CredentialManager()
        StorageAccount(
            storage_account=storage_account,
            credentials=credential_manager.get_resolved_credentials(client_secret_key),
        )
