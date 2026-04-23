import hashlib
import json
from functools import wraps
from typing import Any, ClassVar, TypeVar

from shared.src.logger.default_logger import default_logger


# #tag: to_enhace: currently this is only used on Storage Account, and is seleceting storage_account or the arg[0]
class MultitonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        Return one instance per unique key (e.g., 'name').
        """
        # We only use this for storage account. Add other keys if needed

        key = (
            kwargs.get("storage_account")
            if "storage_account" in kwargs
            else (args[0] if args else "default")
        )

        if (cls, key) not in cls._instances:
            default_logger.debug(
                (
                    f" [MultitonMeta] Creating new instance for key={key!r} in {cls.__name__}"
                )
            )
            instance = super().__call__(*args, **kwargs)
            cls._instances[(cls, key)] = instance
        else:
            default_logger.debug(
                f"[MultitonMeta] Reusing existing instance for key={key!r} in {cls.__name__}"
            )

        return cls._instances[(cls, key)]

    # Utility: inspect what exists
    @classmethod
    def list_instances(mcs):
        return {k: v for k, v in mcs._instances.items()}


T = TypeVar("T")


class MultitonMixin:
    """
    Mixin class to add multiton behavior to any class (especially Pydantic models).
    One instance per unique combination of key fields.
    """

    _multiton_instances: ClassVar[dict[str, Any]] = {}
    _multiton_key_fields: ClassVar[list[str] | None] = None
    _multiton_exclude_fields: ClassVar[list[str] | None] = None

    def _get_cache_key(self) -> str:
        """Generate cache key from specified fields"""
        if self._multiton_key_fields:
            # Use only specified fields
            key_data = {k: getattr(self, k) for k in self._multiton_key_fields}
        else:
            # Use all fields, excluding specified ones
            exclude = set(self._multiton_exclude_fields or [])
            # Add private attributes to exclusions
            exclude.update(k for k in self.__dict__ if k.startswith("_"))

            # Handle both Pydantic models and regular classes
            if hasattr(self, "model_dump"):
                # Pydantic model
                key_data = self.model_dump(exclude=exclude, mode="json")
            else:
                # Regular class
                key_data = {
                    k: v
                    for k, v in self.__dict__.items()
                    if k not in exclude and not k.startswith("_")
                }

        # Convert to JSON-serializable format
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_string.encode()).hexdigest()

    @classmethod
    def get_or_create(cls: type[T], **kwargs: Any) -> T:
        """Get existing instance or create new one"""
        # Create temporary instance to generate key
        temp = cls(**kwargs)
        key = temp._get_cache_key()

        # Initialize class-level dict if needed
        if not hasattr(cls, "_multiton_instances"):
            cls._multiton_instances = {}

        if key not in cls._multiton_instances:
            cls._multiton_instances[key] = temp

        return cls._multiton_instances[key]

    @classmethod
    def get_pool_stats(cls) -> dict[str, Any]:
        """Get statistics about cached instances"""
        if not hasattr(cls, "_multiton_instances"):
            return {"total_instances": 0, "instances": []}

        instances_data = []
        for inst in cls._multiton_instances.values():
            if hasattr(inst, "model_dump"):
                # Pydantic model
                instances_data.append(
                    inst.model_dump(exclude={"password", "account_key", "api_key"})
                )
            else:
                # Regular class
                instances_data.append(
                    {
                        k: v
                        for k, v in inst.__dict__.items()
                        if not k.startswith("_")
                        and k not in {"password", "account_key", "api_key"}
                    }
                )

        return {
            "total_instances": len(cls._multiton_instances),
            "instances": instances_data,
        }

    @classmethod
    def clear_pool(cls):
        """Clear all cached instances"""
        if hasattr(cls, "_multiton_instances"):
            cls._multiton_instances.clear()

    @classmethod
    def get_all_instances(cls: type[T]) -> list[T]:
        """Get all cached instances"""
        if not hasattr(cls, "_multiton_instances"):
            return []
        return list(cls._multiton_instances.values())

    @staticmethod
    def as_decorator(
        include: list[str] | None = None, exclude: list[str] | None = None
    ):
        """
        Use MultitonMixin as a decorator for any class.

        Args:
            include: Specific fields to include in cache key
            exclude: Fields to exclude from cache key

        Usage:
            @MultitonMixin.as_decorator(include=['host', 'port'])
            class DatabaseConnection:
                def __init__(self, host, port, username, password):
                    self.host = host
                    self.port = port
                    self.username = username
                    self.password = password
        """

        def decorator(cls: type[T]) -> type[T]:
            original_init = cls.__init__
            original_new = cls.__new__

            cls._multiton_instances = {}
            cls._multiton_key_fields = include
            cls._multiton_exclude_fields = exclude

            def _get_cache_key(self) -> str:
                if include:
                    key_data = {k: getattr(self, k) for k in include}
                else:
                    exclude_set = set(exclude or [])
                    exclude_set.update(k for k in self.__dict__ if k.startswith("_"))
                    key_data = {
                        k: v for k, v in self.__dict__.items() if k not in exclude_set
                    }
                key_string = json.dumps(key_data, sort_keys=True, default=str)
                return hashlib.md5(key_string.encode()).hexdigest()

            cls._get_cache_key = _get_cache_key

            def __new__(cls_inner, *args, **kwargs):
                if original_new is object.__new__:
                    return object.__new__(cls_inner)
                return original_new(cls_inner)

            @wraps(original_init)
            def __init__(self, *args, **kwargs):
                # Skip re-initialization if this object is already the cached instance.
                if getattr(self, "_multiton_initialized", False):
                    return

                original_init(self, *args, **kwargs)
                key = self._get_cache_key()

                if key in cls._multiton_instances:
                    # Share the cached instance's __dict__ so all variables
                    # pointing to this key refer to the exact same state.
                    self.__dict__ = cls._multiton_instances[key].__dict__
                else:
                    self._multiton_initialized = True
                    cls._multiton_instances[key] = self

            cls.__new__ = __new__
            cls.__init__ = __init__

            # Add helper methods
            @classmethod
            def get_or_create(cls_inner: type[T], *args, **kwargs) -> T:
                """Get existing instance or create new one"""
                # Create temporary instance
                temp = cls_inner(*args, **kwargs)
                key = temp._get_cache_key()

                if key in cls_inner._multiton_instances:
                    return cls_inner._multiton_instances[key]

                return temp

            @classmethod
            def get_pool_stats(cls_inner) -> dict[str, Any]:
                """Get pool statistics"""
                instances_data = []
                for inst in cls_inner._multiton_instances.values():
                    inst_data = {
                        k: v
                        for k, v in inst.__dict__.items()
                        if not k.startswith("_")
                        and k not in {"password", "account_key"}
                    }
                    instances_data.append(inst_data)

                return {
                    "class": cls_inner.__name__,
                    "total_instances": len(cls_inner._multiton_instances),
                    "instances": instances_data,
                }

            @classmethod
            def clear_pool(cls_inner):
                """Clear instance pool"""
                cls_inner._multiton_instances.clear()

            @classmethod
            def get_all_instances(cls_inner: type[T]) -> list[T]:
                """Get all cached instances"""
                return list(cls_inner._multiton_instances.values())

            cls.get_or_create = get_or_create
            cls.get_pool_stats = get_pool_stats
            cls.clear_pool = clear_pool
            cls.get_all_instances = get_all_instances

            return cls

        return decorator


# Alias for convenience
multiton = MultitonMixin.as_decorator

# Example 1: Include specific fields
# @multiton(include=['host', 'port', 'database'])
# class DatabaseConnection:
