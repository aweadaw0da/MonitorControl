from __future__ import annotations

import logging
import platform
import ctypes
from ctypes import wintypes
from typing import Any, Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QEvent, QObject, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QStatusBar,
    QStyle,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from monitor_control_app.core.config_store import ConfigStore
from monitor_control_app.core.device_targets import (
    build_device_target,
    display_device_name,
    get_opposite_device,
    get_primary_action_label,
)
from monitor_control_app.core.hotkeys import MOD_NOREPEAT, Hotkey, parse_hotkey
from monitor_control_app.core.input_sources import describe_input, format_input_code, parse_input_code
from monitor_control_app.core.monitor_service import MonitorService
from monitor_control_app.models.monitor_info import MonitorInfo, OperationResult
from monitor_control_app.ui.settings_dialog import SettingsDialog


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class Worker(QRunnable):
    def __init__(self, task: Callable[[], Any]) -> None:
        super().__init__()
        self.task = task
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.finished.emit(self.task())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class WindowsGlobalHotkey(QObject, QAbstractNativeEventFilter):
    triggered = Signal()

    WM_HOTKEY = 0x0312

    def __init__(self, hotkey_id: int, hotkey: Hotkey, parent: QObject | None = None) -> None:
        QObject.__init__(self, parent)
        QAbstractNativeEventFilter.__init__(self)
        self.hotkey_id = hotkey_id
        self.hotkey = hotkey
        self._registered = False

    def register(self) -> None:
        modifiers = self.hotkey.modifiers | MOD_NOREPEAT
        if not ctypes.windll.user32.RegisterHotKey(None, self.hotkey_id, modifiers, self.hotkey.key):
            raise OSError(ctypes.get_last_error() or "RegisterHotKey failed")
        app = QApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self)
        self._registered = True

    def unregister(self) -> None:
        if not self._registered:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self)
        ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)
        self._registered = False

    def nativeEventFilter(self, event_type: bytes | bytearray, message: int) -> tuple[bool, int]:
        if self._registered and b"windows" in bytes(event_type).lower():
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == self.WM_HOTKEY and int(msg.wParam) == self.hotkey_id:
                self.triggered.emit()
                return True, 0
        return False, 0


