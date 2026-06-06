# 显示器输入源切换软件设计文档

## 1. 背景与目标

本软件用于在桌面端提供一个带 UI 的工具，帮助用户快速切换外接显示器的输入源，例如 DisplayPort、USB-C、HDMI1、HDMI2 等。

核心切换能力基于用户提供方案中的 Python `monitorcontrol` 库实现。该库通过 DDC/CI 与显示器通信，可在 Windows、macOS、Linux 上使用同一套 Python 代码访问显示器能力、读取当前输入源并切换输入源。

### 目标

- 提供图形界面，用户无需使用命令行即可切换显示器输入源。
- 自动扫描可控制的显示器，并展示显示器列表。
- 显示当前输入源，支持手动刷新。
- 支持常见输入源快捷切换：DP、USB-C、HDMI1、HDMI2、DVI。
- 支持 Windows 和 Mac 两端同时安装运行：Windows 端点击切换后显示器切到 Mac 输入源，Mac 端点击切换后显示器切回 Windows 输入源。
- 支持用户自定义输入源代码，解决不同品牌显示器 VCP 输入源值不一致的问题。
- 提供清晰的状态反馈和错误提示。
- 后续可分别打包成 Windows 和 macOS 桌面应用。

### 非目标

- 不实现远程控制或多设备同步。两端应用不需要互相联网通信，只负责通过当前系统能访问到的显示器 DDC/CI 通道发送输入源切换命令。
- 不实现显示器亮度、对比度等其他 DDC/CI 功能，除非后续扩展。
- 不保证所有显示器都可被控制；显示器必须支持并启用 DDC/CI。

## 2. 技术选型

### 语言

- Python 3.10+

### 核心依赖

- `monitorcontrol`
  - 用于枚举显示器、读取当前输入源、设置输入源。

### UI 框架

建议使用 `PySide6`。

选择理由：

- 原生桌面应用体验比简单脚本更完整。
- 支持 Windows 和 macOS 桌面打包。
- 组件体系成熟，适合显示器列表、表单、按钮、状态栏等常规工具界面。
- 后续可扩展托盘图标、快捷键、配置页面。

### 打包工具

- `PyInstaller`
  - 用于生成 Windows `.exe` 和 macOS `.app`。

## 3. 功能范围

### 3.1 显示器扫描

启动时自动调用：

```python
from monitorcontrol import get_monitors

monitors = get_monitors()
```

扫描结果展示在 UI 左侧或顶部列表中。每个显示器展示：

- 显示器序号，例如 `Monitor 1`
- 可读名称，如果库或系统能提供
- 当前输入源代码，例如 `0x0F`
- 状态：可用、读取失败、切换失败

如果没有发现可控制显示器，界面显示空状态并提示检查：

- 显示器是否支持 DDC/CI
- 显示器 OSD 菜单中 DDC/CI 是否已启用
- 当前线缆或显卡驱动是否支持 DDC/CI

### 3.2 当前输入源读取

选中显示器后，应用调用：

```python
with monitor:
    current = monitor.get_input_source()
```

读取成功后：

- 显示原始输入源代码，例如 `0x12`
- 如果该代码在配置映射中存在，显示友好名称，例如 `USB-C`

读取失败时：

- 保留显示器列表
- 在状态栏显示失败原因
- 不阻塞整个程序

### 3.3 输入源切换

用户在 UI 中点击输入源按钮后，应用调用：

```python
with monitor:
    monitor.set_input_source(target_code)
```

默认输入源映射：

| 名称 | VCP 值 | 说明 |
| --- | --- | --- |
| DP | `0x0F` | DisplayPort |
| USB-C | `0x12` | USB-C / Type-C，具体取决于显示器 |
| HDMI1 | `0x10` | HDMI 1 |
| HDMI2 | `0x11` | HDMI 2 |
| DVI | `0x03` | DVI |

### 3.4 双端互切模式

软件的主要使用场景是同一台显示器同时连接 Windows 和 Mac，两台电脑上都安装并运行本软件。

示例连接方式：

