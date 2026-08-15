from __future__ import annotations

from pathlib import Path


def parse_moleculetype_name(itp_path: Path) -> str:
    """Extract the molecule name from an .itp's [ moleculetype ] section (the
    first token on its first non-comment, non-blank data line).
    """
    in_section = False
    for raw_line in Path(itp_path).read_text(errors="replace").splitlines():
        line = raw_line.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            in_section = line.strip("[] ").lower() == "moleculetype"
            continue
        if in_section:
            return line.split()[0]
    raise ValueError(f"No [ moleculetype ] section found in {itp_path}")


def build_wrapping_topology(
    itp_filename: str, force_field: str, molecule_name: str, molecule_count: int = 1
) -> str:
    """A minimal .top that includes a force field and a single .itp molecule,
    for users who have an .itp (e.g. from ATB/LigParGen) but not a full .top.
    `itp_filename` is resolved relative to the .top's own directory, so the
    .itp must be copied alongside it.
    """
    return (
        f'#include "{force_field}.ff/forcefield.itp"\n'
        "\n"
        f'#include "{itp_filename}"\n'
        "\n"
        "[ system ]\n"
        f"{molecule_name}\n"
        "\n"
        "[ molecules ]\n"
        f"{molecule_name:<10} {molecule_count}\n"
    )
