"""Build one or more dbt projects from DWA metadata YAMLs (gap 3, offline step).

Wraps :class:`~dbt_builder.src.runners.dbt_builder.DBTBuilder` so a *set* of
metadata files can be turned into a *set* of dbt projects in one call — the input
to the compile-pass-rate sweep (``dbt_sweep.py``). Pure code generation: no
network, no warehouse. Each project lands in ``<out-root>/<metadata-stem>``.

Example
-------
    python scripts/dbt/build_projects.py \
        --metadata poc/metadata/iec_cim_metadata.yaml \
        --out-root C:/Users/me/dwa_build/projects
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dbt_builder.src.runners.dbt_builder import DBTBuilder  # noqa: E402


def build_all(metadata_paths: list[str], out_root: str) -> list[Path]:
    """Generate a dbt project for every metadata YAML; return the project dirs."""
    root = Path(out_root)
    built: list[Path] = []
    for meta in metadata_paths:
        meta_path = Path(meta)
        if not meta_path.exists():
            raise FileNotFoundError(f"metadata YAML not found: {meta_path}")
        project_dir = root / meta_path.stem
        DBTBuilder(metadata_path=meta_path, output_path=project_dir).build()
        built.append(project_dir)
        print(f"  built {meta_path.name} -> {project_dir}")
    return built


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--metadata", action="append", required=True, help="DWA metadata YAML (repeatable)")
    p.add_argument("--out-root", required=True, help="directory to write the generated projects into")
    args = p.parse_args(argv)

    built = build_all(args.metadata, args.out_root)
    print(f"\nbuilt {len(built)} project(s) under {args.out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
