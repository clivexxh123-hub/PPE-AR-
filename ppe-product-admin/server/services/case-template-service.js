const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const { httpError } = require("./iam/security");

const TEXT_RULES = {
    name: ["案例名称", 160, true],
    industry: ["所属行业", 100, true],
    workScene: ["工种或场景", 120, true],
    description: ["案例说明", 600, true],
    standardReference: ["标准依据", 255, false]
};

function normalizedText(value, field) {
    const [label, maxLength, required] = TEXT_RULES[field];
    const text = String(value ?? "").trim();
    if (required && !text) {
        throw httpError(400, `${label}不能为空`, "CASE_TEMPLATE_400_VALIDATION_FAILED");
    }
    if (text.length > maxLength) {
        throw httpError(400, `${label}不能超过${maxLength}个字符`, "CASE_TEMPLATE_400_VALIDATION_FAILED");
    }
    return text || null;
}

function normalizeProductKeywords(value) {
    let values = value;
    if (typeof values === "string") {
        try {
            values = JSON.parse(values);
        } catch {
            values = values.split(/[,，\n]/);
        }
    }
    if (!Array.isArray(values)) values = [];
    const keywords = [...new Set(values.map((item) => String(item || "").trim()).filter(Boolean))];
    if (!keywords.length) {
        throw httpError(400, "至少填写一个产品关键词", "CASE_TEMPLATE_400_VALIDATION_FAILED");
    }
    if (keywords.length > 12 || keywords.some((item) => item.length > 50)) {
        throw httpError(400, "产品关键词最多 12 个，单项不能超过 50 个字符", "CASE_TEMPLATE_400_VALIDATION_FAILED");
    }
    return keywords;
}

function normalizeCaseTemplateInput(input = {}) {
    return {
        customerId: String(input.customerId || "").trim(),
        name: normalizedText(input.name, "name"),
        industry: normalizedText(input.industry, "industry"),
        workScene: normalizedText(input.workScene, "workScene"),
        description: normalizedText(input.description, "description"),
        standardReference: normalizedText(input.standardReference, "standardReference"),
        productKeywords: normalizeProductKeywords(input.productKeywords)
    };
}

function detectCasePreview(buffer) {
    if (!Buffer.isBuffer(buffer) || buffer.length < 12) {
        throw httpError(400, "请上传有效的案例封面图片", "CASE_TEMPLATE_400_PREVIEW_INVALID");
    }
    if (buffer.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) {
        return { extension: "png", contentType: "image/png" };
    }
    if (buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) {
        return { extension: "jpg", contentType: "image/jpeg" };
    }
    if (buffer.subarray(0, 4).toString("ascii") === "RIFF" && buffer.subarray(8, 12).toString("ascii") === "WEBP") {
        return { extension: "webp", contentType: "image/webp" };
    }
    throw httpError(400, "案例封面仅支持真实 PNG、JPEG 或 WEBP 图片", "CASE_TEMPLATE_400_PREVIEW_INVALID");
}

class CaseTemplateService {
    constructor({
        repository,
        customerService,
        tenantId = process.env.IAM_TENANT_ID || "shoudun-ppe",
        uploadRoot = path.join(__dirname, "..", "uploads", "case-templates"),
        randomUUID = () => crypto.randomUUID()
    }) {
        this.repository = repository;
        this.customerService = customerService;
        this.tenantId = tenantId;
        this.uploadRoot = path.resolve(uploadRoot);
        this.randomUUID = randomUUID;
    }

    async create(input, previewBuffer, actor) {
        const values = normalizeCaseTemplateInput(input);
        const image = detectCasePreview(previewBuffer);
        const customer = await this.customerService.get(values.customerId, actor);
        if (!customer.canEdit) {
            throw httpError(403, "只能为本人负责的客户新建案例", "CASE_TEMPLATE_403_CUSTOMER_OWNERSHIP_REQUIRED");
        }

        const id = `customer-${this.randomUUID()}`;
        await fs.promises.mkdir(this.uploadRoot, { recursive: true });
        const filename = `${id}.${image.extension}`;
        const target = path.resolve(this.uploadRoot, filename);
        if (!target.startsWith(`${this.uploadRoot}${path.sep}`)) {
            throw httpError(400, "案例封面路径无效", "CASE_TEMPLATE_400_PREVIEW_PATH_INVALID");
        }

        await fs.promises.writeFile(target, previewBuffer, { flag: "wx" });
        try {
            return await this.repository.withTransaction(async (transaction) => {
                const created = await transaction.create({
                    id,
                    tenantId: this.tenantId,
                    customerId: customer.id,
                    customerName: customer.companyShortName || customer.customerName,
                    createdBy: { id: actor.id, displayName: actor.displayName },
                    name: values.name,
                    industry: values.industry,
                    workScene: values.workScene,
                    description: values.description,
                    standardReference: values.standardReference || "客户案例，标准依据待复核",
                    selection: {
                        productKeywords: values.productKeywords,
                        sceneKeywords: [...new Set([values.industry, values.workScene])],
                        modelFilters: { shotType: "full_body", view: "front", gender: "all" }
                    },
                    printRules: {
                        logoTreatment: "preserve_brand_color",
                        safeAreaRequired: true,
                        lockedAspectRatio: true
                    },
                    previewUrl: `/uploads/case-templates/${filename}`
                });
                await transaction.createAudit({
                    actorUserId: actor.id,
                    action: "case_template.create",
                    targetType: "case_template",
                    targetId: id,
                    metadata: {
                        customerId: customer.id,
                        customerName: customer.customerName,
                        industry: values.industry,
                        workScene: values.workScene,
                        previewContentType: image.contentType
                    }
                });
                return created;
            });
        } catch (error) {
            await fs.promises.unlink(target).catch(() => {});
            throw error;
        }
    }
}

module.exports = {
    CaseTemplateService,
    detectCasePreview,
    normalizeCaseTemplateInput,
    normalizeProductKeywords
};
