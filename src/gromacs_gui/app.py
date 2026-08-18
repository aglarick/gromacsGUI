import sys

from PySide6.QtWidgets import QApplication

from gromacs_gui.main_window import MainWindow
from gromacs_gui.utils.webengine_env import ensure_webengine_importable


def main() -> int:
    ensure_webengine_importable()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
