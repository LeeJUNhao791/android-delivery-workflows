# AAB 发布预检上手 SOP

[English](getting-started.md) · [返回 README](../README.zh-CN.md)

## 构建并验收 Kotlin 示例

安装 Python 3.11+、JDK 17、Android SDK Platform 35 和 Build Tools 35.0.0。将 `JAVA_HOME` 和 `ANDROID_HOME` 指向本机的 JDK 和 Android SDK，并下载 [bundletool 独立 JAR](https://github.com/google/bundletool/releases/tag/1.18.1)。

在仓库根目录运行。Windows PowerShell 下，把第一条命令的脚本改为 `.\examples\android-app\gradlew.bat`。

```sh
./examples/android-app/gradlew -p examples/android-app :app:bundleRelease
python examples/android-app/prepare-demo.py
python tools/aab-preflight/preflight.py build/demo/candidate.aab --expect build/demo/release.json --bundletool path/to/bundletool-all-1.18.1.jar --report-dir build/pass
python tools/aab-preflight/preflight.py build/demo/candidate.aab --expect build/demo/repeat-version.json --bundletool path/to/bundletool-all-1.18.1.jar --report-dir build/repeat-version
```

第一次预检通过，版本 3 高于上个版本 2。第二次检查同一个包，版本 3 与配置里的上一版本重复，预检拦截。对照两个目录的 `report.md`，包的 SHA-256 一致。示例签名密钥在每次运行时临时生成。

在 [GitHub Actions 运行记录](https://github.com/LeeJUNhao791/android-delivery-workflows/actions/workflows/ci.yml) 中，成功的运行会留下 `aab-preflight-report` 和 `repeat-version-report` 两份报告附件。

## 检查自己的签名包

复制[发布配置模板](../tools/aab-preflight/release.example.json)，填入包名、预期版本号、版本名称和上传证书的 SHA-256 指纹。指纹从你信任的上传证书获取，填写 64 位十六进制字符。首次发布可以省略 `previous_version_code`，有上一版本时填写要比较的版本号。本地运行时可以用 `--commit` 填入构建对应的源码提交。

## 接入自己的 GitHub Actions

构建任务把签名后的包命名为 `candidate.aab`，与 `release.json` 一起上传到同一个附件根目录。然后在本次运行中调用可复用工作流。下面假设你的构建任务叫 `build`。

```yaml
# 放在 build 任务的最后
- uses: actions/upload-artifact@v7
  with:
    name: release-candidate
    path: |
      out/candidate.aab
      out/release.json
    if-no-files-found: error
```

```yaml
# 放在 jobs 下
release-preflight:
  needs: build
  permissions:
    contents: read
  uses: LeeJUNhao791/android-delivery-workflows/.github/workflows/aab-preflight.yml@v0.8.0
  with:
    artifact-name: release-candidate
```

在工作流附件里查看 `aab-preflight-report`。如果 AAB 检查失败，预检任务也会失败。依赖它的任务在 GitHub Actions 默认条件下只会在预检通过后运行。

打开本次运行的 **Summary** 页即可查看 Markdown 报告。要在自己的仓库验证两种结果，先用正确的发布配置运行一次，再把 `previous_version_code` 改成候选包的 `versionCode` 并重跑。如果预检未生成报告，查看 **Check candidate** 步骤的日志。

### 启用 ARM64 分包对齐检查

在上方示例的 `with` 下添加 `check-arm64-16kb: true`。该参数默认为 `false`。发布元数据预检通过后，bundletool 为 ARM64、API 35、480 dpi、`en-US` 的模拟目标生成 APK，工作流逐个检查 ELF 和 ZIP 对齐。校验失败或 APK 无法校验会使任务失败。没有适用原生库的 APK 记录为 `not_applicable`。

从同一个预检附件下载 `arm64-16kb/summary.json` 和每个 APK 的 JSON 报告，任务失败时也会保留。任务日志会列出有问题的 APK 和 SO。该项检查覆盖上述 bundletool 目标的静态对齐情况，设备兼容性和 Google Play 实际交付需另行验证。

#### MediaPipe 签名 Debug AAB 示例

1. 使用固定版本的 MediaPipe 图像分类样例。在 `examples/image_classification/android` 目录运行 `./gradlew --no-configuration-cache :app:verifyModels :app:bundleDebug`。构建环境为 JDK 17、Android SDK Platform 36、Build Tools 36.0.0 和 NDK 27.0.12077973。 [上游固定版本](https://github.com/google-ai-edge/mediapipe-samples/tree/46d60d66baf21ae91977c488ea0875f0e13c4d2b/examples/image_classification/android)
2. 将 `app/build/outputs/bundle/debug/app-debug.aab` 命名为 `candidate.aab`，与 `release.json` 一起上传到同一个附件。配置中填写样例的包名、版本号和版本名称，以及临时 Debug 签名证书的 SHA-256 指纹。
3. 调用 `aab-preflight.yml@v0.8.0` 并设置 `check-arm64-16kb: true`。在自己的仓库使用完整调用示例时，复制工作流并设置 `push` 触发分支。 [调用方工作流](https://github.com/LeeJUNhao791/android-mcp-inspector/blob/47b6b661c883af8515039d9d01a284adc1ba9516/.github/workflows/mediapipe-aab-16kb-proof.yml) · [本次执行的可复用工作流](https://github.com/LeeJUNhao791/android-delivery-workflows/blob/552883397325c56ddb79d45af8676c7456a2a225/.github/workflows/aab-preflight.yml)

GitHub Actions 运行中，AAB 的 6 项预检全部通过。在 ARM64/API 35 目标上，`base-arm64_v8a.apk` 中的 4 个原生库均通过 16 KiB ELF 和 ZIP 对齐检查。`base-master.apk`、`base-en.apk` 和 `base-xxhdpi.apk` 没有原生库，均记为 `not_applicable`。可在运行的 **Summary** 页查看结果，或在 `mediapipe-aab-16kb-report` 附件保留期间查看其中的 `report.json` 和 `arm64-16kb/summary.json`。 [成功运行记录](https://github.com/LeeJUNhao791/android-mcp-inspector/actions/runs/45357346927)

本次验证覆盖这个签名 Debug AAB 和生成分包的静态对齐。Release 构建、设备运行和 Google Play 交付需另行验证。
