import os
import unittest
from unittest.mock import patch

from monitor_control_app.main import configure_qt_for_platform


class MainStartupTest(unittest.TestCase):
    def test_windows_sets_dpi_awareness_platform_argument(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch("monitor_control_app.main.platform.system", return_value="Windows"):
            configure_qt_for_platform()

            self.assertEqual(os.environ["QT_QPA_PLATFORM"], "windows:dpiawareness=0")

    def test_windows_replaces_plain_windows_platform_argument(self) -> None:
        with patch.dict(os.environ, {"QT_QPA_PLATFORM": "windows"}, clear=True), patch(
            "monitor_control_app.main.platform.system", return_value="Windows"
        ):
            configure_qt_for_platform()

            self.assertEqual(os.environ["QT_QPA_PLATFORM"], "windows:dpiawareness=0")

    def test_non_windows_leaves_qt_platform_argument_unchanged(self) -> None:
        with patch.dict(os.environ, {"QT_QPA_PLATFORM": "xcb"}, clear=True), patch(
            "monitor_control_app.main.platform.system", return_value="Linux"
        ):
            configure_qt_for_platform()

            self.assertEqual(os.environ["QT_QPA_PLATFORM"], "xcb")


if __name__ == "__main__":
    unittest.main()
