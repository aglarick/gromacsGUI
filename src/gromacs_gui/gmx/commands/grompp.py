from __future__ import annotations

from pathlib import Path


def build_grompp_command(
    mdp_file: Path,
    structure_gro: Path,
    topology_top: Path,
    output_tpr: Path,
    maxwarn: int = 0,
) -> list[str]:
    args = [
        "grompp",
        "-f",
        str(mdp_file),
        "-c",
        str(structure_gro),
        "-p",
        str(topology_top),
        "-o",
        str(output_tpr),
    ]
    if maxwarn:
        args += ["-maxwarn", str(maxwarn)]
    return args
