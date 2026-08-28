const assert = require("node:assert/strict");
const test = require("node:test");

const {
    normalizeProductShowcaseInput,
    normalizeSellingPoints
} = require("../services/product-showcase");

test("product showcase fields preserve verified source data", () => {
    assert.deepEqual(normalizeProductShowcaseInput({
        material: " ABS ",
        unit_name: "个",
        specification: "帽衬可调节",
        packaging_specification: "20个/箱",
        execution_standard: "GB 2811-2019",
        selling_points: ["抗冲击", "抗冲击", "轻量化"]
    }), {
        material: "ABS",
        unitName: "个",
        specification: "帽衬可调节",
        packagingSpecification: "20个/箱",
        executionStandard: "GB 2811-2019",
        sellingPoints: ["抗冲击", "轻量化"]
    });
});

test("showcase data is bounded instead of silently truncating", () => {
    assert.throws(
        () => normalizeSellingPoints(Array.from({ length: 21 }, (_, index) => `卖点${index}`)),
        (error) => error.statusCode === 400 && error.errorCode === "PRODUCT_400_SHOWCASE_INVALID"
    );
    assert.throws(
        () => normalizeProductShowcaseInput({ execution_standard: "x".repeat(501) }),
        /执行标准不能超过500个字符/
    );
});
