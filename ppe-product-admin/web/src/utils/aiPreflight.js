const PNG_SIGNATURE = Object.freeze([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

export function normalizeEngine(value) {
  return String(value || "").trim().toLowerCase();
}

export function isMockEngine(value) {
  const engine = normalizeEngine(value);
  return engine === "mock" || engine.startsWith("mock+");
}

export function isVerifiedRealEngine(value) {
  const engine = normalizeEngine(value);
  return Boolean(engine) && engine !== "unknown" && !isMockEngine(engine);
}

export function hasPngSignature(bytes) {
  if (!bytes || bytes.length < PNG_SIGNATURE.length) return false;
  return PNG_SIGNATURE.every((value, index) => bytes[index] === value);
}

export function containsTransparentPixel(rgbaBytes) {
  if (!rgbaBytes || rgbaBytes.length < 4) return false;
  for (let index = 3; index < rgbaBytes.length; index += 4) {
    if (rgbaBytes[index] < 255) return true;
  }
  return false;
}

export function analyzeAlphaChannel(rgbaBytes) {
  if (!rgbaBytes || rgbaBytes.length < 4) {
    return { totalPixels: 0, transparentPixels: 0, visiblePixels: 0, transparentRatio: 0, visibleRatio: 0 };
  }
  let transparentPixels = 0;
  let visiblePixels = 0;
  const totalPixels = Math.floor(rgbaBytes.length / 4);
  for (let index = 3; index < totalPixels * 4; index += 4) {
    if (rgbaBytes[index] < 250) transparentPixels += 1;
    if (rgbaBytes[index] > 5) visiblePixels += 1;
  }
  return {
    totalPixels,
    transparentPixels,
    visiblePixels,
    transparentRatio: transparentPixels / totalPixels,
    visibleRatio: visiblePixels / totalPixels
  };
}
