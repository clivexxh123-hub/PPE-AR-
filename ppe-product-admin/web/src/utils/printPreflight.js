const PRINT_STANDARDS = Object.freeze({
  "helmet:front": {
    id: "helmet-front",
    label: "安全帽正面印刷区",
    regularMm: { width: 70, height: 50 },
    minimumMm: { width: 35, height: 20 },
    maximumMm: { width: 90, height: 58 }
  },
  "helmet:back": {
    id: "helmet-back",
    label: "安全帽背面印刷区",
    regularMm: { width: 70, height: 50 },
    minimumMm: { width: 35, height: 20 },
    maximumMm: { width: 90, height: 58 }
  },
  "helmet:left": {
    id: "helmet-side",
    label: "安全帽侧面印刷区",
    regularMm: { width: 90, height: 40 },
    minimumMm: { width: 45, height: 20 },
    maximumMm: { width: 100, height: 45 }
  },
  "helmet:right": {
    id: "helmet-side",
    label: "安全帽侧面印刷区",
    regularMm: { width: 90, height: 40 },
    minimumMm: { width: 45, height: 20 },
    maximumMm: { width: 100, height: 45 }
  },
  "vest:front": {
    id: "vest-front-logo",
    label: "马甲正面 Logo 区",
    regularMm: { width: 90, height: 30 },
    minimumMm: { width: 45, height: 15 },
    maximumMm: { width: 100, height: 40 }
  }
});

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, Number(value) || minimum));
}

export function resolvePrintStandard(surface, face) {
  return PRINT_STANDARDS[`${surface}:${face}`] || {
    id: `${surface || "ppe"}-${face || "front"}`,
    label: "通用印刷区",
    regularMm: null,
    minimumMm: null,
    maximumMm: null
  };
}

export function scaleDimensions(standard, scalePercent = 100) {
  if (!standard?.regularMm) return null;
  const factor = clamp(scalePercent, 60, 120) / 100;
  const raw = {
    width: Math.round(standard.regularMm.width * factor),
    height: Math.round(standard.regularMm.height * factor)
  };
  const minimum = standard.minimumMm || raw;
  const maximum = standard.maximumMm || raw;
  return {
    width: clamp(raw.width, minimum.width, maximum.width),
    height: clamp(raw.height, minimum.height, maximum.height)
  };
}

function srgbChannel(value) {
  const normalized = clamp(value, 0, 255) / 255;
  return normalized <= 0.04045
    ? normalized / 12.92
    : ((normalized + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance(color) {
  return 0.2126 * srgbChannel(color?.r)
    + 0.7152 * srgbChannel(color?.g)
    + 0.0722 * srgbChannel(color?.b);
}

export function contrastRatio(first, second) {
  const light = Math.max(relativeLuminance(first), relativeLuminance(second));
  const dark = Math.min(relativeLuminance(first), relativeLuminance(second));
  return (light + 0.05) / (dark + 0.05);
}

export function contrastDecision(ratio) {
  const value = Number(ratio);
  if (!Number.isFinite(value)) {
    return {
      status: "warning",
      treatment: "请人工确认底色，并优先使用白墨底托或品牌授权单色版"
    };
  }
  if (value < 2.2) {
    return {
      status: "warning",
      treatment: "对比度偏低，建议保留品牌色并增加白墨底托或高对比描边"
    };
  }
  if (value < 3) {
    return {
      status: "warning",
      treatment: "对比度一般，建议打样确认或使用品牌授权单色版"
    };
  }
  return {
    status: "passed",
    treatment: "视觉对比度正常，仍需以实际材质打样为准"
  };
}

export function printPreflightPayload(checks = []) {
  const normalized = checks.map(check => ({
    id: String(check?.id || ""),
    label: String(check?.label || ""),
    status: ["passed", "warning", "failed"].includes(check?.status)
      ? check.status
      : "warning",
    message: String(check?.message || "")
  }));
  return {
    status: normalized.some(check => check.status === "failed")
      ? "failed"
      : normalized.some(check => check.status === "warning") ? "warning" : "passed",
    checkedAt: new Date().toISOString(),
    checks: normalized
  };
}
