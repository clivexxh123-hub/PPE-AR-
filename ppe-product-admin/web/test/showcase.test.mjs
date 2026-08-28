import assert from "node:assert/strict";
import test from "node:test";

import {
  chunkShowcaseProducts,
  facesForSurface,
  longImageHeight,
  inferProductSurface,
  mapProductFilesToFaces,
  missingShowcaseFields,
  normalizeShowcaseProduct
} from "../src/utils/showcase.js";

test("seven products split into stable six-plus-one pages", () => {
  const products = Array.from({ length: 7 }, (_, index) => ({ id: index + 1 }));
  const pages = chunkShowcaseProducts(products);
  assert.deepEqual(pages.map(page => page.map(item => item.id)), [[1, 2, 3, 4, 5, 6], [7]]);
  assert.ok(longImageHeight(6) > longImageHeight(1));
});

test("four-face mapping never reuses a left image as the missing right face", () => {
  const faces = mapProductFilesToFaces([
    { file_type: "view_front", file_url: "/front.png", file_name: "front.png" },
    { file_type: "view_left", file_url: "/left.png", file_name: "left.png" }
  ]);
  assert.equal(faces.find(face => face.id === "front").image, "/front.png");
  assert.equal(faces.find(face => face.id === "left").image, "/left.png");
  assert.equal(faces.find(face => face.id === "right").image, "");
  assert.equal(faces.find(face => face.id === "back").image, "");
});

test("reflective vests never inherit the legacy helmet surface", () => {
  const surface = inferProductSurface({ product_name: "升级加厚多口袋反光马甲" });
  const faces = mapProductFilesToFaces(
    [{ file_type: "view_front", file_url: "/vest.png", file_name: "front.png" }],
    value => value,
    {},
    surface
  );
  assert.equal(surface, "vest");
  assert.equal(faces.find(face => face.id === "front").surface, "vest");
  assert.deepEqual(facesForSurface(surface), ["front", "back"]);
});

test("showcase normalization never invents missing product facts or faces", () => {
  const product = normalizeShowcaseProduct({
    id: 9,
    product_name: "安全帽",
    colors: '["红色"]'
  }, [{ id: "front", image: "/front.png", printText: "安全生产" }]);
  assert.equal(product.material, "");
  assert.equal(product.views.find(view => view.id === "right").image, "");
  const missing = missingShowcaseFields(product);
  assert.ok(missing.includes("材质"));
  assert.ok(missing.includes("右侧底图"));
  assert.equal(missing.some(item => item.includes("印刷说明")), false);
});
