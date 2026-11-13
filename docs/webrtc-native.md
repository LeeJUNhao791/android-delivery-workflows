# Native WebRTC and Flutter bridge

[简体中文](webrtc-native.zh-CN.md) · [Browser preview guide](webrtc-preview.md)

The Android debug example receives the same fixed WebRTC stream as the browser check. It counts frames submitted by the native EGL renderer and records the receiver's WebRTC statistics. USB ADB carries only the test commands and results. Video crosses Wi-Fi via the existing UDP relay.

## Kotlin receiver

Build and install the Android debug app. Use the Android setup in the [getting-started guide](getting-started.md). On Windows use the Gradle batch wrapper.

```sh
./examples/android-app/gradlew -p examples/android-app :app:assembleDebug
adb -s SERIAL install -r examples/android-app/app/build/outputs/apk/debug/app-debug.apk
```

Keep the unlocked test phone and computer on the same Wi-Fi. After installing the Node dependencies from the browser guide, run:

```sh
node tools/webrtc-preview/run.mjs build/webrtc-native --native --host HOST_WIFI_IP --phone PHONE_WIFI_IP --serial SERIAL
```

Use `--adb` if ADB is outside PATH. The runner launches the debug activity, measures normal playback, applies a 600 kbit/s cap, and interrupts relay traffic for four seconds. Read `build/webrtc-native/report.json`. Recovery measures the first rendered frame after relay forwarding resumes.

## Flutter bridge

Use Flutter 3.41.9 with JDK 17, Android SDK Platform 35 and NDK 27.0.12077973. From the repository root:

```sh
cd examples/flutter-preview
flutter pub get
flutter test
flutter build apk --debug --target-platform android-arm64
adb -s SERIAL install -r build/app/outputs/flutter-apk/app-debug.apk
cd ../..
node tools/webrtc-preview/run.mjs build/webrtc-flutter --flutter --host HOST_WIFI_IP --phone PHONE_WIFI_IP --serial SERIAL
```

The Flutter debug activity uses a platform channel for starting, stopping, and receiving status. It opens the same Kotlin receiver activity. The receiver's Stop preview button closes playback and returns to Flutter, where the result remains visible. The example covers Android ARM64 debug builds.

## Phone Wi-Fi recovery

Connect the test phone through USB ADB and keep it on the same Wi-Fi as the computer. Add `--cycle-wifi` to either command above to run a fourth scenario:

```sh
node tools/webrtc-preview/run.mjs build/webrtc-native-wifi --native --cycle-wifi --host HOST_WIFI_IP --phone PHONE_WIFI_IP --serial SERIAL
node tools/webrtc-preview/run.mjs build/webrtc-flutter-wifi --flutter --cycle-wifi --host HOST_WIFI_IP --phone PHONE_WIFI_IP --serial SERIAL
```

The runner disables Wi-Fi, checks that the renderer stops, and re-enables Wi-Fi. After the original IPv4 address returns, it gives the existing WebRTC session 20 seconds to render a new frame. A timeout fails the run and the JSON still records the Wi-Fi and ICE observations. Rerun the preview command to measure a new session if the original session stalls.

## Device results

The Pixel 4 XL (Android 11) native preview rendered its first frame in 435 ms. It rendered 16 frames normally and 10 under the cap in roughly four seconds per sample. The limited leg forwarded 444 kbit/s. The receiver reported 1 dropped frames and 71 lost packets. Playback resumed 3177 ms after relay forwarding resumed.

The Flutter debug build passed all three scenarios on the same Pixel. It rendered the first frame in 514 ms, then rendered 14 frames normally and 6 under the cap. The limited leg forwarded 463 kbit/s. The receiver reported 4 dropped frames and 77 lost packets. Video resumed in 2438 ms. After tapping **Stop preview** on the native screen, Flutter displayed `Stopped` and `Last preview: Preview passed`.

The Pixel 4 XL also ran the Wi-Fi cycle twice per entry. Both entries stopped rendering while Wi-Fi was off, regained the original IPv4 address, and timed out on the original WebRTC session. ICE reached `failed` in both retests. The table shows the retest and a separate run that launched a new session after Wi-Fi was back.

| Entry | Wi-Fi off interval | Frames in the final second offline | Original session after IPv4 return | First frame in a new session |
| --- | ---: | ---: | --- | ---: |
| Kotlin native | 4551 ms | 0 | No frame within 20 s | 506 ms |
| Flutter → Kotlin | 4500 ms | 0 | No frame within 20 s | 1458 ms |
