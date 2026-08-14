from __future__ import annotations

from pathlib import Path

from gromacs_gui.core.step_state import STEP_ORDER

TOPOLOGY_DIR_NAME = "topology"
MANIFEST_FILE_NAME = "project.json"


def step_dir_name(step_name: str) -> str:
    index = STEP_ORDER.index(step_name)
    return f"{index:02d}_{step_name}"


def step_dir(project_root: Path, step_name: str) -> Path:
    return project_root / step_dir_name(step_name)


def topology_dir(project_root: Path) -> Path:
    return project_root / TOPOLOGY_DIR_NAME


def manifest_path(project_root: Path) -> Path:
    return project_root / MANIFEST_FILE_NAME


def create_project_layout(project_root: Path) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    topology_dir(project_root).mkdir(exist_ok=True)
    for step_name in STEP_ORDER:
        step_dir(project_root, step_name).mkdir(exist_ok=True)
