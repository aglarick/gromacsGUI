from __future__ import annotations

from gromacs_gui.core.capabilities import Capability, detect_capabilities


def test_empty_folder_has_no_capabilities(tmp_path):
    assert detect_capabilities(tmp_path) == set()


def test_gro_only_gives_single_frame_trajectory(tmp_path):
    (tmp_path / "system.gro").write_text("fake gro")

    caps = detect_capabilities(tmp_path)

    assert caps == {Capability.STRUCTURE, Capability.TRAJECTORY_SINGLE_FRAME}


def test_trajectory_file_upgrades_to_multi_frame_and_keeps_structure(tmp_path):
    (tmp_path / "system.gro").write_text("fake gro")
    (tmp_path / "traj.xtc").write_bytes(b"\x00")

    caps = detect_capabilities(tmp_path)

    assert Capability.STRUCTURE in caps
    assert Capability.TRAJECTORY_MULTI_FRAME in caps
    assert Capability.TRAJECTORY_SINGLE_FRAME not in caps


def test_edr_file_enables_energy_capability(tmp_path):
    (tmp_path / "run.edr").write_bytes(b"\x00")

    assert Capability.ENERGY in detect_capabilities(tmp_path)


def test_scans_nested_step_folders(tmp_path):
    nested = tmp_path / "04_em"
    nested.mkdir()
    (nested / "em.trr").write_bytes(b"\x00")

    assert Capability.TRAJECTORY_MULTI_FRAME in detect_capabilities(tmp_path)
