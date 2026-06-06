import unittest

from monitor_control_app.core.hotkeys import MOD_ALT, MOD_CONTROL, MOD_SHIFT, parse_hotkey


class HotkeyTest(unittest.TestCase):
    def test_parse_hotkey_normalizes_display_text(self) -> None:
        hotkey = parse_hotkey("ctrl + alt + m")

        self.assertEqual(hotkey.text, "Ctrl+Alt+M")
        self.assertEqual(hotkey.modifiers, MOD_CONTROL | MOD_ALT)
        self.assertEqual(hotkey.key, ord("M"))

    def test_parse_hotkey_supports_function_keys(self) -> None:
        hotkey = parse_hotkey("Shift+F12")

        self.assertEqual(hotkey.text, "Shift+F12")
        self.assertEqual(hotkey.modifiers, MOD_SHIFT)
        self.assertEqual(hotkey.key, 0x7B)

    def test_parse_hotkey_requires_modifier(self) -> None:
        with self.assertRaises(ValueError):
            parse_hotkey("M")

    def test_parse_hotkey_rejects_multiple_main_keys(self) -> None:
        with self.assertRaises(ValueError):
            parse_hotkey("Ctrl+M+N")


if __name__ == "__main__":
    unittest.main()
