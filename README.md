# Android Delivery Workflows

[简体中文](README.zh-CN.md) · [Quick start](docs/getting-started.md) · [CI runs](https://github.com/LeeJUNhao791/android-delivery-workflows/actions/workflows/ci.yml)

Check a signed Android App Bundle against your release expectations before upload. Run the same check locally or in GitHub Actions.

| Check | What the report shows |
| --- | --- |
| Bundle structure and app identity | Package name, `versionCode`, and `versionName` |
| Upload signature | Signed content and the actual SHA-256 fingerprint of the signing certificate |
| Version progression | Whether `versionCode` exceeds the previous version you provide |
| Candidate identity | The AAB's SHA-256 and the source commit when supplied |

## Quick start

Bring a signed `.aab`, Python 3.11+, JDK 17, and the [bundletool 1.18.1 standalone JAR](https://github.com/google/bundletool/releases/tag/1.18.1). Copy the [release contract template](tools/aab-preflight/release.example.json) to `release.json` and enter the expected values.

```sh
python tools/aab-preflight/preflight.py candidate.aab --expect release.json --bundletool path/to/bundletool-all-1.18.1.jar
```

Open `build/preflight/report.md` for the review and `build/preflight/report.json` for automation. Exit codes are `0` for pass, `1` for rejected bundles, and `2` for input or setup errors. The preflight runs offline and covers the checks shown above. Store upload and review happen separately.

[Build the Kotlin demo, reproduce a duplicate version, or add the workflow to your repository](docs/getting-started.md).

## Roadmap

- BLE connection, status reads, and recovery on an Android phone and development board
- ADB diagnostics and an upgrade test that verifies local data survives
- Weak-network WebRTC preview checks and a Flutter-to-Kotlin bridge example

Related projects include [Android SDK Toolkit](https://github.com/LeeJUNhao791/android-sdk-toolkit) for SDK/JNI delivery, [AI App Regression](https://github.com/LeeJUNhao791/ai-app-regression) for cross-platform regression, and [GLB Dimension Check](https://github.com/LeeJUNhao791/glb-dimension-check) for static 3D assets.

[MIT License](LICENSE)
