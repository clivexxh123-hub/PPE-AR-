export const HUMAN_COMPOSITION_OPTIONS = Object.freeze([
  { id: "front-half", view: "front", framing: "half_body", label: "正面 · 半身" },
  { id: "front-full", view: "front", framing: "full_body", label: "正面 · 全身" },
  { id: "side-half", view: "slight_side", framing: "half_body", label: "微侧身 · 半身" },
  { id: "side-full", view: "slight_side", framing: "full_body", label: "微侧身 · 全身" }
]);

export function ppeCategoryForProduct(product) {
  const source = [
    product?.product_name,
    product?.name,
    product?.category_level_1,
    product?.category_level_2,
    product?.category_level_3,
    product?.category1,
    product?.category2,
    product?.category3
  ].filter(Boolean).join(" ").toLowerCase();

  if (/安全帽|头盔|helmet|hard hat/.test(source)) return "helmet";
  if (/反光马甲|反光背心|马甲|背心|vest|waistcoat/.test(source)) return "vest";
  if (/手套|glove/.test(source)) return "gloves";
  if (/安全鞋|劳保鞋|工作鞋|靴子|鞋|shoe|boot|footwear/.test(source)) return "boots";
  if (/护目镜|goggle|eyewear|safety glasses/.test(source)) return "goggles";
  return "unknown";
}

export function compositionsForProduct(product) {
  const category = ppeCategoryForProduct(product);
  // Current half-body model assets do not expose both hands; footwear also
  // requires the complete figure.  Keep the rule here so the UI never submits
  // a composition that the AI service must reject later.
  if (["gloves", "boots"].includes(category)) {
    return HUMAN_COMPOSITION_OPTIONS.filter(option => option.framing === "full_body");
  }
  return HUMAN_COMPOSITION_OPTIONS;
}

export function modelView(model) {
  const explicit = String(model?.view_type || model?.view || "").trim().toLowerCase();
  if (["front", "slight_side"].includes(explicit)) return explicit;

  const source = `${model?.model_key || ""} ${model?.name || ""} ${model?.model_name || ""} ${model?.remark || ""}`.toLowerCase();
  return /slight[-_ ]?side|three[-_ ]?quarter|微侧|侧前方/.test(source)
    ? "slight_side"
    : "front";
}

export function modelForComposition(composition, selectedModel, models = []) {
  if (!composition || !selectedModel) return null;

  const expectedView = composition.view;
  const expectedFraming = composition.framing;
  const matchesComposition = (model) => (
    model?.gender === selectedModel.gender
    && (model?.shot_type || "full_body") === expectedFraming
    && modelView(model) === expectedView
    && Boolean(model?.image || model?.image_url)
  );

  if (matchesComposition(selectedModel)) return selectedModel;
  return models.find(matchesComposition) || null;
}
