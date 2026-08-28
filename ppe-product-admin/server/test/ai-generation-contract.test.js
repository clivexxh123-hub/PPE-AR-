const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const {
    ALLOWED_COMPOSITIONS,
    attachSourceRecord,
    buildBusinessTask,
    canReviseRecord,
    localUploadPath,
    normalizeComposition,
    normalizeEngine,
    ppeCategoryOf,
    publicTaskPayload
} = require("../routes/ai-generation");

function businessPayload(overrides = {}) {
    return {
        tenantId: "untrusted-browser-tenant",
        product: {
            id: "product-1",
            product_name: "工业安全帽",
            category_level_2: "头部防护"
        },
        view: {
            id: "front",
            name: "正面",
            image: "/uploads/products/helmet-transparent.png",
            surface: "helmet"
        },
        logo: {
            id: "logo-1",
            name: "客户 Logo",
            image: "/uploads/logos/customer.png"
        },
        model: {
            id: "model-1",
            name: "模特一",
            image: "/uploads/models/model-one.png"
        },
        scene: {
            id: "scene-1",
            name: "建筑工地",
            industry: "建筑"
        },
        generationMode: "human_wearing",
        composition: { view: "front", framing: "half_body" },
        ...overrides
    };
}

test("the contract exposes the four supported view and framing geometries", () => {
    assert.deepEqual(
        [...ALLOWED_COMPOSITIONS].sort(),
        [
            "front:full_body",
            "front:half_body",
            "slight_side:full_body",
            "slight_side:half_body"
        ]
    );
    assert.deepEqual(
        normalizeComposition({ view: "slight_side", framing: "full_body" }),
        { view: "slight_side", framing: "full_body" }
    );
    assert.throws(
        () => normalizeComposition({ view: "back", framing: "portrait" }),
        /四种固定组合/
    );
});

test("human wearing tasks use real model and PPE image sources", () => {
    const actor = {
        id: "employee-7",
        orgUnit: { code: "jingshan-public-presale-2" }
    };
    const prepared = buildBusinessTask(businessPayload(), actor);

    assert.equal(prepared.generationMode, "human_wearing");
    assert.equal(prepared.humanImage, "/uploads/models/model-one.png");
    assert.equal(prepared.productImage, "/uploads/products/helmet-transparent.png");
    assert.equal(prepared.task.parameters.generation_mode, "human_wearing");
    assert.equal(prepared.task.parameters.view, "front");
    assert.equal(prepared.task.parameters.framing, "half_body");
    assert.equal(prepared.task.parameters.product_view, "front");
    assert.equal(prepared.task.parameters.prompt_overrides.gaze_direction, "looking directly at the camera; face and torso straight-on");
    assert.equal(prepared.task.parameters.requested_by_user_id, "employee-7");
    assert.equal(
        prepared.task.parameters.requested_by_org_code,
        "jingshan-public-presale-2"
    );
});

test("gender-specific full-body tasks carry the target gender into the managed prompt", () => {
    const prepared = buildBusinessTask(businessPayload({
        targetGender: "female",
        model: {
            id: "female-full-body",
            name: "女性正面全身模特",
            gender: "female",
            shot_type: "full_body",
            image: "/uploads/models/female-fullbody-front-generated-v1.png"
        },
        composition: { view: "front", framing: "full_body" }
    }));

    assert.equal(prepared.task.parameters.prompt_overrides.target_gender, "female");
    assert.equal(prepared.task.parameters.prompt_overrides.model_shot_type, "full_body");
    assert.match(prepared.task.parameters.prompt_overrides.gaze_direction, /directly at the camera/);
});

test("reflective vest products override a stale helmet surface from older clients", () => {
    const prepared = buildBusinessTask(businessPayload({
        product: {
            id: "vest-1",
            product_name: "升级加厚多口袋反光马甲",
            category_level_2: "反光马甲"
        },
        view: {
            id: "front",
            name: "正面",
            image: "/uploads/products/vest.png",
            surface: "helmet"
        }
    }));
    assert.equal(prepared.task.parameters.prompt_overrides.product_surface, "vest");
});

