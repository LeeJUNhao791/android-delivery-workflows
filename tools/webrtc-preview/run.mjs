import { mkdir, writeFile } from 'node:fs/promises';
import { networkInterfaces } from 'node:os';
import { resolve } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';
import { chromium } from 'playwright';
import { createRelay } from './relay.mjs';

const output = resolve(process.argv[2] ?? 'build/webrtc-preview');
const sampleMs = 4000;
const outageMs = 4000;
const limit = 600000;

async function openPeers(page, localAddresses) {
  return page.evaluate(async (addresses) => {
    document.body.innerHTML = '<canvas width="640" height="360" hidden></canvas><video autoplay muted playsinline></video>';
    const canvas = document.querySelector('canvas');
    const ctx = canvas.getContext('2d');
    const video = document.querySelector('video');
    const image = ctx.createImageData(640, 360);
    let seed = 12345;
    function draw() {
      for (let i = 0; i < image.data.length; i += 4) {
        seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
        const value = seed >>> 24;
        image.data[i] = value;
        image.data[i + 1] = value;
        image.data[i + 2] = value;
        image.data[i + 3] = 255;
      }
      ctx.putImageData(image, 0, 0);
    }
    draw();
    setInterval(draw, 50);
    const stream = canvas.captureStream(20);
    const sender = new RTCPeerConnection();
    const receiver = new RTCPeerConnection();
    let rendered = 0;
    let firstFrameMs = null;
    let started;
    let restored;
    let recoveryMs = null;
    video.requestVideoFrameCallback(function frame() {
      const now = performance.now();
      rendered++;
      firstFrameMs ??= now - started;
      if (restored !== undefined) recoveryMs ??= now - restored;
      video.requestVideoFrameCallback(frame);
    });
    receiver.ontrack = (event) => { video.srcObject = event.streams[0]; };
    sender.addTrack(stream.getVideoTracks()[0], stream);
    // Exchange SDP before gathering completes so only the relay candidates are passed to the peers.
    const offer = await sender.createOffer();
    const found = [sender, receiver].map((peer) => new Promise((res, reject) => {
      const timer = setTimeout(() => reject(new Error('No usable local UDP ICE candidate')), 5000);
      peer.onicecandidate = ({ candidate }) => {
        if (candidate?.protocol === 'udp' && candidate.type === 'host' && addresses.includes(candidate.address)) {
          clearTimeout(timer);
          res(candidate.toJSON());
        }
      };
    }));
    await sender.setLocalDescription(offer);
    await receiver.setRemoteDescription(offer);
    const answer = await receiver.createAnswer();
    await receiver.setLocalDescription(answer);
    await sender.setRemoteDescription(answer);

    window.preview = {
      async connect(left, right, fromSender, fromReceiver) {
        const through = (candidate, endpoint) => {
          const fields = candidate.candidate.split(' ');
          fields[4] = endpoint.address;
          fields[5] = String(endpoint.port);
          return { ...candidate, candidate: fields.join(' ') };
        };
        started = performance.now();
        await sender.addIceCandidate(through(fromReceiver, left));
        await receiver.addIceCandidate(through(fromSender, right));
      },
      markRestored() { restored = performance.now(); },
      async sample() {
        const stats = [...(await receiver.getStats()).values()];
        const inbound = stats.find((s) => s.type === 'inbound-rtp' && s.kind === 'video');
        const transport = stats.find((s) => s.type === 'transport' && s.selectedCandidatePairId);
        const pair = stats.find((s) => s.id === transport?.selectedCandidatePairId);
        const remote = stats.find((s) => s.id === pair?.remoteCandidateId);
        return {
          rendered, firstFrameMs, recoveryMs,
          remotePort: remote?.port ?? null,
          framesDropped: inbound?.framesDropped ?? null,
          packetsLost: inbound?.packetsLost ?? null,
        };
      },
    };
    return Promise.all(found);
  }, localAddresses);
}

function endpoint(candidate) {
  const fields = candidate.candidate.split(' ');
  return { address: fields[4], port: Number(fields[5]) };
}

