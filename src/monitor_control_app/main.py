from __future__ import annotations

import os
import platform
import sys

from monitor_control_app.core.config_store import ConfigStore
from monitor_control_app.core.logging_setup import setup_logging
from monitor_control_app.core.monitor_service import MonitorService


def configure_qt_for_platform() -> None:
    if platform.system().lower() == "windows":
        qpa_platform = os.environ.get("QT_QPA_PLATFORM", "")
        if not qpa_platform or qpa_platform == "windows":
            os.environ["QT_QPA_PLATFORM"] = "windows:dpiawareness=0"


def main() -> int:
    configure_qt_for_platform()
    from PySide6.QtWidgets import QApplication

    from monitor_control_app.ui.main_window import MainWindow

    logger = setup_logging()
    config_store = ConfigStore()
    service = MonitorService(logger=logger)

    app = QApplication(sys.argv)
    app.setApplicationName("Monitor Control")

    window = MainWindow(config_store=config_store, monitor_service=service, logger=logger)
    window.resize(920, 560)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