| 设备 | 显示器输入源 | VCP 值示例 |
| --- | --- | --- |
| Windows 主机 | DisplayPort | `0x0F` |
| Mac 主机 | USB-C | `0x12` |

在这个场景下：

- Windows 当前有画面时，用户在 Windows 端点击 `切换到 Mac`，应用向显示器发送 `USB-C` 对应的 VCP 值，例如 `0x12`。
- 显示器切到 USB-C 后，Windows 画面消失，显示器显示 Mac 的 UI。
- 用户在 Mac 端点击 `切换到 Windows`，应用向显示器发送 `DP` 对应的 VCP 值，例如 `0x0F`。
- 显示器切到 DP 后，Mac 画面消失，显示器显示 Windows 的 UI。

该模式不要求 Windows 和 Mac 互相发现、互相连接或共享状态。每一端只需要知道：

- 本机身份：`windows` 或 `mac`
- Windows 对应的显示器输入源代码
- Mac 对应的显示器输入源代码
- 默认点击按钮时要切换到哪一端

因此 UI 的主操作不应只暴露技术输入源名称，而应提供面向场景的按钮：

- Windows 端主按钮：`切换到 Mac`
- Mac 端主按钮：`切换到 Windows`

高级设置中仍保留 DP、USB-C、HDMI 等原始输入源切换能力，便于调试和兼容更多接线方式。

切换成功后：

- 状态栏提示已发送切换命令
- 延迟短暂时间后尝试刷新当前输入源
- 如果切换后本机失去显示器通信能力，视为符合预期，不弹出崩溃级错误

切换失败后：

- 显示错误提示
- 不修改 UI 中记录的当前输入源
- 允许用户重试或修改输入源代码

### 3.5 自定义输入源代码

由于不同显示器的输入源 VCP 值可能不同，应用需要提供配置入口：

- 新增输入源名称
- 修改输入源代码
- 删除自定义输入源
- 恢复默认映射
- 设置本机身份：Windows 端或 Mac 端
- 设置 Windows 对应的输入源
- 设置 Mac 对应的输入源

配置示例：

```json
{
  "local_device": "windows",
  "device_targets": {
    "windows": "DP",
    "mac": "USB-C"
  },
  "input_sources": {
    "DP": "0x0F",
    "USB-C": "0x12",
    "HDMI1": "0x10",
    "HDMI2": "0x11",
    "DVI": "0x03"
  }
}
```

配置文件建议存储在用户目录：

- Windows: `%APPDATA%/MonitorControl/config.json`
- macOS: `~/Library/Application Support/MonitorControl/config.json`
- Linux: `~/.config/MonitorControl/config.json`

开发阶段也可先使用项目内 `config.json`，便于调试。

### 3.6 批量切换

第一版建议支持两种模式：

- 单显示器模式：只切换当前选中的显示器。
- 全部显示器模式：对所有扫描到的显示器发送同一个输入源切换命令。

UI 中通过切换开关或复选框控制：

- `仅当前显示器`
- `全部显示器`

默认使用 `仅当前显示器`，降低误操作风险。

### 3.7 日志与反馈

应用应提供简洁的运行反馈：

- 状态栏显示最后一次操作结果。
- 日志面板可折叠，展示最近操作。
- 关键异常写入本地日志文件，便于排查。

日志内容包括：

- 启动时间
- 扫描到的显示器数量
- 当前输入源读取结果
- 本机身份和目标设备，例如 `local=windows target=mac`
- 切换目标输入源
- 异常堆栈摘要

## 4. UI 设计

### 4.1 主界面布局

主界面采用工具型布局，不做营销页或复杂装饰。

推荐结构：

```text
+----------------------------------------------------------------+
| Monitor Control                                       [刷新]   |
+----------------------+-----------------------------------------+
| 显示器列表           | 当前显示器详情                          |
|                      |                                         |
| Monitor 1            | 当前输入源: DP (0x0F)                  |
| Monitor 2            | 本机: Windows                          |
|                      |                                         |
|                      | [切换到 Mac]                           |
|                      | 目标输入源: USB-C (0x12)               |
|                      |                                         |
|                      | 模式: [仅当前] [全部]                  |
|                      |                                         |
|                      | 高级: [DP] [USB-C] [HDMI1] [HDMI2]     |
|                      | 自定义代码: [0x12] [切换]              |
+----------------------+-----------------------------------------+
| 状态: 已发送切换到 Mac: USB-C (0x12)                 |
+----------------------------------------------------------------+
```

