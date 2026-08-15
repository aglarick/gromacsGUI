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
    "(.pdb o .gro), revisa qué moléculas contiene, y guarda una copia "
    "filtrada en la carpeta del proyecto. No genera topología ni avanza el "
    "flujo — no es obligatorio usarla, y no tienes que seguir al paso "
    "'Structure' después. Es útil para quedarte solo con las moléculas que "
    "quieres cuando partes de una caja con varias combinadas."
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

        self._residue_list_layout = QVBoxLayout()

        self._save_button = QPushButton("Guardar copia limpia")
        self._save_button.setEnabled(False)
        self._save_button.clicked.connect(self._on_save_clicked)

        self._status_label = QLabel("", self)
        self._status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(description)
        layout.addLayout(picker_row)
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
        default_removed = self._default_removal_candidates(self._input_path)
        for name, count in sorted(residues.items()):
            checkbox = QCheckBox(f"{name} ×{count}")
            checkbox.setChecked(name in default_removed)
            self._residue_list_layout.addWidget(checkbox)
            self._residue_checkboxes[name] = checkbox

        self._save_button.setEnabled(bool(residues))

    @staticmethod
    def _default_removal_candidates(path: Path) -> set[str]:
        """Pre-check likely-unwanted residues when we can tell (HETATM in a
        .pdb); .gro has no such marker, so nothing is pre-checked there and
        the user picks explicitly.
        """
        if path.suffix.lower() == ".pdb":
            return set(list_heteroatom_residues(path))
        return set()

    def _on_save_clicked(self) -> None:
        assert self._input_path is not None
        residues_to_remove = {
            name for name, checkbox in self._residue_checkboxes.items() if checkbox.isChecked()
        }

        cleanup_dir = self.project.root / "cleanup"
        cleanup_dir.mkdir(exist_ok=True)
        output_path = cleanup_dir / f"{self._input_path.stem}_cleaned{self._input_path.suffix}"

        if residues_to_remove:
            remove_residues(self._input_path, output_path, residues_to_remove)
        else:
            shutil.copyfile(self._input_path, output_path)

        self._status_label.setText(f"Guardado en: {output_path.relative_to(self.project.root)}")
