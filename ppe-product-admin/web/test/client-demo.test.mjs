import assert from "node:assert/strict";
import test from "node:test";

import {
  clientDemoImageForModel,
  clientDemoMissingProducts,
  createClientDemoResult,
  hasCompleteClientDemoProductSet,
  isClientDemoResult
} from "../src/utils/clientDemo.js";

const products = [
  { product_name: "升级加厚多口袋反光马甲（铁路黄色）" },
  { product_name: "PVC 点塑手套" },
  { product_name: "P10 安全帽（橙色）" }
];

test("client demo requires the exact three PPE categories", () => {
  assert.equal(hasCompleteClientDemoProductSet(products), true);
  assert.deepEqual(clientDemoMissingProducts(products.slice(0, 2)), ["P10 安全帽（橙色）"]);
});

test("female framing and view map to stable static assets", () => {
  assert.equal(
    clientDemoImageForModel({ shot_type: "half_body", view_type: "slight_side" }),
    "/uploads/client-demo/female-half-slight-side.png"
  );
  assert.equal(
    clientDemoImageForModel({ shot_type: "full_body", view_type: "front" }),
    "/uploads/client-demo/female-full-front.png"
  );
});

test("logo is absent unless explicitly supplied", () => {
  const plain = createClientDemoResult({ model: { shot_type: "full_body", view_type: "front" } });
  assert.equal(plain.vestLogoImage, "");
  assert.equal(plain.logoImage, "");
  assert.equal(plain.engine, "comfyui");
  assert.equal(isClientDemoResult(plain), true);
  const branded = createClientDemoResult({
    model: { shot_type: "full_body", view_type: "front" },
    logo: { image: "/state-grid.png", name: "国家电网" }
  });
  assert.equal(branded.vestLogoImage, "/state-grid.png");
  assert.equal(branded.logoImage, "/state-grid.png");
});
