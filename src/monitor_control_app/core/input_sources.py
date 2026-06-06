from __future__ import annotations

DEFAULT_INPUT_SOURCES: dict[str, str] = {
    "DP": "0x10",
    "USB-C": "0x0F",
    "HDMI1": "0x11",
    "HDMI2": "0x12",
    "DVI": "0x03",
}


def get_default_sources() -> dict[str, str]:
    return dict(DEFAULT_INPUT_SOURCES)


def parse_input_code(value: str | int) -> int:
    if isinstance(value, int):
        if value < 0:
            raise ValueError("输入源代码不能为负数")
        return value

    normalized = value.strip()
    if not normalized:
        raise ValueError("输入源代码不能为空")

    try:
        base = 16 if normalized.lower().startswith("0x") else 10
        parsed = int(normalized, base)
    except ValueError as exc:
        raise ValueError(f"无效输入源代码: {value}") from exc

    if parsed < 0:
        raise ValueError("输入源代码不能为负数")
    return parsed


def format_input_code(value: int | None) -> str:
    if value is None:
        return "未知"
    return f"0x{value:02X}"


def normalize_sources(sources: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for label, raw_code in sources.items():
        cleaned_label = label.strip()
        if not cleaned_label:
            continue
        normalized[cleaned_label] = format_input_code(parse_input_code(raw_code))
    return normalized


def find_label_by_code(value: int | None, sources: dict[str, str]) -> str | None:
    if value is None:
        return None

    for label, raw_code in sources.items():
        try:
            if parse_input_code(raw_code) == value:
                return label
        except ValueError:
            continue
    return None


def describe_input(value: int | None, sources: dict[str, str]) -> str:
    if value is None:
        return "未知"
    label = find_label_by_code(value, sources)
    code = format_input_code(value)
    return f"{label} ({code})" if label else code
