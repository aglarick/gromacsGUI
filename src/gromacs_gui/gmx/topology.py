from __future__ import annotations

import re
from pathlib import Path


def parse_moleculetype_name(itp_path: Path) -> str:
    """Extract the molecule name from an .itp's [ moleculetype ] section (the
    first token on its first non-comment, non-blank data line).
    """
    try:
        return parse_moleculetype_name_from_text(Path(itp_path).read_text(errors="replace"))
    except ValueError:
        raise ValueError(f"No [ moleculetype ] section found in {itp_path}") from None


def parse_moleculetype_name_from_text(text: str) -> str:
    """Same as parse_moleculetype_name, but on text already in memory (e.g.
    a chunk extracted by extract_generated_topology_chunk) rather than a
    file on disk.
    """
    in_section = False
    for raw_line in text.splitlines():
        line = raw_line.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            in_section = line.strip("[] ").lower() == "moleculetype"
            continue
        if in_section:
            return line.split()[0]
    raise ValueError("No [ moleculetype ] section found")


def extract_generated_topology_chunk(top_path: Path, include_water_and_ions: bool) -> str:
    """pdb2gmx writes a full, self-contained topology: its own force field
    #include, one or more [ moleculetype ] blocks (with a position-restraint
    #ifdef), and - unless -water none was used - a water model #include and
    ions #include, followed by [ system ]/[ molecules ]. To combine several
    pdb2gmx-generated molecules into one shared topol.top, only the
    moleculetype block(s) are kept from each; the force field #include and
    [ system ]/[ molecules ] are written once by the caller instead.

    include_water_and_ions keeps the water/ions #include block from this
    particular chunk - pass True for exactly one of the rows being combined
    (they're all identical, since every row shares the step's chosen water
    model), False for the rest, so it isn't defined more than once.
    """
    text = Path(top_path).read_text(errors="replace")

    start = text.find("[ moleculetype ]")
    if start == -1:
        raise ValueError(f"No [ moleculetype ] section found in {top_path}")

    end = text.find("\n[ system ]")
    chunk = text[start:] if end == -1 else text[start:end]

    if not include_water_and_ions:
        water_marker = chunk.find("; Include water topology")
        if water_marker != -1:
            chunk = chunk[:water_marker]

    return chunk.strip() + "\n"


def rename_moleculetype(text: str, new_name: str) -> str:
    """Rename a chunk's [ moleculetype ] to new_name (needed when combining
    several pdb2gmx-generated molecules whose auto-derived names happen to
    collide, e.g. two single-chain inputs both named "Protein_chain_A").
    Only the first [ moleculetype ] block's name is replaced; everything
    else on that line (nrexcl, trailing comment) is preserved as-is.
    """
    lines = text.splitlines(keepends=True)
    in_section = False
    for i, raw_line in enumerate(lines):
        line = raw_line.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            in_section = line.strip("[] ").lower() == "moleculetype"
            continue
        if in_section:
            lines[i] = re.sub(r"^(\s*)\S+", rf"\g<1>{new_name}", raw_line, count=1)
            return "".join(lines)
    raise ValueError("No [ moleculetype ] section found")


def rename_posre_include(text: str, old_filename: str, new_filename: str) -> str:
    """Point a chunk's #include "posre.itp" at a renamed file, needed when
    several pdb2gmx-generated molecules' posre.itp files are copied into the
    same topology/ folder and must not collide.
    """
    return text.replace(f'#include "{old_filename}"', f'#include "{new_filename}"')


def build_combined_topology(
    force_field_includes: list[str],
    molecule_chunks: list[str],
    molecules: list[tuple[str, int]],
    system_name: str = "Combined system",
) -> str:
    """Assemble one topol.top out of pieces gathered from several molecule
    rows: one or more force field #include lines (deduplicated by the
    caller - combining several molecules can legitimately need more than
    one, e.g. a pdb2gmx-generated protein plus a self-contained ligand .itp
    that needs its own force field folder), each molecule's own topology
    chunk (a [ moleculetype ] block or a bare #include of a user .itp), and
    a final [ system ]/[ molecules ] listing every molecule once.
    """
    parts = list(force_field_includes)
    parts.extend(molecule_chunks)
    parts.append("[ system ]\n; Name\n" + system_name + "\n")
    molecules_lines = "\n".join(f"{name:<10} {count}" for name, count in molecules)
    parts.append("[ molecules ]\n; Compound        #mols\n" + molecules_lines + "\n")
    return "\n".join(parts)


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
