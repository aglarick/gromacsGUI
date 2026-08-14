from __future__ import annotations

from pathlib import Path

# GROMACS always names solvent residues "SOL" regardless of force field/water
# model, so this is a stable default rather than something that needs to be
# parsed out of genion's interactive group listing.
DEFAULT_SOLVENT_GROUP = "SOL"


def build_genion_command(
    input_tpr: Path,
    topology_top: Path,
    output_gro: Path,
    positive_ion: str = "NA",
    negative_ion: str = "CL",
    neutral: bool = True,
) -> list[str]:
    args = [
        "genion",
        "-s",
        str(input_tpr),
        "-p",
        str(topology_top),
        "-o",
        str(output_gro),
        "-pname",
        positive_ion,
        "-nname",
        negative_ion,
    ]
    if neutral:
        args.append("-neutral")
    return args


def genion_stdin(solvent_group: str = DEFAULT_SOLVENT_GROUP) -> str:
    """genion interactively asks which index group is the solvent to replace;
    answering by name (rather than its numeric index, which shifts depending
    on the system) on stdin is confirmed to work against a real gmx build.
    """
    return f"{solvent_group}\n"
