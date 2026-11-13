# Verify an APK upgrade with ADB

[简体中文](adb-upgrade.zh-CN.md) · [README](../README.md)

The upgrade example uses the dedicated package `io.github.leejunhao791.deliverydemo.upgrade`. Install Python 3.11+, JDK 17, Android SDK Platform 35, Build Tools 35.0.0, and Platform Tools. See the [AAB setup guide](getting-started.md) for the build environment.

## Build both APKs

Run from the repository root with `JAVA_HOME` and `ANDROID_HOME` set. In PowerShell, use `.\examples\android-app\gradlew.bat` in place of the shell wrapper.

```sh
./examples/android-app/gradlew -p examples/android-app :upgrade-demo:assembleBaselineDebug :upgrade-demo:assembleCandidateDebug
```

Both variants use the same debug signer. Their version codes are 1 and 2.

## Run on a test device

Connect the device, authorize USB debugging, and use its serial from `adb devices -l`. Choose a device without an existing Upgrade Demo install. The script checks this before installing.

```sh
apk=examples/android-app/upgrade-demo/build/outputs/apk
python tools/adb-upgrade/upgrade.py verify \
  --serial '<device serial>' \
  --adb "$ANDROID_HOME/platform-tools/adb" \
  --aapt "$ANDROID_HOME/build-tools/35.0.0/aapt" \
  --apksigner-jar "$ANDROID_HOME/build-tools/35.0.0/lib/apksigner.jar" \
  --java "$JAVA_HOME/bin/java" \
  --baseline "$apk/baseline/debug/upgrade-demo-baseline-debug.apk" \
  --candidate "$apk/candidate/debug/upgrade-demo-candidate-debug.apk"
```

On Windows, see the [PowerShell command](adb-upgrade.zh-CN.md).

The script checks package names, versions, and signatures before installation. It installs version 1 and uses `run-as` to write a unique marker into the demo's private files. It then installs version 2 in place, launches it, and reads the same marker. A final attempt to reinstall version 1 must return `INSTALL_FAILED_VERSION_DOWNGRADE`. The script verifies version 2 and the marker again.

The JSON report is written to `build/adb-upgrade/report.json`. Exit codes are 0 for pass, 1 for failed acceptance, and 2 for setup or input issues. The demo remains installed for inspection. To rerun, remove **Upgrade Demo** in Android Settings, which clears its demo data.

## Device result

All 12 steps passed on Kalama (Android 15, API 35, ARM64). Version 2 read the same private file after the in-place upgrade and displayed the marker in the app. Android rejected the version 1 reinstall with:

```text
INSTALL_FAILED_VERSION_DOWNGRADE: Downgrade detected: Update version code 1 is older than current 2
```

Version 2 and the marker were still present after the rejection. This run used the demo's debug signing and file storage.

## Diagnose saved install output

```sh
python tools/adb-upgrade/upgrade.py diagnose examples/android-app/upgrade-demo/downgrade.example.txt
```

The command reads the log file and prints the install code, original output, and a troubleshooting hint. The included log is a sample diagnostic input.
