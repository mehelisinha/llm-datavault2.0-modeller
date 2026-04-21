"""
DbtRunner — thin wrapper around dbt's programmatic API for running a dbt project.

Uses ``dbt.cli.main.dbtRunner`` so dbt runs in-process (no subprocess overhead),
which is the recommended approach for Databricks notebooks and orchestrators.
"""

from __future__ import annotations

import subprocess
import traceback
from logging import Logger
from pathlib import Path
from typing import Literal

from dbt.cli.main import dbtRunner, dbtRunnerResult
from dbt_common.events.base_types import EventMsg

from shared.logger.default_logger import default_logger


class DbtDbRunner:
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
        if profiles_dir:
            self.profiles_dir = Path(profiles_dir)
        else:
            self.profiles_dir = Path.home() / ".dbt"
            self.profiles_dir.mkdir(exist_ok=True)  # create it if missing
        self.logger = logger
        self._runner = dbtRunner(callbacks=[self.print_version_callback])
        self.logger.debug(
            f"Initialized DbtRunner with project_path='{self.project_path}', profiles_dir='{self.profiles_dir}'"
        )

    # ------------------------------------------------------------------
    # Public commands
    # ------------------------------------------------------------------

    def deps(self, caller: Literal["dbt", "subprocess"] = "dbt") -> dbtRunnerResult:
        """Install dbt package dependencies (e.g. automate_dv)."""
        return self._invoke(["deps"], caller=caller)

    def compile(
        self, select: str | None = None, caller: Literal["dbt", "subprocess"] = "dbt"
    ) -> dbtRunnerResult:
        """Compile models without executing them."""
        return self._invoke(["compile"], select=select, caller=caller)

    def debug(self, caller: Literal["dbt", "subprocess"] = "dbt") -> dbtRunnerResult:
        """Compile models without executing them."""
        return self._invoke(["run", "--debug", "--log-level", "debug"], caller=caller)

    def run(
        self, select: str | None = None, caller: Literal["dbt", "subprocess"] = "dbt"
    ) -> dbtRunnerResult:
        """Run dbt models. Pass a selector to target a subset."""
        return self._invoke(["run"], select=select, caller=caller)

    def test(
        self, select: str | None = None, caller: Literal["dbt", "subprocess"] = "dbt"
    ) -> dbtRunnerResult:
        """Run dbt tests."""
        return self._invoke(["test"], select=select, caller=caller)

    def run_layer(
        self, tag: str, caller: Literal["dbt", "subprocess"] = "dbt"
    ) -> dbtRunnerResult:
        """Run all models tagged with ``tag`` (e.g. 'staging', 'raw_vault')."""
        return self.run(select=f"tag:{tag}", caller=caller)

    def run_all_layers(self, caller: Literal["dbt", "subprocess"] = "dbt") -> None:
        """Run the full pipeline: deps → staging → raw_vault."""
        self.logger.info("Running full dbt pipeline: deps → staging → raw_vault")
        self.logger.info("Installing dependencies...")
        self.deps(caller=caller)
        self.logger.info("Running staging layer...")
        self.run_layer("staging", caller=caller)
        self.logger.info("Running raw_vault layer...")
        self.run_layer("raw_vault", caller=caller)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    @staticmethod
    def print_version_callback(event: EventMsg):
        if event.info.name == "MainReportVersion":
            print(f"Rrunning dbt{event.data.version}")

    def _base_args(self) -> list[str]:
        args = [
            "--project-dir",
            str(self.project_path),
        ]
        if self.profiles_dir and self.profiles_dir.exists():
            self.logger.debug(f"Using profiles directory: {self.profiles_dir}")
            args += ["--profiles-dir", str(self.profiles_dir)]
        else:
            self.logger.warning(
                f"Profiles directory '{self.profiles_dir}'"
                "dbt will use cluster connection"
            )
        return args

    def _invoke_dbt(
        self, args: list[str], select: str | None = None
    ) -> dbtRunnerResult:
        full_args = args + self._base_args() + ["--no-partial-parse", "--fail-fast"]
        if select:
            full_args += ["--select", select]

        self.logger.info(f"Running dbt with args: dbt {' '.join(full_args)}")
        result: dbtRunnerResult = self._runner.invoke(full_args)
        self._log_result(result)
        return result

    # def _invoke_subprocess(
    #     self, args: list[str], select: str | None = None
    # ) -> subprocess.CompletedProcess:
    #     full_args = (
    #         ["dbt"] + args + self._base_args() + ["--no-partial-parse", "--fail-fast"]
    #     )
    #     if select:
    #         full_args += ["--select", select]

    #     self.logger.info(f"[_invoke] Running dbt with args: {' '.join(full_args)}")

    #     result = subprocess.run(
    #         full_args,
    #         capture_output=True,
    #         text=True,
    #         timeout=600,
    #     )
    #     self.logger.info(result.stdout)
    #     if result.returncode != 0:
    #         self.logger.error(result.stderr)
    #         raise RuntimeError(f"dbt failed with return code {result.returncode}")
    #     return result

    def _invoke_subprocess(self, args: list[str], select: str | None = None) -> None:
        full_args = (
            ["dbt"] + args + self._base_args() + ["--no-partial-parse", "--fail-fast"]
        )
        if select:
            full_args += ["--select", select]

        self.logger.info(f"Running dbt with args: {' '.join(full_args)}")

        process = subprocess.Popen(
            full_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # merge stderr into stdout
            text=True,
        )

        for line in process.stdout:
            self.logger.info(line.rstrip())

        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"dbt failed with return code {process.returncode}")

    def _invoke(
        self,
        args: list[str],
        select: str | None = None,
        caller: Literal["dbt", "subprocess"] = "dbt",
    ) -> subprocess.CompletedProcess | dbtRunnerResult:
        if caller == "dbt":
            return self._invoke_dbt(args, select=select)
        elif caller == "subprocess":
            return self._invoke_subprocess(args, select=select)
        else:
            raise ValueError(f"Invalid caller: {caller}")

    def _log_result(self, result: dbtRunnerResult) -> None:
        if result.exception:
            self.logger.error(f"dbt raised an exception: {result.exception}")
            self.logger.error(f"Exception type: {type(result.exception)}")
            self.logger.error(
                f"Traceback: {''.join(traceback.format_exception(type(result.exception), result.exception, result.exception.__traceback__))}"
            )
            raise result.exception

        nodes = getattr(result.result, "results", None) or []
        for r in nodes:
            name = getattr(getattr(r, "node", None), "name", str(r))
            status = str(getattr(r, "status", "unknown"))
            if status in ("error", "fail"):
                self.logger.error(f"  ✗ {name}: {status}")
            elif status == "warn":
                self.logger.warning(f"  ⚠ {name}: {status}")
            else:
                self.logger.info(f"  ✓ {name}: {status}")

        if not result.success:
            self.logger.error("dbt command finished with failures.")
            raise RuntimeError("dbt command failed. Check logs for details.")
        else:
            self.logger.info("dbt command completed successfully.")

