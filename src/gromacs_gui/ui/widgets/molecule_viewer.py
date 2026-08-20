"""Lightweight embedded 3D scatter preview for structure/box files.

Deliberately the simplest thing that lets a user see what they're about to
save without leaving the GUI (no VMD, no temp files): parse coordinates once,
render with matplotlib's mplot3d directly in the widget. Good enough for a
single molecule or a moderately sized box; matplotlib's own limitations with
very large point clouds are a known tradeoff, not something to work around
here - if a heavier system needs proper inspection, saving the file and
opening it in VMD is still always available outside the GUI.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from gromacs_gui.gmx.structure_files import AtomPosition

# Above this many atoms, mplot3d gets sluggish to redraw on every checkbox
# toggle - fall back to a text notice rather than freezing the UI.
_MAX_PREVIEW_ATOMS = 20000


class MoleculeViewer3D(QWidget):
    """Embeds a matplotlib 3D scatter plot, color-coded by residue name."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._figure = Figure()
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._axes = self._figure.add_subplot(projection="3d")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        self.show_message("Select a file to preview.")

    def show_message(self, text: str) -> None:
        self._axes.clear()
        self._axes.text2D(0.5, 0.5, text, ha="center", va="center", transform=self._axes.transAxes)
        self._axes.set_axis_off()
        self._canvas.draw_idle()

    def set_atoms(self, atoms: list[AtomPosition]) -> None:
        if not atoms:
            self.show_message("Nothing selected to save.")
            return
        if len(atoms) > _MAX_PREVIEW_ATOMS:
            self.show_message(
                f"Selection too large to preview ({len(atoms)} atoms).\n"
                "Save the file and inspect it with VMD or another external tool."
            )
            return

        elev, azim = self._axes.elev, self._axes.azim
        self._axes.clear()

        by_residue: dict[str, list[AtomPosition]] = {}
        for atom in atoms:
            by_residue.setdefault(atom.residue_name, []).append(atom)

        for name, group in sorted(by_residue.items()):
            self._axes.scatter(
                [a.x for a in group],
                [a.y for a in group],
                [a.z for a in group],
                label=name,
                s=15,
                depthshade=True,
            )

        if len(by_residue) > 1:
            self._axes.legend(loc="upper right", fontsize="small")
        self._axes.set_axis_off()
        self._axes.set_box_aspect((1, 1, 1))
        self._axes.view_init(elev=elev, azim=azim)
        self._canvas.draw_idle()
