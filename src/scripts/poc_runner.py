#!/usr/bin/env python3
"""
POC Runner — end-to-end orchestration script for the DWA Data Vault POC.

Runs the full pipeline on Databricks:
  1. Metadata-driven dbt model generation (SQL + YAML files)
  2. dbt run: bronze layer
  3. dbt run: staging layer
  4. dbt run: raw vault layer
  5. Validation: query Databricks to verify tables, row counts, and hash keys

Prerequisites:
  - ~/.dbt/profiles.yml configured for iec_dv2_databricks profile
  - DATABRICKS_HOST and DATABRICKS_TOKEN env vars set (or in .envrc)
  - Python dependencies installed (uv pip install -e .)

Usage:
    python poc_runner.py                    # full run
    python poc_runner.py --generate-only    # only regenerate dbt model files
    python poc_runner.py --skip-generate    # skip generation, run dbt directly
    python poc_runner.py --validate-only    # only run validation queries
    python poc_runner.py --profiles-dir /path/to/profiles  # custom profiles dir
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from dbt.cli.main import dbtRunner, dbtRunnerResult



# Ensure src/ is importable
PROJECT_ROOT = Path.cwd().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_METADATA = SRC_DIR / "metadata" / "iec_cim_metadata.yaml"
DBT_PROJECT_DIR = SRC_DIR
DEFAULT_MODELS_OUTPUT = PROJECT_ROOT / "models"
DEFAULT_PROFILES_DIR = Path.home() / ".dbt"

CATALOG = "edh_unreg_silver_dev_st"
RAW_VAULT_SCHEMA = "raw_vault"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def log(msg: str, level: str = "INFO") -> None:
    icons = {"INFO": "ℹ️ ", "OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "STEP": "🔷"}
    print(f"{icons.get(level, '  ')} {msg}", flush=True)


def run_command(cmd: list[str], cwd: Path, step_name: str) -> int:
    """Run a shell command and return exit code."""
    log(f"{step_name}: {' '.join(cmd)}", "STEP")
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        log(f"{step_name} failed with exit code {result.returncode}", "ERR")
    else:
        log(f"{step_name} succeeded", "OK")
    return result.returncode


def dbt_run(
    select: str,
    profiles_dir: Path,
    step_name: str,
) -> int:
    """Run `dbt run --select <select>` in the dbt project directory."""
    # cmd = [
    #     "dbt",
    #     "run",
    #     "--select",
    #     select,
    #     "--profiles-dir",
    #     str(profiles_dir),
    #     "--project-dir",
    #     str(DBT_PROJECT_DIR),
    # ]
    # return run_command(cmd, DBT_PROJECT_DIR, step_name)
    # initialize
    dbt = dbtRunner()

    # create CLI args as a list of strings
    cli_args = ["run", "--select", f"tag:{step_name}"]

    # run the command
    res: dbtRunnerResult = dbt.invoke(cli_args)

    # inspect the results
    for r in res.result:
        print(f"{r.node.name}: {r.status}")


# ---------------------------------------------------------------------------
# Step 1: Generate dbt model files from metadata
# ---------------------------------------------------------------------------


def step_generate(models_output: Path) -> None:
    log("Step 1: Generating dbt models from metadata ...", "STEP")
    generate_script = SRC_DIR / "scripts" / "generate_models.py"
    cmd = [
        sys.executable,
        str(generate_script),
        "--config",
        str(DEFAULT_METADATA),
        "--output",
        str(models_output),
        "--overwrite",
    ]
    rc = run_command(cmd, PROJECT_ROOT, "Model generation")
    if rc != 0:
        sys.exit(rc)


# ---------------------------------------------------------------------------
# Step 2–4: dbt run by layer
# ---------------------------------------------------------------------------


def step_dbt_bronze(profiles_dir: Path) -> None:
    log("Step 2: Running dbt — Bronze layer ...", "STEP")
    rc = dbt_run("tag:bronze", profiles_dir, "dbt run bronze")
    if rc != 0:
        sys.exit(rc)


def step_dbt_staging(profiles_dir: Path) -> None:
    log("Step 3: Running dbt — Staging layer ...", "STEP")
    rc = dbt_run("tag:staging", profiles_dir, "dbt run staging")
    if rc != 0:
        sys.exit(rc)


def step_dbt_raw_vault(profiles_dir: Path) -> None:
    log("Step 4: Running dbt — Raw Vault layer ...", "STEP")
    rc = dbt_run("tag:raw_vault", profiles_dir, "dbt run raw_vault")
    if rc != 0:
        sys.exit(rc)


# ---------------------------------------------------------------------------
# Step 5: Validation via Databricks SQL
# ---------------------------------------------------------------------------


def step_validate() -> None:
    """Query Databricks to confirm tables exist and contain expected data."""
    log("Step 5: Validating results on Databricks ...", "STEP")

    try:
        from databricks import sql as dbsql
    except ImportError:
        log(
            "databricks-sql-connector not installed. "
            "Install it with: pip install databricks-sql-connector",
            "WARN",
        )
        log("Skipping validation — run manually via Databricks UI or SQL editor", "WARN")
        return

    host = os.environ.get("DATABRICKS_HOST", "").lstrip("https://")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    http_path = os.environ.get("DATABRICKS_HTTP_PATH", "")

    if not all([host, token, http_path]):
        log(
            "Missing env vars: DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH. "
            "Skipping validation.",
            "WARN",
        )
        return

    # Tables to validate
    tables = [
        f"{CATALOG}.{RAW_VAULT_SCHEMA}.hub_conducting_equipment",
        f"{CATALOG}.{RAW_VAULT_SCHEMA}.hub_connectivity_node",
        f"{CATALOG}.{RAW_VAULT_SCHEMA}.hub_terminal",
        f"{CATALOG}.{RAW_VAULT_SCHEMA}.lnk_terminal_equipment_node",
        f"{CATALOG}.{RAW_VAULT_SCHEMA}.sat_conducting_equipment_details",
        f"{CATALOG}.{RAW_VAULT_SCHEMA}.sat_conducting_equipment_operational",
        f"{CATALOG}.{RAW_VAULT_SCHEMA}.sat_connectivity_node_details",
        f"{CATALOG}.{RAW_VAULT_SCHEMA}.sat_terminal_details",
        f"{CATALOG}.{RAW_VAULT_SCHEMA}.eff_sat_terminal_equipment_node",
    ]

    with dbsql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token,
    ) as connection:
        with connection.cursor() as cursor:
            all_ok = True
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                    row = cursor.fetchone()
                    count = row[0]
                    status = "OK" if count > 0 else "WARN"
                    log(f"  {table}: {count} rows", status)
                    if count == 0:
                        all_ok = False
                except Exception as e:
                    log(f"  {table}: ERROR — {e}", "ERR")
                    all_ok = False

            # Verify hash key format for hub_conducting_equipment
            log("Checking HK format in hub_conducting_equipment ...", "INFO")
            cursor.execute(
                f"SELECT HK_CONDUCTING_EQUIPMENT FROM {CATALOG}.{RAW_VAULT_SCHEMA}.hub_conducting_equipment LIMIT 3"
            )
            rows = cursor.fetchall()
            for r in rows:
                hk = r[0]
                if hk and len(hk) == 32:
                    log(f"  HK (MD5 32-char): {hk}", "OK")
                elif hk and len(hk) == 64:
                    log(f"  HK (SHA256 64-char): {hk}", "OK")
                else:
                    log(f"  Unexpected HK length ({len(hk) if hk else 'null'}): {hk}", "WARN")

            # Check CDC SWAP scenario: CE-SW-001 should have 3 operational satellite rows
            log("Checking SWAP scenario satellite history for CE-SW-001 ...", "INFO")
            cursor.execute(
                f"""
                SELECT COUNT(*) as cnt
                FROM {CATALOG}.{RAW_VAULT_SCHEMA}.sat_conducting_equipment_operational s
                JOIN {CATALOG}.{RAW_VAULT_SCHEMA}.hub_conducting_equipment h
                  ON s.HK_CONDUCTING_EQUIPMENT = h.HK_CONDUCTING_EQUIPMENT
                WHERE h.mrid = 'CE-SW-001'
                """
            )
            swap_count = cursor.fetchone()[0]
            if swap_count >= 2:
                log(f"  SWAP scenario: {swap_count} history rows for CE-SW-001 ✓", "OK")
            else:
                log(
                    f"  SWAP scenario: only {swap_count} row(s) for CE-SW-001 — expected ≥2",
                    "WARN",
                )

            if all_ok:
                log("All validation checks passed!", "OK")
            else:
                log("Some checks had warnings — review above", "WARN")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DWA POC Runner — end-to-end Databricks pipeline."
    )
    parser.add_argument(
        "--profiles-dir",
        default=str(DEFAULT_PROFILES_DIR),
        help="Path to directory containing dbt profiles.yml (default: ~/.dbt)",
    )
    parser.add_argument(
        "--models-output",
        default=str(DEFAULT_MODELS_OUTPUT),
        help="Output directory for generated dbt models (default: <project_root>/models)",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only run model generation step; skip dbt and validation",
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Skip model generation; run dbt layers + validation",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run the validation queries against Databricks",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profiles_dir = Path(args.profiles_dir)
    models_output = Path(args.models_output)

    start = time.time()
    log("=" * 60, "INFO")
    log("DWA POC Runner — IEC61968 CIM Data Vault on Databricks", "INFO")
    log("=" * 60, "INFO")

    if args.validate_only:
        step_validate()
    elif args.generate_only:
        step_generate(models_output)
    else:
        if not args.skip_generate:
            step_generate(models_output)
        step_dbt_bronze(profiles_dir)
        step_dbt_staging(profiles_dir)
        step_dbt_raw_vault(profiles_dir)
        step_validate()

    elapsed = time.time() - start
    log(f"Done in {elapsed:.1f}s", "OK")


if __name__ == "__main__":
    main()
