const assert = require("node:assert/strict");
const test = require("node:test");

const { mapCaseTemplate } = require("../services/case-template-repository");
const {
    detectCasePreview,
    normalizeCaseTemplateInput
} = require("../services/case-template-service");
const { normalizeTemplateId } = require("../routes/case-templates");

test("published case rows expose editable AI selection data", () => {
    const template = mapCaseTemplate({
        id: "construction-general-v1",
        name: "建筑普通作业标准方案",
        industry: "建筑",
        work_scene: "普通作业",
        selection_json: JSON.stringify({ productKeywords: ["安全帽", "反光衣"] }),
        print_rules_json: JSON.stringify({ lockedAspectRatio: true }),
        version_no: 1,
        status: "published"
    });
    assert.deepEqual(template.selection.productKeywords, ["安全帽", "反光衣"]);
    assert.equal(template.printRules.lockedAspectRatio, true);
});

test("customer case input keeps visible scene and editable product keywords", () => {
    const input = normalizeCaseTemplateInput({
        customerId: "e797641d-35bc-43ea-91cc-d7b3c27320f9",
        name: "广东项目夏季施工案例",
        industry: "建筑",
        workScene: "室外施工",
        description: "用于客户夏季施工场景的视觉方案。",
        productKeywords: "安全帽，反光衣, 劳保鞋"
    });
    assert.deepEqual(input.productKeywords, ["安全帽", "反光衣", "劳保鞋"]);
    assert.equal(input.workScene, "室外施工");
});

test("customer cases require a real preview image", () => {
    assert.throws(() => detectCasePreview(Buffer.from("not-an-image")), /案例封面/);
    const png = Buffer.concat([
        Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
        Buffer.alloc(4)
    ]);
    assert.equal(detectCasePreview(png).extension, "png");
});

test("case template identifiers reject route-shaped input", () => {
    assert.equal(normalizeTemplateId("construction-general-v1"), "construction-general-v1");
    assert.throws(() => normalizeTemplateId("../private"), /ID 格式无效/);
});
