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

The first preflight passes because version 2 exceeds 1. The second rejects the same AAB because version 2 does not exceed 2. Compare `build/pass/report.md` and `build/repeat-version/report.md`. Both report the same bundle hash. The demo uses a disposable key generated at run time.

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
  uses: LeeJUNhao791/android-delivery-workflows/.github/workflows/aab-preflight.yml@v0.1.0
  with:
    artifact-name: release-candidate
```

Use the `aab-preflight-report` artifact to review results. An AAB check failure also fails the job. Jobs that depend on this preflight run only when it passes under the default GitHub Actions conditions.
