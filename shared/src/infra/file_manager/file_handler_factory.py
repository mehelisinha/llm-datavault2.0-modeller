from shared.src.infra.file_manager.concrete.file_handler import FileHandler
from shared.src.infra.file_manager.concrete.json_handler import JsonHandler
from shared.src.infra.file_manager.concrete.text_handler import TextHandler
from shared.src.infra.file_manager.concrete.yml_handler import YamlHandler


class FileHandlerFactory:
    _handlers = {
        "yml": YamlHandler(),
        "yaml": YamlHandler(),
        "json": JsonHandler(),
        "sql": TextHandler(),
        "css": TextHandler(),
        "txt": TextHandler(),
    }

    @classmethod
    def get(cls, extension: str) -> FileHandler:
        handler = cls._handlers.get(extension.lower())
        if not handler:
            raise ValueError(f"No handler for extension: {extension}")
        return handler
