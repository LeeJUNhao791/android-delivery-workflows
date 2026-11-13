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

## Read the JSON report

Open `build/webrtc-preview/report.json`. The process exits with 0 on success and 1 on a failed scenario.

| Scenario | What is checked |
| --- | --- |
| Normal | A first video frame arrives and preview continues for the sample window. |
| Rate limited | The sender leg is paced to 600 kbit/s of UDP payload, with a bounded queue. The report records measured throughput, rendered frames, receiver dropped frames, and packet loss. At least one frame must render under the cap. |
| Outage and recovery | The relay drops traffic in both directions for four seconds. The test verifies no datagrams were forwarded and no frames rendered in the final second of the outage. When forwarding resumes, a new frame must arrive on the same peer connection within 12 seconds. |

First-frame time begins when the peers receive their relay candidates. Recovery time begins when forwarding is restored. `framesDropped` is the receiver's WebRTC statistic. Compare it with `renderedFrames` and `packetsLost` when judging preview quality. A low drop count can occur alongside a low rendered frame count.

This first version exercises WebRTC transport and rendering in desktop Chromium. Android playback and physical Wi-Fi remain separate acceptance work. GitHub Actions runs the same check and retains the JSON report.
