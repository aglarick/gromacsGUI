import stat

from gromacs_gui.utils import settings as settings_module
from gromacs_gui.utils.settings import find_gmx_binary


def test_find_gmx_binary_locates_executable_in_path(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gmx = bin_dir / "gmx"
    gmx.write_text("#!/bin/sh\necho fake gmx\n")
    gmx.chmod(gmx.stat().st_mode | stat.S_IEXEC)

    env = {"PATH": str(bin_dir)}

    assert find_gmx_binary(env) == str(gmx)


def test_find_gmx_binary_returns_none_when_absent(tmp_path):
    env = {"PATH": str(tmp_path)}

    assert find_gmx_binary(env) is None


def test_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(settings_module, "CONFIG_FILE", tmp_path / "cfg" / "settings.json")

    settings_module.Settings(gmxrc_path="/opt/gromacs/bin/GMXRC").save()

    loaded = settings_module.Settings.load()

    assert loaded.gmxrc_path == "/opt/gromacs/bin/GMXRC"
