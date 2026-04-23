"""dbt runner strategies for programmatic and subprocess execution."""

from __future__ import annotations

import shlex
import subprocess
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import Any, Literal

from dbt.cli.main import dbtRunner, dbtRunnerResult
from dbt_common.events.base_types import EventMsg

from shared.src.logger.default_logger import default_logger

RunnerType = Literal["dbt", "subprocess"]


@dataclass
class DbtCommandResult:
    success: bool
    command: str
    return_code: int
    raw_result: Any | None = None


class BaseDbtRunner(ABC):
    """Shared interface for dbt execution strategies."""

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
            self.profiles_dir.mkdir(exist_ok=True)
        self.logger = logger

    def deps(self) -> DbtCommandResult:
        return self._invoke(["deps"])

    def compile(self, select: str | None = None) -> DbtCommandResult:
        return self._invoke(["compile"], select=select)

    def debug(self) -> DbtCommandResult:
        return self._invoke(["debug", "--log-level", "debug"])

    def run(self, select: str | None = None) -> DbtCommandResult:
        return self._invoke(["run"], select=select)

    def test(self, select: str | None = None) -> DbtCommandResult:
        return self._invoke(["test"], select=select)

    def run_layer(self, tag: str) -> DbtCommandResult:
        return self.run(select=f"tag:{tag}")

    def run_all_layers(self) -> None:
        self.logger.info("Running full dbt pipeline: deps -> staging -> raw_vault")
        self.logger.info("Installing dependencies...")
        self.deps()
        self.logger.info("Running staging layer...")
        self.run_layer("staging")
        self.logger.info("Running raw_vault layer...")
        self.run_layer("raw_vault")

    def _base_args(self) -> list[str]:
        args = ["--project-dir", str(self.project_path)]
        if self.profiles_dir and self.profiles_dir.exists():
            self.logger.debug(f"Using profiles directory: {self.profiles_dir}")
            args += ["--profiles-dir", str(self.profiles_dir)]
        else:
            self.logger.warning(
                f"Profiles directory '{self.profiles_dir}' not found; dbt will use default resolution."
            )
        return args

    def _build_args(self, args: list[str], select: str | None = None) -> list[str]:
        full_args = args + self._base_args() + ["--no-partial-parse", "--fail-fast"]
        if select:
            full_args += ["--select", select]
        return full_args

    @abstractmethod
    def _invoke(self, args: list[str], select: str | None = None) -> DbtCommandResult:
        """Execute a dbt command."""


class DbtProgrammaticRunner(BaseDbtRunner):
    """Run dbt in-process using dbtRunner."""

    def __init__(
        self,
        project_path: str | Path,
        profiles_dir: str | Path | None = None,
        logger: Logger = default_logger,
    ):
        super().__init__(
            project_path=project_path, profiles_dir=profiles_dir, logger=logger
        )
        self._runner = dbtRunner(callbacks=[self.print_version_callback])
        self.logger.debug(
            f"Initialized DbtProgrammaticRunner with project_path='{self.project_path}', profiles_dir='{self.profiles_dir}'"
        )

    @staticmethod
    def print_version_callback(event: EventMsg) -> None:
        if event.info.name == "MainReportVersion":
            print(f"Running dbt {event.data.version}")

    def _invoke(self, args: list[str], select: str | None = None) -> DbtCommandResult:
        full_args = self._build_args(args, select=select)
        command = f"dbt {' '.join(full_args)}"
        self.logger.info(f"Running dbt with args: {command}")
        result: dbtRunnerResult = self._runner.invoke(full_args)
        self._log_result(result)
        return DbtCommandResult(
            success=result.success,
            command=command,
            return_code=0 if result.success else 1,
            raw_result=result,
        )

    def _log_result(self, result: dbtRunnerResult) -> None:
        if result.exception:
            self.logger.error(f"dbt raised an exception: {result.exception}")
            self.logger.error(f"Exception type: {type(result.exception)}")
            self.logger.error(
                "Traceback: "
                + "".join(
                    traceback.format_exception(
                        type(result.exception),
                        result.exception,
                        result.exception.__traceback__,
                    )
                )
            )
            raise result.exception

        nodes = getattr(result.result, "results", None) or []
        for node_result in nodes:
            name = getattr(getattr(node_result, "node", None), "name", str(node_result))
            status = str(getattr(node_result, "status", "unknown"))
            if status in ("error", "fail"):
                self.logger.error(f"  x {name}: {status}")
            elif status == "warn":
                self.logger.warning(f"  ! {name}: {status}")
            else:
                self.logger.info(f"  ok {name}: {status}")

        if not result.success:
            self.logger.error("dbt command finished with failures.")
            raise RuntimeError("dbt command failed. Check logs for details.")

        self.logger.info("dbt command completed successfully.")


