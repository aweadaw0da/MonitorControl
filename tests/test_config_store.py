import json
import unittest

from monitor_control_app.core.config_store import ConfigStore, get_default_config, merge_config


class ConfigStoreTest(unittest.TestCase):
    def test_merge_config_preserves_defaults_and_normalizes_sources(self) -> None:
        config = merge_config(
            {
                "local_device": "mac",
                "mode": "all",
                "input_sources": {"USB-C": "18", "HDMI3": "0x13"},
            }
        )

        self.assertEqual(config["local_device"], "mac")
        self.assertEqual(config["mode"], "all")
        self.assertEqual(config["input_sources"]["USB-C"], "0x12")
        self.assertEqual(config["input_sources"]["HDMI3"], "0x13")
        self.assertEqual(config["device_targets"]["windows"], "DP")

    def test_config_store_creates_default_config(self) -> None:
        with self.subTest("uses temp path"):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "config.json"
                store = ConfigStore(path)

                config = store.load_config()

                self.assertEqual(config, get_default_config())
                self.assertTrue(path.exists())

    def test_merge_config_migrates_legacy_input_source_defaults(self) -> None:
        config = merge_config(
            {
                "input_sources": {
                    "DP": "0x0F",
                    "USB-C": "0x12",
                    "HDMI1": "0x10",
                    "HDMI2": "0x11",
                    "DVI": "0x03",
                }
            }
        )

        self.assertEqual(config["input_sources"]["DP"], "0x10")
        self.assertEqual(config["input_sources"]["USB-C"], "0x0F")
        self.assertEqual(config["input_sources"]["HDMI1"], "0x11")
        self.assertEqual(config["input_sources"]["HDMI2"], "0x12")

    def test_merge_config_migrates_reversed_dp_usb_c_defaults(self) -> None:
        config = merge_config(
            {
                "input_sources": {
                    "DP": "0x0F",
                    "USB-C": "0x10",
                    "HDMI1": "0x11",
                    "HDMI2": "0x12",
                    "DVI": "0x03",
                }
            }
        )

        self.assertEqual(config["input_sources"]["DP"], "0x10")
        self.assertEqual(config["input_sources"]["USB-C"], "0x0F")

    def test_config_store_backs_up_broken_config(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("{broken", encoding="utf-8")
            store = ConfigStore(path)

            config = store.load_config()

            self.assertEqual(config, get_default_config())
            self.assertTrue(path.with_suffix(".broken.json").exists())

    def test_config_store_saves_merged_config(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            store = ConfigStore(path)
            config = get_default_config()
            config["local_device"] = "mac"

            store.save_config(config)

            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["local_device"], "mac")
            self.assertEqual(raw["input_sources"]["DP"], "0x10")

    def test_merge_config_preserves_default_monitor_id(self) -> None:
        config = merge_config({"default_monitor_id": "monitor-1"})

        self.assertEqual(config["default_monitor_id"], "monitor-1")

    def test_merge_config_normalizes_switch_hotkey(self) -> None:
        config = merge_config({"switch_hotkey": "ctrl + shift + f8"})

        self.assertEqual(config["switch_hotkey"], "Ctrl+Shift+F8")

    def test_merge_config_ignores_invalid_switch_hotkey(self) -> None:
        config = merge_config({"switch_hotkey": "M"})

        self.assertEqual(config["switch_hotkey"], get_default_config()["switch_hotkey"])


if __name__ == "__main__":
    unittest.main()
