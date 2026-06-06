import unittest

from monitor_control_app.core.input_sources import (
    describe_input,
    find_label_by_code,
    format_input_code,
    parse_input_code,
)


class InputSourcesTest(unittest.TestCase):
    def test_parse_hex_and_decimal_input_codes(self) -> None:
        self.assertEqual(parse_input_code("0x0F"), 15)
        self.assertEqual(parse_input_code("0X12"), 18)
        self.assertEqual(parse_input_code("16"), 16)
        self.assertEqual(parse_input_code(3), 3)

    def test_parse_rejects_invalid_input_codes(self) -> None:
        with self.assertRaises(ValueError):
            parse_input_code("")
        with self.assertRaises(ValueError):
            parse_input_code("not-a-code")
        with self.assertRaises(ValueError):
            parse_input_code("-1")

    def test_format_and_describe_input_codes(self) -> None:
        sources = {"DP": "0x0F", "USB-C": "0x12"}

        self.assertEqual(format_input_code(15), "0x0F")
        self.assertEqual(format_input_code(None), "未知")
        self.assertEqual(find_label_by_code(18, sources), "USB-C")
        self.assertEqual(describe_input(15, sources), "DP (0x0F)")
        self.assertEqual(describe_input(17, sources), "0x11")


if __name__ == "__main__":
    unittest.main()