test("PPE categories are explicit and footwear rejects half-body compositions", () => {
    const shoe = {
        id: "shoe-1",
        product_name: "防砸防刺穿安全鞋",
        category_level_2: "足部防护"
    };
    assert.equal(ppeCategoryOf(shoe), "boots");
    assert.throws(
        () => buildBusinessTask(businessPayload({ product: shoe })),
        /鞋子只能使用全身构图/
    );
    const prepared = buildBusinessTask(businessPayload({
        product: shoe,
        ppeCategory: "boots",
        composition: { view: "front", framing: "full_body" }
    }));
    assert.equal(prepared.task.parameters.ppe_category, "boots");
    assert.equal(prepared.task.parameters.prompt_overrides.ppe_category, "boots");
});

test("the back end uploads its own absolute local asset URL instead of forwarding a private URL", () => {
    const expected = path.resolve(
        __dirname,
        "..",
        "uploads",
        "products",
        "yellow-helmet.png"
    );
    assert.equal(
        localUploadPath("http://127.0.0.1:9530/uploads/products/yellow-helmet.png"),
        expected
    );
    assert.equal(
        localUploadPath("http://localhost:9530/uploads/products/yellow-helmet.png"),
        expected
    );
    assert.equal(
        localUploadPath("http://127.0.0.1:8188/uploads/products/yellow-helmet.png"),
        null
    );
    assert.equal(
        localUploadPath("https://assets.example/products/yellow-helmet.png"),
        null
    );
});

test("the browser cannot choose the task tenant", () => {
    const prepared = buildBusinessTask(businessPayload(), { id: "employee-7" });
    assert.equal(prepared.task.tenantId, process.env.IAM_TENANT_ID || "shoudun-ppe");
    assert.notEqual(prepared.task.tenantId, "untrusted-browser-tenant");
});

test("human wearing refuses a text-only model selection", () => {
    assert.throws(
        () => buildBusinessTask(businessPayload({ model: { id: "model-without-image" } })),
        /必须选择带图片的模特/
    );
});

test("task responses expose a normalized server-observed engine", () => {
    assert.equal(normalizeEngine(" ComfyUI+Pillow "), "comfyui+pillow");
    assert.equal(normalizeEngine("invalid engine value"), "unknown");
    assert.deepEqual(
        publicTaskPayload({ jobId: "job-1", status: "succeeded", message: "ok" }, "MOCK"),
        {
            jobId: "job-1",
            status: "succeeded",
            engine: "mock",
            message: "ok",
            errorCode: null,
            errorMessage: null,
            retryable: null,
            resultUrl: "/api/ai/generations/job-1/result",
            pollUrl: "/api/ai/generations/job-1"
        }
    );
    assert.equal(
        publicTaskPayload({ jobId: "job-2", status: "succeeded", engine: "ComfyUI" }).engine,
        "comfyui"
    );
});

test("regeneration keeps a source link while using the normal AI generation task", () => {
    const prepared = buildBusinessTask(businessPayload(), { id: "employee-7" });
    const linked = attachSourceRecord(prepared, { jobId: "source-job-1" });
    assert.equal(linked, prepared);
    assert.equal(prepared.sourceJobId, "source-job-1");
    assert.equal(prepared.task.parameters.source_job_id, "source-job-1");
    assert.equal(prepared.task.parameters.generation_mode, "human_wearing");
});

test("only the owner or a super administrator can open a record for regeneration", () => {
    const record = { user: { id: "employee-7" } };
    const owner = { id: "employee-7", roles: [{ id: "sales" }], permissions: ["records.write_own"] };
    const other = { id: "employee-8", roles: [{ id: "sales" }], permissions: ["records.write_own"] };
    const admin = { id: "admin-1", roles: [{ id: "admin" }], permissions: [] };
    assert.equal(canReviseRecord(owner, record), true);
    assert.equal(canReviseRecord(other, record), false);
    assert.equal(canReviseRecord(admin, record), true);
});
