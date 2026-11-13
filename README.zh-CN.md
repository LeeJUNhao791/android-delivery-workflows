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

## 后续方向

- BLE 真机连接、状态读取与断连恢复
- ADB 诊断和覆盖升级数据保留验收
- WebRTC 弱网预览验收和 Flutter 调用 Kotlin 的桥接示例

相关项目包括 [Android SDK Toolkit](https://github.com/LeeJUNhao791/android-sdk-toolkit) 的 SDK/JNI 交付、[AI App Regression](https://github.com/LeeJUNhao791/ai-app-regression) 的跨端回归，以及 [GLB Dimension Check](https://github.com/LeeJUNhao791/glb-dimension-check) 的静态 3D 尺寸检查。

[MIT 许可证](LICENSE)
