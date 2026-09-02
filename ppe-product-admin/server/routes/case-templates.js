const express = require("express");
const multer = require("multer");

const pool = require("../db");
const { isSuperAdministrator, requirePermission } = require("../services/iam/access");
const { httpError } = require("../services/iam/security");
const { CaseTemplateRepository } = require("../services/case-template-repository");
const { CaseTemplateService } = require("../services/case-template-service");
const { CustomerRepository } = require("../services/customer-repository");
const { CustomerService } = require("../services/customer-service");

const router = express.Router();
const repository = new CaseTemplateRepository(pool);
const service = new CaseTemplateService({
    repository,
    customerService: new CustomerService({ repository: new CustomerRepository(pool) })
});
const tenantId = String(process.env.IAM_TENANT_ID || "shoudun-ppe");
const previewUpload = multer({
    storage: multer.memoryStorage(),
    limits: { fileSize: 8 * 1024 * 1024, files: 1 }
});

function normalizeTemplateId(value) {
    const id = String(value || "").trim();
    if (!/^[a-z0-9][a-z0-9_-]{2,63}$/i.test(id)) {
        throw httpError(400, "案例模板 ID 格式无效", "CASE_TEMPLATE_400_ID_INVALID");
    }
    return id;
}

router.get("/", requirePermission("generation.use"), async (request, response) => {
    const items = await repository.listPublished(tenantId, {
        industry: String(request.query.industry || "").trim() || null,
        workScene: String(request.query.workScene || "").trim() || null,
        actorUserId: request.auth.user.id,
        includeAllCustomerCases: isSuperAdministrator(request.auth.user)
    });
    response.json({ success: true, data: { items, total: items.length } });
});

router.get("/:templateId", requirePermission("generation.use"), async (request, response) => {
    const item = await repository.findPublishedById(
        normalizeTemplateId(request.params.templateId),
        tenantId,
        {
            actorUserId: request.auth.user.id,
            includeAllCustomerCases: isSuperAdministrator(request.auth.user)
        }
    );
    if (!item) {
        throw httpError(404, "案例模板不存在或已停用", "CASE_TEMPLATE_404_NOT_FOUND");
    }
    response.json({ success: true, data: item });
});

router.post(
    "/",
    requirePermission("records.write_own"),
    previewUpload.single("preview"),
    async (request, response) => {
        if (!request.file?.buffer) {
            throw httpError(400, "请上传案例封面图片", "CASE_TEMPLATE_400_PREVIEW_REQUIRED");
        }
        const item = await service.create(request.body || {}, request.file.buffer, request.auth.user);
        response.status(201).json({ success: true, data: item });
    }
);

module.exports = router;
module.exports.normalizeTemplateId = normalizeTemplateId;
