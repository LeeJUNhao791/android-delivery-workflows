# Android 应用交付工作流

[English](README.md) · [上手 SOP](docs/getting-started.zh-CN.md) · [CI 运行记录](https://github.com/LeeJUNhao791/android-delivery-workflows/actions/workflows/ci.yml)

在上传前检查签名后的 Android App Bundle。本地和 GitHub Actions 使用同一套预检。

| 检查项 | 报告内容 |
| --- | --- |
| 包结构和应用信息 | 包名、`versionCode` 和 `versionName` |
| 上传签名 | 包内内容的签名和签名证书的 SHA-256 指纹 |
| 版本递增 | `versionCode` 是否高于你提供的上一版本 |
| 构建包追溯 | AAB 的 SHA-256 和你提供的源码提交 |

## 快速开始

准备签名后的 `.aab`、Python 3.11+、JDK 17 和 [bundletool 1.18.1 独立 JAR](https://github.com/google/bundletool/releases/tag/1.18.1)。将[发布配置模板](tools/aab-preflight/release.example.json)另存为 `release.json`，填入预期值。

```sh
python tools/aab-preflight/preflight.py candidate.aab --expect release.json --bundletool path/to/bundletool-all-1.18.1.jar
```

在 `build/preflight/report.md` 查看报告，自动化可以读取同目录的 `report.json`。退出码 `0` 表示通过，`1` 表示候选包被拦截，`2` 表示输入或环境有误。预检可以离线执行，应用商店上传和审核另行完成。

[构建 Kotlin 示例、复现重复版本，或把工作流接到自己的仓库](docs/getting-started.zh-CN.md)。

## BLE 计数器示例

Kotlin 示例扫描 Windows BLE 外设，读取计数、订阅通知，并在断连后重试。查看 [BLE 验收 SOP](docs/ble-recovery.zh-CN.md)和[真机记录](docs/ble-evidence.md)。Pixel 4 XL 自动恢复订阅并在 11.643 秒内收到新通知。Kalama 首次连接返回 GATT 133。

## ADB 升级与安装诊断

构建同一个示例的两版 APK，检查覆盖安装后本地记录是否保留，并诊断低版本安装被拦截的原因。Kalama（Android 15）实测从版本 1 升到 2 后记录保留，降级安装被系统拦截。[ADB 升级验收 SOP](docs/adb-upgrade.zh-CN.md)

## WebRTC 弱网预览验收

用固定视频源跑正常、限速和断网恢复场景，记录首帧、接收端统计和恢复耗时。[上手 SOP](docs/webrtc-preview.zh-CN.md)

## 原生预览与 Flutter 桥接

用 Kotlin 调试页运行同一组 WebRTC 场景，也可通过 Flutter 平台通道启动原生接收页。[原生预览与桥接 SOP](docs/webrtc-native.zh-CN.md)

相关项目包括 [Android SDK Toolkit](https://github.com/LeeJUNhao791/android-sdk-toolkit) 的 SDK/JNI 交付、[AI App Regression](https://github.com/LeeJUNhao791/ai-app-regression) 的跨端回归，以及 [GLB Dimension Check](https://github.com/LeeJUNhao791/glb-dimension-check) 的静态 3D 尺寸检查。

[MIT 许可证](LICENSE)
