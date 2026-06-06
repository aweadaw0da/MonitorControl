from __future__ import annotations

import logging
import sys
from typing import Any

from monitor_control_app.models.monitor_info import MonitorInfo, OperationResult


class MonitorService:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("monitor_control_app")
        self._monitors: dict[str, Any] = {}

    def list_monitors(self) -> list[MonitorInfo]:
        if sys.platform == "darwin":
            return self._list_monitors_macos()
        return self._list_monitors_generic()

    def get_current_input(self, monitor_id: str) -> int:
        monitor = self._get_monitor(monitor_id)
        if sys.platform == "darwin":
            display_index = self._monitors[monitor_id]
            from monitor_control_app.core.macos_monitor_backend import get_input
            value = get_input(display_index)
            if value is None:
                raise RuntimeError(f"读取输入源失败: {monitor_id}")
            return value
        return self._read_current_input(monitor)

    def set_input(self, monitor_id: str, input_code: int) -> None:
        if sys.platform == "darwin":
            display_index = self._get_monitor(monitor_id)
            from monitor_control_app.core.macos_monitor_backend import set_input as macos_set_input
            macos_set_input(display_index, input_code)
        else:
            monitor = self._get_monitor(monitor_id)
            with monitor:
                monitor.set_input_source(input_code)
        self._logger.info("已发送输入源切换 monitor=%s code=0x%02X", monitor_id, input_code)

    def set_input_for_all(self, input_code: int) -> list[OperationResult]:
        results: list[OperationResult] = []
        for monitor_id in list(self._monitors):
            try:
                self.set_input(monitor_id, input_code)
            except Exception as exc:
                message = str(exc)
                self._logger.warning("批量切换失败 monitor=%s error=%s", monitor_id, message)
                results.append(OperationResult(monitor_id=monitor_id, success=False, message=message))
            else:
                results.append(OperationResult(monitor_id=monitor_id, success=True, message="已发送切换命令"))
        return results

    def _get_monitor(self, monitor_id: str) -> Any:
        if monitor_id not in self._monitors:
            raise KeyError(f"显示器不存在或需要刷新: {monitor_id}")
        return self._monitors[monitor_id]

    @staticmethod
    def _make_monitor_id(index: int, monitor: Any) -> str:
        return f"monitor-{index}"

    @staticmethod
    def _get_monitor_name(index: int, monitor: Any) -> str:
        for attr in ("name", "model", "description"):
            value = getattr(monitor, attr, None)
            if value:
                return str(value)
        return f"Monitor {index + 1}"

    @staticmethod
    def _read_current_input(monitor: Any) -> int:
        with monitor:
            return int(monitor.get_input_source())

    @staticmethod
    def _read_capabilities(monitor: Any) -> dict[str, Any]:
        with monitor:
            capabilities = monitor.get_vcp_capabilities()
        return capabilities if isinstance(capabilities, dict) else {}

    # ------------------------------------------------------------------
    # macOS backend (m1ddc)
    # ------------------------------------------------------------------

    def _list_monitors_macos(self) -> list[MonitorInfo]:
        from monitor_control_app.core.macos_monitor_backend import (
            is_available,
            list_displays,
            get_input,
            _M1DDC_NOT_FOUND_MSG,
        )

        if not is_available():
            self._logger.error("m1ddc 未安装")
            return [MonitorInfo(id="missing-m1ddc", index=0, name="缺少 m1ddc", error=_M1DDC_NOT_FOUND_MSG)]

        try:
            displays = list_displays()
        except Exception as exc:
            self._logger.exception("m1ddc 扫描显示器失败")
            return [MonitorInfo(id="scan-error", index=0, name="扫描失败", error=str(exc))]

        # _monitors maps monitor_id -> m1ddc display index (1-based int)
        self._monitors = {}
        infos: list[MonitorInfo] = []

        for display in displays:
            monitor_id = f"monitor-macos-{display.index}"
            self._monitors[monitor_id] = display.index

            current_input = get_input(display.index)
            error: str | None = None
            if current_input is None:
                error = "读取输入源失败（显示器可能不支持 DDC/CI）"

            infos.append(
                MonitorInfo(
                    id=monitor_id,
                    index=display.index - 1,  # 0-based for UI
                    name=display.name,
                    current_input=current_input,
                    error=error,
                )
            )

        self._logger.info("macOS: 扫描到 %s 台显示器", len(infos))
        return infos

    # ------------------------------------------------------------------
    # Generic (Windows / Linux) backend (monitorcontrol)
    # ------------------------------------------------------------------

    def _list_monitors_generic(self) -> list[MonitorInfo]:
        try:
            from monitorcontrol import get_monitors
        except ImportError as exc:
            message = "未安装 monitorcontrol，请先安装依赖"
            self._logger.exception(message)
            return [MonitorInfo(id="missing-monitorcontrol", index=0, name="依赖缺失", error=f"{message}: {exc}")]

        try:
            raw_monitors = list(get_monitors())
        except Exception as exc:
            self._logger.exception("扫描显示器失败")
            return [MonitorInfo(id="scan-error", index=0, name="扫描失败", error=str(exc))]

        self._monitors = {
            self._make_monitor_id(index, monitor): monitor
            for index, monitor in enumerate(raw_monitors)
        }
        infos: list[MonitorInfo] = []

        for index, monitor in enumerate(raw_monitors):
            monitor_id = self._make_monitor_id(index, monitor)
            name = self._get_monitor_name(index, monitor)
            current_input: int | None = None
            error: str | None = None

            try:
                capabilities = self._read_capabilities(monitor)
                model = capabilities.get("model")
                if model:
                    name = str(model)
                inputs = capabilities.get("inputs")
                if inputs:
                    self._logger.info("显示器 %s 支持输入源: %s", name, inputs)
            except Exception as exc:
                self._logger.warning("读取显示器能力失败 monitor=%s error=%s", monitor_id, exc)

            try:
                current_input = self._read_current_input(monitor)
            except Exception as exc:
                error = str(exc)
                self._logger.warning("读取显示器输入源失败: %s", error)

            infos.append(
                MonitorInfo(
                    id=monitor_id,
                    index=index,
                    name=name,
                    current_input=current_input,
                    error=error,
                )
            )

        self._logger.info("扫描到 %s 台显示器", len(infos))
        return infos
