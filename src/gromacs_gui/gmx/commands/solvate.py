from __future__ import annotations

from pathlib import Path

# A bare filename here is resolved by gmx itself against GMXLIB/the library
# top directory, so this doesn't need to be an absolute path.
DEFAULT_SOLVENT_BOX = "spc216.gro"


def build_solvate_command(
    input_gro: Path,
    topology_top: Path,
    output_gro: Path,
    solvent_box: str = DEFAULT_SOLVENT_BOX,
) -> list[str]:
    return [
        "solvate",
        "-cp",
        str(input_gro),
        "-cs",
        solvent_box,
        "-o",
        str(output_gro),
        "-p",
        str(topology_top),
    ]
