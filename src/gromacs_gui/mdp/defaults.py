from __future__ import annotations

from pathlib import Path

from gromacs_gui.mdp.mdp_model import MdpFile

TEMPLATES_DIR = Path(__file__).parent / "templates"

_STAGE_TEMPLATE_NAMES = {
    "em": "em.mdp",
    "nvt": "nvt.mdp",
    "npt": "npt.mdp",
    "production": "production.mdp",
}


def default_mdp_path(stage: str) -> Path:
    try:
        filename = _STAGE_TEMPLATE_NAMES[stage]
    except KeyError as exc:
        raise ValueError(f"No default .mdp template for stage {stage!r}") from exc
    return TEMPLATES_DIR / filename


def load_default_mdp(stage: str) -> MdpFile:
    return MdpFile.load(default_mdp_path(stage))
