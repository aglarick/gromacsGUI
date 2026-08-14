from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GromacsGUI")
        self.resize(900, 600)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("GromacsGUI — Phase 1 scaffold"))
        self.setCentralWidget(central)
