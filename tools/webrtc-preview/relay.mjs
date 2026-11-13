import dgram from 'node:dgram';
import { EventEmitter, once } from 'node:events';

async function bind(address) {
  const socket = dgram.createSocket('udp4');
  socket.bind(0, address);
  await once(socket, 'listening');
  return socket;
}

export async function createRelay(a, b, receiverInterface = a.address) {
  const left = await bind(a.address);
  let right;
  try {
    right = await bind(receiverInterface);
  } catch (error) {
    left.close();
    throw error;
  }
  const events = new EventEmitter();
  const counters = { forwardedPackets: 0, forwardedBytes: 0, senderForwardedBytes: 0, queueDrops: 0, outageDrops: 0 };
  const queue = [];
  let profile = {};
  let timer;
  let queuedBytes = 0;

  function drop(counter) {
    counters[counter]++;
    events.emit('drop');
  }

  function forward(data, source, expected, target, output, limited) {
    if (source.address !== expected.address || source.port !== expected.port) return;
    if (profile.offline) return drop('outageDrops');

    function send() {
      output.send(data, target.port, target.address);
      counters.forwardedPackets++;
      counters.forwardedBytes += data.length;
      if (limited) counters.senderForwardedBytes += data.length;
    }
    if (!limited || !profile.bitsPerSecond) return send();

    if ((queuedBytes + data.length) * 8000 / profile.bitsPerSecond > 250) {
      return drop('queueDrops');
    }
    queuedBytes += data.length;
    queue.push({ bytes: data.length, send });
    if (!timer) drain();
  }

  function drain() {
    const packet = queue[0];
    if (!packet) return;
    // Start pacing the next packet after this send, including any timer delay.
    timer = setTimeout(() => {
      timer = undefined;
      queue.shift();
      queuedBytes -= packet.bytes;
      packet.send();
      drain();
    }, Math.ceil(packet.bytes * 8000 / profile.bitsPerSecond));
  }

  left.on('message', (data, source) => forward(data, source, a, b, right, true));
  right.on('message', (data, source) => forward(data, source, b, a, left, false));

  function resetQueue() {
    clearTimeout(timer);
    timer = undefined;
    queue.length = 0;
    queuedBytes = 0;
  }

  return {
    left: left.address(),
    right: right.address(),
    events,
    stats: () => ({ ...counters }),
    profile(next) {
      resetQueue();
      profile = next;
    },
    close() {
      resetQueue();
      left.close();
      right.close();
    },
  };
}
