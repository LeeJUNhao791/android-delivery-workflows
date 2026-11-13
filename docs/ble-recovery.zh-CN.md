# BLE 断连恢复验收 SOP

[English](ble-recovery.md) · [返回 README](../README.zh-CN.md)

## 准备两台设备

需要一台带 BLE 外设模式适配器的 Windows 电脑，以及一台支持 BLE 的 Android 设备。Windows 安装 Python 3.11，Android 构建环境见[AAB 上手 SOP](getting-started.zh-CN.md)。Windows 端提供一个递增的 32 位 GATT 计数值，支持读取和通知。

在仓库根目录打开 PowerShell 并执行：

```powershell
python -m venv build/ble-venv
.\build\ble-venv\Scripts\python.exe -m pip install -r examples/ble-peripheral/requirements.txt
.\examples\android-app\gradlew.bat -p examples/android-app :app:testDebugUnitTest :app:assembleDebug
adb install -r examples/android-app/app/build/outputs/apk/debug/app-debug.apk
```

打开 **Android Delivery Demo**，点 **Start BLE session** 并授予权限。Android 6–11 还需打开系统定位以便扫描。测试时保持 App 在前台。

## 断开并恢复连接

在另一个终端运行 Windows 外设。命令会在 30 秒后关闭电脑蓝牙，8 秒后重新开启，退出时恢复原状态。电脑上的其他蓝牙设备也会在测试期间断开。

```powershell
.\build\ble-venv\Scripts\python.exe examples/ble-peripheral/windows_counter.py --interrupt-after 30 --interrupt-for 8 --duration 85
```

1. 断开前确认 App 已显示读取值，且通知值在变化。
2. Windows 终端输出 `RADIO_OFF` 后保持 App 运行，观察断连和重试。
3. 出现 `RADIO_ON` 后，等待 App 自动读取、恢复订阅并收到比断开前更大的通知值。全过程只在开始时点一次 Start，App 应显示 **Recovered in … ms**。
4. 运行 `adb logcat -d -s BleCounter:I` 保存事件日志。恢复耗时从 Android 收到断连回调开始，到恢复订阅后收到第一条通知为止。

只验证初次连接时，可省略时间参数，完成后按 Ctrl+C。如果 App 只显示 `CONNECTING` 和 `RETRY`，记录状态码，先确认设备能稳定连接。

## 验收记录

JVM 测试覆盖重试间隔和恢复计时。[真机记录](ble-evidence.md)分别记录 Pixel 4 XL（Android 11）的完整通过结果和 Kalama（Android 15）的连接失败。
