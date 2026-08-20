from __future__ import annotations

from pathlib import Path

from gromacs_gui.gmx.forcefields import (
    list_force_fields,
    list_recognized_residues,
    list_water_models,
)


def _make_fake_top_dir(tmp_path: Path) -> Path:
    top_dir = tmp_path / "top"
    ff_dir = top_dir / "myff.ff"
    ff_dir.mkdir(parents=True)
    (ff_dir / "forcefield.itp").write_text("")
    (ff_dir / "forcefield.doc").write_text("My Test Force Field\nSome more info\n")
    (ff_dir / "watermodels.dat").write_text(
        "tip3p    TIP3P     TIP 3-point\nspc      SPC       simple point charge\n"
    )
    return top_dir


def test_list_force_fields_reads_description_from_doc(tmp_path):
    top_dir = _make_fake_top_dir(tmp_path)

    force_fields = list_force_fields(top_dir)

    assert len(force_fields) == 1
    assert force_fields[0].name == "myff"
    assert force_fields[0].description == "My Test Force Field"


def test_list_water_models_parses_watermodels_dat(tmp_path):
    top_dir = _make_fake_top_dir(tmp_path)

    models = list_water_models(top_dir, "myff")

    assert [m.name for m in models] == ["tip3p", "spc"]
    assert models[0].label == "TIP3P"


def test_list_water_models_returns_empty_when_no_file(tmp_path):
    top_dir = tmp_path / "top"
    (top_dir / "bare.ff").mkdir(parents=True)

    assert list_water_models(top_dir, "bare") == []


def test_list_recognized_residues_scans_all_rtp_files(tmp_path):
    top_dir = tmp_path / "top"
    ff_dir = top_dir / "myff.ff"
    ff_dir.mkdir(parents=True)
    (ff_dir / "aminoacids.rtp").write_text(
        "[ bondedtypes ]\n; not a residue\n\n[ ALA ]\n [ atoms ]\n\n[ LYS ]\n [ atoms ]\n"
    )
    (ff_dir / "dna.rtp").write_text("[ DA ]\n [ atoms ]\n")

    residues = list_recognized_residues(top_dir, "myff")

    assert residues == {"ALA", "LYS", "DA"}


def test_list_recognized_residues_returns_empty_when_no_rtp(tmp_path):
    top_dir = tmp_path / "top"
    (top_dir / "bare.ff").mkdir(parents=True)

    assert list_recognized_residues(top_dir, "bare") == set()


def test_list_recognized_residues_adds_bare_his_when_a_variant_is_present(tmp_path):
    """Real bug: no bundled force field defines a bare "HIS" residue (only
    protonation variants like HID/HIE/HIP), but pdb2gmx resolves plain
    "HIS" from a real PDB just fine on its own - confirmed against a real
    gmx build. Scanning .rtp files alone would otherwise wrongly say a
    completely ordinary protein isn't recognized.
    """
    top_dir = tmp_path / "top"
    ff_dir = top_dir / "amber.ff"
    ff_dir.mkdir(parents=True)
    (ff_dir / "aminoacids.rtp").write_text("[ ALA ]\n [ atoms ]\n\n[ HID ]\n [ atoms ]\n")

    residues = list_recognized_residues(top_dir, "amber")

    assert "HIS" in residues
    assert "HID" in residues


def test_list_recognized_residues_does_not_add_his_without_a_variant(tmp_path):
    top_dir = tmp_path / "top"
    ff_dir = top_dir / "myff.ff"
    ff_dir.mkdir(parents=True)
    (ff_dir / "aminoacids.rtp").write_text("[ ALA ]\n [ atoms ]\n")

    assert "HIS" not in list_recognized_residues(top_dir, "myff")
