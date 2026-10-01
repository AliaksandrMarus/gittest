"""Точка входа: ТендерАгент — мониторинг тендеров Беларуси и подготовка предложений."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    from PySide6.QtWidgets import QApplication

    from tenderagent.config import APP_NAME
    from tenderagent.gui.common import STYLE
    from tenderagent.gui.main_window import MainWindow

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TenderAgent.BY")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
