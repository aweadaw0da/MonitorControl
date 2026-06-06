from __future__ import annotations

from typing import Any

from monitor_control_app.core.input_sources import parse_input_code
from monitor_control_app.models.monitor_info import DeviceTarget

DEVICE_WINDOWS = "windows"
DEVICE_MAC = "mac"
VALID_DEVICES = {DEVICE_WINDOWS, DEVICE_MAC}


def normalize_device(value: str) -> str:
    normalized = value.strip().lower()
    aliases = {
        "win": DEVICE_WINDOWS,
        "windows": DEVICE_WINDOWS,
        "mac": DEVICE_MAC,
        "macos": DEVICE_MAC,
        "osx": DEVICE_MAC,
    }
    if normalized not in aliases:
        raise ValueError(f"未知设备身份: {value}")
    return aliases[normalized]


def display_device_name(device_name: str) -> str:
    device = normalize_device(device_name)
    return "Windows" if device == DEVICE_WINDOWS else "Mac"


def get_opposite_device(local_device: str) -> str:
    device = normalize_device(local_device)
    return DEVICE_MAC if device == DEVICE_WINDOWS else DEVICE_WINDOWS


def get_primary_action_label(local_device: str) -> str:
    target = get_opposite_device(local_device)
    return f"切换到 {display_device_name(target)}"


def get_target_source_for_device(device_name: str, config: dict[str, Any]) -> str:
    device = normalize_device(device_name)
    source_label = config.get("device_targets", {}).get(device)
    if not source_label:
        raise ValueError(f"未配置 {display_device_name(device)} 对应的输入源")
    return str(source_label)


def resolve_target_input_code(device_name: str, config: dict[str, Any]) -> int:
    source_label = get_target_source_for_device(device_name, config)
    input_sources = config.get("input_sources", {})
    if source_label not in input_sources:
        raise ValueError(f"输入源 {source_label} 不存在")
    return parse_input_code(input_sources[source_label])


def build_device_target(device_name: str, config: dict[str, Any]) -> DeviceTarget:
    device = normalize_device(device_name)
    source_label = get_target_source_for_device(device, config)
    input_code = resolve_target_input_code(device, config)
    return DeviceTarget(device_name=device, source_label=source_label, input_code=input_code)
