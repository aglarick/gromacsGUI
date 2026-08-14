from __future__ import annotations

from gromacs_gui.mdp.mdp_model import MdpFile
from gromacs_gui.ui.widgets.mdp_editor import MdpEditor


def test_editor_loads_and_returns_equivalent_mdp(qtbot):
    editor = MdpEditor()
    qtbot.addWidget(editor)
    original = MdpFile.parse("integrator = steep\nnsteps = 100\n")

    editor.load_mdp(original)
    result = editor.to_mdp()

    assert result.get("integrator") == "steep"
    assert result.get("nsteps") == "100"


def test_editor_save_to_writes_edited_text(tmp_path, qtbot):
    editor = MdpEditor()
    qtbot.addWidget(editor)
    editor.load_mdp(MdpFile.parse("integrator = steep\n"))

    path = tmp_path / "out.mdp"
    editor.save_to(path)

    assert MdpFile.load(path).get("integrator") == "steep"
