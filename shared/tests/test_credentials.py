"""
Unit tests for shared/auth/credentials.py — Pydantic credential models.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..")))

import unittest

from pydantic import ValidationError

from shared.src.auth.credentials import (
    ResolvedCredentials,
    SecretReferenceConfig,
    ServicePrincipalSecretRef,
)
from shared.tests.conftest import SharedTestBase

# ---------------------------------------------------------------------------
# ServicePrincipalSecretRef
# ---------------------------------------------------------------------------


class TestServicePrincipalSecretRef(SharedTestBase):
    """ServicePrincipalSecretRef must accept valid data and reject missing fields."""

    def _valid_data(self) -> dict:
        return {
            "client_id_key": "SP_CLIENT_ID",
            "tenant_id": "tenant-123",
            "scope": "edh-scope",
        }

    def test_valid_construction(self) -> None:
        ref = ServicePrincipalSecretRef(**self._valid_data())
        self.assertEqual(ref.client_id_key, "SP_CLIENT_ID")
        self.assertEqual(ref.tenant_id, "tenant-123")
        self.assertEqual(ref.scope, "edh-scope")

    def test_missing_client_id_key_raises(self) -> None:
        data = self._valid_data()
        del data["client_id_key"]
        with self.assertRaises(ValidationError):
            ServicePrincipalSecretRef(**data)

    def test_missing_tenant_id_raises(self) -> None:
        data = self._valid_data()
        del data["tenant_id"]
        with self.assertRaises(ValidationError):
            ServicePrincipalSecretRef(**data)

    def test_missing_scope_raises(self) -> None:
        data = self._valid_data()
        del data["scope"]
        with self.assertRaises(ValidationError):
            ServicePrincipalSecretRef(**data)


# ---------------------------------------------------------------------------
# SecretReferenceConfig
# ---------------------------------------------------------------------------


class TestSecretReferenceConfig(SharedTestBase):
    """SecretReferenceConfig extends the parent with client_secret_key."""

    def _valid_data(self) -> dict:
        return {
            "client_id_key": "SP_CLIENT_ID",
            "tenant_id": "tenant-456",
            "scope": "edh-scope",
            "client_secret_key": "SP_CLIENT_SECRET",
        }

    def test_valid_construction(self) -> None:
        cfg = SecretReferenceConfig(**self._valid_data())
        self.assertEqual(cfg.client_secret_key, "SP_CLIENT_SECRET")

    def test_missing_client_secret_key_raises(self) -> None:
        data = self._valid_data()
        del data["client_secret_key"]
        with self.assertRaises(ValidationError):
            SecretReferenceConfig(**data)

    def test_inherits_parent_fields(self) -> None:
        cfg = SecretReferenceConfig(**self._valid_data())
        self.assertEqual(cfg.scope, "edh-scope")
        self.assertEqual(cfg.tenant_id, "tenant-456")

    def test_is_instance_of_parent(self) -> None:
        cfg = SecretReferenceConfig(**self._valid_data())
        self.assertIsInstance(cfg, ServicePrincipalSecretRef)


# ---------------------------------------------------------------------------
# ResolvedCredentials
# ---------------------------------------------------------------------------


class TestResolvedCredentials(SharedTestBase):
    """ResolvedCredentials holds the actual resolved secret values."""

    def _valid_data(self) -> dict:
        return {
            "client_id": "abc-def-ghi",
            "client_secret": "super-secret-value",
            "tenant_id": "tenant-789",
        }

    def test_valid_construction(self) -> None:
        cred = ResolvedCredentials(**self._valid_data())
        self.assertEqual(cred.client_id, "abc-def-ghi")
        self.assertEqual(cred.client_secret, "super-secret-value")
        self.assertEqual(cred.tenant_id, "tenant-789")

    def test_missing_client_secret_raises(self) -> None:
        data = self._valid_data()
        del data["client_secret"]
        with self.assertRaises(ValidationError):
            ResolvedCredentials(**data)

    def test_missing_client_id_raises(self) -> None:
        data = self._valid_data()
        del data["client_id"]
        with self.assertRaises(ValidationError):
            ResolvedCredentials(**data)

    def test_missing_tenant_id_raises(self) -> None:
        data = self._valid_data()
        del data["tenant_id"]
        with self.assertRaises(ValidationError):
            ResolvedCredentials(**data)

    def test_not_instance_of_secret_ref(self) -> None:
        cred = ResolvedCredentials(**self._valid_data())
        self.assertNotIsInstance(cred, ServicePrincipalSecretRef)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
