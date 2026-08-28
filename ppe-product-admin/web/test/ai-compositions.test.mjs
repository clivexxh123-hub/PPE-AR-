import assert from "node:assert/strict";
import test from "node:test";

import {
  compositionsForProduct,
  compositionsForProducts,
  HUMAN_COMPOSITION_OPTIONS,
  modelForComposition,
  modelView,
  ppeCategoryForProduct
} from "../src/utils/aiCompositions.js";

test("generation exposes only the four standard composition outputs", () => {
  assert.equal(HUMAN_COMPOSITION_OPTIONS.length, 4);
  assert.deepEqual(
    HUMAN_COMPOSITION_OPTIONS.map(({ id, view, framing }) => ({ id, view, framing })),
    [
      { id: "front-half", view: "front", framing: "half_body" },
      { id: "front-full", view: "front", framing: "full_body" },
      { id: "side-half", view: "slight_side", framing: "half_body" },
      { id: "side-full", view: "slight_side", framing: "full_body" }
    ]
  );
});

test("each standard composition uses the matching gender, framing and view asset", () => {
  const models = HUMAN_COMPOSITION_OPTIONS.map((composition) => ({
    id: composition.id,
    gender: "male",
    shot_type: composition.framing,
    view_type: composition.view,
    image: `/${composition.id}.png`
  }));
  const selected = models[0];

  for (const composition of HUMAN_COMPOSITION_OPTIONS) {
    assert.equal(modelForComposition(composition, selected, models)?.id, composition.id);
  }
  assert.equal(modelForComposition(HUMAN_COMPOSITION_OPTIONS[0], null, models), null);
  assert.equal(modelForComposition({ view: "front", framing: "half_body" }, selected, []), selected);
});

test("legacy model view can be inferred from its key or remark", () => {
  assert.equal(modelView({ model_key: "full_body-male-front-generated-v1" }), "front");
  assert.equal(modelView({ remark: "约 25° 微侧身站直" }), "slight_side");
});

test("PPE category rules keep footwear and gloves on full-body models", () => {
  assert.equal(ppeCategoryForProduct({ product_name: "铁路反光背心" }), "vest");
  assert.equal(ppeCategoryForProduct({ product_name: "耐磨防护手套" }), "gloves");
  assert.equal(ppeCategoryForProduct({ product_name: "防砸安全鞋" }), "boots");
  assert.equal(ppeCategoryForProduct({ product_name: "ABS 安全帽" }), "helmet");
  assert.deepEqual(
    compositionsForProduct({ product_name: "防砸安全鞋" }).map(item => item.framing),
    ["full_body", "full_body"]
  );
  assert.deepEqual(
    compositionsForProduct({ product_name: "耐磨防护手套" }).map(item => item.framing),
    ["full_body", "full_body"]
  );
  assert.equal(compositionsForProduct({ product_name: "铁路反光背心" }).length, 4);
  assert.deepEqual(
    compositionsForProducts([
      { product_name: "铁路反光背心" },
      { product_name: "耐磨防护手套" },
      { product_name: "ABS 安全帽" }
    ]).map(item => item.framing),
    ["full_body", "full_body"]
  );
});