### 4.2 关键控件

- 刷新按钮：重新扫描显示器并读取当前输入源。
- 显示器列表：展示所有可控制显示器。
- 主切换按钮：根据本机身份显示 `切换到 Mac` 或 `切换到 Windows`。
- 本机身份选择：Windows / Mac，用于决定主切换按钮的目标。
- 设备输入源映射：配置 Windows 对应哪个显示器输入源，Mac 对应哪个显示器输入源。
- 高级输入源按钮组：DP、USB-C、HDMI1、HDMI2、DVI。
- 自定义输入框：允许输入十六进制 VCP 值。
- 模式切换：当前显示器 / 全部显示器。
- 配置按钮：打开输入源映射配置窗口。
- 状态栏：展示操作结果。

### 4.3 状态设计

| 状态 | UI 表现 |
| --- | --- |
| 正在扫描 | 刷新按钮禁用，显示加载状态 |
| 无显示器 | 显示空状态提示 |
| 读取成功 | 当前输入源正常展示 |
| 读取失败 | 当前输入源显示未知，状态栏展示错误 |
| 切换中 | 目标按钮进入 loading 或禁用 |
| 切换成功 | 状态栏显示成功，尝试刷新当前输入源 |
| 切换后失去当前画面 | 状态栏记录已发送命令，不要求继续刷新成功 |
| 切换失败 | 状态栏显示失败原因 |

## 5. 程序架构

### 5.1 模块划分

建议目录结构：

```text
MonitorControl/
  README.md
  DESIGN.md
  requirements.txt
  src/
    monitor_control_app/
      __init__.py
      main.py
      ui/
        __init__.py
        main_window.py
        settings_dialog.py
      core/
        __init__.py
        monitor_service.py
        input_sources.py
        device_targets.py
        config_store.py
        logging_setup.py
      models/
        __init__.py
        monitor_info.py
```

### 5.2 核心职责

#### `monitor_service.py`

封装所有 `monitorcontrol` 调用，避免 UI 直接依赖底层库。

主要方法：

- `list_monitors() -> list[MonitorInfo]`
- `get_current_input(monitor_id: str) -> int`
- `set_input(monitor_id: str, input_code: int) -> None`
- `set_input_for_all(input_code: int) -> list[OperationResult]`

#### `input_sources.py`

管理输入源名称和 VCP 值之间的映射。

主要方法：

- `get_default_sources()`
- `parse_input_code(value: str) -> int`
- `format_input_code(value: int) -> str`
- `find_label_by_code(value: int) -> str | None`

#### `device_targets.py`

管理 Windows / Mac 设备身份和它们对应的显示器输入源。

主要方法：

- `get_opposite_device(local_device: str) -> str`
- `get_target_source_for_device(device_name: str, config) -> str`
- `resolve_target_input_code(device_name: str, config) -> int`
- `get_primary_action_label(local_device: str) -> str`

#### `config_store.py`

负责读取和写入配置文件。

主要方法：

- `load_config()`
- `save_config(config)`
- `get_config_path()`

#### `main_window.py`

负责主界面展示和用户交互。

不直接访问 `monitorcontrol`，只调用 `MonitorService`。

### 5.3 数据模型

```python
from dataclasses import dataclass

@dataclass
class MonitorInfo:
    id: str
    index: int
    name: str
    current_input: int | None
    error: str | None = None
```

```python
from dataclasses import dataclass

@dataclass
class OperationResult:
    monitor_id: str
    success: bool
    message: str
```

```python
from dataclasses import dataclass

@dataclass
class DeviceTarget:
    device_name: str
    source_label: str
    input_code: int
```

## 6. 线程模型

DDC/CI 调用可能阻塞 UI，因此扫描、读取和切换操作不应直接在主线程执行。

