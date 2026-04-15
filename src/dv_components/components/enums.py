from enum import Enum


class DvModelNames(Enum):
    HUB = "hub"
    LINK = "link"
    T_LINKS ="t_link"
    SATELLITE = "sat"
    EFF_SATELLITE = "eff_sat"


class OutputFormat(Enum):
    SQL = "sql"
    YAML = "yml"
