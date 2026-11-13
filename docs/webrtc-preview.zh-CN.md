# WebRTC 弱网预览验收

[English](webrtc-preview.md) · [返回 README](../README.zh-CN.md)

用同一个 640×360 Canvas 测试源，在两个 Chromium WebRTC 对端之间传输视频。测试源固定随机种子，目标采集频率为 20 帧/秒。接收端记录实际渲染的帧数。

## 运行

安装 Node.js 22 或更新版本。在仓库根目录执行：

```sh
cd tools/webrtc-preview
npm ci
npx playwright install chromium --only-shell
npm test
node run.mjs ../../build/webrtc-preview
```

Linux 可用 `npx playwright install --with-deps chromium --only-shell` 一并安装系统依赖。测试需要本机 IPv4 接口，通过本地 UDP 中继传输，无需摄像头、TURN 服务或公开视频源。

## 用电脑摄像头测试

在发送端电脑接好摄像头，并在系统设置允许桌面应用访问摄像头。安装 Node 依赖后，从仓库根目录执行以下命令。摄像头模式需要完整的 Playwright Chromium。

```sh
cd tools/webrtc-preview
npx playwright install chromium --no-shell
node run.mjs ../../build/webrtc-camera/desktop --camera
```

浏览器选用默认摄像头，只采集视频。报告记录摄像头名称、浏览器选定的分辨率和帧率设置，以及与固定视频源相同的接收端和中继指标。测试只保存 JSON。

要把电脑摄像头画面发到手机，可在 [Kotlin 或 Flutter 命令](webrtc-native.zh-CN.md#手机-wi-fi-恢复)后加 `--camera`。每轮使用独立的输出目录。

本次发送端是 Windows 上的 HP True Vision FHD Camera，浏览器选择了 640×360、20 fps。Android 接收端是 Pixel 4 XL（Android 11）。

| 接收端 | 首帧 | 600 kbit/s 上限下的实测转发码率 | UDP 中继恢复 | 手机 Wi-Fi 恢复 |
| --- | ---: | ---: | ---: | ---: |
| 桌面 Chromium | 144 ms | 27.4 kbit/s | 2066 ms | — |
| Kotlin 原生 | 480 ms | 27.4 kbit/s | 1949 ms | 7017 ms |
| Flutter → Kotlin | 525 ms | 29.1 kbit/s | 2042 ms | 8866 ms |

两个 Android 入口都在手机拿回原 IPv4 地址后重建一次会话。实测摄像头流量远低于上限。需要复现带宽压力时，用上面的固定视频源。

## 查看 JSON 报告

打开 `build/webrtc-preview/report.json`。成功返回 0，场景失败返回 1。

| 场景 | 验收条件 |
| --- | --- |
| 正常 | 收到首帧，采样期间持续渲染。 |
| 限速 | 中继将发送方向的 UDP 载荷限制在 600 kbit/s，队列满时丢包。报告记录实测吞吐、渲染帧、接收端掉帧和丢包。采样期间至少渲染一帧。 |
| 断网恢复 | 双向丢弃数据包 4 秒。期间中继转发数必须为 0，最后一秒渲染数也必须为 0。恢复转发后，原连接须在 12 秒内收到新帧。 |

首帧耗时从开始交换中继候选地址算起，恢复耗时从重新开启转发算起。`framesDropped` 来自 WebRTC 接收端统计。评估预览效果时同时看 `renderedFrames` 和 `packetsLost`，接收端掉帧为 0 时，渲染帧数仍可能下降。

GitHub Actions 会执行桌面检查并保留 JSON 报告。手机实测按下节操作。

## Android Chrome 真机验收

电脑和手机连同一个 Wi-Fi。用 USB 连接并授权 ADB，在解锁的手机上打开 Chrome。用 `adb devices -l` 取得设备序列号，用 `adb -s SERIAL shell ip -4 addr show wlan0` 查看手机 Wi-Fi 的 IPv4 地址。

安装好前面的桌面依赖后，从仓库根目录运行：

```sh
adb -s SERIAL forward tcp:9222 localabstract:chrome_devtools_remote
node tools/webrtc-preview/run.mjs build/webrtc-android --cdp http://127.0.0.1:9222 --host HOST_WIFI_IP --phone PHONE_WIFI_IP --serial SERIAL --cycle-wifi
adb -s SERIAL forward --remove tcp:9222
```

`HOST_WIFI_IP` 填电脑的 Wi-Fi IPv4 地址，手机需要能访问该地址上的本地 UDP 端口。ADB 未加入 PATH 时可用 `--adb` 指定路径。终端使用 HTTP 代理时，将本机地址加入代理例外。

前 3 个场景沿用桌面发送端和中继。指定 `--cycle-wifi` 后，脚本还会通过 USB ADB 关闭手机 Wi-Fi，确认画面停止，再重新开启。等手机恢复原 IPv4 地址后，记录下一帧耗时。报告单独记录 ICE 状态，短暂中断期间可能一直显示已连接。本节覆盖 Android Chrome 在同一 Wi-Fi、同一 IPv4 地址下的恢复。Kotlin 和 Flutter 的结果见[原生预览验收](webrtc-native.zh-CN.md#手机-wi-fi-恢复)。

## 实测记录

同一个固定测试源，Windows 桌面 Chromium 和 Pixel 4 XL（Android 11，Chrome 156.0.8078.47）分别跑完验收。

| 接收端 | 首帧 | 正常/限速渲染帧 | 4 秒中继断流后恢复 |
| --- | ---: | ---: | ---: |
| Windows Chromium | 300 ms | 14 / 10 | 2987 ms |
| Pixel 4 XL | 483 ms | 15 / 8 | 2573 ms |

Pixel 限速阶段实测 586 kbit/s，接收端统计掉帧 0、丢包 59。手机 Wi-Fi 实际关闭约 4.446 秒后重新开启，检测到原 IPv4 地址后 3047 ms 收到新画面。原 WebRTC 连接在这次中断中保持使用。
