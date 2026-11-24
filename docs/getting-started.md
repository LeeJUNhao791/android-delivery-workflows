# Run the AAB preflight

[简体中文](getting-started.zh-CN.md) · [README](../README.md)

## Build and check the Kotlin example

Install Python 3.11+, JDK 17, Android SDK Platform 35, and Build Tools 35.0.0. Set `JAVA_HOME` and `ANDROID_HOME` to the JDK and SDK directories. Download the [bundletool standalone JAR](https://github.com/google/bundletool/releases/tag/1.18.1).

Run from the repository root. On Windows PowerShell, use `.\examples\android-app\gradlew.bat` in the first command.

```sh
./examples/android-app/gradlew -p examples/android-app :app:bundleRelease
python examples/android-app/prepare-demo.py
python tools/aab-preflight/preflight.py build/demo/candidate.aab --expect build/demo/release.json --bundletool path/to/bundletool-all-1.18.1.jar --report-dir build/pass
python tools/aab-preflight/preflight.py build/demo/candidate.aab --expect build/demo/repeat-version.json --bundletool path/to/bundletool-all-1.18.1.jar --report-dir build/repeat-version
```

The first preflight passes because version 3 exceeds 2. The second rejects the same AAB because version 3 does not exceed 3. Compare `build/pass/report.md` and `build/repeat-version/report.md`. Both report the same bundle hash. The demo uses a disposable key generated at run time.

GitHub Actions uploads the successful and rejected reports as `aab-preflight-report` and `repeat-version-report` on each successful [CI run](https://github.com/LeeJUNhao791/android-delivery-workflows/actions/workflows/ci.yml).

## Check your own signed bundle

Copy the [release contract template](../tools/aab-preflight/release.example.json). Set the application ID, intended version code and version name, and expected upload certificate fingerprint as 64 hexadecimal digits without separators. Use the fingerprint from your trusted upload certificate. If there is no previous release, omit `previous_version_code`. Otherwise provide the last version code you want the tool to compare against. Use `--commit` to supply the source commit when running locally.

## Call the workflow from your repository

Upload your signed AAB as `candidate.aab` and your contract as `release.json` at the root of a single artifact from your build job. Then call the reusable workflow in the same run. In this example your build job is named `build`.

```yaml
# Steps at the end of your build job
- uses: actions/upload-artifact@v7
  with:
    name: release-candidate
    path: |
      out/candidate.aab
      out/release.json
    if-no-files-found: error
```

```yaml
# Additional job under jobs
release-preflight:
  needs: build
  permissions:
    contents: read
  uses: LeeJUNhao791/android-delivery-workflows/.github/workflows/aab-preflight.yml@v0.8.0
  with:
    artifact-name: release-candidate
```

Use the `aab-preflight-report` artifact to review results. An AAB check failure also fails the job. Jobs that depend on this preflight run only when it passes under the default GitHub Actions conditions.

Open the workflow run's **Summary** tab to see the Markdown report. To try both outcomes in your repository, run once with the expected contract, then set `previous_version_code` equal to the candidate's `versionCode` and rerun. If the checker cannot generate a report, see the **Check candidate** log.

### Opt in to the ARM64 split alignment check

Add `check-arm64-16kb: true` under `with` in the example above. The input defaults to `false`. After the release metadata passes, bundletool generates APKs for a synthetic ARM64/API 35 target with 480 dpi and the `en-US` locale. The workflow checks the ELF and ZIP alignment of each generated APK. A failed or invalid APK check fails the job. APKs without eligible native libraries are recorded as `not_applicable`.

Download `arm64-16kb/summary.json` and the per-APK JSON reports from the same preflight artifact, including after failure. The job logs name the affected APKs and shared libraries. The check covers static alignment for this bundletool target. Device compatibility and Google Play delivery require separate verification.

#### MediaPipe signed Debug AAB example

1. In the pinned MediaPipe Image Classification sample, run `./gradlew --no-configuration-cache :app:verifyModels :app:bundleDebug` from `examples/image_classification/android`. Use JDK 17, Android SDK Platform 36, Build Tools 36.0.0, and NDK 27.0.12077973. [Pinned sample](https://github.com/google-ai-edge/mediapipe-samples/tree/46d60d66baf21ae91977c488ea0875f0e13c4d2b/examples/image_classification/android)
2. Upload `app/build/outputs/bundle/debug/app-debug.aab` as `candidate.aab` alongside `release.json` in the same artifact. Set the contract to the sample's app ID and versions and the disposable debug certificate's SHA-256 fingerprint.
3. Call `aab-preflight.yml@v0.8.0` with `check-arm64-16kb: true`. To use the complete caller workflow in your repository, copy it and set its `push` branch. [Caller workflow](https://github.com/LeeJUNhao791/android-mcp-inspector/blob/47b6b661c883af8515039d9d01a284adc1ba9516/.github/workflows/mediapipe-aab-16kb-proof.yml) · [Reusable workflow at the tested commit](https://github.com/LeeJUNhao791/android-delivery-workflows/blob/552883397325c56ddb79d45af8676c7456a2a225/.github/workflows/aab-preflight.yml)

In the hosted run, all six AAB checks passed. For the ARM64/API 35 target, all four native libraries in `base-arm64_v8a.apk` passed both 16 KiB ELF and ZIP alignment checks. `base-master.apk`, `base-en.apk`, and `base-xxhdpi.apk` contained no native libraries and were marked `not_applicable`. See the run's **Summary** or open `report.json` and `arm64-16kb/summary.json` in the `mediapipe-aab-16kb-report` artifact while it is available. [Successful run](https://github.com/LeeJUNhao791/android-mcp-inspector/actions/runs/45357346927)

The run covers this signed Debug bundle and static alignment of its generated split APKs. Release builds, device execution, and Google Play delivery require separate verification.
