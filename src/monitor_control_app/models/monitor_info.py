from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonitorInfo:
    id: str
    index: int
    name: str
    current_input: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class OperationResult:
    monitor_id: str
    success: bool
    message: str


@dataclass(frozen=True)
class DeviceTarget:
    device_name: str
    source_label: str
    input_code: int
