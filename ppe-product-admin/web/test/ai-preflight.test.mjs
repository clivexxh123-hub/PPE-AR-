import assert from "node:assert/strict";
import test from "node:test";

import {
  analyzeAlphaChannel,
  containsTransparentPixel,
  hasPngSignature,
  isMockEngine,
  isVerifiedRealEngine,
  normalizeEngine
} from "../src/utils/aiPreflight.js";

test("engine labels never treat mock or unknown as verified AI", () => {
  assert.equal(normalizeEngine(" ComfyUI "), "comfyui");
  assert.equal(isMockEngine("mock"), true);
  assert.equal(isMockEngine("mock+pillow"), true);
  assert.equal(isVerifiedRealEngine("unknown"), false);
  assert.equal(isVerifiedRealEngine("comfyui"), true);
  assert.equal(isVerifiedRealEngine("comfyui+pillow"), true);
});

test("PNG and alpha checks use bytes instead of filename claims", () => {
  assert.equal(hasPngSignature(Uint8Array.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])), true);
  assert.equal(hasPngSignature(Uint8Array.from([0xff, 0xd8, 0xff, 0xe0])), false);
  assert.equal(containsTransparentPixel(Uint8ClampedArray.from([0, 0, 0, 255, 0, 0, 0, 254])), true);
  assert.equal(containsTransparentPixel(Uint8ClampedArray.from([0, 0, 0, 255, 0, 0, 0, 255])), false);
  assert.deepEqual(analyzeAlphaChannel(Uint8ClampedArray.from([0, 0, 0, 0, 0, 0, 0, 255])), {
    totalPixels: 2,
    transparentPixels: 1,
    visiblePixels: 1,
    transparentRatio: 0.5,
    visibleRatio: 0.5
  });
});
