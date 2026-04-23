"""
Unit tests for shared/singleton/multiton.py — MultitonMixin, MultitonMeta,
and the @multiton decorator.
"""

import unittest

from shared.src.singleton.multiton import MultitonMeta, MultitonMixin, multiton
from shared.tests.conftest import SharedTestBase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StorageAccount(metaclass=MultitonMeta):
    """Minimal class using MultitonMeta (keyed by storage_account kwarg)."""

    def __init__(self, storage_account: str, region: str = "westeurope") -> None:
        self.storage_account = storage_account
        self.region = region


class _Connection(MultitonMixin):
    """Minimal class using MultitonMixin (keyed by all public fields)."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port


@multiton(include=["host", "port"])
class _DbConn:
    """Class using the @multiton decorator with explicit key fields."""

    def __init__(self, host: str, port: int, password: str = "secret") -> None:
        self.host = host
        self.port = port
        self.password = password


# ---------------------------------------------------------------------------
# MultitonMeta
# ---------------------------------------------------------------------------


class TestMultitonMeta(SharedTestBase):
    """MultitonMeta: one instance per key, reuse across calls."""

    def setUp(self) -> None:
        super().setUp()
        MultitonMeta._instances.clear()

    def tearDown(self) -> None:
        super().tearDown()
        MultitonMeta._instances.clear()

    def test_same_key_returns_same_instance(self) -> None:
        a = _StorageAccount(storage_account="sa1")
        b = _StorageAccount(storage_account="sa1")
        self.assertIs(a, b)

    def test_different_keys_return_different_instances(self) -> None:
        a = _StorageAccount(storage_account="sa1")
        b = _StorageAccount(storage_account="sa2")
        self.assertIsNot(a, b)

    def test_list_instances(self) -> None:
        _StorageAccount(storage_account="sa1")
        _StorageAccount(storage_account="sa2")
        instances = MultitonMeta.list_instances()
        keys = [k[1] for k in instances if k[0] is _StorageAccount]
        self.assertIn("sa1", keys)
        self.assertIn("sa2", keys)


# ---------------------------------------------------------------------------
# MultitonMixin
# ---------------------------------------------------------------------------


class TestMultitonMixin(SharedTestBase):
    """MultitonMixin: get_or_create, clear_pool, get_pool_stats."""

    def setUp(self) -> None:
        super().setUp()
        _Connection.clear_pool()

    def tearDown(self) -> None:
        super().tearDown()
        _Connection.clear_pool()

    def test_get_or_create_returns_same_for_same_args(self) -> None:
        a = _Connection.get_or_create(host="localhost", port=5432)
        b = _Connection.get_or_create(host="localhost", port=5432)
        self.assertIs(a, b)

    def test_get_or_create_returns_different_for_different_args(self) -> None:
        a = _Connection.get_or_create(host="host-a", port=5432)
        b = _Connection.get_or_create(host="host-b", port=5432)
        self.assertIsNot(a, b)

    def test_clear_pool_empties_cache(self) -> None:
        _Connection.get_or_create(host="localhost", port=5432)
        _Connection.clear_pool()
        stats = _Connection.get_pool_stats()
        self.assertEqual(stats["total_instances"], 0)

    def test_get_pool_stats_counts_instances(self) -> None:
        _Connection.get_or_create(host="a", port=1)
        _Connection.get_or_create(host="b", port=2)
        stats = _Connection.get_pool_stats()
        self.assertEqual(stats["total_instances"], 2)

    def test_get_all_instances_returns_list(self) -> None:
        _Connection.get_or_create(host="x", port=9)
        all_inst = _Connection.get_all_instances()
        self.assertIsInstance(all_inst, list)
        self.assertEqual(len(all_inst), 1)

    def test_empty_pool_returns_empty_list(self) -> None:
        self.assertEqual(_Connection.get_all_instances(), [])


# ---------------------------------------------------------------------------
# @multiton decorator
# ---------------------------------------------------------------------------


class TestMultitonDecorator(SharedTestBase):
    """The @multiton decorator must provide the same caching semantics."""

    def setUp(self) -> None:
        super().setUp()
        _DbConn.clear_pool()

    def tearDown(self) -> None:
        super().tearDown()
        _DbConn.clear_pool()

    def test_same_key_fields_yield_equivalent_state(self) -> None:
        # Decorator returns objects sharing the same __dict__, so mutations
        # on one are visible on the other (shared state / same effective identity).
        a = _DbConn(host="db", port=5432, password="p1")
        b = _DbConn(host="db", port=5432, password="p2")
        # include=['host','port'] — password excluded from key
        self.assertEqual(a.host, b.host)
        self.assertEqual(a.port, b.port)
        # Shared __dict__: mutating a is reflected in b
        a.host = "changed"
        self.assertEqual(b.host, "changed")

    def test_different_key_fields_yield_different_instances(self) -> None:
        a = _DbConn(host="db1", port=5432)
        b = _DbConn(host="db2", port=5432)
        self.assertIsNot(a, b)

    def test_get_pool_stats(self) -> None:
        _DbConn(host="db1", port=1)
        _DbConn(host="db2", port=2)
        stats = _DbConn.get_pool_stats()
        self.assertEqual(stats["total_instances"], 2)

    def test_clear_pool_empties_cache(self) -> None:
        _DbConn(host="db1", port=1)
        _DbConn.clear_pool()
        stats = _DbConn.get_pool_stats()
        self.assertEqual(stats["total_instances"], 0)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
