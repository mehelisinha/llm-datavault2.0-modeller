from dataclasses import dataclass

GREEN = "\033[32m"
RESET = "\033[0m"


@dataclass(frozen=True)
class DLTGenericOperations:
    dropping: str = "💣"
    alter: str = "🧩"
    change_owner: str = "🧑‍💼"
    grant: str = "🔑"


@dataclass(frozen=True)
class DatabaseOperations(DLTGenericOperations):
    creating: str = "🏛️"


@dataclass(frozen=True)
class TableOperations(DLTGenericOperations):
    creating: str = "🗄️"


@dataclass(frozen=True)
class TableDataOperations:
    add_new_data: str = "➕"
    merge: str = "🔀"
    update: str = "♻️"
    delete: str = "🗑️"
    clean: str = "🧹"
    overwrite: str = "🔥📝"
    write: str = "📝"


@dataclass(frozen=True)
class TableState:
    exists: str = f"{GREEN}✔{RESET}"
    not_exists: str = "⚠️"
    internal: str = "🏠"
    external: str = "🌐"


@dataclass(frozen=True)
class GenericActions:
    check: str = "🔍"
    done: str = "🎯"
    fetch: str = "📄"
    info: str = "ℹ️"
    creating: str = "🆕"
    optimize: str = "⚡"


@dataclass(frozen=True)
class TableEmojis:
    database_operations: DatabaseOperations = DatabaseOperations()
    table_operations: TableOperations = TableOperations()
    data_operations: TableDataOperations = TableDataOperations()
    state: TableState = TableState()
    actions: GenericActions = GenericActions()
