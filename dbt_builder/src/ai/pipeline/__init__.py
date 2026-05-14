"""Deterministic pipeline steps that flank the LLM agents.

This sub-package implements Steps 1, 2, 3 from the Option-B architecture:

* :mod:`catalog_inspector` — reads the *current state* of the target vault.
* :mod:`bronze_reader`     — reads the *source state* of the bronze layer.
* :mod:`diff_analyzer`     — categorises every bronze table NEW / DRIFT /
  UNCHANGED / ORPHANED relative to the existing vault.

Every module here is pure Python (no Spark / Databricks at import time). The
catalog and bronze readers accept a ``describe_table`` / ``list_tables``
callable so production code can wire in Spark while tests pass fakes. This
keeps the deterministic core idempotent and CI-runnable offline.
"""
