from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QKeySequenceEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from monitor_control_app.core.config_store import get_default_config
from monitor_control_app.core.hotkeys import normalize_hotkey
from monitor_control_app.core.input_sources import format_input_code, normalize_sources, parse_input_code
from monitor_control_app.core.device_targets import DEVICE_MAC, DEVICE_WINDOWS


class SettingsDialog(QDialog):
    def __init__(self, config: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(560, 440)
        self._config = deepcopy(config)

        self.local_device_combo = QComboBox()
        self.local_device_combo.addItem("Windows", DEVICE_WINDOWS)
        self.local_device_combo.addItem("Mac", DEVICE_MAC)

        local_index = self.local_device_combo.findData(self._config.get("local_device", DEVICE_WINDOWS))
        self.local_device_combo.setCurrentIndex(max(0, local_index))

        self.windows_source_combo = QComboBox()
        self.mac_source_combo = QComboBox()
        self.switch_hotkey_edit = QKeySequenceEdit()
        self.switch_hotkey_edit.setKeySequence(self._config.get("switch_hotkey", "Ctrl+Alt+M"))

        self.sources_table = QTableWidget(0, 2)
        self.sources_table.setHorizontalHeaderLabels(["名称", "VCP 值"])
        self.sources_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.sources_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.sources_table.verticalHeader().setVisible(False)
        self.sources_table.itemChanged.connect(self._refresh_target_combos)

        add_button = QPushButton("新增输入源")
        add_button.clicked.connect(self._add_source_row)
        delete_button = QPushButton("删除选中")
        delete_button.clicked.connect(self._delete_selected_source)
        default_button = QPushButton("恢复默认")
        default_button.clicked.connect(self._restore_defaults)

        table_actions = QHBoxLayout()
        table_actions.addWidget(add_button)
        table_actions.addWidget(delete_button)
        table_actions.addStretch(1)
        table_actions.addWidget(default_button)

        form = QFormLayout()
        form.addRow("本机身份", self.local_device_combo)
        form.addRow("Windows 输入源", self.windows_source_combo)
        form.addRow("Mac 输入源", self.mac_source_combo)
        form.addRow("切换快捷键", self.switch_hotkey_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("输入源映射"))
        layout.addWidget(self.sources_table)
        layout.addLayout(table_actions)
        layout.addWidget(buttons)

        self._populate_sources_table(self._config.get("input_sources", {}))
        self._refresh_target_combos()

    def config(self) -> dict[str, Any]:
        return deepcopy(self._config)

    def _populate_sources_table(self, sources: dict[str, str]) -> None:
        self.sources_table.blockSignals(True)
        self.sources_table.setRowCount(0)
        for label, code in sources.items():
            row = self.sources_table.rowCount()
            self.sources_table.insertRow(row)
            self.sources_table.setItem(row, 0, QTableWidgetItem(label))
            self.sources_table.setItem(row, 1, QTableWidgetItem(code))
        self.sources_table.blockSignals(False)

    def _read_sources_from_table(self) -> dict[str, str]:
        sources: dict[str, str] = {}
        for row in range(self.sources_table.rowCount()):
            label_item = self.sources_table.item(row, 0)
            code_item = self.sources_table.item(row, 1)
            label = label_item.text().strip() if label_item else ""
            code = code_item.text().strip() if code_item else ""
            if not label and not code:
                continue
            if not label:
                raise ValueError("输入源名称不能为空")
            if label in sources:
                raise ValueError(f"输入源名称重复: {label}")
            sources[label] = format_input_code(parse_input_code(code))
        if not sources:
            raise ValueError("至少需要保留一个输入源")
        return normalize_sources(sources)

    def _refresh_target_combos(self) -> None:
        current_windows = self.windows_source_combo.currentData() or self._config.get("device_targets", {}).get("windows")
        current_mac = self.mac_source_combo.currentData() or self._config.get("device_targets", {}).get("mac")

        labels: list[str] = []
        for row in range(self.sources_table.rowCount()):
            item = self.sources_table.item(row, 0)
            label = item.text().strip() if item else ""
            if label and label not in labels:
                labels.append(label)

        for combo, current in ((self.windows_source_combo, current_windows), (self.mac_source_combo, current_mac)):
            combo.blockSignals(True)
            combo.clear()
            for label in labels:
                combo.addItem(label, label)
            index = combo.findData(current)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def _add_source_row(self) -> None:
        row = self.sources_table.rowCount()
        self.sources_table.insertRow(row)
        self.sources_table.setItem(row, 0, QTableWidgetItem(f"Source{row + 1}"))
        self.sources_table.setItem(row, 1, QTableWidgetItem("0x00"))

    def _delete_selected_source(self) -> None:
        selected_rows = sorted({index.row() for index in self.sources_table.selectedIndexes()}, reverse=True)
        for row in selected_rows:
            self.sources_table.removeRow(row)
        self._refresh_target_combos()

    def _restore_defaults(self) -> None:
        defaults = get_default_config()
        self._populate_sources_table(defaults["input_sources"])
        self._config["device_targets"] = deepcopy(defaults["device_targets"])
        self._refresh_target_combos()

    def _validate_and_accept(self) -> None:
        try:
            sources = self._read_sources_from_table()
            hotkey = normalize_hotkey(self.switch_hotkey_edit.keySequence().toString())
        except ValueError as exc:
            QMessageBox.warning(self, "设置无效", str(exc))
            return

        self._config["local_device"] = self.local_device_combo.currentData()
        self._config["input_sources"] = sources
        self._config["device_targets"] = {
            "windows": self.windows_source_combo.currentData(),
            "mac": self.mac_source_combo.currentData(),
        }
        self._config["switch_hotkey"] = hotkey
        self.accept()
