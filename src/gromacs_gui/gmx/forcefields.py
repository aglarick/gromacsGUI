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
    """List water models available for a bundled force field, parsed from
    its watermodels.dat (same file `gmx pdb2gmx`'s interactive menu reads
    from).
    """
    return list_water_models_in_folder(Path(top_dir) / f"{force_field_name}.ff")


def list_water_models_in_folder(ff_dir: Path) -> list[WaterModel]:
    """Same as list_water_models, but for a force field folder anywhere on
    disk (e.g. a user-supplied custom .ff folder) rather than one composed
    from <GMXDATA>/top/<name>.ff.
    """
    watermodels_file = Path(ff_dir) / "watermodels.dat"
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


def _read_forcefield_doc(ff_dir: Path) -> str | None:
    doc_file = ff_dir / "forcefield.doc"
    if not doc_file.is_file():
        return None
    for line in doc_file.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None
