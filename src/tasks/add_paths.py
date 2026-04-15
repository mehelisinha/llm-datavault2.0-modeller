# Databricks notebook source
# COMMAND ----------
import sys
from pathlib import Path


def get_root_folder(path_str: str, parent_name:str = "src") -> Path | None:
    current_path = Path(path_str)
    for parent in current_path.parents:
        if parent.name == parent_name:
            return parent.parent  # Get the parent of "src"
    return None  # Return None if "src" is not found


def append_path(current_path: str):
    if current_path not in sys.path:
        sys.path.append(current_path)
    else:
        print(f"Path {current_path} already in sys.path")


# get current path
current_path: str = (
    dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
)

# extract root
root_path = get_root_folder(current_path, "src")

# append path
# append_path(f'/Workspace{root_path}')
append_path(f"/Workspace/{root_path}")

print(root_path)
