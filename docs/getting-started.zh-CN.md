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

第一次预检通过，版本 2 高于上个版本 1。第二次检查同一个包，版本 2 与配置里的上一版本重复，预检拦截。对照两个目录的 `report.md`，包的 SHA-256 一致。示例签名密钥在每次运行时临时生成。

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
  uses: LeeJUNhao791/android-delivery-workflows/.github/workflows/aab-preflight.yml@v0.1.0
  with:
    artifact-name: release-candidate
```

在工作流附件里查看 `aab-preflight-report`。如果 AAB 检查失败，预检任务也会失败。依赖它的任务在 GitHub Actions 默认条件下只会在预检通过后运行。