建议：

- UI 主线程只负责渲染和响应用户操作。
- 使用 `QThread` 或 `QRunnable + QThreadPool` 执行显示器操作。
- 操作完成后通过 Qt signal 更新 UI。

需要异步执行的操作：

- 扫描显示器
- 读取当前输入源
- 切换输入源
- 批量切换全部显示器

切换到对端设备后，刷新当前输入源只能作为尽力而为操作。实现上应先记录“切换命令已发送”，再异步尝试读取；读取失败不覆盖已发送成功的状态。

## 7. 异常处理

常见失败场景：

- 未安装 `monitorcontrol`
- 没有发现显示器
- 显示器不支持 DDC/CI
- 显示器 DDC/CI 未开启
- 当前输入源通道无法继续通信
- 输入源 VCP 值不适配该显示器
- 系统权限、驱动或线缆导致通信失败

处理原则：

- 单个显示器失败不影响其他显示器。
- 用户输入非法十六进制代码时，在 UI 内即时提示。
- 后台异常写入日志，UI 展示简短可理解的信息。
- 切换输入源后如果显示器断开当前链路，应用不把它视为程序崩溃。

## 8. 配置与默认值

默认配置：

```json
{
  "local_device": "windows",
  "mode": "single",
  "device_targets": {
    "windows": "DP",
    "mac": "USB-C"
  },
  "input_sources": {
    "DP": "0x0F",
    "USB-C": "0x12",
    "HDMI1": "0x10",
    "HDMI2": "0x11",
    "DVI": "0x03"
  },
  "refresh_after_switch_ms": 1500,
  "show_log_panel": false
}
```

Windows 端和 Mac 端可以使用不同的本地配置。

Windows 端示例：

```json
{
  "local_device": "windows",
  "device_targets": {
    "windows": "DP",
    "mac": "USB-C"
  }
}
```

Mac 端示例：

```json
{
  "local_device": "mac",
  "device_targets": {
    "windows": "DP",
    "mac": "USB-C"
  }
}
```

两端的 `device_targets` 应保持一致，`local_device` 不同。这样 Windows 端主按钮会解析为 `切换到 Mac -> USB-C -> 0x12`，Mac 端主按钮会解析为 `切换到 Windows -> DP -> 0x0F`。

配置加载策略：

1. 如果用户配置文件存在，读取用户配置。
2. 如果不存在，创建默认配置。
3. 如果配置损坏，备份损坏文件并恢复默认配置。
4. 如果未设置 `local_device`，首次启动时要求用户在设置页选择 Windows 或 Mac。
5. 如果目标设备没有配置输入源，主切换按钮禁用并提示进入设置。

## 9. 安装与运行

开发环境安装。

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install monitorcontrol PySide6
python -m monitor_control_app
```

macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install monitorcontrol PySide6
python -m monitor_control_app
```

建议 `requirements.txt`：

```text
monitorcontrol
PySide6
pyinstaller
```

## 10. 打包方案

打包需要分别在目标平台执行。Windows 版本在 Windows 上构建，macOS 版本在 macOS 上构建；PyInstaller 不能稳定跨平台生成另一套系统的原生应用包。

### 10.1 Windows 打包

Windows 打包命令示例：

```bash
pyinstaller --noconsole --name MonitorControl src/monitor_control_app/main.py
```

打包产物：

```text
dist/
  MonitorControl/
    MonitorControl.exe
```

Windows 后续可增加：

- 应用图标
- 版本信息
- 安装包，例如 Inno Setup 或 NSIS
- 开机自启动选项
- 系统托盘入口

### 10.2 macOS 打包

macOS 打包命令示例：

```bash
pyinstaller --windowed --name MonitorControl src/monitor_control_app/main.py
```

打包产物：

```text
dist/
  MonitorControl.app
```

如果需要生成 `.dmg`，可在 `.app` 生成后使用 `create-dmg` 或类似工具：

```bash
create-dmg dist/MonitorControl.app dist/
```

macOS 后续可增加：

