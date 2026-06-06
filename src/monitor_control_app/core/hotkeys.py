from __future__ import annotations

from dataclasses import dataclass


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

MODIFIER_ALIASES = {
    "ALT": MOD_ALT,
    "CTRL": MOD_CONTROL,
    "CONTROL": MOD_CONTROL,
    "SHIFT": MOD_SHIFT,
    "META": MOD_WIN,
    "WIN": MOD_WIN,
    "WINDOWS": MOD_WIN,
    "SUPER": MOD_WIN,
    "CMD": MOD_WIN,
    "COMMAND": MOD_WIN,
}

MODIFIER_DISPLAY = {
    MOD_CONTROL: "Ctrl",
    MOD_ALT: "Alt",
    MOD_SHIFT: "Shift",
    MOD_WIN: "Win",
}

KEY_ALIASES = {
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
    "SPACE": 0x20,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "RETURN": 0x0D,
    "BACKSPACE": 0x08,
    "DELETE": 0x2E,
    "DEL": 0x2E,
    "INSERT": 0x2D,
    "INS": 0x2D,
    "HOME": 0x24,
    "END": 0x23,
    "PAGEUP": 0x21,
    "PGUP": 0x21,
    "PAGEDOWN": 0x22,
    "PGDN": 0x22,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
}


@dataclass(frozen=True)
class Hotkey:
    text: str
    modifiers: int
    key: int


def normalize_hotkey(text: object) -> str:
    if not isinstance(text, str):
        return ""
    return parse_hotkey(text).text


def parse_hotkey(text: str) -> Hotkey:
    parts = [part.strip() for part in text.replace("-", "+").split("+") if part.strip()]
    if not parts:
        raise ValueError("快捷键不能为空")

    modifiers = 0
    key: int | None = None
    key_text: str | None = None

    for part in parts:
        normalized = part.upper().replace(" ", "")
        if normalized in MODIFIER_ALIASES:
            modifiers |= MODIFIER_ALIASES[normalized]
            continue
        if key is not None:
            raise ValueError("快捷键只能包含一个主键")
        key = _parse_key(normalized)
        key_text = _display_key(normalized, key)

    if key is None or key_text is None:
        raise ValueError("快捷键缺少主键")
    if modifiers == 0:
        raise ValueError("快捷键至少需要一个修饰键")

    display_parts = [label for bit, label in MODIFIER_DISPLAY.items() if modifiers & bit]
    display_parts.append(key_text)
    return Hotkey(text="+".join(display_parts), modifiers=modifiers, key=key)


def _parse_key(text: str) -> int:
    if len(text) == 1 and ("A" <= text <= "Z" or "0" <= text <= "9"):
        return ord(text)
    if text.startswith("F") and text[1:].isdigit():
        number = int(text[1:])
        if 1 <= number <= 24:
            return 0x6F + number
    if text in KEY_ALIASES:
        return KEY_ALIASES[text]
    raise ValueError(f"不支持的快捷键主键: {text}")


def _display_key(text: str, key: int) -> str:
    if len(text) == 1 and ("A" <= text <= "Z" or "0" <= text <= "9"):
        return text
    if 0x70 <= key <= 0x87:
        return f"F{key - 0x6F}"
    for label, alias_key in KEY_ALIASES.items():
        if alias_key == key and label not in {"ESCAPE", "RETURN", "DEL", "INS", "PGUP", "PGDN"}:
            return label.title()
    return text.title()
