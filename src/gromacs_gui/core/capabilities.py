from __future__ import annotations

from enum import StrEnum
from pathlib import Path


class Capability(StrEnum):
    STRUCTURE = "structure"
    ENERGY = "energy"
    TRAJECTORY_SINGLE_FRAME = "trajectory_single_frame"
    TRAJECTORY_MULTI_FRAME = "trajectory_multi_frame"


_STRUCTURE_EXTENSIONS = {".gro", ".pdb", ".g96"}
_TRAJECTORY_EXTENSIONS = {".trr", ".xtc"}
_ENERGY_EXTENSIONS = {".edr"}


def detect_capabilities(project_root: Path) -> set[Capability]:
    """Scan every file actually present under a project folder and report
    which analyses look possible, independent of what Project's own manifest
    says the GUI ran. What matters for enabling an analysis tab is what's
    really on disk (a project folder may have files placed there by hand, or
    finished on another machine), not just our own history of it.
    """
    found_extensions: set[str] = set()
    for path in Path(project_root).rglob("*"):
        if path.is_file():
            found_extensions.add(path.suffix.lower())

    capabilities: set[Capability] = set()
    if found_extensions & _STRUCTURE_EXTENSIONS:
        capabilities.add(Capability.STRUCTURE)
    if found_extensions & _ENERGY_EXTENSIONS:
        capabilities.add(Capability.ENERGY)
    if found_extensions & _TRAJECTORY_EXTENSIONS:
        capabilities.add(Capability.TRAJECTORY_MULTI_FRAME)
    elif found_extensions & _STRUCTURE_EXTENSIONS:
        capabilities.add(Capability.TRAJECTORY_SINGLE_FRAME)
    return capabilities