class MainWindow(QMainWindow):
    def __init__(
        self,
        config_store: ConfigStore,
        monitor_service: MonitorService,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Monitor Control")

        self.config_store = config_store
        self.monitor_service = monitor_service
        self.logger = logger or logging.getLogger("monitor_control_app")
        self.config = self.config_store.load_config()
        self.thread_pool = QThreadPool.globalInstance()
        self._active_workers: list[Worker] = []
        self.monitors: list[MonitorInfo] = []
        self._allow_close = False
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._tray_primary_action: QAction | None = None
        self._tray_sources_menu: QMenu | None = None
        self._tray_show_action: QAction | None = None
        self._global_hotkey: WindowsGlobalHotkey | None = None
        self._app_shortcut: QShortcut | None = None

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh_monitors)
        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.open_settings)

        self.monitor_list = QListWidget()
        self.monitor_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.monitor_list.currentRowChanged.connect(self._on_monitor_selected)
        self.default_monitor_button = QPushButton("设为默认")
        self.default_monitor_button.clicked.connect(self.set_selected_monitor_as_default)
        self.default_monitor_label = QLabel("默认显示器: 未设置")

        self.empty_label = QLabel("未发现可控制显示器。请确认显示器支持并已启用 DDC/CI。")
        self.empty_label.setWordWrap(True)

        self.current_input_label = QLabel("当前输入源: 未知")
        self.local_device_combo = QComboBox()
        self.local_device_combo.addItem("Windows", "windows")
        self.local_device_combo.addItem("Mac", "mac")
        self.local_device_combo.currentIndexChanged.connect(self._on_local_device_changed)

        self.primary_button = QPushButton()
        self.primary_button.setMinimumHeight(44)
        self.primary_button.clicked.connect(self.switch_to_opposite_device)
        self.target_label = QLabel("目标输入源: 未配置")

        self.mode_group = QButtonGroup(self)
        self.single_mode_button = QToolButton()
        self.single_mode_button.setText("仅当前")
        self.single_mode_button.setCheckable(True)
        self.all_mode_button = QToolButton()
        self.all_mode_button.setText("全部")
        self.all_mode_button.setCheckable(True)
        self.mode_group.addButton(self.single_mode_button)
        self.mode_group.addButton(self.all_mode_button)
        self.single_mode_button.clicked.connect(lambda: self._set_mode("single"))
        self.all_mode_button.clicked.connect(lambda: self._set_mode("all"))

        self.advanced_buttons_layout = QGridLayout()
        self.custom_code_input = QLineEdit()
        self.custom_code_input.setPlaceholderText("0x10")
        self.custom_switch_button = QPushButton("切换")
        self.custom_switch_button.clicked.connect(self.switch_custom_code)

        self.log_toggle = QCheckBox("显示日志")
        self.log_toggle.stateChanged.connect(self._toggle_log_panel)
        self.log_panel = QPlainTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumBlockCount(200)

        self._build_layout()
        self._setup_tray()
        self._apply_config_to_ui()
        self.refresh_monitors()

    def _build_layout(self) -> None:
        top_bar = QHBoxLayout()
        title = QLabel("Monitor Control")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        top_bar.addWidget(title)
        top_bar.addStretch(1)
        top_bar.addWidget(self.refresh_button)
        top_bar.addWidget(self.settings_button)

        left = QVBoxLayout()
        left.addWidget(QLabel("显示器列表"))
        left.addWidget(self.monitor_list)
        default_row = QHBoxLayout()
        default_row.addWidget(self.default_monitor_button)
        default_row.addWidget(self.default_monitor_label, 1)
        left.addLayout(default_row)

        details = QVBoxLayout()
        details.addWidget(self.empty_label)
        details.addWidget(self.current_input_label)

        identity_row = QHBoxLayout()
        identity_row.addWidget(QLabel("本机"))
        identity_row.addWidget(self.local_device_combo)
        identity_row.addStretch(1)
        details.addLayout(identity_row)

        details.addSpacing(12)
        details.addWidget(self.primary_button)
        details.addWidget(self.target_label)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("模式"))
        mode_row.addWidget(self.single_mode_button)
        mode_row.addWidget(self.all_mode_button)
        mode_row.addStretch(1)
        details.addLayout(mode_row)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        details.addWidget(separator)

        details.addWidget(QLabel("高级输入源"))
        details.addLayout(self.advanced_buttons_layout)

        custom_row = QHBoxLayout()
        custom_row.addWidget(QLabel("自定义代码"))
        custom_row.addWidget(self.custom_code_input)
        custom_row.addWidget(self.custom_switch_button)
        details.addLayout(custom_row)

        details.addStretch(1)
        details.addWidget(self.log_toggle)
        details.addWidget(self.log_panel)

        content = QHBoxLayout()
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMinimumWidth(260)
        left_widget.setMaximumWidth(340)
        right_widget = QWidget()
        right_widget.setLayout(details)
        right_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content.addWidget(left_widget)
        content.addWidget(right_widget, 1)

        root = QVBoxLayout()
        root.addLayout(top_bar)
        root.addLayout(content, 1)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._set_status("系统托盘不可用，将只使用主窗口")
            return

        QApplication.setQuitOnLastWindowClosed(False)

        icon = self.windowIcon()
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
            self.setWindowIcon(icon)

        self._tray_menu = QMenu(self)
        self._tray_primary_action = QAction("", self)
        self._tray_primary_action.triggered.connect(self.switch_to_opposite_device)
        self._tray_menu.addAction(self._tray_primary_action)

        self._tray_sources_menu = self._tray_menu.addMenu("切换输入源")
        self._tray_menu.addSeparator()

        refresh_action = QAction("刷新显示器", self)
        refresh_action.triggered.connect(self.refresh_monitors)
        self._tray_menu.addAction(refresh_action)

        self._tray_show_action = QAction("显示主窗口", self)
        self._tray_show_action.triggered.connect(self.show_from_tray)
        self._tray_menu.addAction(self._tray_show_action)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.quit_from_tray)
        self._tray_menu.addAction(exit_action)

        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip("Monitor Control")
        self._tray_icon.setContextMenu(self._tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _apply_config_to_ui(self) -> None:
        local_index = self.local_device_combo.findData(self.config.get("local_device", "windows"))
        self.local_device_combo.blockSignals(True)
        self.local_device_combo.setCurrentIndex(max(0, local_index))
        self.local_device_combo.blockSignals(False)

        self.single_mode_button.setChecked(self.config.get("mode", "single") == "single")
        self.all_mode_button.setChecked(self.config.get("mode", "single") == "all")
        self.log_toggle.setChecked(bool(self.config.get("show_log_panel", False)))
        self.log_panel.setVisible(self.log_toggle.isChecked())

        self._rebuild_advanced_buttons()
        self._update_primary_action()
        self._rebuild_tray_menu()
        self._update_default_monitor_label()
        self._register_switch_hotkey()

    def _rebuild_advanced_buttons(self) -> None:
        while self.advanced_buttons_layout.count():
            item = self.advanced_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        sources = self.config.get("input_sources", {})
        for index, label in enumerate(sources):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, source_label=label: self.switch_source_label(source_label))
            self.advanced_buttons_layout.addWidget(button, index // 5, index % 5)

    def _rebuild_tray_menu(self) -> None:
        if self._tray_primary_action is not None:
            self._tray_primary_action.setText(get_primary_action_label(self.config.get("local_device", "windows")))
            self._tray_primary_action.setEnabled(self.primary_button.isEnabled())

        if self._tray_sources_menu is None:
            return

        self._tray_sources_menu.clear()
        sources = self.config.get("input_sources", {})
        if not sources:
            empty_action = self._tray_sources_menu.addAction("未配置输入源")
            empty_action.setEnabled(False)
            return

        for label in sources:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, source_label=label: self.switch_source_label(source_label))
            self._tray_sources_menu.addAction(action)

    def refresh_monitors(self) -> None:
        self._set_busy(True, "正在扫描显示器...")
        self._start_worker(
            self.monitor_service.list_monitors,
            self._on_monitors_loaded,
            lambda message: self._operation_failed(f"扫描失败: {message}"),
        )

    def switch_to_opposite_device(self) -> None:
        try:
            target_device = get_opposite_device(self.config.get("local_device", "windows"))
            target = build_device_target(target_device, self.config)
        except ValueError as exc:
            QMessageBox.warning(self, "目标未配置", str(exc))
            return
        self._append_log(f"local={self.config.get('local_device')} target={target.device_name}")
        self._switch_input(target.input_code, f"{display_device_name(target.device_name)}: {target.source_label}")

    def switch_source_label(self, source_label: str) -> None:
        try:
            raw_code = self.config.get("input_sources", {})[source_label]
            input_code = parse_input_code(raw_code)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "输入源无效", str(exc))
            return
        self._switch_input(input_code, source_label)

    def switch_custom_code(self) -> None:
        try:
            raw_code = self.custom_code_input.text().strip() or self.custom_code_input.placeholderText()
            input_code = parse_input_code(raw_code)
        except ValueError as exc:
            QMessageBox.warning(self, "代码无效", str(exc))
            return
        self._switch_input(input_code, format_input_code(input_code))

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() != SettingsDialog.Accepted:
            return

        self.config = dialog.config()
        self.config_store.save_config(self.config)
        self._append_log("设置已保存")
        self._apply_config_to_ui()
        self._update_monitor_details()

    def set_selected_monitor_as_default(self) -> None:
        selected = self._selected_monitor()
        if selected is None:
            self._set_status("请先选择显示器")
            return

        self.config["default_monitor_id"] = selected.id
        self.config_store.save_config(self.config)
        self._update_default_monitor_label()
        self._set_status(f"默认显示器已设置为 {self._monitor_display_name(selected)}")

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_from_tray(self) -> None:
        self._allow_close = True
        self._unregister_switch_hotkey()
        if self._tray_icon is not None:
            self._tray_icon.hide()
        QApplication.quit()

    def _switch_input(self, input_code: int, label: str) -> None:
        if not self.monitors:
            self._set_status("没有可切换的显示器")
            return

        selected = self._selected_monitor()
        is_all_mode = self.config.get("mode", "single") == "all"
        if not is_all_mode and selected is None:
            self._set_status("请先选择显示器")
            return

        target_scope = "全部显示器" if is_all_mode else self._monitor_display_name(selected)
        self._set_busy(True, f"正在向 {target_scope} 发送切换命令: {label} ({format_input_code(input_code)})")
        if is_all_mode:
            task = lambda: self.monitor_service.set_input_for_all(input_code)
        else:
            task = lambda: self._set_single_input(selected.id, input_code)

        self._start_worker(
            task,
            lambda result: self._on_switch_finished(result, label, input_code, target_scope),
            lambda message: self._operation_failed(f"切换失败: {message}"),
        )

    def _set_single_input(self, monitor_id: str, input_code: int) -> list[OperationResult]:
        self.monitor_service.set_input(monitor_id, input_code)
        return [OperationResult(monitor_id=monitor_id, success=True, message="已发送切换命令")]

    def _on_monitors_loaded(self, monitors: object) -> None:
        previous_row = self.monitor_list.currentRow()
        self.monitors = list(monitors) if isinstance(monitors, list) else []
        self.monitor_list.clear()

        for monitor in self.monitors:
            title = monitor.name
            current = describe_input(monitor.current_input, self.config.get("input_sources", {}))
            suffix = f" - {current}" if monitor.current_input is not None else " - 未知"
            if monitor.error:
                suffix += " (读取失败)"
            item = QListWidgetItem(title + suffix)
            item.setData(256, monitor.id)
            self.monitor_list.addItem(item)

        if self.monitors:
            next_row = self._preferred_monitor_row(previous_row)
            self.monitor_list.setCurrentRow(next_row)
            self._set_status(f"扫描完成: {len(self.monitors)} 台显示器")
        else:
            self._set_status("未发现可控制显示器")
            self._update_monitor_details()

        self._set_busy(False)
        self._update_default_monitor_label()

    def _on_switch_finished(self, result: object, label: str, input_code: int, target_scope: str) -> None:
        results = result if isinstance(result, list) else []
        success_count = sum(1 for item in results if isinstance(item, OperationResult) and item.success)
        failure_count = len(results) - success_count
        message = f"已向 {target_scope} 发送切换到 {label}: {format_input_code(input_code)}"
        if failure_count:
            message += f"，失败 {failure_count} 台"
        self._set_status(message)
        self._append_log(message)
        self._set_busy(False)

        delay = int(self.config.get("refresh_after_switch_ms", 1500))
        if delay >= 0:
            QTimer.singleShot(delay, self.refresh_monitors)

    def _operation_failed(self, message: str) -> None:
        self._set_busy(False)
        self._set_status(message)
        self._append_log(message)

    def _on_monitor_selected(self, _row: int) -> None:
        self._update_monitor_details()

    def _update_monitor_details(self) -> None:
        selected = self._selected_monitor()
        has_monitors = bool(self.monitors)
        self.empty_label.setVisible(not has_monitors)

        if selected is None:
            self.current_input_label.setText("当前输入源: 未知")
            return

        current = describe_input(selected.current_input, self.config.get("input_sources", {}))
        if selected.error:
            self.current_input_label.setText("当前输入源: 未知（读取失败，仍可尝试切换）")
            self.current_input_label.setToolTip(selected.error)
        else:
            self.current_input_label.setText(f"当前输入源: {current}")
            self.current_input_label.setToolTip("")

    def _update_primary_action(self) -> None:
        local_device = self.config.get("local_device", "windows")
        self.primary_button.setText(get_primary_action_label(local_device))
        try:
            target = build_device_target(get_opposite_device(local_device), self.config)
        except ValueError as exc:
            self.target_label.setText(f"目标输入源: {exc}")
            self.primary_button.setEnabled(False)
            if self._tray_primary_action is not None:
                self._tray_primary_action.setText(self.primary_button.text())
                self._tray_primary_action.setEnabled(False)
            return

        self.primary_button.setEnabled(True)
        target_code = format_input_code(target.input_code)
        self.target_label.setText(f"目标输入源: {target.source_label} ({target_code})")
        self.custom_code_input.setPlaceholderText(target_code)
        if self._tray_primary_action is not None:
            self._tray_primary_action.setText(self.primary_button.text())
            self._tray_primary_action.setEnabled(self.primary_button.isEnabled())

    def _selected_monitor(self) -> MonitorInfo | None:
        row = self.monitor_list.currentRow()
        if row < 0 or row >= len(self.monitors):
            return None
        monitor = self.monitors[row]
        return None if monitor.error and monitor.current_input is None and monitor.id.startswith("scan-error") else monitor

    def _preferred_monitor_row(self, previous_row: int) -> int:
        default_monitor_id = self.config.get("default_monitor_id")
        if isinstance(default_monitor_id, str):
            for row, monitor in enumerate(self.monitors):
                if monitor.id == default_monitor_id:
                    return row
        if 0 <= previous_row < len(self.monitors):
            return previous_row
        return 0

    def _update_default_monitor_label(self) -> None:
        default_monitor_id = self.config.get("default_monitor_id")
        if not default_monitor_id:
            self.default_monitor_label.setText("默认显示器: 未设置")
            return

        for monitor in self.monitors:
            if monitor.id == default_monitor_id:
                self.default_monitor_label.setText(f"默认显示器: {self._monitor_display_name(monitor)}")
                return

        self.default_monitor_label.setText(f"默认显示器: {default_monitor_id}（未发现）")

    @staticmethod
    def _monitor_display_name(monitor: MonitorInfo | None) -> str:
        if monitor is None:
            return "当前显示器"
        return f"{monitor.name}（Monitor {monitor.index + 1}）"

    def _on_local_device_changed(self) -> None:
        self.config["local_device"] = self.local_device_combo.currentData()
        self.config_store.save_config(self.config)
        self._update_primary_action()

    def _set_mode(self, mode: str) -> None:
        self.config["mode"] = mode
        self.config_store.save_config(self.config)

    def _register_switch_hotkey(self) -> None:
        self._unregister_switch_hotkey()
        hotkey_text = self.config.get("switch_hotkey", "Ctrl+Alt+M")

        try:
            hotkey = parse_hotkey(hotkey_text)
        except ValueError as exc:
            self._set_status(f"快捷键无效: {exc}")
            return

        if platform.system().lower() == "windows":
            try:
                self._global_hotkey = WindowsGlobalHotkey(1, hotkey, self)
                self._global_hotkey.triggered.connect(self.switch_to_opposite_device)
                self._global_hotkey.register()
                self._append_log(f"已注册系统快捷键: {hotkey.text}")
                return
            except OSError as exc:
                self._global_hotkey = None
                self._set_status(f"系统快捷键注册失败，改用应用内快捷键: {exc}")

        self._app_shortcut = QShortcut(QKeySequence(hotkey.text), self)
        self._app_shortcut.setContext(Qt.ApplicationShortcut)
        self._app_shortcut.activated.connect(self.switch_to_opposite_device)
        self._append_log(f"已注册应用内快捷键: {hotkey.text}")

    def _unregister_switch_hotkey(self) -> None:
        if self._global_hotkey is not None:
            self._global_hotkey.unregister()
            self._global_hotkey = None
        if self._app_shortcut is not None:
            self._app_shortcut.setEnabled(False)
            self._app_shortcut.deleteLater()
            self._app_shortcut = None

    def _toggle_log_panel(self) -> None:
        visible = self.log_toggle.isChecked()
        self.log_panel.setVisible(visible)
        self.config["show_log_panel"] = visible
        self.config_store.save_config(self.config)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        }:
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self.show_from_tray()

    def _set_busy(self, busy: bool, status: str | None = None) -> None:
        self.refresh_button.setEnabled(not busy)
        self.primary_button.setEnabled(not busy)
        self.settings_button.setEnabled(not busy)
        self.custom_switch_button.setEnabled(not busy)
        if self._tray_primary_action is not None:
            self._tray_primary_action.setEnabled(not busy and self.primary_button.isEnabled())
        if self._tray_sources_menu is not None:
            for action in self._tray_sources_menu.actions():
                action.setEnabled(not busy)
        if status:
            self._set_status(status)
        if not busy:
            self._update_primary_action()

    def _set_status(self, message: str) -> None:
        self.statusBar().showMessage(message)
        self.logger.info(message)

    def _append_log(self, message: str) -> None:
        self.log_panel.appendPlainText(message)
        self.logger.info(message)

    def _start_worker(
        self,
        task: Callable[[], Any],
        on_finished: Callable[[object], None],
        on_failed: Callable[[str], None],
    ) -> None:
        worker = Worker(task)
        worker.setAutoDelete(False)
        self._active_workers.append(worker)

        def cleanup() -> None:
            if worker in self._active_workers:
                self._active_workers.remove(worker)

        worker.signals.finished.connect(on_finished)
        worker.signals.finished.connect(lambda _result: cleanup())
        worker.signals.failed.connect(on_failed)
        worker.signals.failed.connect(lambda _message: cleanup())
        self.thread_pool.start(worker)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and self.isMinimized() and self._tray_icon is not None:
            QTimer.singleShot(0, self.hide)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close or self._tray_icon is None:
            self._unregister_switch_hotkey()
            super().closeEvent(event)
            return

        event.ignore()
        self.hide()
        self._set_status("已最小化到系统托盘")
