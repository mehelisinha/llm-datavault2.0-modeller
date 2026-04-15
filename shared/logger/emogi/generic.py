from dataclasses import dataclass

# ========== Terminal Colors ==========
GREEN = "\033[32m"
RESET = "\033[0m"


# ============================================================
# 🛑 Error and Alert Emojis
# ============================================================
@dataclass(frozen=True)
class AlertEmojis:
    """Emojis for logging errors, warnings, and critical issues."""

    error_general: str = "❌"  # General or unexpected error
    warning: str = "⚠️"  # Recoverable warning
    error_critical: str = "💥"  # System-level critical failure
    stop: str = "🛑"  # Expected or forced stop condition
    attention: str = "❗"  # marks something that isn’t an necessary an error but needs special attention


# ============================================================
# 🚀 Lifecycle / Execution Emojis
# ============================================================
@dataclass(frozen=True)
class LifecycleEmojis:
    """Emojis representing process and execution lifecycle events."""

    start: str = "🚀"  # Starting a process or pipeline
    setup: str = "🔧"  # Initialization or setup phase
    build_component: str = "🧩"  # Building or connecting a component
    refresh: str = "♻️"  # Refreshing, reloading, or reprocessing


# ============================================================
# 🚀 Pipeline Emojis
# ============================================================
@dataclass(frozen=True)
class PipelineEmojis:
    """Emojis representing process and execution lifecycle events."""

    start: str = "🚀"  # Starting a process or pipeline
    setup_table: str = "🔧🗄️"
    setup_table: str = "🔧🧱"
    build_plan: str = "📐"  # Building or connecting a component
    execute_plan: str = "⚙️"  # Refreshing, reloading, or reprocessing
    register_checkpoint: str = "🧱"
    completion: str = "🎉"
    refresh: str = "♻️"  # Refreshing, reloading, or reprocessing
    fetched_config: str = "📄"
    info: str = "ℹ️"  # General information


# ============================================================
# 🎯 Status and Result Emojis
# ============================================================
@dataclass(frozen=True)
class StatusEmojis:
    """Emojis indicating progress, completion, or success states."""

    success: str = "✅"  # Task or process completed successfully
    success_goal: str = "🎯"  # Target achieved / milestone hit
    in_progress: str = "⏳"  # Task currently in progress
    small_check: str = f"{GREEN}✔{RESET}"  # Small confirmation / step complete


# ============================================================
# ℹ️ Information and Context Emojis
# ============================================================
@dataclass(frozen=True)
class InfoEmojis:
    """Emojis for informational or contextual logging messages."""

    info: str = "ℹ️"  # General information
    info_diamond = "🔹"  # Blue diamond sign for info
    fetch: str = "📄"  # Reading or fetching data
    search: str = "🔍"  # Searching / lookup operation
    optimize: str = "⚡"  # Optimization or performance-related action
    attention: str = "💡"  # Special info


# ============================================================
# 🗂️ Data Operation Emojis
# ============================================================
@dataclass(frozen=True)
class DataEmojis:
    """Emojis representing data operations and transformations."""

    add: str = "➕"  # Adding new data or entity
    delete: str = "🗑️"  # Deleting or cleaning up data
    create: str = "🆕"  # Creating a new resource
    update: str = "🔄"  # Updating existing data
    merge: str = "🔀"  # Merging or combining data/config
    transfer: str = "📦"  # Moving / copying data between systems
    transform: str = "🧩"  # Transformingdata
    optimize: str = "⚡"  # Optimize


# ============================================================
# 🧭 Aggregated Access Point
# ============================================================
@dataclass(frozen=True)
class LogEmojis:
    """
    Centralized access point for all emoji categories used in logging.

    Usage:
        from src.common.logger.emojis import LogEmojis

        logger.info(f"{LogEmojis.lifecycle.start} Starting pipeline...")
        logger.warning(f"{LogEmojis.errors.warning} Missing config key.")
        logger.info(f"{LogEmojis.status.success_goal} Pipeline finished successfully!")
    """

    lifecycle: LifecycleEmojis = LifecycleEmojis()
    status: StatusEmojis = StatusEmojis()
    info: InfoEmojis = InfoEmojis()
    data: DataEmojis = DataEmojis()
    errors: AlertEmojis = AlertEmojis()
    pipeline: PipelineEmojis = PipelineEmojis()
