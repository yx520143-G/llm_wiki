from __future__ import annotations

import shutil
from pathlib import Path


def assert_inside_project(project_root: Path, output_path: Path) -> None:
    root = project_root.resolve()
    target = output_path.resolve()
    if root == target or root not in target.parents:
        raise ValueError(f"Output path must be inside project root: {target}")


def replace_output_dir(staged: Path, final: Path) -> None:
    if not staged.is_dir():
        raise ValueError(f"Staged output is not a directory: {staged}")
    if final.exists() and not final.is_dir():
        raise ValueError(f"Final output exists and is not a directory: {final}")
    backup = final.with_name(final.name + ".bak")
    if backup.exists() and not backup.is_dir():
        raise ValueError(f"Backup output exists and is not a directory: {backup}")
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