async function run() {
  const browser = await chromium.launch({
    args: ['--disable-features=WebRtcHideLocalIpsWithMdns'],
  });
  let relay;
  const report = {
    result: 'FAIL', browser: browser.version(), platform: process.platform,
    source: { width: 640, height: 360, framesPerSecond: 20, seed: 12345 },
    scenarios: {},
  };
  try {
    const page = await browser.newPage();
    await page.route('http://127.0.0.1:8765/', (route) => route.fulfill({
      contentType: 'text/html', body: '<!doctype html><title>WebRTC preview</title>',
    }));
    await page.goto('http://127.0.0.1:8765/');
    const addresses = Object.values(networkInterfaces()).flat()
      .filter((entry) => entry.family === 'IPv4' && !entry.internal).map((entry) => entry.address);
    if (!addresses.length) throw new Error('Chromium needs a local IPv4 network interface');
    const [fromSender, fromReceiver] = await openPeers(page, addresses);
    relay = await createRelay(endpoint(fromSender), endpoint(fromReceiver));
    const sample = () => page.evaluate(() => window.preview.sample());
    const waitForFrames = async (predicate, message) => {
      const deadline = performance.now() + 12000;
      while (performance.now() < deadline) {
        const current = await sample();
        if (predicate(current)) return current;
        await sleep(100);
      }
      throw new Error(message);
    };
    await page.evaluate(([left, right, a, b]) => window.preview.connect(left, right, a, b),
      [relay.left, relay.right, fromSender, fromReceiver]);
    const first = await waitForFrames((s) => s.rendered > 0, 'No first video frame');
    report.firstFrameMs = Math.round(first.firstFrameMs);
    const windowStats = async (duration) => {
      const before = await sample();
      const counters = relay.stats();
      const start = performance.now();
      await sleep(duration);
      const elapsed = performance.now() - start;
      const after = await sample();
      if (after.remotePort !== relay.right.port || after.framesDropped === null) {
        throw new Error('Could not verify the selected relay path and receiver stats');
      }
      const delta = (name) => relay.stats()[name] - counters[name];
      return {
        durationMs: Math.round(elapsed), renderedFrames: after.rendered - before.rendered,
        framesDropped: after.framesDropped - before.framesDropped,
        packetsLost: after.packetsLost === null || before.packetsLost === null
          ? null : after.packetsLost - before.packetsLost,
        forwardedBytes: delta('forwardedBytes'), queueDrops: delta('queueDrops'),
        outageDrops: delta('outageDrops'),
        senderForwardedBitsPerSecond: Math.round(delta('senderForwardedBytes') * 8000 / elapsed),
      };
    };
    report.scenarios.normal = await windowStats(sampleMs);
    if (report.scenarios.normal.renderedFrames < 1) throw new Error('Normal video stalled');

    relay.profile({ bitsPerSecond: limit });
    report.scenarios.limited = { senderLimitBitsPerSecond: limit, ...await windowStats(sampleMs) };
    const limited = report.scenarios.limited;
    // The short sample can include one datagram whose transmission began before the window.
    const rateTolerance = 12000 / (limited.durationMs / 1000);
    if (limited.renderedFrames < 1 || limited.senderForwardedBitsPerSecond <= 0
      || limited.senderForwardedBitsPerSecond > limit + rateTolerance) {
      throw new Error('Preview did not meet the bitrate-limited playback check');
    }

    relay.profile({ offline: true });
    const before = relay.stats();
    const startOutage = performance.now();
    await sleep(outageMs - 1000);
    const drain = await sample();
    await sleep(1000);
    const stopped = await sample();
    const dropped = relay.stats().outageDrops - before.outageDrops;
    const forwarded = relay.stats().forwardedPackets - before.forwardedPackets;
    report.scenarios.outage = {
      durationMs: Math.round(performance.now() - startOutage),
      forwardedPackets: forwarded,
      outageDrops: dropped,
      renderedFramesInFinalSecond: stopped.rendered - drain.rendered,
    };
    if (forwarded !== 0 || dropped === 0 || stopped.rendered !== drain.rendered) {
      throw new Error('Outage did not interrupt the media path');
    }
    await page.evaluate(() => window.preview.markRestored());
    relay.profile({});
    const resumed = await waitForFrames((s) => s.recoveryMs !== null && s.rendered > stopped.rendered,
      'No video frame after restoring the relay');
    if (resumed.remotePort !== relay.right.port) throw new Error('Recovery bypassed the relay');
    report.scenarios.outage.recoveryMs = Math.round(resumed.recoveryMs);
    report.result = 'PASS';
  } catch (error) {
    report.error = error.message;
  } finally {
    relay?.close();
    await browser.close();
  }
  await mkdir(output, { recursive: true });
  await writeFile(resolve(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(`${report.result} · ${resolve(output, 'report.json')}`);
  if (report.error) console.error(report.error);
  process.exitCode = report.result === 'PASS' ? 0 : 1;
}

await run();
