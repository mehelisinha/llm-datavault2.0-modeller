import io
import logging
import sys
from typing import Any, Dict, Literal

from shared.src.singleton.singleton import SingletonMeta


class SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "context"):
            record.context = ""

        class_name = getattr(record, "class_name", "")
        func_name = getattr(record, "funcName", "")

        if class_name and func_name:
            record.location = f"[{class_name}.{func_name}]"
        elif func_name:
            record.location = f"[{func_name}]"
        else:
            record.location = ""

        return super().format(record)


class EDHLogger(metaclass=SingletonMeta):
    """
    Singleton logger for EDH applications.

    Features:
    - Singleton lifecycle (single instance, single initialization)
    - Custom SUCCESS log level
    - Configurable output targets (stdout, memory, both)
    - Optional contextual logging via LoggerAdapter
    """

    SUCCESS_LEVEL_NUM: int = 25  # Between INFO (20) and WARNING (30)

    def __init__(
        self,
        name: str = "DBFSLogger",
        log_level: int = logging.INFO,
        logger_source: Literal["stdout", "memory", "both"] = "stdout",
    ) -> None:
        """
        Initialize the logger.

        NOTE:
            Due to singleton behavior, initialization arguments are applied
            only on the first instantiation.

        Args:
            name: Logger name.
            log_level: Logging level (e.g. logging.INFO, logging.DEBUG).
            logger_source: Output destination:
                - "stdout": standard output
                - "memory": in-memory buffer
                - "both": stdout + memory
        """
        if getattr(self, "_initialized", False):
            return

        self._register_success_level()
        # self._register_record_factory()

        self.logger: logging.Logger = logging.getLogger(name)
        self.logger.setLevel(log_level)

        self.logger_source: Literal["stdout", "memory", "both"] = logger_source
        self.log_capture_string: io.StringIO | None = None

        self._set_logger_handlers()

    # =====================================================
    # Custom Log Level Setup
    # =====================================================
    @classmethod
    def _register_success_level(cls) -> None:
        """
        Register the custom SUCCESS log level and Logger.success() method.

        This operation is idempotent and safe to call multiple times.
        """
        if hasattr(logging, "SUCCESS"):
            return

        logging.addLevelName(cls.SUCCESS_LEVEL_NUM, "SUCCESS")

        def success(
            self: logging.Logger,
            message: str,
            *args: Any,
            **kwargs: Any,
        ) -> None:
            if self.isEnabledFor(cls.SUCCESS_LEVEL_NUM):
                self._log(
                    cls.SUCCESS_LEVEL_NUM,
                    message,
                    args,
                    **kwargs,
                    stacklevel=2,
                )

        logging.Logger.success = success  # type: ignore[attr-defined]
        logging.SUCCESS = cls.SUCCESS_LEVEL_NUM

    # =====================================================
    # Factory for adding class and method to log in message
    # =====================================================
    # @classmethod
    # def _register_record_factory(cls) -> None:
    #     """
    #     Register a custom LogRecord factory to inject class_name into log records.
    #     Safe to call multiple times.
    #     """
    #     if cls._record_factory_set:
    #         return

    #     old_factory = logging.getLogRecordFactory()

    #     # def record_factory(*args, **kwargs):
    #     #     record = old_factory(*args, **kwargs)

    #     #     # Default
    #     #     record.class_name = ""

    #     #     # Walk back frames to find `self`
    #     #     frame = inspect.currentframe()
    #     #     while frame:
    #     #         local_self = frame.f_locals.get("self")
    #     #         if local_self:
    #     #             record.class_name = local_self.__class__.__name__
    #     #             break
    #     #         frame = frame.f_back

    #     #     return record
    #     def record_factory(*args, **kwargs):
    #         record = old_factory(*args, **kwargs)
    #         record.class_name = ""
    #         return record
    #     logging.setLogRecordFactory(record_factory)
    #     cls._record_factory_set = True

    # =====================================================
    # Handler Setup
    # =====================================================
    def _has_handler(self, handler_type: type[logging.Handler]) -> bool:
        """
        Check if a handler of a given type is already attached to the logger.
        """
        return any(isinstance(h, handler_type) for h in self.logger.handlers)

    def _set_logger_handlers(self) -> None:
        """
        Configure logger handlers based on the configured logger_source.

        Prevents duplicate handlers from being added.
        """
        if self._has_handler(logging.StreamHandler):
            self.logger.debug(
                "Logger already has StreamHandler(s). Skipping handler initialization."
            )
            return

        if self.logger_source in ("stdout", "both"):
            self._add_stdout_handler()

        if self.logger_source in ("memory", "both"):
            self._add_memory_handler()

        self.logger.propagate = False

    def _add_stdout_handler(self) -> None:
        """Attach a StreamHandler that logs to stdout."""
        self.logger.debug("Initializing stdout logger handler")

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(self._get_formatter())
        self.logger.addHandler(handler)

    def _add_memory_handler(self) -> None:
        """Attach a StreamHandler that logs to an in-memory buffer."""
        self.logger.debug("Initializing in-memory logger handler")

        self.log_capture_string = io.StringIO()
        handler = logging.StreamHandler(self.log_capture_string)
        handler.setFormatter(self._get_formatter())
        self.logger.addHandler(handler)

    @staticmethod
    def _get_formatter() -> logging.Formatter:
        """
        Return the standardized log formatter.
        """
        # return SafeFormatter("%(asctime)s - %(levelname)s - %(message)s%(context)s")
        return SafeFormatter(
            "%(asctime)s - %(levelname)s - %(location)s %(message)s%(context)s"
        )

    # =====================================================
    # Public API
    # =====================================================
    def get_logger(self) -> logging.Logger:
        """
        Return the underlying logger instance.
        """
        return self.logger

    def get_logs(self) -> str:
        """
        Retrieve logs captured in memory.

        Returns:
            The captured log output, or an empty string if memory logging
            is not enabled.
        """
        if self.log_capture_string is not None:
            return self.log_capture_string.getvalue()
        return ""

    def get_adapter(
        self,
        context: str | Dict[str, Any],
    ) -> logging.LoggerAdapter:
        """
        Return a LoggerAdapter enriched with contextual information.

        Args:
            context:
                - str: free-form context string
                - dict: key/value context converted to `key=value` pairs

        Returns:
            logging.LoggerAdapter
        """
        if isinstance(context, dict):
            context_str = " ".join(f"{k}={v}" for k, v in context.items())
        else:
            context_str = context

        return logging.LoggerAdapter(
            self.logger,
            extra={"context": f" {context_str}" if context_str else ""},
        )
