const { httpError } = require("./iam/security");

function optionalText(value, label, maxLength) {
    const text = String(value ?? "").trim();
    if (text.length > maxLength) {
        throw httpError(400, `${label}不能超过${maxLength}个字符`, "PRODUCT_400_SHOWCASE_INVALID");
    }
    return text || null;
}

function stringArray(value) {
    if (Array.isArray(value)) return value;
    if (!value) return [];
    if (typeof value === "string") {
        try {
            const parsed = JSON.parse(value);
            if (Array.isArray(parsed)) return parsed;
        } catch {
            return value.split(/[,，、\n]/);
        }
    }
    return [];
}

function normalizeSellingPoints(value) {
    const points = [...new Set(stringArray(value)
        .map((item) => String(item || "").trim())
        .filter(Boolean))];
    if (points.length > 20 || points.some((item) => item.length > 300)) {
        throw httpError(400, "商品卖点最多20条且每条不超过300个字符", "PRODUCT_400_SHOWCASE_INVALID");
    }
    return points;
}

function normalizeProductShowcaseInput(input = {}) {
    return {
        material: optionalText(input.material ?? input.product_material, "商品材质", 500),
        unitName: optionalText(input.unit_name ?? input.unit, "计量单位", 80),
        specification: optionalText(
            input.specification ?? input.specifications ?? input.product_specification,
            "产品规格",
            1000
        ),
        packagingSpecification: optionalText(
            input.packaging_specification ?? input.package_specification ?? input.packaging_spec,
            "包装规格",
            1000
        ),
        executionStandard: optionalText(
            input.execution_standard ?? input.national_standard ?? input.standard,
            "执行标准",
            500
        ),
        sellingPoints: normalizeSellingPoints(
            input.selling_points ?? input.product_selling_points ?? input.highlights
        )
    };
}

module.exports = {
    normalizeProductShowcaseInput,
    normalizeSellingPoints,
    optionalText,
    stringArray
};
