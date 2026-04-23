from pathlib import Path
from typing import Any, ClassVar, Dict, List

from pydantic import BaseModel, Field, computed_field

from shared.src.config_io.worckspace import (
    EdhVersion,
    EnvType,
    NetType,
    WorkspaceConfigType,
)


class StaticConfigurations(BaseModel):
    """
    Static configuration registry for config files and workspace mappings.
    """

    # -----------------------
    # Base paths
    # -----------------------
    repo_path_config_files: Path = Path("devops/config/files")
    source_folder_non_env: str = "shared"
    path_config_files: Path = Path("dbfs:/mnt/config_files")
    dynamic_config_dir: Path = Path("shared")

    # -----------------------
    # File names
    # -----------------------
    storage_file_name: str = "storage.yml"
    app_conn_file_name: str = "app_conn.yml"

    # -----------------------
    # Environment
    # -----------------------
    envs: List[EnvType] = Field(
        default_factory=lambda: [EnvType.DEV, EnvType.QAS, EnvType.RUN]
    )

    # -----------------------
    # Workspace URLs Mapping
    # -----------------------
    @computed_field
    @property
    def workspace_url_mapping(self) -> Dict[str, WorkspaceConfigType]:
        return {
            # new workspace
            "96acdf6191bea033df96cdd8d926dc3f466684642b2fc0894d9dea2bf54f783d": {
                "env": EnvType.DEV,
                "net_type": NetType.REG,
                "edh_version": EdhVersion.v2,
            },
            "091cfb4217bc6520bf912eae65f5608c8a46e6933d96e132396bf4ce76fbedbb": {
                "env": EnvType.DEV,
                "net_type": NetType.UNREG,
                "edh_version": EdhVersion.v2,
            },
            "77cc6a8b85013d0e8f7280ff1e522553e9f4a6881936418c27f893b9cb17acfe": {
                "env": EnvType.QAS,
                "net_type": NetType.REG,
                "edh_version": EdhVersion.v2,
            },
            "8e25106d85e2d548d3ad55ba496266e0e7730337b2fa848c2e54d4e9d15ee142": {
                "env": EnvType.QAS,
                "net_type": NetType.UNREG,
                "edh_version": EdhVersion.v2,
            },
            "a669007f3ed7190c02840481acf5b96ab30a9f3b48fec3046287a5116a5442d8": {
                "env": EnvType.RUN,
                "net_type": NetType.REG,
                "edh_version": EdhVersion.v2,
            },
            "8b8bb231962a7bc8705c1815c51cfc0ed04eb317bf7618e4e4796331bb00f662": {
                "env": EnvType.RUN,
                "net_type": NetType.UNREG,
                "edh_version": EdhVersion.v2,
            },
            # old worspace
            "9b9187528339219b10ec58ca8df35251927f65712832ee05d77f69660343e121": {
                "env": EnvType.DEV,
                "net_type": NetType.REG,
                "edh_version": EdhVersion.v1,
            },
            "51a917063ae3cd18cc7987035fb713d406dace97772bef1a24b20c84f386f497": {
                "env": EnvType.DEV,
                "net_type": NetType.UNREG,
                "edh_version": EdhVersion.v1,
            },
            "5704192a833f7558e2dcda1a1dffdd424f7f77c247da58f69c3e14260f9ed48d": {
                "env": EnvType.QAS,
                "net_type": NetType.REG,
                "edh_version": EdhVersion.v1,
            },
            "037d8b7937a7184bdd9caffc09986e8ed83d90c9a2168f98b34d51fcbe665183": {
                "env": EnvType.QAS,
                "net_type": NetType.UNREG,
                "edh_version": EdhVersion.v1,
            },
            "55a3e0e2b5eb90642c14e55dedf8f7fb7f498bf8202a066716cc7f124b9d14ae": {
                "env": EnvType.RUN,
                "net_type": NetType.REG,
                "edh_version": EdhVersion.v1,
            },
            "54952d43a258e36827401cfb7db0c2b3d3dbe54752c28a2773f2d749a2fbde7d": {
                "env": EnvType.RUN,
                "net_type": NetType.UNREG,
                "edh_version": EdhVersion.v1,
            },
        }

    # -----------------------
    # Singleton
    # -----------------------
    _instance: ClassVar["StaticConfigurations | None"] = None

    def __new__(cls, *args: Any, **kwargs: Any):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    model_config = {
        "frozen": True,
        "extra": "forbid",
    }
