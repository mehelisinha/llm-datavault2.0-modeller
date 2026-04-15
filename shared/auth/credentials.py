from pydantic import BaseModel, Field


class ServicePrincipalSecretRef(BaseModel):
    """
    Reference to a Service Principal stored in Databricks Secret Scope.
    Contains only secret *identifiers*, not secret values.
    """

    client_id_key: str = Field(
        description="The key name in the secret scope to retrieve the actual client ID"
    )
    tenant_id: str
    scope: str = Field(
        description="Databricks secret scope where credentials are stored"
    )


class SecretReferenceConfig(ServicePrincipalSecretRef):
    """
    App credential class for storing configuration for getting authentication details from key vault.

    Attributes:
        scope: The Databricks secret scope where credentials are stored.
        client_id_key: The key name in the secret scope to retrieve the actual client ID.
        client_secret_key: The key name in the secret scope to retrieve the actual client secret.
        tenant_id: The tenant ID associated with the application.
    """

    client_secret_key: str = Field(
        description="The key name in the secret scope to retrieve the actual client secret."
    )


class ResolvedCredentials(BaseModel):
    """class for storing authentication details as retreaved from key vault.

    Attributes:
        client_id: The client ID retrieved from the secret scope.
        client_secret: The client secret retrieved from the secret scope.
        tenant_id: The tenant ID associated with the application.
    """

    client_id: str = Field(description="The client ID retrieved from the secret scope")
    client_secret: str = Field(
        description="The client secret retrieved from the secret scope"
    )
    tenant_id: str
