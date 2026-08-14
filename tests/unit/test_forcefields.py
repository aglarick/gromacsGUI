from __future__ import annotations

from pathlib import Path

from gromacs_gui.gmx.forcefields import list_force_fields, list_water_models


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
