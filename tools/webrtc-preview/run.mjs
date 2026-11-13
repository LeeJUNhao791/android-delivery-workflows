import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { networkInterfaces } from 'node:os';
import { resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { setTimeout as sleep } from 'node:timers/promises';
import { chromium } from 'playwright';
import { createRelay } from './relay.mjs';

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: { cdp: { type: 'string' }, host: { type: 'string' }, phone: { type: 'string' },
    adb: { type: 'string', default: 'adb' }, serial: { type: 'string' }, 'cycle-wifi': { type: 'boolean' } },
});
const output = resolve(positionals[0] ?? 'build/webrtc-preview');
const sampleMs = 4000;
const outageMs = 4000;
const limit = 600000;
const mobile = Boolean(values.cdp);
if (mobile && (!values.host || !values.phone)) throw new Error('Use --host and --phone with --cdp');
if (values['cycle-wifi'] && (!mobile || !values.serial)) {
  throw new Error('Wi-Fi cycling needs --cdp and --serial');
}

async function openPeer(page, sender, addresses, phoneAddress) {
  return page.evaluate(({ sender, addresses, phoneAddress }) => {
    const peer = new RTCPeerConnection();
    let rendered = 0;
    let firstFrameMs = null;
    let started;
    let restored;
    let recoveryMs = null;
    if (sender) {
      document.body.innerHTML = '<canvas width="640" height="360" hidden></canvas>';
      const canvas = document.querySelector('canvas');
      const ctx = canvas.getContext('2d');
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
      peer.addTrack(stream.getVideoTracks()[0], stream);
    } else {
      document.head.insertAdjacentHTML('beforeend', '<meta name="viewport" content="width=device-width, initial-scale=1">');
      document.body.style.cssText = 'margin:16px;background:#0f1823;color:#fff;font:16px system-ui';
      document.body.innerHTML = '<h1>WebRTC preview</h1><video autoplay muted playsinline style="width:100%;max-width:640px"></video><p id="status">Waiting for the first frame</p>';
      const video = document.querySelector('video');
      const status = document.querySelector('#status');
      video.requestVideoFrameCallback(function frame() {
        const now = performance.now();
        rendered++;
        firstFrameMs ??= now - started;
        if (restored !== undefined) recoveryMs ??= now - restored;
        status.textContent = `Frames ${rendered} · First frame ${Math.round(firstFrameMs)} ms`;
        video.requestVideoFrameCallback(frame);
      });
      peer.ontrack = (event) => { video.srcObject = event.streams[0]; };
    }

    let localCandidate;
    const candidates = [];
    peer.onicecandidate = ({ candidate }) => {
        if (candidate) candidates.push(candidate.candidate);
      if (!candidate || candidate.protocol !== 'udp' || candidate.type !== 'host') return;
        if (addresses.includes(candidate.address) || (phoneAddress && candidate.address.endsWith('.local'))) {
        localCandidate ??= candidate.toJSON();
      }
    };
    window.preview = {
      async describe(type, description) {
        if (description) await peer.setRemoteDescription(description);
        const local = type === 'offer' ? await peer.createOffer() : await peer.createAnswer();
        await peer.setLocalDescription(local);
        return local;
      },
      answer(description) { return peer.setRemoteDescription(description); },
      candidate() { return localCandidate; },
      candidates,
      async connect(relay, candidate) {
        const fields = candidate.candidate.split(' ');
        fields[4] = relay.address;
        fields[5] = String(relay.port);
        started = performance.now();
        await peer.addIceCandidate({ ...candidate, candidate: fields.join(' ') });
      },
      markRestored() { restored = performance.now(); recoveryMs = null; },
      async sample() {
        const stats = [...(await peer.getStats()).values()];
        const inbound = stats.find((s) => s.type === 'inbound-rtp' && s.kind === 'video');
        const transport = stats.find((s) => s.type === 'transport' && s.selectedCandidatePairId);
        const pair = stats.find((s) => s.id === transport?.selectedCandidatePairId);
        const remote = stats.find((s) => s.id === pair?.remoteCandidateId);
        return {
          rendered, firstFrameMs, recoveryMs,
          connectionState: peer.connectionState, iceState: peer.iceConnectionState,
          remotePort: remote?.port ?? null,
          framesDropped: inbound?.framesDropped ?? null,
          packetsLost: inbound?.packetsLost ?? null,
        };
      },
    };
  }, { sender, addresses, phoneAddress });
}

async function previewPage(browser, remote = false) {
  const page = remote ? await browser.contexts()[0].newPage() : await browser.newPage();
  await page.route('http://127.0.0.1:8765/', (route) => route.fulfill({
    contentType: 'text/html', body: '<!doctype html><title>WebRTC preview</title>',
  }));
  await page.goto('http://127.0.0.1:8765/');
  if (remote) await page.bringToFront();
  return page;
}

function endpoint(candidate, phoneAddress) {
  const fields = candidate.candidate.split(' ');
  return { address: phoneAddress ?? fields[4], port: Number(fields[5]) };
}

async function waitFor(predicate, message, timeout = 12000) {
  const deadline = performance.now() + timeout;
  while (performance.now() < deadline) {
    const result = await predicate();
    if (result) return result;
    await sleep(100);
  }
  throw new Error(message);
}

