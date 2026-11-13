import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const runner = fileURLToPath(new URL('./run.mjs', import.meta.url));

test('requires USB ADB before cycling Wi-Fi in either native entry', () => {
  for (const entry of ['--native', '--flutter']) {
    const result = spawnSync(process.execPath, [runner, entry, '--cycle-wifi',
      '--host', '192.0.2.1', '--phone', '192.0.2.2', '--serial', '192.0.2.2:5555'],
    { encoding: 'utf8', timeout: 5000 });

    assert.ifError(result.error);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Wi-Fi cycling needs a USB ADB device/);
  }
});
