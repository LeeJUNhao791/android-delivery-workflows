import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createSignal } from './native-signal.mjs';

test('exchanges one command and result with the native receiver', async () => {
  const signal = await createSignal();
  try {
    const url = `http://127.0.0.1:${signal.port}/command`;
    const result = signal.call('offer', { sdp: 'example' });
    const command = await (await fetch(url)).json();
    assert.deepEqual(command, { action: 'offer', sdp: 'example' });
    assert.equal((await fetch(url, { method: 'POST', body: '{"sdp":"answer"}' })).status, 204);
    assert.deepEqual(await result, { sdp: 'answer' });
    assert.equal((await fetch(url)).status, 204);
  } finally {
    await signal.close();
  }
});

test('rejects errors reported by the receiver', async () => {
  const signal = await createSignal();
  try {
    const url = `http://127.0.0.1:${signal.port}/command`;
    const result = assert.rejects(signal.call('sample'), /receiver error/);
    await fetch(url);
    await fetch(url, { method: 'POST', body: '{"error":"receiver error"}' });
    await result;
  } finally {
    await signal.close();
  }
});
