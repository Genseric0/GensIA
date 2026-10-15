const { test } = require('node:test');
const assert = require('node:assert/strict');
const { validateMetrics } = require('../scripts/validate_catalog_visual.cjs');
const good = { width: 390, scrollWidth: 390, cards: 4, visibleCards: 4, notice: true };
test('accepts complete layout', () => validateMetrics(good));
test('rejects overflow', () => assert.throws(() => validateMetrics({ ...good, scrollWidth: 391 })));
test('rejects missing state warning', () => assert.throws(() => validateMetrics({ ...good, notice: false })));
test('rejects missing or clipped cards', () => {
  assert.throws(() => validateMetrics({ ...good, cards: 3 }));
  assert.throws(() => validateMetrics({ ...good, visibleCards: 3 }));
});
