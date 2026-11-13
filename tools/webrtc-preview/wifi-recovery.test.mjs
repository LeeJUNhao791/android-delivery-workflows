import assert from 'node:assert/strict';
import { test } from 'node:test';
import { recoverWifi } from './wifi-recovery.mjs';

test('keeps a working session and makes only one replacement for a stalled session', async () => {
  for (const resumed of [true, false]) {
    const state = {};
    let attempts = 0;
    await recoverWifi(state, performance.now(), async (timeout) => {
      if (attempts === 0 && !resumed) return null;
      assert.ok(timeout > 0 && timeout <= 20000);
      return { iceState: 'connected' };
    }, async () => { attempts++; });
    assert.equal(state.reconnectAttempts, resumed ? 0 : 1);
    assert.equal(attempts, state.reconnectAttempts);
    assert.equal(state.reconnect, resumed ? 'original peer connection' : 'new peer connection');
  }
});

test('reports one attempted replacement when the replacement also stalls', async () => {
  const state = {};
  let attempts = 0;
  await assert.rejects(recoverWifi(state, performance.now(), async () => null,
    async () => { attempts++; }), /No video frame after Wi-Fi returned/);
  assert.equal(attempts, 1);
  assert.equal(state.reconnectAttempts, 1);
  assert.equal(state.reconnect, 'new peer connection');
  assert.equal(state.nextFrameAfterIpMs, undefined);
});
