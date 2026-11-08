const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');

function background() {
  const session = {};
  const local = {};
  const spoken = [];
  const messages = [];
  let listener;
  let contextMenu;
  let offscreen = false;
  let stopped = 0;
  const area = (data) => ({
    get: async (key) => ({ [key]: data[key] }),
    set: async (value) => Object.assign(data, value),
  });
  const chrome = {
    runtime: {
      id: 'test', getURL: (path) => path,
      onInstalled: { addListener() {} },
      onMessage: { addListener(fn) { listener = fn; } },
      getContexts: async () => offscreen ? [{}] : [],
      sendMessage: async (message) => { messages.push(message); return { ok: true }; },
    },
    contextMenus: { onClicked: { addListener(fn) { contextMenu = fn; } } },
    offscreen: { createDocument: async () => { offscreen = true; } },
    storage: { session: area(session), local: area(local) },
    tts: {
      getVoices: async () => [{ lang: 'pt-BR', voiceName: 'Brasileira', extensionId: 'engine' }],
      stop() { stopped++; }, pause() {}, resume() {},
      speak(text, options, callback) { spoken.push({ text, options }); callback(); },
    },
    action: { setBadgeText: async () => {}, setBadgeBackgroundColor: async () => {} },
  };
  const settings = fs.readFileSync('extension/settings.js', 'utf8').replaceAll('export ', '');
  const source = fs.readFileSync('extension/background.js', 'utf8').replace(/^import .*;\n/, '');
  vm.runInNewContext(settings + '\n' + source, { chrome, crypto: webcrypto });
  const send = (type, extra = {}) => new Promise((resolve) => {
    listener({ target: 'background', type, ...extra }, { id: 'test' }, resolve);
  });
  return { chrome, session, local, spoken, messages, send, contextMenu, get stopped() { return stopped; } };
}
const tick = () => new Promise((resolve) => setImmediate(resolve));

test('native PT-BR reading, pause, resume and stop; old events cannot revive a stopped reading', async () => {
  const app = background();
  assert.equal((await app.send('speak', { text: ' Olá, Brasil! ', settings: { rate: 1.2, pitch: 0.8 } })).ok, true);
  const { text, options } = app.spoken[0];
  assert.equal(text, 'Olá, Brasil!');
  assert.equal(options.lang, 'pt-BR');
  assert.equal(options.extensionId, 'engine');
  assert.equal(options.rate, 1.2);
  options.onEvent({ type: 'start' });
  await tick();
  assert.equal(app.session.playback.phase, 'playing');
  await app.send('pause');
  assert.equal(app.session.playback.phase, 'paused');
  await app.send('resume');
  assert.equal(app.session.playback.phase, 'playing');
  await app.send('stop');
  options.onEvent({ type: 'end' });
  await tick();
  assert.equal(app.session.playback.message, 'Leitura parada.');
});

test('missing Brazilian voice reports actionable error instead of selecting another language', async () => {
  const app = background();
  app.chrome.tts.getVoices = async () => [{ lang: 'en-US', voiceName: 'English' }];
  const result = await app.send('speak', { text: 'Mensagem' });
  assert.equal(result.ok, false);
  assert.match(result.error, /Nenhuma voz PT-BR/);
  assert.equal(app.spoken.length, 0);
});

test('invalid input stops previous audio and reports an error', async () => {
  const app = background();
  await app.send('speak', { text: 'Uma leitura' });
  const stopped = app.stopped;
  assert.equal((await app.send('speak', { text: ' ' })).ok, false);
  assert.ok(app.stopped > stopped);
  assert.equal(app.session.playback.phase, 'error');
  assert.equal((await app.send('speak', { text: 'a'.repeat(10001) })).ok, false);
});

test('local settings are forwarded; concurrent Stop wins and stale status is ignored', async () => {
  const app = background();
  const settings = { engine: 'local', instruction: 'Voz feminina brasileira', style: 'calm', rate: 1.1 };
  const reading = app.send('speak', { text: 'Mensagem', settings });
  const stopping = app.send('stop');
  await Promise.all([reading, stopping]);
  const request = app.messages.find((message) => message.type === 'speak');
  assert.equal(request.settings.instruction, settings.instruction);
  assert.equal(request.settings.style, 'calm');
  assert.equal(app.messages.at(-1).type, 'stop');
  await app.send('audio-status', { requestId: request.requestId, phase: 'playing', message: 'stale' });
  assert.equal(app.session.playback.message, 'Leitura parada.');
});

test('context menu uses saved voice settings', async () => {
  const app = background();
  app.local.settings = { engine: 'local', style: 'epic', instruction: 'Voz grave' };
  app.contextMenu({ menuItemId: 'voxarcana-read-selection', selectionText: 'Trecho selecionado' });
  await tick();
  const request = app.messages.find((message) => message.type === 'speak');
  assert.equal(request.text, 'Trecho selecionado');
  assert.equal(request.settings.style, 'epic');
});

function offscreen() {
  let listener;
  let pending;
  const reports = [];
  const events = {};
  const revoked = [];
  const player = {
    pause() {}, removeAttribute() {}, load() {},
    addEventListener(type, fn) { events[type] = fn; },
    play: async () => {},
  };
  const context = {
    document: { getElementById: () => player },
    chrome: { runtime: {
      id: 'test', onMessage: { addListener(fn) { listener = fn; } },
      sendMessage: async (message) => { reports.push(message); return { ok: true }; },
    } },
    URL: { createObjectURL: () => 'blob:test', revokeObjectURL: (url) => revoked.push(url) },
    AbortController, TypeError, setTimeout: () => 1, clearTimeout() {},
    fetch: (_url, options) => new Promise((resolve, reject) => { pending = { resolve, reject, options }; }),
  };
  vm.runInNewContext(fs.readFileSync('extension/offscreen.js', 'utf8'), context);
  const send = (type, extra = {}) => listener({ target: 'offscreen', type, ...extra }, { id: 'test' }, () => {});
  return { send, reports, player, events, revoked, get pending() { return pending; } };
}

test('stopping an in-flight generation aborts fetch and prevents late playback', async () => {
  const app = offscreen();
  app.send('speak', { requestId: '1', text: 'Olá', settings: { rate: 1, voice: 'narrator-br', style: 'neutral' } });
  const request = app.pending;
  app.send('stop');
  assert.equal(request.options.signal.aborted, true);
  request.resolve({ ok: true, blob: async () => ({}) });
  await tick();
  assert.equal(app.player.src, undefined);
  assert.equal(app.reports.length, 0);
});

test('local audio plays, reports completion and releases its Blob URL', async () => {
  const app = offscreen();
  app.send('speak', { requestId: '1', text: 'Olá', settings: { rate: 1.2, instruction: 'Voz suave' } });
  assert.equal(JSON.parse(app.pending.options.body).instruction, 'Voz suave');
  app.pending.resolve({ ok: true, blob: async () => ({}) });
  await tick();
  assert.equal(app.player.src, 'blob:test');
  assert.equal(app.player.playbackRate, 1.2);
  assert.equal(app.reports[0].phase, 'playing');
  app.events.ended();
  await tick();
  assert.equal(app.reports.at(-1).phase, 'idle');
  assert.deepEqual(app.revoked, ['blob:test']);
});

test('connection errors from local engine reach the popup status', async () => {
  const app = offscreen();
  app.send('speak', { requestId: '1', text: 'Olá', settings: {} });
  app.pending.reject(new TypeError('Failed to fetch'));
  await tick();
  assert.equal(app.reports[0].phase, 'error');
  assert.match(app.reports[0].message, /127.0.0.1:8765/);
});
