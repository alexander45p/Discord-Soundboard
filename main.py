import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from backend.config import SETTINGS_FILE
from backend.storage import load_json
from frontend.main_window import MainWindow
from frontend.theme import T, THEMES, build_qss


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Bahnschrift", 10))
    settings = load_json(SETTINGS_FILE, {})
    T.update(THEMES.get(settings.get("tema", "Cyberpunk"), THEMES["Cyberpunk"]))
    app.setStyleSheet(build_qss(T))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
