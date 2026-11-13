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

The runner disables Wi-Fi, checks that the renderer stops, and re-enables Wi-Fi. When the original IPv4 address returns, the runner gives the existing WebRTC session up to five seconds to resume. If it still stalls, the runner uses USB signaling to rebuild the sender, Kotlin peer connection and UDP relay once. The preview activity stays open.

The 20-second budget starts when the runner detects the original IPv4 address. The report records the time until the runner observes a new rendered frame, the number of replacement attempts and the connection used. A timeout fails the run and preserves the Wi-Fi and ICE observations.

## Device results

The Pixel 4 XL (Android 11) native preview rendered its first frame in 435 ms. It rendered 16 frames normally and 10 under the cap in roughly four seconds per sample. The limited leg forwarded 444 kbit/s. The receiver reported 1 dropped frames and 71 lost packets. Playback resumed 3177 ms after relay forwarding resumed.

The Flutter debug build passed all three scenarios on the same Pixel. It rendered the first frame in 514 ms, then rendered 14 frames normally and 6 under the cap. The limited leg forwarded 463 kbit/s. The receiver reported 4 dropped frames and 77 lost packets. Video resumed in 2438 ms. After tapping **Stop preview** on the native screen, Flutter displayed `Stopped` and `Last preview: Preview passed`.

Before automatic replacement, the Pixel 4 XL ran the Wi-Fi cycle twice per entry. Both entries stopped rendering while Wi-Fi was off, regained the original IPv4 address, and timed out on the original WebRTC session. ICE reached `failed` in both retests. The table shows the retest and a separate run that launched a new session after Wi-Fi was back. [Kotlin baseline](evidence/webrtc-kotlin-wifi-baseline.json) · [Flutter baseline](evidence/webrtc-flutter-wifi-baseline.json)

| Entry | Wi-Fi off interval | Frames in the final second offline | Original session after IPv4 return | First frame in a new session |
| --- | ---: | ---: | --- | ---: |
| Kotlin native | 4551 ms | 0 | No frame within 20 s | 506 ms |
| Flutter → Kotlin | 4500 ms | 0 | No frame within 20 s | 1458 ms |

With automatic replacement enabled, the same Pixel passed three consecutive runs per entry. Each run passed normal playback, rate limiting, UDP relay interruption and the phone Wi-Fi cycle. Each Wi-Fi cycle recovered after one replacement.

| Entry | Runs passed | IPv4 return to a rendered frame observed by the runner |
| --- | ---: | --- |
| Kotlin native | 3/3 | 6183, 6379, 6271 ms |
| Flutter → Kotlin | 3/3 | 6276, 6237, 6214 ms |

After the last run, **Stop preview** returned to Flutter with `Stopped` and `Last preview: Preview passed`. The individual JSON reports are attached to the [v0.5.1 release](https://github.com/LeeJUNhao791/android-delivery-workflows/releases/tag/v0.5.1).
