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

## 查看 JSON 报告

打开 `build/webrtc-preview/report.json`。成功返回 0，场景失败返回 1。

| 场景 | 验收条件 |
| --- | --- |
| 正常 | 收到首帧，采样期间持续渲染。 |
| 限速 | 中继将发送方向的 UDP 载荷限制在 600 kbit/s，队列满时丢包。报告记录实测吞吐、渲染帧、接收端掉帧和丢包。采样期间至少渲染一帧。 |
| 断网恢复 | 双向丢弃数据包 4 秒。期间中继转发数必须为 0，最后一秒渲染数也必须为 0。恢复转发后，原连接须在 12 秒内收到新帧。 |

首帧耗时从开始交换中继候选地址算起，恢复耗时从重新开启转发算起。`framesDropped` 来自 WebRTC 接收端统计。评估预览效果时同时看 `renderedFrames` 和 `packetsLost`，接收端掉帧为 0 时，渲染帧数仍可能下降。

首版验收覆盖桌面 Chromium 的 WebRTC 传输与渲染。Android 播放和实际 Wi-Fi 弱网是后续验收项。GitHub Actions 会运行同一套检查并保留 JSON 报告。
