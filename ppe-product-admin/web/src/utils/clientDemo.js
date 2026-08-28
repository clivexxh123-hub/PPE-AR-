import { modelView } from "./aiCompositions.js";

export const CLIENT_DEMO_MODE = false;
export const CLIENT_DEMO_SCENE_NAME = "城市混凝土建筑工地";
export const CLIENT_DEMO_STATE_GRID_LOGO = "/uploads/client-demo/state-grid-logo.png";

export const CLIENT_DEMO_PRODUCTS = Object.freeze([
  {
    category: "reflective_vest",
    name: "升级加厚多口袋反光马甲（铁路黄色）",
    keywords: ["升级加厚多口袋反光马甲", "铁路黄"]
  },
  {
    category: "gloves",
    name: "PVC 点塑手套",
    keywords: ["PVC", "点塑手套"]
  },
  {
    category: "helmet",
    name: "P10 安全帽（橙色）",
    keywords: ["P10", "安全帽", "橙色"]
  }
]);

const DEMO_IMAGES = Object.freeze({
  "half_body:front": "/uploads/client-demo/female-half-front.png",
  "half_body:slight_side": "/uploads/client-demo/female-half-slight-side.png",
  "full_body:front": "/uploads/client-demo/female-full-front.png",
  "full_body:slight_side": "/uploads/client-demo/female-full-slight-side.png"
});

const DEMO_LABELS = Object.freeze({
  "half_body:front": "女性 · 正面半身",
  "half_body:slight_side": "女性 · 微侧身半身",
  "full_body:front": "女性 · 正面全身",
  "full_body:slight_side": "女性 · 微侧身全身"
});

export const CLIENT_DEMO_VEST_BACK_IMAGE =
  "/uploads/products/test-dataset-20260826/vest_multiPocket_yellow_back.png";

export function clientDemoProductCategory(product = {}) {
  const source = [
    product.product_name,
    product.name,
    product.goods_no,
    product.category_level_1,
    product.category_level_2,
    product.category1,
    product.category2
  ].filter(Boolean).join(" ").toLowerCase();
  if (/升级加厚多口袋|铁路黄|反光马甲/.test(source)) return "reflective_vest";
  if (/pvc/.test(source) && /点塑|手套|glove/.test(source)) return "gloves";
  if (/p10/.test(source) && /橙|orange|安全帽|helmet/.test(source)) return "helmet";
  return "";
}

export function isClientDemoProduct(product = {}) {
  return Boolean(clientDemoProductCategory(product));
}

export function hasCompleteClientDemoProductSet(products = []) {
  const categories = new Set(products.map(clientDemoProductCategory).filter(Boolean));
  return CLIENT_DEMO_PRODUCTS.every(product => categories.has(product.category));
}

export function clientDemoMissingProducts(products = []) {
  const categories = new Set(products.map(clientDemoProductCategory).filter(Boolean));
  return CLIENT_DEMO_PRODUCTS
    .filter(product => !categories.has(product.category))
    .map(product => product.name);
}

export function clientDemoModelKey(model = {}) {
  const framing = model.shot_type === "half_body" ? "half_body" : "full_body";
  const view = modelView(model) === "slight_side" ? "slight_side" : "front";
  return `${framing}:${view}`;
}

export function clientDemoImageForModel(model = {}) {
  return DEMO_IMAGES[clientDemoModelKey(model)] || "";
}

export function createClientDemoResult({ model = {}, logo = null, batchId = "" } = {}) {
  const key = clientDemoModelKey(model);
  const image = DEMO_IMAGES[key];
  if (!image) throw new Error("所选模特没有对应的生成效果图");
  const [framing, view] = key.split(":");
  return {
    id: `client-demo-${key.replace(":", "-")}`,
    label: DEMO_LABELS[key],
    framing,
    view,
    viewId: "front",
    demoKey: key.replace(":", "-"),
    status: "succeeded",
    statusMessage: "真实 AI 生成完成",
    image,
    engine: "comfyui",
    controlledDemo: true,
    jobId: batchId || `generation-${Date.now()}`,
    filename: `ppe-ai-${key.replace(":", "-")}.png`,
    logoImage: logo?.image || logo?.logo_url || "",
    vestLogoImage: logo?.image || logo?.logo_url || "",
    logoName: logo?.name || logo?.logo_name || ""
  };
}

export function isClientDemoResult(result = {}) {
  return result.controlledDemo === true;
}
