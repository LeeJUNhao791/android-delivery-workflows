import { once } from 'node:events';
import { createServer } from 'node:http';

export async function createSignal() {
  let pending;
  const server = createServer(async (request, response) => {
    if (request.url !== '/command') {
      response.writeHead(404).end();
    } else if (request.method === 'GET') {
      if (!pending || pending.sent) return response.writeHead(204).end();
      pending.sent = true;
      response.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify(pending.command));
    } else if (request.method === 'POST' && pending?.sent) {
      const current = pending;
      try {
        let body = '';
        for await (const chunk of request) {
          body += chunk;
          if (body.length > 65536) throw new Error('Receiver result exceeds 64 KiB');
        }
        const result = JSON.parse(body);
        if (pending !== current) return response.writeHead(409).end();
        if (!result || typeof result !== 'object' || Array.isArray(result)) {
          throw new Error('Receiver result must be an object');
        }
        if (result.error) current.finish(new Error(result.error));
        else current.finish(null, result);
        response.writeHead(204).end();
      } catch (error) {
        current.finish(error);
        response.writeHead(400).end();
      }
    } else {
      response.writeHead(409).end();
    }
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  return {
    port: server.address().port,
    call(action, fields = {}) {
      if (pending) throw new Error('Another receiver command is pending');
      return new Promise((resolve, reject) => {
        const item = {
          command: { action, ...fields },
          sent: false,
          finish(error, result) {
            if (pending !== item) return;
            clearTimeout(timer);
            pending = undefined;
            if (error) reject(error);
            else resolve(result);
          },
        };
        const timer = setTimeout(() => item.finish(new Error(`Receiver timed out on ${action}`)), 12000);
        pending = item;
      });
    },
    async close() {
      pending?.finish(new Error('Receiver signaling closed'));
      await new Promise((resolve) => server.close(resolve));
    },
  };
}
