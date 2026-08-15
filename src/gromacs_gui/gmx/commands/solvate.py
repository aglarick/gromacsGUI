from __future__ import annotations

from pathlib import Path

# A bare filename here is resolved by gmx itself against GMXLIB/the library
# top directory, so this doesn't need to be an absolute path.
DEFAULT_SOLVENT_BOX = "spc216.gro"

# spc216.gro is 3-site water coordinates and works as the seed structure for
# spc/spce/tip3p alike (their geometries are close enough; the exact model
# comes from the .itp, not this box). 4- and 5-site models add virtual sites
# spc216.gro doesn't have, so they need their own matching box.
_WATER_MODEL_BOXES = {
    "tip4p": "tip4p.gro",
    "tip4pew": "tip4p.gro",
    "tip5p": "tip5p.gro",
}


def default_solvent_box_for_water_model(water_model: str | None) -> str:
    if water_model is None:
        return DEFAULT_SOLVENT_BOX
    return _WATER_MODEL_BOXES.get(water_model.lower(), DEFAULT_SOLVENT_BOX)


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
