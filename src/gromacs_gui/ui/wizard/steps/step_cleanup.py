from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gromacs_gui.core.project import Project
from gromacs_gui.gmx.commands.pdb2gmx import list_heteroatom_residues
from gromacs_gui.gmx.structure_files import list_residues, remove_residues

_DESCRIPTION = (
    "Herramienta de limpieza: carga cualquier archivo de estructura o caja "
    "(.pdb o .gro), revisa qué moléculas contiene, y marca las que quieres "
    "CONSERVAR — el resto se descarta. Útil para extraer una sola molécula "
    "de una caja con varias combinadas (p. ej. para usarla después en el "
    "paso 'Structure'). No genera topología ni avanza el flujo, y no es "
    "obligatorio usarla."
)


class CleanupToolWidget(QWidget):
    """Standalone structure-cleaning tool, not a pipeline step: it doesn't
    touch Project's manifest and isn't gated by (or gates) anything else.
    Cleaned files land in the project folder for convenience, but using this
    tool is entirely optional.
    """

    def __init__(
        self, project: Project, gmx_env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.project = project
        self._input_path: Path | None = None
        self._residue_checkboxes: dict[str, QCheckBox] = {}

        description = QLabel(_DESCRIPTION, self)
        description.setWordWrap(True)

        self._input_label = QLabel("No file selected")
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._on_browse_clicked)
        picker_row = QHBoxLayout()
        picker_row.addWidget(self._input_label, 1)
        picker_row.addWidget(browse_button)

        select_all_button = QPushButton("Seleccionar todo")
        select_all_button.clicked.connect(lambda: self._set_all_checked(True))
        select_none_button = QPushButton("Deseleccionar todo")
        select_none_button.clicked.connect(lambda: self._set_all_checked(False))
        select_row = QHBoxLayout()
        select_row.addWidget(select_all_button)
        select_row.addWidget(select_none_button)
        select_row.addStretch(1)

        self._residue_list_layout = QVBoxLayout()

        self._save_button = QPushButton("Guardar selección")
        self._save_button.setEnabled(False)
        self._save_button.clicked.connect(self._on_save_clicked)

        self._status_label = QLabel("", self)
        self._status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(description)
        layout.addLayout(picker_row)
        layout.addLayout(select_row)
        layout.addLayout(self._residue_list_layout)
        layout.addWidget(self._save_button)
        layout.addWidget(self._status_label)
        layout.addStretch(1)

    def _on_browse_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a structure or box file",
            str(Path.home()),
            "Structure files (*.pdb *.gro)",
        )
        if not path:
            return
        self._set_input_path(Path(path))

    def _set_input_path(self, path: Path) -> None:
        self._input_path = path
        self._input_label.setText(path.name)
        self._status_label.setText("")
        self._rebuild_residue_checklist()

    def _rebuild_residue_checklist(self) -> None:
        while self._residue_list_layout.count():
            item = self._residue_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._residue_checkboxes.clear()

        if self._input_path is None:
            self._save_button.setEnabled(False)
            return

        residues = list_residues(self._input_path)
        default_kept = self._default_kept_candidates(self._input_path, residues)
        for name, count in sorted(residues.items()):
            checkbox = QCheckBox(f"{name} ×{count}")
            checkbox.setChecked(name in default_kept)
            self._residue_list_layout.addWidget(checkbox)
            self._residue_checkboxes[name] = checkbox

        self._save_button.setEnabled(bool(residues))

    @staticmethod
    def _default_kept_candidates(path: Path, residues: dict[str, int]) -> set[str]:
        """Pre-check residues to keep: for .pdb, everything except HETATM
        (crystallographic water, ions, buffer components) - the same net
        effect as the old "remove HETATM by default" behavior, just phrased
        as "keep". .gro has no ATOM/HETATM marker to tell apart, so instead
        of guessing, everything defaults kept (a safe no-op save) - use
        "Deseleccionar todo" to start from an empty selection when extracting
        a single molecule out of a combined box.
        """
        if path.suffix.lower() == ".pdb":
            return set(residues) - set(list_heteroatom_residues(path))
        return set(residues)

    def _set_all_checked(self, checked: bool) -> None:
        for checkbox in self._residue_checkboxes.values():
            checkbox.setChecked(checked)

    def _on_save_clicked(self) -> None:
        assert self._input_path is not None
        residues_to_keep = {
            name for name, checkbox in self._residue_checkboxes.items() if checkbox.isChecked()
        }
        residues_to_remove = set(self._residue_checkboxes) - residues_to_keep

        cleanup_dir = self.project.root / "cleanup"
        cleanup_dir.mkdir(exist_ok=True)
        output_path = cleanup_dir / f"{self._input_path.stem}_cleaned{self._input_path.suffix}"

        if residues_to_remove:
            remove_residues(self._input_path, output_path, residues_to_remove)
        else:
            shutil.copyfile(self._input_path, output_path)

        self._status_label.setText(f"Guardado en: {output_path.relative_to(self.project.root)}")
