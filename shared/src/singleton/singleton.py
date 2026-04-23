import threading


class SingletonMeta(type):
    """
    Singleton metaclass that ensures:
    - Only one instance of each class is created.
    - __init__() is called only once.
    """
    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            # Check if instance exists
            if cls not in cls._instances:
                # Create new instance and call __init__()
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
            else:
                # Skip __init__() call if already initialized
                if args or kwargs:
                    raise RuntimeError(
                        f"{cls.__name__} already initialized. "
                        "Do not pass arguments again."
                    )
        return cls._instances[cls]
