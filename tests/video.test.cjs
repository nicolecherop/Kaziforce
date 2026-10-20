/* Behavior checks for decorative media without requiring a browser dependency. */
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { runInNewContext } = require('node:vm');
const { test } = require('node:test');
const assert = require('node:assert/strict');

const sourceCode = readFileSync(resolve(__dirname, '../static/js/landing.js'), 'utf8');

function createPreview({ reducedMotion = false, saveData = false, rejectPlayback = false } = {}) {
  const videoEvents = {};
  const documentEvents = {};
  const classes = new Set();
  const source = { dataset: { src: '/video.mp4' }, addEventListener: (name, action) => { source[name] = action; } };
  const video = {
    paused: true, ended: false, loadCount: 0,
    classList: { add: (name) => classes.add(name), remove: (name) => classes.delete(name) },
    querySelector: () => source,
    addEventListener: (name, action) => { videoEvents[name] = action; },
    load() { this.loadCount += 1; },
    async play() {
      if (rejectPlayback) throw new Error('Autoplay unavailable');
      this.paused = false;
      videoEvents.playing();
    },
    pause() { this.paused = true; },
  };
  const motion = { matches: reducedMotion, addEventListener: (name, action) => { motion[name] = action; } };
  const status = {};
  const document = {
    hidden: false,
    querySelector: (selector) => ({ '[data-hero-video]': video, '[data-video-status]': status }[selector]),
    addEventListener: (name, action) => { documentEvents[name] = action; },
  };
  runInNewContext(sourceCode, { document, window: { matchMedia: () => motion }, navigator: { connection: { saveData } } });
  return { video, source, classes, document, documentEvents, motion, status };
}

test('reduced motion shows the still without downloading video', () => {
  const preview = createPreview({ reducedMotion: true });
  assert.equal(preview.video.loadCount, 0);
  assert.equal(preview.video.paused, true);
  assert.equal(preview.classes.has('is-playing'), false);
});

test('save-data preference does not start video after returning to the tab', () => {
  const preview = createPreview({ saveData: true });
  preview.documentEvents.visibilitychange();
  assert.equal(preview.video.loadCount, 0);
});

test('background playback stops when hidden and respects a changed motion preference', () => {
  const preview = createPreview();
  assert.equal(preview.video.paused, false);
  preview.document.hidden = true;
  preview.documentEvents.visibilitychange();
  assert.equal(preview.video.paused, true);
  preview.document.hidden = false;
  preview.documentEvents.visibilitychange();
  assert.equal(preview.video.paused, false);
  preview.motion.matches = true;
  preview.motion.change();
  assert.equal(preview.video.paused, true);
  assert.equal(preview.classes.has('is-playing'), false);
});

test('a failed video source keeps the poster and is not retried on visibility changes', () => {
  const preview = createPreview();
  preview.source.error();
  assert.equal(preview.classes.has('is-playing'), false);
  preview.documentEvents.visibilitychange();
  assert.equal(preview.video.paused, true);
  assert.match(preview.status.textContent, /still image/);
});

test('autoplay rejection keeps the still-image fallback', async () => {
  const preview = createPreview({ rejectPlayback: true });
  await Promise.resolve();
  assert.equal(preview.video.paused, true);
  assert.equal(preview.classes.has('is-playing'), false);
});
