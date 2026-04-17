from typing import Any


class YmlHelper:
    @classmethod
    def to_kebab_case(cls, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k.replace("_", "-"): cls.to_kebab_case(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [cls.to_kebab_case(i) for i in obj]
        return obj
