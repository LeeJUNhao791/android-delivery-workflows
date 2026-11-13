# Kotlin 原生 WebRTC 与 Flutter 桥接

[English](webrtc-native.md) · [浏览器验收 SOP](webrtc-preview.zh-CN.md)

Android 调试版默认接收固定 WebRTC 测试流。要发送真实画面，参照[电脑摄像头测试](webrtc-preview.zh-CN.md#用电脑摄像头测试)。报告记录 EGL 实际渲染帧数和接收端 WebRTC 统计。USB ADB 只传输测试指令和结果，视频通过 Wi-Fi 和现有 UDP 中继传输。

## Kotlin 原生接收

按 [Android 构建 SOP](getting-started.zh-CN.md) 准备环境。以下是仓库根目录下的 PowerShell 命令。

```powershell
.\examples\android-app\gradlew.bat -p examples/android-app :app:assembleDebug
adb -s SERIAL install -r examples/android-app/app/build/outputs/apk/debug/app-debug.apk
```

保持手机解锁，和电脑连接同一 Wi-Fi。安装浏览器 SOP 中的 Node 依赖后运行：

```powershell
node tools/webrtc-preview/run.mjs build/webrtc-native --native --host HOST_WIFI_IP --phone PHONE_WIFI_IP --serial SERIAL
```

ADB 未加入 PATH 时使用 `--adb`。脚本会启动调试页，依次验证正常播放、600 kbit/s 限速和 4 秒中继断流。结果写入 `build/webrtc-native/report.json`，恢复耗时从重开中继转发到实际渲染新画面。

## Flutter 桥接

使用 Flutter 3.41.9、JDK 17、Android SDK Platform 35 和 NDK 27.0.12077973。从仓库根目录执行：

```powershell
cd examples/flutter-preview
flutter pub get
flutter test
flutter build apk --debug --target-platform android-arm64
adb -s SERIAL install -r build/app/outputs/flutter-apk/app-debug.apk
cd ../..
node tools/webrtc-preview/run.mjs build/webrtc-flutter --flutter --host HOST_WIFI_IP --phone PHONE_WIFI_IP --serial SERIAL
```

Flutter 调试页通过平台通道开始、停止和接收状态，播放时打开同一个 Kotlin 原生接收页。在原生页点 **Stop preview** 可结束预览并返回 Flutter，上一轮结果仍可查看。示例覆盖 Android ARM64 调试构建。

## 手机 Wi-Fi 恢复

用 USB 连接并授权 ADB，手机与电脑保持在同一 Wi-Fi。给任一预览命令加上 `--cycle-wifi`，即可运行第四项场景。

```powershell
node tools/webrtc-preview/run.mjs build/webrtc-native-wifi --native --cycle-wifi --host HOST_WIFI_IP --phone PHONE_WIFI_IP --serial SERIAL
node tools/webrtc-preview/run.mjs build/webrtc-flutter-wifi --flutter --cycle-wifi --host HOST_WIFI_IP --phone PHONE_WIFI_IP --serial SERIAL
```

脚本关闭 Wi-Fi，确认画面停止后再开启 Wi-Fi。手机拿回原 IPv4 地址后，脚本先等原 WebRTC 会话恢复，最多等 5 秒。仍停画时，脚本通过 USB 信令重建一次发送端、Kotlin 连接和 UDP 中继，预览页面保持打开。

总预算 20 秒，从脚本检测到原 IPv4 地址开始计时。报告记录脚本观察到新渲染帧的耗时、重建次数和最终使用的连接。超时判失败，JSON 仍会保留 Wi-Fi 和 ICE 状态。

## 真机记录

Pixel 4 XL（Android 11）原生预览首帧 435 ms。正常与限速阶段各采样约 4 秒，分别渲染 16 和 10 帧。限速阶段实测 444 kbit/s，接收端掉帧 1，丢包 71。中继恢复转发后 3177 ms 渲染新画面。

Flutter 调试版在同一台 Pixel 上通过三项场景。首帧 514 ms，正常和限速阶段分别渲染 14 和 6 帧。限速阶段实测 463 kbit/s，接收端掉帧 4，丢包 77。中继恢复后 2438 ms 渲染新画面。点原生页的 **Stop preview** 后，Flutter 页面显示 `Stopped` 和 `Last preview: Preview passed`。

加入自动重建前，同一台 Pixel 4 XL 用两个入口各测了两次 Wi-Fi 开关。每次都确认断开时停画，手机随后拿回原 IPv4 地址，原 WebRTC 会话均等待超时。两组复测结束时 ICE 均为 `failed`。下表记录复测结果，以及 Wi-Fi 恢复后另行启动新会话的首帧。 [Kotlin 基线](evidence/webrtc-kotlin-wifi-baseline.json) · [Flutter 基线](evidence/webrtc-flutter-wifi-baseline.json)

| 入口 | Wi-Fi 关闭到重新启用 | 断开期间最后一秒渲染帧数 | 原 IPv4 恢复后原会话 | 新会话首帧 |
| --- | ---: | ---: | --- | ---: |
| Kotlin 原生 | 4551 ms | 0 | 20 秒内未出画 | 506 ms |
| Flutter → Kotlin | 4500 ms | 0 | 20 秒内未出画 | 1458 ms |

加入自动重建后，同一台 Pixel 的两个入口各连续通过 3 轮。每轮都通过正常播放、限速、UDP 中继断流和手机 Wi-Fi 开关四项检查，Wi-Fi 回连后均重建一次会话并恢复出画。

| 入口 | 通过轮次 | 检测到原 IPv4 后至观察到新画面 |
| --- | ---: | --- |
| Kotlin 原生 | 3/3 | 6183、6379、6271 ms |
| Flutter → Kotlin | 3/3 | 6276、6237、6214 ms |

最后一轮点 **Stop preview** 返回 Flutter 后，页面显示 `Stopped` 和 `Last preview: Preview passed`。逐轮 JSON 见 [v0.5.1 Release](https://github.com/LeeJUNhao791/android-delivery-workflows/releases/tag/v0.5.1)。
