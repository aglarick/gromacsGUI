from __future__ import annotations

from pathlib import Path


def build_editconf_command(
    input_gro: Path,
    output_gro: Path,
    box_type: str = "cubic",
    distance_nm: float = 1.0,
    center: bool = True,
) -> list[str]:
    args = [
        "editconf",
        "-f",
        str(input_gro),
        "-o",
        str(output_gro),
        "-bt",
        box_type,
        "-d",
        str(distance_nm),
    ]
    if center:
        args.append("-c")
    return args
