from logging import Logger
from pathlib import Path
from typing import Any

import yaml

from shared.infra.file_manager.concrete.file_handler import FileHandler
from shared.logger.default_logger import default_logger


def _make_jinja_dumper() -> type:
    """Return a yaml.Dumper subclass that double-quotes Jinja expressions."""

    class JinjaDumper(yaml.Dumper):
        pass

    def _jinja_str_representer(dumper: yaml.Dumper, value: str) -> yaml.ScalarNode:
        if "{{" in value and "}}" in value:
            return dumper.represent_scalar("tag:yaml.org,2002:str", value, style='"')
        return dumper.represent_scalar("tag:yaml.org,2002:str", value)

    JinjaDumper.add_representer(str, _jinja_str_representer)
    return JinjaDumper


class YamlHandler(FileHandler):
    @classmethod
    def read(cls, file_path: Path):
        cls.ensure_exists(file_path)
        with file_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @classmethod
    def _write(cls, file_path: Path, content: Any):
        with file_path.open("w", encoding="utf-8") as f:
            if isinstance(content, str):
                # Content is already rendered YAML; write as-is to avoid double-dumping.
                f.write(content)
                return
            yaml.safe_dump(content, f, sort_keys=False, default_flow_style=False)

    @classmethod
    def generate(
        cls, dic_content: dict[str, Any], logger: Logger = default_logger
    ) -> str:
        """Return the YAML content as a string."""
        yaml_str = yaml.dump(
            dic_content,
            sort_keys=False,
            default_flow_style=False,
        )
        logger.debug(f"Generated :\n{yaml_str}")
        return yaml_str

    @classmethod
    def generate_with_jinja(
        cls, dic_content: dict[str, Any], logger: Logger = default_logger
    ) -> str:
        """Return the YAML content as a string, double-quoting Jinja expressions
        so that inner single quotes (e.g. env_var('VAR')) are preserved verbatim."""
        yaml_str = yaml.dump(
            dic_content,
            Dumper=_make_jinja_dumper(),
            sort_keys=False,
            default_flow_style=False,
        )
        logger.debug(f"Generated :\n{yaml_str}")
        return yaml_str

    @classmethod
    def to_kebab_case(cls, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k.replace("_", "-"): cls.to_kebab_case(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [cls.to_kebab_case(i) for i in obj]
        return obj
