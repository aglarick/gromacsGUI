from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ForceField:
    name: str
    description: str


@dataclass
class WaterModel:
    name: str
    label: str
    description: str


def gmxdata_top_dir(env: dict[str, str]) -> Path | None:
    """Resolve <GMXDATA>/top (where force field directories live) from a
    GMXRC-sourced environment.
    """
    gmxdata = env.get("GMXDATA")
    if not gmxdata:
        return None
    top_dir = Path(gmxdata) / "top"
    return top_dir if top_dir.is_dir() else None


def list_force_fields(top_dir: Path) -> list[ForceField]:
    """List installed force fields by scanning <GMXDATA>/top for `<name>.ff` dirs.

    Mirrors what `gmx pdb2gmx`'s interactive force field menu shows, so the
    -ff flag can be used instead (no interactive prompt to automate).
    """
    force_fields = []
    for entry in sorted(Path(top_dir).glob("*.ff")):
        if not entry.is_dir():
            continue
        name = entry.name[: -len(".ff")]
        force_fields.append(ForceField(name=name, description=_read_forcefield_doc(entry) or name))
    return force_fields


def list_water_models(top_dir: Path, force_field_name: str) -> list[WaterModel]:
    """List water models available for a force field, parsed from its
    watermodels.dat (same file `gmx pdb2gmx`'s interactive menu reads from).
    """
    watermodels_file = Path(top_dir) / f"{force_field_name}.ff" / "watermodels.dat"
    if not watermodels_file.is_file():
        return []

    models = []
    for line in watermodels_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        name, label = parts[0], parts[1]
        description = parts[2] if len(parts) > 2 else label
        models.append(WaterModel(name=name, label=label, description=description))
    return models


# None of GROMACS's bundled force fields define a bare "HIS" residue - they
# all only have protonation-state-specific variants (AMBER: HID/HIE/HIP,
# CHARMM: HSD/HSE/HSP, OPLS/GROMOS: HISD/HISE/HISH...). Real PDB files
# almost always just say "HIS" though, and pdb2gmx resolves that
# ambiguity itself with an internal default when run non-interactively
# (confirmed against a real build: it succeeds on plain "HIS" with no
# prompt) - this isn't visible by scanning .rtp files, so it's special
# cased here rather than left to silently report "unrecognized".
_HISTIDINE_VARIANTS = {
    "HID",
    "HIE",
    "HIP",
    "HSD",
    "HSE",
    "HSP",
    "HISD",
    "HISE",
    "HISH",
}


def list_recognized_residues(top_dir: Path, force_field_name: str) -> set[str]:
    """Residue names a force field's .rtp database(s) define - the same
    mechanism pdb2gmx itself uses to decide whether it can process a given
    residue, so the GUI can check compatibility before offering pdb2gmx
    rather than letting the command fail. A force field can ship more than
    one .rtp (aminoacids.rtp, dna.rtp, rna.rtp, lipids.rtp, ...); all are
    scanned.
    """
    ff_dir = Path(top_dir) / f"{force_field_name}.ff"
    residues: set[str] = set()
    for rtp_file in sorted(ff_dir.glob("*.rtp")):
        residues.update(_parse_rtp_residue_names(rtp_file))
    if residues & _HISTIDINE_VARIANTS:
        residues.add("HIS")
    return residues


def _parse_rtp_residue_names(rtp_file: Path) -> set[str]:
    """Each residue in a .rtp is a top-level `[ Name ]` section (unindented);
    its own sub-sections (`[ atoms ]`, `[ bonds ]`, ...) use the same
    bracket syntax but are indented, so indentation is what distinguishes
    a residue header from one of its sub-sections. `[ bondedtypes ]` at the
    top isn't a residue either and must be skipped.
    """
    names = set()
    for line in rtp_file.read_text(errors="replace").splitlines():
        if not line.startswith("["):
            continue
        name = line.strip().strip("[] \t")
        if name and name.lower() != "bondedtypes":
            names.add(name)
    return names


def _read_forcefield_doc(ff_dir: Path) -> str | None:
    doc_file = ff_dir / "forcefield.doc"
    if not doc_file.is_file():
        return None
    for line in doc_file.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None
