"""
Unit tests for shared/logger/logger_manager.py — EDHLogger singleton.
"""

import logging
import unittest

from shared.src.logger.logger_manager import EDHLogger
from shared.src.singleton.singleton import SingletonMeta
from shared.tests.conftest import SharedTestBase


class TestEDHLoggerSingleton(SharedTestBase):
    """EDHLogger must satisfy the singleton contract."""

    def test_same_instance_returned_on_repeated_calls(self) -> None:
        a = EDHLogger(name="test-logger", logger_source="memory")
        b = EDHLogger()
        self.assertIs(a, b)

    def test_raises_on_second_init_with_args(self) -> None:
        EDHLogger(name="first", logger_source="memory")
        with self.assertRaises(RuntimeError):
            EDHLogger(name="second", logger_source="memory")

    def test_instance_stored_in_singleton_registry(self) -> None:
        instance = EDHLogger(name="reg-test", logger_source="memory")
        self.assertIn(EDHLogger, SingletonMeta._instances)
        self.assertIs(SingletonMeta._instances[EDHLogger], instance)


class TestEDHLoggerSuccessLevel(SharedTestBase):
    """The custom SUCCESS level must be registered and usable."""

    def test_success_level_registered(self) -> None:
        EDHLogger(name="lvl-test", logger_source="memory")
        self.assertTrue(hasattr(logging, "SUCCESS"))
        self.assertEqual(logging.SUCCESS, EDHLogger.SUCCESS_LEVEL_NUM)  # type: ignore[attr-defined]

    def test_success_method_exists_on_logger(self) -> None:
        edh = EDHLogger(name="method-test", logger_source="memory")
        self.assertTrue(hasattr(edh.get_logger(), "success"))

    def test_success_message_captured(self) -> None:
        edh = EDHLogger(name="success-cap", logger_source="memory")
        edh.get_logger().success("all good")  # type: ignore[attr-defined]
        logs = edh.get_logs()
        self.assertIn("all good", logs)


class TestEDHLoggerMemoryCapture(SharedTestBase):
    """Memory-mode logger must capture all messages."""

    def test_info_message_captured_in_memory(self) -> None:
        edh = EDHLogger(name="mem-test", logger_source="memory")
        edh.get_logger().info("hello memory")
        self.assertIn("hello memory", edh.get_logs())

    def test_debug_message_captured_in_memory(self) -> None:
        edh = EDHLogger(
            name="debug-mem", log_level=logging.DEBUG, logger_source="memory"
        )
        edh.get_logger().debug("debug line")
        self.assertIn("debug line", edh.get_logs())

    def test_get_logs_empty_without_memory_handler(self) -> None:
        edh = EDHLogger(name="stdout-only", logger_source="stdout")
        self.assertEqual(edh.get_logs(), "")


class TestEDHLoggerHandlerDedup(SharedTestBase):
    """Calling _set_logger_handlers twice must not add duplicate handlers."""

    def test_no_duplicate_handlers(self) -> None:
        edh = EDHLogger(name="dedup-test", logger_source="stdout")
        before = len(edh.get_logger().handlers)
        edh._set_logger_handlers()
        after = len(edh.get_logger().handlers)
        self.assertEqual(before, after)


class TestEDHLoggerAdapter(SharedTestBase):
    """get_adapter must return a LoggerAdapter with context extras."""

    def test_adapter_from_string_context(self) -> None:
        edh = EDHLogger(name="adapter-str", logger_source="memory")
        adapter = edh.get_adapter("run_id=123")
        self.assertIsInstance(adapter, logging.LoggerAdapter)

    def test_adapter_from_dict_context(self) -> None:
        edh = EDHLogger(name="adapter-dict", logger_source="memory")
        adapter = edh.get_adapter({"env": "dev", "version": "1"})
        self.assertIsInstance(adapter, logging.LoggerAdapter)
        self.assertIn("env=dev", adapter.extra["context"])
        self.assertIn("version=1", adapter.extra["context"])

    def test_adapter_logs_message(self) -> None:
        edh = EDHLogger(name="adapter-log", logger_source="memory")
        adapter = edh.get_adapter("ctx")
        adapter.info("via adapter")
        self.assertIn("via adapter", edh.get_logs())


class TestEDHLoggerGetLogger(SharedTestBase):
    """get_logger must return a standard logging.Logger."""

    def test_returns_logging_logger(self) -> None:
        edh = EDHLogger(name="get-logger-test", logger_source="memory")
        self.assertIsInstance(edh.get_logger(), logging.Logger)

    def test_propagate_disabled(self) -> None:
        edh = EDHLogger(name="propagate-test", logger_source="stdout")
        self.assertFalse(edh.get_logger().propagate)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