class DbtSubprocessRunner(BaseDbtRunner):
    """Run dbt via shell commands in a subprocess with timeout support."""

    def __init__(
        self,
        project_path: str | Path,
        profiles_dir: str | Path | None = None,
        logger: Logger = default_logger,
        timeout_seconds: int = 600,
        shell_executable: str = "/bin/zsh",
    ):
        super().__init__(
            project_path=project_path, profiles_dir=profiles_dir, logger=logger
        )
        self.timeout_seconds = timeout_seconds
        self.shell_executable = shell_executable
        self.logger.debug(
            f"Initialized DbtSubprocessRunner with project_path='{self.project_path}', profiles_dir='{self.profiles_dir}', timeout_seconds={self.timeout_seconds}"
        )

    def _invoke(self, args: list[str], select: str | None = None) -> DbtCommandResult:
        full_args = ["dbt", *self._build_args(args, select=select)]
        command = " ".join(shlex.quote(arg) for arg in full_args)
        self.logger.info(f"Running dbt shell command: {command}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project_path),
                executable=self.shell_executable,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            self.logger.error(
                f"dbt command timed out after {self.timeout_seconds} seconds: {command}"
            )
            raise TimeoutError(
                f"dbt command timed out after {self.timeout_seconds} seconds: {command}"
            ) from exc

        if result.stdout:
            for line in result.stdout.splitlines():
                self.logger.info(line)
        if result.stderr:
            for line in result.stderr.splitlines():
                self.logger.error(line)

        if result.returncode != 0:
            raise RuntimeError(
                f"dbt failed with return code {result.returncode}: {command}"
            )

        self.logger.info("dbt command completed successfully.")
        return DbtCommandResult(
            success=True,
            command=command,
            return_code=result.returncode,
            raw_result=result,
        )


class DbtRunnerFactory:
    """Factory for dbt runner strategies."""

    @staticmethod
    def create(
        runner_type: RunnerType,
        project_path: str | Path,
        profiles_dir: str | Path | None = None,
        logger: Logger = default_logger,
        timeout_seconds: int = 600,
    ) -> BaseDbtRunner:
        if runner_type == "dbt":
            return DbtProgrammaticRunner(
                project_path=project_path,
                profiles_dir=profiles_dir,
                logger=logger,
            )
        if runner_type == "subprocess":
            return DbtSubprocessRunner(
                project_path=project_path,
                profiles_dir=profiles_dir,
                logger=logger,
                timeout_seconds=timeout_seconds,
            )
        raise ValueError(f"Invalid runner type: {runner_type}")


class DbtDbRunner:
    """Backward-compatible facade over the concrete dbt runners."""

    def __init__(
        self,
        project_path: str | Path,
        profiles_dir: str | Path | None = None,
        logger: Logger = default_logger,
        timeout_seconds: int = 600,
    ):
        self.project_path = Path(project_path)
        self.profiles_dir = Path(profiles_dir) if profiles_dir else None
        self.logger = logger
        self.timeout_seconds = timeout_seconds

    def _get_runner(self, caller: RunnerType) -> BaseDbtRunner:
        return DbtRunnerFactory.create(
            runner_type=caller,
            project_path=self.project_path,
            profiles_dir=self.profiles_dir,
            logger=self.logger,
            timeout_seconds=self.timeout_seconds,
        )

    def deps(self, caller: RunnerType = "dbt") -> DbtCommandResult:
        return self._get_runner(caller).deps()

    def compile(
        self,
        select: str | None = None,
        caller: RunnerType = "dbt",
    ) -> DbtCommandResult:
        return self._get_runner(caller).compile(select=select)

    def debug(self, caller: RunnerType = "dbt") -> DbtCommandResult:
        return self._get_runner(caller).debug()

    def run(
        self,
        select: str | None = None,
        caller: RunnerType = "dbt",
    ) -> DbtCommandResult:
        return self._get_runner(caller).run(select=select)

    def test(
        self,
        select: str | None = None,
        caller: RunnerType = "dbt",
    ) -> DbtCommandResult:
        return self._get_runner(caller).test(select=select)

    def run_layer(self, tag: str, caller: RunnerType = "dbt") -> DbtCommandResult:
        return self._get_runner(caller).run_layer(tag)

    def run_all_layers(self, caller: RunnerType = "dbt") -> None:
        self._get_runner(caller).run_all_layers()
