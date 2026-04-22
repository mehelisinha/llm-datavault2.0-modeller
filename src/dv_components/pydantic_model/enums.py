from enum import StrEnum


class DBTModelNames(StrEnum):
    HUB = "hub"
    LINK = "link"
    SATELLITE = "satellite"
    EFF_SAT = "eff_sat"
    STAGING = "staging"
    RAW_VAULT = "raw_vault"
    BUSINESS_VAULT = "business_vault"
    PROJECT = "dbt_project"
    SOURCES = "sources"
    PACKAGES = "packages"
    PROFILES = "profiles"


class DbtPaths(StrEnum):
    MODELS = "models"
    MACROS = "macros"
    STAGING = f"models/{DBTModelNames.STAGING}"
    RAW_VAULT = f"models/{DBTModelNames.RAW_VAULT}"
    HUBS = f"models/{DBTModelNames.RAW_VAULT}/hubs"
    LINKS = f"models/{DBTModelNames.RAW_VAULT}/links"
    SATELLITES = f"models/{DBTModelNames.RAW_VAULT}/satellites"
    EFF_SATS = f"models/{DBTModelNames.RAW_VAULT}/eff_sats"
    BUSINESS_VAULTS = f"models/{DBTModelNames.BUSINESS_VAULT}"
    SNAPSHOTS = "snapshots"
    SEEDS = "seeds"
    TESTS = "tests"
    ANALYSES = "analyses"
    TARGET = "target"
    DBT_PACKAGES = "dbt_packages"
