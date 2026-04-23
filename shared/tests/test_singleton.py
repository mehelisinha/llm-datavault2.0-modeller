"""
Unit tests for shared/singleton/singleton.py — SingletonMeta metaclass.
"""

import threading
import unittest

from shared.src.singleton.singleton import SingletonMeta
from shared.tests.conftest import SharedTestBase


class _Counter(metaclass=SingletonMeta):
    """Minimal singleton class used only inside tests."""

    def __init__(self, value: int = 0) -> None:
        self.value = value


class TestSingletonMetaSameInstance(SharedTestBase):
    """SingletonMeta must return the exact same object on every call."""

    def test_same_instance_returned(self) -> None:
        a = _Counter(1)
        b = _Counter()
        self.assertIs(a, b)

    def test_state_is_preserved(self) -> None:
        _Counter(42)
        instance = _Counter()
        self.assertEqual(instance.value, 42)


class TestSingletonMetaReinitGuard(SharedTestBase):
    """Passing args to an already-initialized singleton must raise RuntimeError."""

    def test_raises_on_second_init_with_args(self) -> None:
        _Counter(1)
        with self.assertRaises(RuntimeError):
            _Counter(99)

    def test_no_error_on_second_call_without_args(self) -> None:
        _Counter(1)
        try:
            _Counter()
        except RuntimeError:
            self.fail("_Counter() raised RuntimeError unexpectedly")


class TestSingletonMetaReset(SharedTestBase):
    """After clearing _instances a fresh singleton can be created."""

    def test_fresh_instance_after_reset(self) -> None:
        first = _Counter(10)
        SingletonMeta._instances.clear()
        second = _Counter(20)
        self.assertIsNot(first, second)
        self.assertEqual(second.value, 20)


class TestSingletonMetaThreadSafety(SharedTestBase):
    """Concurrent construction must still yield a single instance."""

    def test_thread_safe_creation(self) -> None:
        instances: list[_Counter] = []
        barrier = threading.Barrier(10)

        def create() -> None:
            barrier.wait()
            instances.append(_Counter())

        _Counter(0)  # prime singleton before threads race

        threads = [threading.Thread(target=create) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertTrue(all(i is instances[0] for i in instances))


class TestSingletonMetaIsolation(SharedTestBase):
    """Two distinct singleton classes must each have their own instance."""

    def test_separate_classes_are_independent(self) -> None:
        class _A(metaclass=SingletonMeta):
            pass

        class _B(metaclass=SingletonMeta):
            pass

        a = _A()
        b = _B()
        self.assertIsNot(a, b)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
