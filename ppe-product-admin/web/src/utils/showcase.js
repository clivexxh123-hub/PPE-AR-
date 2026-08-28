export const FACE_ORDER = Object.freeze(["front", "back", "left", "right"]);
export const FACE_LABELS = Object.freeze({
  front: "正面",
  back: "背面",
  left: "左侧",
  right: "右侧"
});
export const MAX_PRODUCTS_PER_LONG_IMAGE = 6;

export function facesForSurface(surface = "ppe") {
  if (surface === "vest") return ["front", "back"];
  if (surface === "gloves") return ["front"];
  return FACE_ORDER;
}

const FACE_DEFINITIONS = Object.freeze([
  { id: "front", fileType: "view_front", keywords: ["正面", "正视", "front"], printType: "logo" },
  { id: "left", fileType: "view_left", keywords: ["左侧", "左视", "left"], printType: "text" },
  { id: "right", fileType: "view_right", keywords: ["右侧", "右视", "right"], printType: "text" },
  { id: "back", fileType: "view_back", keywords: ["背面", "背视", "back", "rear"], printType: "text" }
]);

export function parseTextArray(value) {
  if (Array.isArray(value)) return value.map(String).map(item => item.trim()).filter(Boolean);
  if (!value) return [];
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed)) return parseTextArray(parsed);
    } catch {
      return value.split(/[,，、\n]/).map(item => item.trim()).filter(Boolean);
    }
  }
  return [];
}

export function inferProductSurface(product = {}) {
  const source = [
    product.product_name,
    product.name,
    product.category_level_1,
    product.category_level_2,
    product.category_level_3,
    product.category1,
    product.category2,
    product.category3
  ].filter(Boolean).join(" ").toLowerCase();
  if (/反光马甲|反光背心|马甲|背心|reflective vest|safety vest|hi-vis/.test(source)) return "vest";
  if (/护目镜|眼镜|goggle|eyewear|glasses/.test(source)) return "eyewear";
  if (/手套|glove/.test(source)) return "gloves";
  if (/安全帽|头盔|helmet|hard hat/.test(source)) return "helmet";
  return "ppe";
}

export function mapProductFilesToFaces(
  files = [],
  resolveUrl = value => value,
  defaultPrintTexts = {},
  surface = "ppe"
) {
  const available = files.filter(file => file?.file_url);
  const used = new Set();
  const assignments = new Map();
  for (const definition of FACE_DEFINITIONS) {
    const exact = available.find(file => !used.has(file) && file.file_type === definition.fileType);
    const matched = exact || available.find((file) => {
      if (used.has(file)) return false;
      const descriptor = `${file.file_name || ""} ${file.remark || ""}`.toLowerCase();
      return definition.keywords.some(keyword => descriptor.includes(keyword));
    });
    if (matched) {
      used.add(matched);
      assignments.set(definition.id, matched);
    }
  }
  if (!assignments.has("front")) {
    assignments.set("front", available.find(file => (
      !used.has(file) && ["cover", "cover_image", "white_image"].includes(file.file_type)
    )) || null);
  }
  return FACE_DEFINITIONS.map((definition) => {
    const file = assignments.get(definition.id);
    return {
      id: definition.id,
      name: FACE_LABELS[definition.id],
      image: file ? resolveUrl(file.file_url) : "",
      selected: definition.id === "front",
      surface,
      printType: definition.printType,
      logo: null,
      printText: defaultPrintTexts[definition.id] || ""
    };
  });
}

export function facePrintInstruction(view) {
  if (!view) return "未提供该面底图及印刷说明";
  const zones = Array.isArray(view.printZones) ? view.printZones : [];
  const zoneInstructions = zones.map((zone) => {
    const zoneLogoName = String(zone.logo?.name || zone.logo?.logo_name || "").trim();
    if (zone.type === "logo" && zoneLogoName) return `Logo：${zoneLogoName}`;
    const zoneText = String(zone.text || zone.printText || "").trim();
    if (zone.type === "text" && zoneText) return `文字：${zoneText}`;
    return "";
  }).filter(Boolean);
  if (zoneInstructions.length) return zoneInstructions.join("；");
  const logoName = String(view.logo?.name || view.logo?.logo_name || "").trim();
  const text = String(view.printText || "").trim();
  if (logoName) return `Logo：${logoName}`;
  if (text) return `文字：${text}`;
  return "未设置印刷内容";
}

export function normalizeShowcaseProduct(product = {}, views = []) {
  const surface = inferProductSurface(product);
  const normalizedViews = FACE_ORDER.map((id) => {
    const source = views.find(view => view.id === id) || {};
    return {
      id,
      name: FACE_LABELS[id],
      surface,
      image: String(source.image || "").trim(),
      printText: String(source.printText || "").trim(),
      logo: source.logo ? {
        name: String(source.logo.name || source.logo.logo_name || "").trim(),
        image: String(source.logo.image || source.logo.logo_url || "").trim()
      } : null,
      printZones: Array.isArray(source.printZones)
        ? source.printZones.map(zone => ({
          id: String(zone.id || ""),
          face: String(zone.face || id),
          type: zone.type === "logo" ? "logo" : "text",
          text: String(zone.text || zone.printText || "").trim(),
          logo: zone.logo ? {
            name: String(zone.logo.name || zone.logo.logo_name || "").trim(),
            image: String(zone.logo.image || zone.logo.logo_url || "").trim()
          } : null
        }))
        : []
    };
  });
  return {
    id: String(product.id || product.goods_no || "").trim(),
    productName: String(product.product_name || product.name || "未命名产品").trim(),
    goodsNo: String(product.goods_no || product.goods_id || "").trim(),
    material: String(product.material || product.product_material || "").trim(),
    colors: parseTextArray(product.colors || product.color_list || product.product_colors),
    specification: String(
      product.specification || product.specifications || product.product_specification || ""
    ).trim(),
    executionStandard: String(
      product.execution_standard || product.national_standard || product.standard || ""
    ).trim(),
    surface,
    sellingPoints: parseTextArray(
      product.selling_points || product.product_selling_points || product.highlights
    ),
    views: normalizedViews
  };
}

export function missingShowcaseFields(product) {
  const missing = [];
  if (!product.material) missing.push("材质");
  if (!product.colors?.length) missing.push("颜色");
  if (!product.specification) missing.push("产品规格");
  if (!product.executionStandard) missing.push("执行标准");
  if (!product.sellingPoints?.length) missing.push("卖点");
  for (const face of facesForSurface(product.surface)) {
    const view = product.views?.find(item => item.id === face);
    if (!view?.image) missing.push(`${FACE_LABELS[face]}底图`);
  }
  return missing;
}

export function chunkShowcaseProducts(products, size = MAX_PRODUCTS_PER_LONG_IMAGE) {
  const safeSize = Math.max(1, Math.min(MAX_PRODUCTS_PER_LONG_IMAGE, Number(size) || MAX_PRODUCTS_PER_LONG_IMAGE));
  const chunks = [];
  for (let index = 0; index < products.length; index += safeSize) {
    chunks.push(products.slice(index, index + safeSize));
  }
  return chunks;
}

export function longImageHeight(productCount) {
  const count = Math.max(1, Math.min(MAX_PRODUCTS_PER_LONG_IMAGE, Number(productCount) || 1));
  return 210 + count * 390 + 110;
}

export function safeExportName(value) {
  return String(value || "首盾PPE方案")
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_")
    .replace(/\s+/g, "-")
    .slice(0, 80) || "首盾PPE方案";
}
