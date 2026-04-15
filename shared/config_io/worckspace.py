from enum import Enum
from pathlib import Path
from typing import Literal, Union

from typing_extensions import TypedDict

PathLike = Union[str, Path]


class EnvType(str, Enum):
    DEV = "dev"
    QAS = "qas"
    RUN = "run"


class EdhVersion(str, Enum):
    v1 = "is01"
    v2 = "is02"


NetTypeDataType = Literal["regulated", "unregulated"]


class NetType(str, Enum):
    REG = "regulated"
    UNREG = "unregulated"

    @property
    def net_code(self) -> str:
        """Return the associated short code for each net type."""
        match self:
            case NetType.REG:
                return "en"
            case NetType.UNREG:
                return "unreg"
        raise ValueError("Invalid NetType")

    @property
    def admin_sp_net_value(self) -> str:
        """Return the associated short code for each net type."""
        match self:
            case NetType.REG:
                return "-en"
            case NetType.UNREG:
                return "unreg"
        raise ValueError("Invalid NetType")

    @classmethod
    def from_string(cls, value: str) -> "NetType":
        """Convert a string to the corresponding NetType enum."""
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Unknown net type: {value}")


class WorkspaceConfigType(TypedDict, total=False):
    edh_version: EdhVersion
    env: EnvType
    net_type: NetType
