import unittest

from monitor_control_app.core.config_store import get_default_config
from monitor_control_app.core.device_targets import (
    build_device_target,
    get_opposite_device,
    get_primary_action_label,
    resolve_target_input_code,
)


class DeviceTargetsTest(unittest.TestCase):
    def test_opposite_device_and_action_label(self) -> None:
        self.assertEqual(get_opposite_device("windows"), "mac")
        self.assertEqual(get_opposite_device("mac"), "windows")
        self.assertEqual(get_primary_action_label("windows"), "切换到 Mac")
        self.assertEqual(get_primary_action_label("mac"), "切换到 Windows")

    def test_resolve_target_input_code_from_default_config(self) -> None:
        config = get_default_config()

        self.assertEqual(resolve_target_input_code("windows", config), 0x10)
        self.assertEqual(resolve_target_input_code("mac", config), 0x0F)

        target = build_device_target("mac", config)
        self.assertEqual(target.device_name, "mac")
        self.assertEqual(target.source_label, "USB-C")
        self.assertEqual(target.input_code, 0x0F)

    def test_missing_target_source_is_reported(self) -> None:
        config = get_default_config()
        config["device_targets"]["mac"] = "Missing"

        with self.assertRaises(ValueError):
            resolve_target_input_code("mac", config)


if __name__ == "__main__":
    unittest.main()
