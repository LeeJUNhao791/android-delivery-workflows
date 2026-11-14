# Verify a WebRTC preview under a weak link

[简体中文](webrtc-preview.zh-CN.md) · [README](../README.md)

Run a fixed 640×360 canvas stream through two Chromium WebRTC peers and a local UDP relay. The canvas requests 20 frames per second with a fixed seed. The receiver measures frames actually rendered.

## Run

Install Node.js 22 or newer. From the repository root:

```sh
cd tools/webrtc-preview
npm ci
npx playwright install chromium --only-shell
npm test
node run.mjs ../../build/webrtc-preview
```

On Linux, use `npx playwright install --with-deps chromium --only-shell` to install Chromium and system dependencies together. Chromium and the relay need a local IPv4 interface. The test uses local UDP traffic and does not require a camera, TURN server, or public stream.

## Run with a desktop camera

Connect a camera to the sending computer and allow desktop apps to use it in the operating system. Install the full Playwright Chromium build for camera capture. Run from the repository root after installing the Node dependencies:

```sh
cd tools/webrtc-preview
npx playwright install chromium --no-shell
node run.mjs ../../build/webrtc-camera/desktop --camera
```

The browser selects its default camera and requests video only. The report records the camera label and browser-selected resolution and frame-rate setting. It also records the same receiver and relay metrics as the fixed-source run. The test does not save photos or video.

To send the camera to an Android phone, add `--camera` to the Android Chrome command below or either [Kotlin or Flutter command](webrtc-native.md#phone-wi-fi-recovery). Use a separate output directory for each run. The camera stays on the sending computer.

On Windows, the HP True Vision FHD Camera ran at a browser-selected 640×360 and 20 fps. The Android receiver was a Pixel 4 XL on Android 11.

| Receiver | First frame | Forwarded rate under the 600 kbit/s cap | UDP relay recovery | Phone Wi-Fi recovery |
| --- | ---: | ---: | ---: | ---: |
| Desktop Chromium | 144 ms | 27.4 kbit/s | 2066 ms | — |
| Kotlin native | 480 ms | 27.4 kbit/s | 1949 ms | 7017 ms |
| Flutter → Kotlin | 525 ms | 29.1 kbit/s | 2042 ms | 8866 ms |
| Android Chrome | 508 ms | 29.0 kbit/s | 2115 ms | 2793 ms |

Kotlin and Flutter each used one new session after the phone regained its original IPv4 address. Android Chrome resumed on the original session when the phone and computer shared the same Wi-Fi. The camera stream stayed well below the cap. Use the fixed source above to exercise the relay's bandwidth limit.

### Kalama development board

The Kotlin receiver ran on a Kalama development board with Android 15 (ARM64). The Windows sender used the same HP camera at 640×360 with a 20 fps capture setting. Build and install the [Kotlin debug APK](webrtc-native.md#kotlin-receiver), connect the board over USB ADB, and join the same Wi-Fi as the computer. Run from the repository root:

```sh
node tools/webrtc-preview/run.mjs build/webrtc-camera/kalama-playback --camera --native --host HOST_WIFI_IP --phone BOARD_WIFI_IP --serial SERIAL
```

For the Wi-Fi cycle, add `--cycle-wifi` and use a separate output directory.

| Run | First frame | Forwarded rate under the 600 kbit/s cap | UDP relay recovery | Wi-Fi cycle |
| --- | ---: | ---: | ---: | --- |
| [Playback](evidence/webrtc-kalama-camera-playback.json) | 557 ms | 29.5 kbit/s | 2069 ms | — |
| [Wi-Fi retest](evidence/webrtc-kalama-camera-wifi-retest.json) | 492 ms | 28.6 kbit/s | 2017 ms | Original IPv4 did not return within 30 s |

Playback continued under the configured cap in both runs. The Wi-Fi cycle stopped video as expected, then timed out waiting for the board to rejoin. Device logs showed that Android had disabled automatic selection of this network after its internet check failed. After the saved network was selected manually, the separate playback run passed. WebRTC recovery after an automatic Wi-Fi rejoin remains unverified on this board.

## Read the JSON report

Open `build/webrtc-preview/report.json`. The process exits with 0 on success and 1 on a failed scenario.

| Scenario | What is checked |
| --- | --- |
| Normal | A first video frame arrives and preview continues for the sample window. |
| Rate limited | The sender leg is paced to 600 kbit/s of UDP payload, with a bounded queue. The report records measured throughput, rendered frames, receiver dropped frames, and packet loss. At least one frame must render under the cap. |
| Outage and recovery | The relay drops traffic in both directions for four seconds. The test verifies no datagrams were forwarded and no frames rendered in the final second of the outage. When forwarding resumes, a new frame must arrive on the same peer connection within 12 seconds. |

First-frame time begins when the peers receive their relay candidates. Recovery time begins when forwarding is restored. `framesDropped` is the receiver's WebRTC statistic. Compare it with `renderedFrames` and `packetsLost` when judging preview quality. A low drop count can occur alongside a low rendered frame count.

GitHub Actions runs the desktop check and retains the JSON report. Use the Android procedure below for a physical Wi-Fi run.

## Run on Android Chrome

Connect the computer and phone to the same Wi-Fi network. Use a USB cable for ADB and open Chrome on the unlocked phone. Get the device serial from `adb devices -l`, and the phone IPv4 address from `adb -s SERIAL shell ip -4 addr show wlan0`.

From the repository root, after installing the desktop dependencies:

```sh
adb -s SERIAL forward tcp:9222 localabstract:chrome_devtools_remote
node tools/webrtc-preview/run.mjs build/webrtc-android --cdp http://127.0.0.1:9222 --host HOST_WIFI_IP --phone PHONE_WIFI_IP --serial SERIAL --cycle-wifi
adb -s SERIAL forward --remove tcp:9222
```

Use the computer's Wi-Fi IPv4 address for `HOST_WIFI_IP`. The phone must be able to reach local UDP ports on that address. Use `--adb` to supply the executable path when ADB is outside PATH. If the shell uses an HTTP proxy, add localhost to its no-proxy list.

The first three scenarios use the same sender and relay as the desktop run. With `--cycle-wifi`, the script then turns off phone Wi-Fi via USB ADB, checks that video stops, and re-enables Wi-Fi. It waits for the original IPv4 address, then times the next rendered frame. The browser's ICE state is recorded separately and can stay connected through a short interruption. The procedure measures recovery in Android Chrome on the same Wi-Fi network and original IPv4 address. See the [native preview guide](webrtc-native.md#phone-wi-fi-recovery) for the Kotlin and Flutter results.

## Measured results

Windows desktop Chromium and a Pixel 4 XL (Android 11, Chrome 156.0.8078.47) used the same fixed source.

| Receiver | First frame | Normal / limited rendered frames | Recovery after the 4 s relay outage |
| --- | ---: | ---: | ---: |
| Windows Chromium | 300 ms | 14 / 10 | 2987 ms |
| Pixel 4 XL | 483 ms | 15 / 8 | 2573 ms |

The Pixel measured 586 kbit/s under the cap, with 0 receiver-reported dropped frames and 59 lost packets. Wi-Fi was switched off for about 4.446 seconds. A new frame rendered 3047 ms after the original IPv4 address was observed again. The original WebRTC connection resumed playback.
