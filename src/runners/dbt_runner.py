"""
DbtRunner — thin wrapper around dbt's programmatic API for running a dbt project.

Uses ``dbt.cli.main.dbtRunner`` so dbt runs in-process (no subprocess overhead),
which is the recommended approach for Databricks notebooks and orchestrators.
"""

from __future__ import annotations

from logging import Logger
from pathlib import Path

from dbt.cli.main import dbtRunner, dbtRunnerResult

from shared.logger.default_logger import default_logger


class DbtRunner:
    """
    Runs dbt commands against a generated dbt project directory.

    Args:
        project_path:  Path to the dbt project root (contains dbt_project.yml).
        profiles_dir:  Path to the directory holding profiles.yml.
                       Defaults to ``~/.dbt``.
        logger:        Optional logger instance.

    Usage::

        runner = DbtRunner(project_path="/dbt/IEC61968_CIM")
        runner.deps()
        runner.run_layer("staging")
        runner.run_layer("raw_vault")
        runner.test()
    """

    def __init__(
        self,
        project_path: str | Path,
        profiles_dir: str | Path | None = None,
        logger: Logger = default_logger,
    ):
        self.project_path = Path(project_path)
        self.profiles_dir = Path(profiles_dir) if profiles_dir else Path.home() / ".dbt"
        self.logger = logger
        self._runner = dbtRunner()

    # ------------------------------------------------------------------
    # Public commands
    # ------------------------------------------------------------------

    def deps(self) -> dbtRunnerResult:
        """Install dbt package dependencies (e.g. automate_dv)."""
        return self._invoke(["deps"])

    def compile(self, select: str | None = None) -> dbtRunnerResult:
        """Compile models without executing them."""
        return self._invoke(["compile"], select=select)

    def run(self, select: str | None = None) -> dbtRunnerResult:
        """Run dbt models. Pass a selector to target a subset."""
        return self._invoke(["run"], select=select)

    def test(self, select: str | None = None) -> dbtRunnerResult:
        """Run dbt tests."""
        return self._invoke(["test"], select=select)

    def run_layer(self, tag: str) -> dbtRunnerResult:
        """Run all models tagged with ``tag`` (e.g. 'staging', 'raw_vault')."""
        return self.run(select=f"tag:{tag}")

    def run_all_layers(self) -> None:
        """Run the full pipeline: deps → staging → raw_vault."""
        self.deps()
        self.run_layer("staging")
        self.run_layer("raw_vault")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _base_args(self) -> list[str]:
        return [
            "--project-dir", str(self.project_path),
            "--profiles-dir", str(self.profiles_dir),
        ]

    def _invoke(self, args: list[str], select: str | None = None) -> dbtRunnerResult:
        full_args = args + self._base_args()
        if select:
            full_args += ["--select", select]

        self.logger.info(f"dbt {' '.join(full_args)}")
        result: dbtRunnerResult = self._runner.invoke(full_args)
        self._log_result(result)
        return result

    def _log_result(self, result: dbtRunnerResult) -> None:
        if result.exception:
            self.logger.error(f"dbt raised an exception: {result.exception}")
            return

        nodes = getattr(result.result, "results", None) or []
        for r in nodes:
            name   = getattr(getattr(r, "node", None), "name", str(r))
            status = str(getattr(r, "status", "unknown"))
            if status in ("error", "fail"):
                self.logger.error(f"  ✗ {name}: {status}")
            elif status == "warn":
                self.logger.warning(f"  ⚠ {name}: {status}")
            else:
                self.logger.info(f"  ✓ {name}: {status}")

        if not result.success:
            self.logger.error("dbt command finished with failures.")
        else:
            self.logger.info("dbt command completed successfully.")
