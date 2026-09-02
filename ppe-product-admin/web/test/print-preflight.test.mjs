import assert from "node:assert/strict";
import test from "node:test";

import {
  contrastDecision,
  contrastRatio,
  resolvePrintStandard,
  scaleDimensions
} from "../src/utils/printPreflight.js";

test("print standards clamp logo size to physical limits", () => {
  const standard = resolvePrintStandard("helmet", "front");
  assert.deepEqual(scaleDimensions(standard, 100), { width: 70, height: 50 });
  assert.deepEqual(scaleDimensions(standard, 120), { width: 84, height: 58 });
  assert.deepEqual(scaleDimensions(standard, 20), { width: 42, height: 30 });
});

test("low color contrast returns an actionable production treatment", () => {
  const ratio = contrastRatio({ r: 20, g: 20, b: 20 }, { r: 25, g: 25, b: 25 });
  const decision = contrastDecision(ratio);
  assert.equal(decision.status, "warning");
  assert.match(decision.treatment, /白墨底托|单色版/);
});

test("high color contrast passes the visual preflight", () => {
  const ratio = contrastRatio({ r: 0, g: 0, b: 0 }, { r: 255, g: 255, b: 255 });
  assert.equal(Math.round(ratio), 21);
  assert.equal(contrastDecision(ratio).status, "passed");
});
