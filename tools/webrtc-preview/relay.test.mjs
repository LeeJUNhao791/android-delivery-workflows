import assert from 'node:assert/strict';
import dgram from 'node:dgram';
import { once } from 'node:events';
import { test } from 'node:test';
import { createRelay } from './relay.mjs';

async function endpoint(address = '127.0.0.1') {
  const socket = dgram.createSocket('udp4');
  socket.bind(0, address);
  await once(socket, 'listening');
  return socket;
}

test('routes both directions and blackholes packets during outage', { timeout: 4000 }, async () => {
  const a = await endpoint();
  const b = await endpoint();
  const relay = await createRelay(a.address(), b.address());
  try {
    const atB = once(b, 'message');
    a.send('from-a', relay.left.port, relay.left.address);
    const [fromA, source] = await atB;
    assert.equal(fromA.toString(), 'from-a');
    assert.equal(source.port, relay.right.port);

    const atA = once(a, 'message');
    b.send('from-b', relay.right.port, relay.right.address);
    assert.equal((await atA)[0].toString(), 'from-b');

    relay.profile({ offline: true });
    a.send('discard-me', relay.left.port, relay.left.address);
    await once(relay.events, 'drop');
    assert.equal(relay.stats().outageDrops, 1);

    relay.profile({});
    const restored = once(b, 'message');
    a.send('restored', relay.left.port, relay.left.address);
    assert.equal((await restored)[0].toString(), 'restored');
  } finally {
    relay.close();
    a.close();
    b.close();
  }
});

test('limits bitrate and rejects packets that would exceed the queue budget', { timeout: 4000 }, async () => {
  const a = await endpoint();
  const b = await endpoint();
  const relay = await createRelay(a.address(), b.address());
  try {
    relay.profile({ bitsPerSecond: 8000 });
    const received = once(b, 'message');
    const dropped = once(relay.events, 'drop');
    const start = performance.now();
    a.send(Buffer.alloc(150), relay.left.port, relay.left.address);
    a.send(Buffer.alloc(150), relay.left.port, relay.left.address);
    await dropped;
    await received;
    assert.ok(performance.now() - start >= 120);
    assert.equal(relay.stats().queueDrops, 1);
  } finally {
    relay.close();
    a.close();
    b.close();
  }
});

test('binds both relay sockets to the host interface for a remote peer', { timeout: 4000 }, async () => {
  const a = await endpoint();
  const b = await endpoint('127.0.0.2');
  let relay;
  try {
    relay = await createRelay(a.address(), b.address());
    assert.equal(relay.left.address, '127.0.0.1');
    assert.equal(relay.right.address, '127.0.0.1');
    const atB = once(b, 'message');
    a.send('remote', relay.left.port, relay.left.address);
    assert.equal((await atB)[0].toString(), 'remote');
    const atA = once(a, 'message');
    b.send('return', relay.right.port, relay.right.address);
    assert.equal((await atA)[0].toString(), 'return');
  } finally {
    relay?.close();
    a.close();
    b.close();
  }
});
