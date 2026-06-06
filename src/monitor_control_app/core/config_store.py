from __future__ import annotations

import json
import os
import platform
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from monitor_control_app.core.hotkeys import normalize_hotkey
from monitor_control_app.core.input_sources import get_default_sources, normalize_sources


DEFAULT_CONFIG: dict[str, Any] = {
    "local_device": "windows",
    "mode": "single",
    "device_targets": {
        "windows": "DP",
        "mac": "USB-C",
    },
    "input_sources": get_default_sources(),
    "default_monitor_id": None,
    "switch_hotkey": "Ctrl+Alt+M",
    "refresh_after_switch_ms": 1500,
    "show_log_panel": False,
}


def get_config_path() -> Path:
    system = platform.system().lower()
    if system == "windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "MonitorControl" / "config.json"
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "MonitorControl" / "config.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "MonitorControl" / "config.json"


def get_log_path() -> Path:
    return get_config_path().with_name("monitor-control.log")


def get_default_config() -> dict[str, Any]:
    return deepcopy(DEFAULT_CONFIG)


def merge_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = get_default_config()

    if isinstance(raw.get("local_device"), str):
        config["local_device"] = raw["local_device"].strip().lower()
    if raw.get("mode") in {"single", "all"}:
        config["mode"] = raw["mode"]
    if isinstance(raw.get("device_targets"), dict):
        config["device_targets"].update(raw["device_targets"])
    if isinstance(raw.get("input_sources"), dict):
        config["input_sources"].update(raw["input_sources"])
        _migrate_legacy_input_sources(config["input_sources"])
    if raw.get("default_monitor_id") is None or isinstance(raw.get("default_monitor_id"), str):
        config["default_monitor_id"] = raw.get("default_monitor_id")
    if isinstance(raw.get("switch_hotkey"), str):
        try:
            config["switch_hotkey"] = normalize_hotkey(raw["switch_hotkey"])
        except ValueError:
            pass
    if isinstance(raw.get("refresh_after_switch_ms"), int):
        config["refresh_after_switch_ms"] = max(0, raw["refresh_after_switch_ms"])
    if isinstance(raw.get("show_log_panel"), bool):
        config["show_log_panel"] = raw["show_log_panel"]

    config["input_sources"] = normalize_sources(config["input_sources"])
    return config


def _migrate_legacy_input_sources(input_sources: dict[str, str]) -> None:
    if (
        str(input_sources.get("USB-C", "")).lower() == "0x12"
        and str(input_sources.get("HDMI1", "")).lower() == "0x10"
        and str(input_sources.get("HDMI2", "")).lower() == "0x11"
    ):
        input_sources["DP"] = "0x10"
        input_sources["USB-C"] = "0x0F"
        input_sources["HDMI1"] = "0x11"
        input_sources["HDMI2"] = "0x12"

    if (
        str(input_sources.get("DP", "")).lower() == "0x0f"
        and str(input_sources.get("USB-C", "")).lower() == "0x10"
        and str(input_sources.get("HDMI1", "")).lower() == "0x11"
        and str(input_sources.get("HDMI2", "")).lower() == "0x12"
    ):
        input_sources["DP"] = "0x10"
        input_sources["USB-C"] = "0x0F"


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_config_path()

    def load_config(self) -> dict[str, Any]:
        if not self.path.exists():
            config = get_default_config()
            self.save_config(config)
            return config

        try:
            with self.path.open("r", encoding="utf-8") as config_file:
                raw = json.load(config_file)
            if not isinstance(raw, dict):
                raise ValueError("配置文件根节点必须是对象")
            return merge_config(raw)
        except Exception:
            backup_path = self.path.with_suffix(".broken.json")
            shutil.copy2(self.path, backup_path)
            config = get_default_config()
            self.save_config(config)
            return config

    def save_config(self, config: dict[str, Any]) -> None:
        merged = merge_config(config)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as config_file:
            json.dump(merged, config_file, ensure_ascii=False, indent=2)