- `.icns` 应用图标
- `Info.plist` 应用元数据
- `.dmg` 安装镜像
- 开发者签名
- Notarization 公证
- 系统托盘菜单栏入口

### 10.3 平台发布注意事项

- Windows 和 macOS 应分别验证真实显示器切换能力，不能只验证 UI 启动。
- macOS 上 DDC/CI 能力可能受显示器、接口、系统版本和底层 I2C/DDC 访问限制影响，需要在 README 中单独说明兼容性。
- 如果 macOS 打包后无法访问显示器，需要优先确认源码运行是否可用，再排查打包缺失依赖。
- 发布文件命名建议包含平台和版本，例如 `MonitorControl-1.0.0-windows-x64.exe`、`MonitorControl-1.0.0-macos-arm64.dmg`。

## 11. 测试计划

### 11.1 单元测试

重点测试：

- 输入源代码解析
- 配置文件读写
- 配置损坏恢复
- 输入源标签和代码互转
- 本机身份到目标设备的解析，例如 Windows -> Mac、Mac -> Windows
- 目标设备到输入源 VCP 值的解析

### 11.2 集成测试

在真实显示器环境下测试：

- 是否能扫描显示器
- 是否能读取当前输入源
- DP、USB-C、HDMI1、HDMI2 是否能正确切换
- 切换到另一个输入源后程序是否稳定
- Windows 端点击 `切换到 Mac` 后，显示器切到 Mac 对应输入源
- Mac 端点击 `切换到 Windows` 后，显示器切到 Windows 对应输入源
- 切换后当前系统失去画面或读取失败时，程序记录状态但不崩溃

### 11.3 UI 测试

手动验证：

- 无显示器时界面不崩溃
- 扫描时按钮状态正确
- 切换中不会重复提交
- 错误信息可读
- 自定义代码输入校验正常
- 首次启动可以设置本机身份
- Windows 端主按钮文案为 `切换到 Mac`
- Mac 端主按钮文案为 `切换到 Windows`
- 目标输入源未配置时主按钮禁用

## 12. 开发里程碑

### M1：最小可用版本

- 创建 Python 项目结构。
- 集成 `monitorcontrol`。
- 实现显示器扫描。
- 实现主窗口。
- 实现 DP、USB-C、HDMI1、HDMI2、DVI 切换按钮。
- 实现本机身份配置和 `切换到对端设备` 主按钮。
- 实现状态栏反馈。

### M2：配置化版本

- 支持配置文件。
- 支持自定义输入源代码。
- 支持恢复默认配置。
- 增加日志文件。

### M3：稳定性增强

- 后台线程执行 DDC/CI 操作。
- 增强异常提示。
- 支持全部显示器批量切换。
- 补充单元测试。

### M4：发布版本

- 使用 PyInstaller 分别打包 Windows 和 macOS 版本。
- 添加应用图标和版本信息。
- 编写 README 使用说明。
- 在 Windows 和 macOS 真实显示器环境验证。

## 13. 风险与限制

- DDC/CI 支持取决于显示器、线缆、显卡驱动和系统环境。
- 不同品牌显示器的输入源代码可能不一致，必须允许用户自定义。
- 切换到某些输入源后，当前连接链路可能断开，程序无法立即读取新的状态。
- Windows 端切到 Mac 后，Windows 可能无法继续显示 UI；Mac 端切回 Windows 同理。这是核心使用场景的一部分，不应被视为异常退出。
- 双端互切依赖两台电脑都能通过各自连接向显示器发送 DDC/CI 命令；如果某个输入源不支持 DDC/CI 回写，另一端可能无法切回。
- 多显示器环境下，显示器枚举顺序可能变化，需要后续考虑稳定标识。
- macOS 和 Linux 的底层权限或驱动依赖可能需要额外安装说明。
- macOS 应用签名和公证会增加发布复杂度；未签名应用可能被 Gatekeeper 拦截。

## 14. 后续扩展

- 系统托盘快速切换。
- 全局快捷键。
- 针对不同显示器保存不同输入源映射。
- 启动时自动切换到指定输入源。
- 亮度、对比度、音量等 DDC/CI 控制。
- 导入和导出配置。
