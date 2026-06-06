from __future__ import annotations

import shutil
from pathlib import Path


def assert_inside_project(project_root: Path, output_path: Path) -> None:
    root = project_root.resolve()
    target = output_path.resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"Output path escapes project root: {target}")


def replace_output_dir(staged: Path, final: Path) -> None:
    if not staged.is_dir():
        raise ValueError(f"Staged output is not a directory: {staged}")
    backup = final.with_name(final.name + ".bak")
    if backup.exists():
        shutil.rmtree(backup)
    if final.exists():
        final.rename(backup)
    try:
        staged.rename(final)
    except Exception:
        if final.exists():
            shutil.rmtree(final)
        if backup.exists():
            backup.rename(final)
        raise
    if backup.exists():
        shutil.rmtree(backup)
