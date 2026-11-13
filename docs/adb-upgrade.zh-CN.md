# ADB 覆盖升级与安装诊断

[English](adb-upgrade.md) · [返回 README](../README.zh-CN.md)

升级示例使用独立包名 `io.github.leejunhao791.deliverydemo.upgrade`。准备 Python 3.11+、JDK 17、Android SDK Platform 35、Build Tools 35.0.0 和 Platform Tools。构建环境可参照 [AAB 上手 SOP](getting-started.zh-CN.md)。

## 构建两版 APK

在仓库根目录运行。以下为 PowerShell 示例，先将 `ANDROID_HOME` 和 `JAVA_HOME` 指向本机的 SDK 与 JDK。

```powershell
.\examples\android-app\gradlew.bat -p examples/android-app :upgrade-demo:assembleBaselineDebug :upgrade-demo:assembleCandidateDebug
```

`baselineDebug` 和 `candidateDebug` 使用同一调试签名，`versionCode` 分别为 1 和 2。

## 真机验收

连接测试机并授权 USB 调试。先运行 `adb devices -l` 取得序列号。使用未安装 Upgrade Demo 的设备。脚本会拦截已存在的示例安装，整个过程保留其他 App 的数据。

```powershell
$sdk = $env:ANDROID_HOME
$apk = 'examples/android-app/upgrade-demo/build/outputs/apk'
python tools/adb-upgrade/upgrade.py verify `
  --serial '<设备序列号>' `
  --adb "$sdk/platform-tools/adb.exe" `
  --aapt "$sdk/build-tools/35.0.0/aapt.exe" `
  --apksigner-jar "$sdk/build-tools/35.0.0/lib/apksigner.jar" `
  --java "$env:JAVA_HOME/bin/java.exe" `
  --baseline "$apk/baseline/debug/upgrade-demo-baseline-debug.apk" `
  --candidate "$apk/candidate/debug/upgrade-demo-candidate-debug.apk"
```

脚本先核对两版 APK 的包名、版本和证书，再安装版本 1，通过 `run-as` 在示例 App 私有目录写入本次验收标记。覆盖安装版本 2 后，脚本启动新版并读取同一标记。最后尝试装回版本 1，要求系统返回 `INSTALL_FAILED_VERSION_DOWNGRADE`，并再次确认设备上的版本和标记未变。

查看 `build/adb-upgrade/report.json`。通过返回 0，验收失败返回 1，输入或环境问题返回 2。运行会把示例留在设备上以便检查。复测前可在测试机的应用设置里手动卸载 **Upgrade Demo**，该操作会删除示例数据。

## 真机结果

在 Kalama（Android 15，API 35，ARM64）上运行，12 个步骤全部通过。版本 1 写入的私有文件在覆盖安装版本 2 后仍可读取，新版界面也显示了同一条记录。随后尝试安装版本 1，系统返回：

```text
INSTALL_FAILED_VERSION_DOWNGRADE: Downgrade detected: Update version code 1 is older than current 2
```

拦截后仍是版本 2，记录内容一致。本次测试使用示例的调试签名和文件存储。

Pixel 4 XL（Android 11，API 30，ARM64）使用与 Kalama 相同的两版 APK，12 个步骤全部通过。版本 2 界面显示版本 1 写入的同一条记录。系统返回同一个降级错误码，拦截后版本和记录保持一致。

## 分析已有安装日志

```powershell
python tools/adb-upgrade/upgrade.py diagnose examples/android-app/upgrade-demo/downgrade.example.txt
```

这条命令只读取文件。输出包含 Android 返回的错误码、原始日志和对应排查建议。仓库中的日志是可复现的诊断输入样例。
