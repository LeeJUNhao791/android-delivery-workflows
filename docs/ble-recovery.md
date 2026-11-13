# Reproduce BLE disconnect and recovery

[简体中文](ble-recovery.zh-CN.md) · [README](../README.md)

## Set up the two devices

Use a Windows PC with a Bluetooth LE adapter that supports the peripheral role, and a BLE-capable Android device. Install Python 3.11 on Windows and follow the [Android build setup](getting-started.md). Windows supplies an incrementing 32-bit counter over one GATT characteristic with Read and Notify.

From the repository root in PowerShell:

```powershell
python -m venv build/ble-venv
.\build\ble-venv\Scripts\python.exe -m pip install -r examples/ble-peripheral/requirements.txt
.\examples\android-app\gradlew.bat -p examples/android-app :app:testDebugUnitTest :app:assembleDebug
adb install -r examples/android-app/app/build/outputs/apk/debug/app-debug.apk
```

Open **Android Delivery Demo**, tap **Start BLE session**, and grant the requested permission. On Android 6–11, also enable system location for BLE scanning. Keep the app in the foreground during the test.

## Interrupt the link

Start the Windows counter in a separate terminal. The command switches the Windows Bluetooth radio off after 30 seconds, switches it back on after 8 seconds, and restores its original state on exit. Other Bluetooth devices on the PC will disconnect during the test.

```powershell
.\build\ble-venv\Scripts\python.exe examples/ble-peripheral/windows_counter.py --interrupt-after 30 --interrupt-for 8 --duration 85
```

1. Before the interruption, confirm the app shows a Read value and at least one changing Notification value.
2. At `RADIO_OFF` in the Windows terminal, leave the Android app running. The app should report a disconnect or retry.
3. After `RADIO_ON`, look for a new read and subscription, then a notification value greater than the last value seen before the interruption. The app should show **Recovered in … ms** without tapping Start again.
4. Save the event trace with `adb logcat -d -s BleCounter:I`. The recovery time starts at the Android disconnect callback and ends at the first notification after resubscription.

For a baseline run without a scheduled interruption, omit the timing flags and press Ctrl+C when finished. If the app only shows `CONNECTING` followed by `RETRY`, capture the status code and verify a stable connection before evaluating recovery.

## Evidence

The JVM tests cover retry backoff and when recovery is counted. The [hardware run](ble-evidence.md) records the passing run on Pixel 4 XL (Android 11) and the connection failure on Kalama (Android 15).
