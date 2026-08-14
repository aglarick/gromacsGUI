from __future__ import annotations

from gromacs_gui.mdp.mdp_model import MdpFile

SAMPLE = """; em.mdp - example
integrator  = steep   ; steepest descent
emtol       = 1000.0
emstep      = 0.01

nsteps      = 50000
"""


def test_parse_preserves_comments_and_blank_lines_on_roundtrip():
    mdp = MdpFile.parse(SAMPLE)

    assert mdp.to_text() == SAMPLE


def test_get_reads_known_key_case_insensitively():
    mdp = MdpFile.parse(SAMPLE)

    assert mdp.get("integrator") == "steep"
    assert mdp.get("EmTol") == "1000.0"
    assert mdp.get("missing-key") is None


def test_set_replaces_value_and_preserves_inline_comment():
    mdp = MdpFile.parse(SAMPLE)

    mdp.set("integrator", "cg")

    assert mdp.get("integrator") == "cg"
    text = mdp.to_text()
    assert "integrator  = cg" in text
    assert "; steepest descent" in text


def test_set_replaces_value_without_inline_comment():
    mdp = MdpFile.parse(SAMPLE)

    mdp.set("nsteps", "100")

    assert mdp.get("nsteps") == "100"
    assert "nsteps      = 100" in mdp.to_text()


def test_set_appends_new_key_when_absent():
    mdp = MdpFile.parse(SAMPLE)

    mdp.set("dt", "0.002")

    assert mdp.get("dt") == "0.002"
    assert "dt" in mdp.keys()


def test_load_and_save_roundtrip_via_file(tmp_path):
    path = tmp_path / "test.mdp"
    path.write_text(SAMPLE)

    mdp = MdpFile.load(path)
    mdp.set("nsteps", "200")
    mdp.save(path)

    reloaded = MdpFile.load(path)
    assert reloaded.get("nsteps") == "200"
    assert reloaded.get("integrator") == "steep"
