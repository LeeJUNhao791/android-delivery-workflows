# Demo evidence / 演示依据

The PNG is a static visualization of actual preflight reports generated on 2026-11-26, not a screen recording. Input: a locally compiled PageProbe diagnostic app (`local.pageguard.probe`, version `1` / `1.0`), packaged with bundletool and signed with a test key. This is a compiled demo fixture, not a production app or a synthetic ZIP presented as an app. The fixture binary and signing key are not distributed here.

PNG 是 2026-11-26 本轮实际预检报告的静态可视化，不是录屏。输入为本地编译的 PageProbe 诊断应用（`local.pageguard.probe`，版本 `1` / `1.0`），用 bundletool 打包并使用测试密钥签名。它是实际编译的示例夹具，不是生产应用，也不是伪装成应用的合成 ZIP。本仓库不分发该二进制或签名密钥。

| Evidence / 依据 | Value / 值 |
| --- | --- |
| Workflow source base / 工具源码基线 | `1afb8561b2663f753773b2848e84d242286b806a` |
| AAB filename / 文件名 | `pageprobe-arm64-debug.aab` |
| AAB SHA-256 | `05fb2fa8bc6f30f5ed09d8086ca8f8271021ab65dc5e139cacff634a43ba7e8c` |
| bundletool | `1.18.1`; SHA-256 `675786493983787ffa11550bdb7c0715679a44e1643f3ff980a529e9c822595c` |
| Expected certificate / 预期证书 SHA-256 | `50f3e913775e103d86ba11ec4b0a5079d9cd4d39667e41eb3ec55385100a5d55` |
| First contract / 第一份约定 | `PASS`, exit / 退出码 `0`; `6/6` checks / 项通过 |
| Add `previous_version_code: 1` / 增加上一版本 | `FAIL`, exit / 退出码 `1`; `6/7` pass / 项通过; `version_code_increased`: expected / 预期 `> 1`, got / 实际 `1` |
| App source commit / 应用源码提交 | Not supplied / 未提供; `report.commit=null` |

The first run checked structure, application ID, version code, version name, signature, and certificate fingerprint. It had no previous-version comparison. The second run added that check and rejected the unchanged AAB; both reports contain the same AAB hash.

首次检查包结构、包名、版本号、版本名、签名及证书指纹，不包含版本递增比较。第二次增加递增检查后拦截同一个 AAB，两份报告的 AAB 哈希一致。

## Run on a signed AAB / 对签名 AAB 复现检查

Use Python 3.11+, JDK 17 (`JAVA_HOME`), and bundletool 1.18.1. From the repository root, copy the [contract template](../../tools/aab-preflight/release.example.json) to `release.json`. Fill in the app ID, version code/name, and trusted certificate fingerprint of your authorized input. Omit `previous_version_code` for the first run. Replace the AAB and JAR paths below.

准备 Python 3.11+、JDK 17（设置 `JAVA_HOME`）及 bundletool 1.18.1。在仓库根目录，将[约定模板](../../tools/aab-preflight/release.example.json)另存为 `release.json`，填写获准检查的 AAB 的包名、版本及可信证书指纹。首次省略 `previous_version_code`。替换以下 AAB、JAR 路径。

```sh
python tools/aab-preflight/preflight.py path/to/candidate.aab --expect release.json --bundletool path/to/bundletool-all-1.18.1.jar --report-dir build/demo-pass
```

Copy `release.json` to `duplicate-release.json` and set `previous_version_code` equal to the candidate's `version_code`. Run against the same AAB; expect exit `1` and only `version_code_increased` to fail when the other contract fields match.

将 `release.json` 复制为 `duplicate-release.json`，增加 `previous_version_code`，值等于候选包的 `version_code`。再次检查同一个 AAB；当其他约定字段均匹配时，预期退出码为 `1`，仅 `version_code_increased` 失败。

```sh
python tools/aab-preflight/preflight.py path/to/candidate.aab --expect duplicate-release.json --bundletool path/to/bundletool-all-1.18.1.jar --report-dir build/demo-duplicate
```

Each output directory contains `report.json` and `report.md`. The exact local PageProbe fixture is not publicly downloadable here. For a rebuild from public source, follow the [Kotlin demo guide](../getting-started.md); its package, version, key, and hash differ from this capture.

每个输出目录都包含 `report.json`、`report.md`。本轮本地 PageProbe 夹具不在此提供公开下载。如需从公开源码重建，可用[仓库自带 Kotlin 示例](../getting-started.zh-CN.md)；其包名、版本、密钥及哈希与图片中的输入不同。

This run covers offline bundle metadata and signature checks. It did not generate split APKs, install or run an app, or upload to Google Play. An AAB preflight pass alone does not establish 16 KB runtime compatibility.

本轮覆盖离线包信息与签名检查，未生成 APK 分包、安装或运行应用、上传 Google Play。AAB 预检通过不能单独证明 16 KB 运行兼容性。
