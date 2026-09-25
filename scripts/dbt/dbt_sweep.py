"""Run dbt stages over a set of projects and report pass rates (gaps 2 & 3).

For each project directory this runs the requested dbt stages
(``deps``/``parse``/``compile``/``run``/``test``) against the live warehouse, tees
each stage's log into the project's ``target/`` folder, and then parses
``target/run_results.json`` into pass counts via
:func:`dbt_builder.src.runners.dbt_results.pass_rates`. Across projects it reports:

* **compile-pass rate** (gap 3) — fraction of projects whose ``compile`` exited 0;
* **execution** (gap 2) — models built and data tests passed, from ``run``/``test``.

This is the *live* step: it needs a working dbt profile (Databricks OAuth) and
writes to the warehouse on ``run``. It does not fabricate anything — it only reads
back what dbt actually reported. Authentication and the decision to materialise
tables are the operator's; this script just orchestrates and summarises.

Examples
--------
    # Gap 3: compile-pass rate over every project under a root
    python scripts/dbt/dbt_sweep.py --projects-root C:/Users/me/dwa_build/projects \
        --stages deps,compile --profiles-dir C:/Users/me/.dbt --results-out sweep.json

    # Gap 2: build + test one project, capture execution pass counts
    python scripts/dbt/dbt_sweep.py --project output/iec_dv2 \
        --stages deps,run,test --profiles-dir C:/Users/me/.dbt --results-out exec.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dbt_builder.src.runners.dbt_results import pass_rates  # noqa: E402


def _find_dbt(explicit: str | None) -> str:
    """Resolve the dbt executable: explicit arg, then the repo venv, then PATH."""
    if explicit:
        return explicit
    venv = _REPO_ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
        "dbt.exe" if os.name == "nt" else "dbt"
    )
    if venv.exists():
        return str(venv)
    found = shutil.which("dbt")
    if not found:
        raise FileNotFoundError("dbt executable not found — pass --dbt <path>")
    return found


def _projects(args: argparse.Namespace) -> list[Path]:
    if args.project:
        return [Path(p) for p in args.project]
    root = Path(args.projects_root)
    # A dbt project is any dir with a dbt_project.yml.
    return sorted(p.parent for p in root.glob("*/dbt_project.yml"))


def _run_stage(dbt: str, stage: str, project: Path, env: dict[str, str]) -> int:
    """Run one dbt stage in ``project``; tee output to target/<stage>.log."""
    print(f"    $ dbt {stage}  (cwd={project.name})")
    proc = subprocess.run(
        [dbt, stage],
        cwd=str(project),
        env=env,
        capture_output=True,
        text=True,
    )
    log_dir = project / "target"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{stage}.log").write_text(
        (proc.stdout or "") + "\n----- STDERR -----\n" + (proc.stderr or ""),
        encoding="utf-8",
    )
    tail = (proc.stdout or "").strip().splitlines()[-1:] or ["(no output)"]
    print(f"      exit={proc.returncode}  {tail[0][:120]}")
    return proc.returncode


def sweep(args: argparse.Namespace) -> dict:
    dbt = _find_dbt(args.dbt)
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    env = dict(os.environ)
    if args.profiles_dir:
        env["DBT_PROFILES_DIR"] = args.profiles_dir

    projects = _projects(args)
    if not projects:
        raise SystemExit("no projects found (use --project or --projects-root)")

    per_project: list[dict] = []
    for project in projects:
        print(f"\n=== {project} ===")
        stage_exit: dict[str, int] = {}
        for stage in stages:
            stage_exit[stage] = _run_stage(dbt, stage, project, env)
        rr_path = project / "target" / "run_results.json"
        rates = (
            pass_rates(json.loads(rr_path.read_text(encoding="utf-8")))
            if rr_path.exists()
            else None
        )
        per_project.append(
            {
                "project": str(project),
                "stage_exit": stage_exit,
                "compile_ok": stage_exit.get("compile") == 0 if "compile" in stage_exit else None,
                "rates": rates,
            }
        )

    compiled = [p for p in per_project if p["compile_ok"] is not None]
    compile_pass_rate = (
        sum(1 for p in compiled if p["compile_ok"]) / len(compiled) if compiled else None
    )
    return {
        "n_projects": len(per_project),
        "compile_pass_rate": compile_pass_rate,
        "projects": per_project,
    }


def _print_summary(summary: dict) -> None:
    print("\n================ SWEEP SUMMARY ================")
    cpr = summary["compile_pass_rate"]
    print(f"projects           : {summary['n_projects']}")
    if cpr is not None:
        n = sum(1 for p in summary["projects"] if p["compile_ok"])
        print(f"compile-pass rate  : {cpr:.3f}  ({n}/{sum(1 for p in summary['projects'] if p['compile_ok'] is not None)} compiled clean)")
    for p in summary["projects"]:
        name = Path(p["project"]).name
        rates = p["rates"] or {}
        line = f"  {name:24} stages={p['stage_exit']}"
        if rates.get("models_total"):
            line += f"  models {rates['models_success']}/{rates['models_total']}"
        if rates.get("tests_total"):
            line += f"  tests {rates['tests_passed']}/{rates['tests_total']}"
        print(line)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--project", action="append", help="a dbt project dir (repeatable)")
    src.add_argument("--projects-root", help="dir containing generated project subdirs")
    p.add_argument("--stages", default="deps,compile", help="comma-separated dbt stages in order")
    p.add_argument("--profiles-dir", default=None, help="DBT_PROFILES_DIR (Databricks OAuth profile)")
    p.add_argument("--dbt", default=None, help="path to the dbt executable (default: venv, then PATH)")
    p.add_argument("--results-out", default=None, help="write the full sweep summary JSON here")
    args = p.parse_args(argv)

    summary = sweep(args)
    _print_summary(summary)
    if args.results_out:
        Path(args.results_out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\nwrote {args.results_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
