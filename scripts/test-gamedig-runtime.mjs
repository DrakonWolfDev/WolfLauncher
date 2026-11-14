// Run after npm ci --ignore-scripts --prefix packaging/npm.
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import dgram from 'node:dgram';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import FarmingSimulator from '../packaging/npm/node_modules/gamedig/protocols/farmingsimulator.js';

const runtime = new URL('../packaging/npm/', import.meta.url);

test('patched stop-node parser rejects hostile XML within a bounded process', () => {
  const result = spawnSync(process.execPath, ['--input-type=module', '-e', `
    import { XMLParser } from './node_modules/fast-xml-parser/src/fxp.js';
    import assert from 'node:assert/strict';
    const parser = new XMLParser({ stopNodes: ['stop'] });
    assert.throws(() => parser.parse('<stop>' + '<a '.repeat(100000)));
  `], { cwd: runtime, timeout: 3000, encoding: 'utf8' });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
});

test('GameDig XML consumer retains server attributes and player parsing', async () => {
  const protocol = new FarmingSimulator();
  protocol.options = { host: '127.0.0.1', port: 8080, token: 'fixture' };
  protocol.request = async () => `<Server name="Fixture &amp; server" mapName="Map">
    <Slots numUsed="1" capacity="16">
      <Player isUsed="true" isAdmin="false" uptime="42" x="1" y="2" z="3">Alice</Player>
      <Player isUsed="false">Empty</Player>
    </Slots></Server>`;
  const state = { players: [] };
  await protocol.run(state);
  assert.equal(state.name, 'Fixture & server');
  assert.equal(state.map, 'Map');
  assert.equal(state.numplayers, 1);
  assert.equal(state.maxplayers, 16);
  assert.equal(state.players.length, 1);
  assert.equal(state.players[0].name, 'Alice');
});

test('bundled CLI decodes a local DayZ UDP fixture', { timeout: 8000 }, async () => {
  const server = dgram.createSocket('udp4');
  const packet = (...parts) => Buffer.concat([
    Buffer.from([255, 255, 255, 255]), ...parts.map(p => Buffer.isBuffer(p) ? p : Buffer.from(p))
  ]);
  const info = packet([0x49, 17], 'Fixture DayZ\0ChernarusPlus\0dayz\0DayZ\0',
    [0, 0, 0, 60, 0, 100, 119, 0, 1], '1.28\0', [0x20], 'no3rd,lqs2\0');
  const seen = new Set();
  server.on('message', (message, remote) => {
    const type = message[4];
    seen.add(type);
    const response = type === 0x54 ? info
      : type === 0x55 ? packet([0x44, 0])
      : type === 0x56 ? packet([0x45, 0, 0]) : null;
    if (response) server.send(response, remote.port, remote.address);
  });
  server.bind(0, '127.0.0.1');
  await once(server, 'listening');
  let child;
  try {
    child = spawn(process.execPath, [fileURLToPath(new URL('node_modules/gamedig/bin/gamedig.js', runtime)),
      '--type', 'dayz', `127.0.0.1:${server.address().port}`, '--maxAttempts', '1',
      '--socketTimeout', '1000', '--requestRules', '--requestPlayers'], { windowsHide: true });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', data => { stdout += data; });
    child.stderr.on('data', data => { stderr += data; });
    const timer = setTimeout(() => child.kill(), 5000);
    let code;
    try { [code] = await once(child, 'close'); } finally { clearTimeout(timer); }
    assert.equal(code, 0, stderr);
    const result = JSON.parse(stdout);
    assert.equal(result.name, 'Fixture DayZ', stdout);
    assert.equal(result.map, 'ChernarusPlus');
    assert.equal(result.maxplayers, 60);
    assert.equal(result.raw.firstPerson, true);
    assert.equal(result.raw.queue, 2);
    assert.deepEqual([...seen].sort(), [0x54, 0x55, 0x56]);
  } finally {
    if (child && child.exitCode === null) child.kill();
    server.close();
  }
});
