from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "gromacs_gui"
CONFIG_FILE = CONFIG_DIR / "settings.json"


class GmxEnvironmentError(RuntimeError):
    """Raised when GMXRC can't be sourced or gmx can't be located."""


@dataclass
class Settings:
    gmxrc_path: str | None = None

    @classmethod
    def load(cls) -> Settings:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
            return cls(**data)
        return cls()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2))


def resolve_gmx_environment(gmxrc_path: str | Path) -> dict[str, str]:
    """Source GMXRC in a subshell and capture the resulting environment.

    GROMACS requires GMXRC to be sourced to set GMXLIB/PATH/LD_LIBRARY_PATH; a GUI
    launched from a desktop icon won't have that already loaded, unlike a terminal.
    """
    gmxrc_path = Path(gmxrc_path)
    if not gmxrc_path.is_file():
        raise GmxEnvironmentError(f"GMXRC not found at {gmxrc_path}")

    result = subprocess.run(
        ["bash", "-c", f'source "{gmxrc_path}" && env -0'],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise GmxEnvironmentError(f"Failed to source {gmxrc_path}: {stderr}")

    env: dict[str, str] = {}
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        key, _, value = entry.decode(errors="replace").partition("=")
        env[key] = value
    return env


def with_gmx_defaults(env: dict[str, str]) -> dict[str, str]:
    """Copy of env with GROMACS's own numbered-backup-file feature disabled.

    Project already tracks step history via numbered step folders + the
    manifest, so GROMACS's own `#file.N#` backups would just be clutter
    inside those folders.
    """
    result = dict(env)
    result["GMX_MAXBACKUP"] = "-1"
    return result


def find_gmx_binary(env: dict[str, str]) -> str | None:
    """Locate the gmx executable using PATH from a (possibly GMXRC-sourced) environment."""
    for directory in env.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / "gmx"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None