function adb(...args) {
  return execFileSync(values.adb, ['-s', values.serial, 'shell', ...args], {
    encoding: 'utf8', timeout: 5000, windowsHide: true,
  });
}

async function testWifi(page, sample, relay) {
  const start = await sample();
  const state = { startIceState: start.iceState };
  const address = () => adb('ip', '-4', 'addr', 'show', 'wlan0');
  if (!address().includes(`inet ${values.phone}/`)) throw new Error('Phone Wi-Fi IP does not match --phone');
  const startOff = performance.now();
  adb('svc', 'wifi', 'disable');
  try {
    await waitFor(() => !address().includes('inet '), 'Phone Wi-Fi did not disconnect');
    await sleep(3000);
    const stopped = await sample();
    await sleep(1000);
    const final = await sample();
    state.framesInFinalSecond = final.rendered - stopped.rendered;
    state.iceWhileOff = final.iceState;
    if (state.framesInFinalSecond !== 0) throw new Error('Preview did not stop with Wi-Fi disabled');
  } finally {
    adb('svc', 'wifi', 'enable');
  }
  state.offMs = Math.round(performance.now() - startOff);
  await waitFor(() => address().includes(`inet ${values.phone}/`),
    'Phone did not recover its original Wi-Fi IPv4 address', 30000);
  await page.evaluate(() => window.preview.markRestored());
  const resumed = await waitFor(async () => {
    const s = await sample();
    return s.recoveryMs !== null && s.rendered > start.rendered ? s : null;
  }, 'No video frame after Wi-Fi returned', 20000);
  if (resumed.remotePort !== relay.right.port) throw new Error('Wi-Fi recovery bypassed the relay');
  return { ...state, nextFrameAfterIpMs: Math.round(resumed.recoveryMs),
    iceAfterRecovery: resumed.iceState, reconnect: 'original peer connection' };
}

async function run() {
  const browser = await chromium.launch({
    args: ['--disable-features=WebRtcHideLocalIpsWithMdns'],
  });
  let relay;
  let phoneBrowser;
  let page;
  const report = {
    result: 'FAIL', browser: browser.version(), platform: process.platform, receiver: mobile ? 'Android Chrome' : 'desktop Chromium',
    source: { width: 640, height: 360, framesPerSecond: 20, seed: 12345 },
    scenarios: {},
  };
  try {
    const sender = await previewPage(browser);
    if (mobile) {
      phoneBrowser = await chromium.connectOverCDP(values.cdp, { timeout: 10000 });
      report.receiverBrowser = phoneBrowser.version();
    }
    page = await previewPage(phoneBrowser ?? browser, mobile);
    const addresses = Object.values(networkInterfaces()).flat()
      .filter((entry) => entry.family === 'IPv4' && !entry.internal).map((entry) => entry.address);
    if (!addresses.length) throw new Error('Chromium needs a local IPv4 network interface');
    await openPeer(sender, true, addresses);
    await openPeer(page, false, mobile ? [values.phone] : addresses, values.phone);
    const offer = await sender.evaluate(() => window.preview.describe('offer'));
    const answer = await page.evaluate((offer) => window.preview.describe('answer', offer), offer);
    await sender.evaluate((answer) => window.preview.answer(answer), answer);
    const [fromSender, fromReceiver] = await Promise.all([sender, page].map(async (peer, index) => {
      try {
        const handle = await peer.waitForFunction(() => window.preview.candidate(), null,
          { timeout: 7000, polling: 100 });
        try { return await handle.jsonValue(); } finally { await handle.dispose(); }
      } catch (error) {
        const candidates = await peer.evaluate(() => window.preview.candidates);
        throw new Error(`No usable ${index ? 'receiver' : 'sender'} UDP candidate (${candidates.map(
          (candidate) => candidate.split(' ').slice(2, 8).join(' ')).join(', ') || 'none'})`, { cause: error });
      }
    }));
    relay = await createRelay(endpoint(fromSender), endpoint(fromReceiver, values.phone), values.host);
    const sample = () => page.evaluate(() => window.preview.sample());
    const waitForFrames = (predicate, message) => waitFor(async () => {
      const current = await sample();
      return predicate(current) ? current : null;
    }, message);
    await Promise.all([
      sender.evaluate(([relay, candidate]) => window.preview.connect(relay, candidate), [relay.left, fromReceiver]),
      page.evaluate(([relay, candidate]) => window.preview.connect(relay, candidate), [relay.right, fromSender]),
    ]);
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
    if (values['cycle-wifi']) report.scenarios.wifi = await testWifi(page, sample, relay);
    report.result = 'PASS';
  } catch (error) {
    report.error = error.message;
  } finally {
    relay?.close();
    try {
      if (phoneBrowser) {
        try { await page?.close(); } finally { await phoneBrowser.close(); }
      }
    } finally {
      await browser.close();
    }
  }
  await mkdir(output, { recursive: true });
  await writeFile(resolve(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(`${report.result} · ${resolve(output, 'report.json')}`);
  if (report.error) console.error(report.error);
  process.exitCode = report.result === 'PASS' ? 0 : 1;
}

await run();
