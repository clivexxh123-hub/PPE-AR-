const express = require("express");
const multer = require("multer");

const pool = require("../db");
const { requirePermission } = require("../services/iam/access");
const { CustomerRepository } = require("../services/customer-repository");
const { CustomerService } = require("../services/customer-service");
const { GenerationArchiveRepository } = require("../services/generation-archive-repository");
const { GenerationArchiveService } = require("../services/generation-archive-service");
const { GenerationRecordRepository } = require("../services/generation-records");

const router = express.Router();
const service = new CustomerService({ repository: new CustomerRepository(pool) });
const generationArchives = new GenerationArchiveService({
    repository: new GenerationArchiveRepository(pool)
});
const generationRecords = new GenerationRecordRepository(pool);
const archiveUpload = multer({
    storage: multer.memoryStorage(),
    limits: { fileSize: 20 * 1024 * 1024, files: 1 }
});

router.get("/", requirePermission("records.read_all"), async (request, response) => {
    const result = await service.list(request.query, request.auth.user);
    response.json({ success: true, data: result });
});

router.get(
    "/:customerId/generation-records",
    requirePermission("records.read_all"),
    async (request, response) => {
        const customer = await service.get(request.params.customerId, request.auth.user);
        const records = await generationRecords.list({
            customerId: customer.id,
            limit: request.query.limit || 200
        });
        response.json({
            success: true,
            data: records.map((record) => ({
                ...record,
                resultUrl: record.status === "succeeded"
                    ? `/api/ai/generations/${encodeURIComponent(record.jobId)}/result`
                    : null
            }))
        });
    }
);

router.get("/:customerId", requirePermission("records.read_all"), async (request, response) => {
    const customer = await service.get(request.params.customerId, request.auth.user);
    response.json({ success: true, data: customer });
});

router.get(
    "/:customerId/generation-archives",
    requirePermission("records.read_all"),
    async (request, response) => {
        const records = await generationArchives.list(
            request.params.customerId,
            request.auth.user,
            request.query.limit
        );
        response.json({ success: true, data: records });
    }
);

router.post(
    "/:customerId/generation-archives",
    requirePermission("records.write_own"),
    archiveUpload.single("image"),
    async (request, response) => {
        if (!request.file?.buffer) {
            const error = new Error("请选择需要归档的生成图片");
            error.statusCode = 400;
            error.errorCode = "ARCHIVE_400_IMAGE_REQUIRED";
            throw error;
        }
        const record = await generationArchives.archive({
            customerId: request.params.customerId,
            jobId: request.body?.jobId,
            buffer: request.file.buffer
        }, request.auth.user);
        response.status(record.idempotent ? 200 : 201).json({ success: true, data: record });
    }
);

router.post("/", requirePermission("records.write_own"), async (request, response) => {
    const customer = await service.create(request.body || {}, request.auth.user);
    response.status(201).json({ success: true, data: customer });
});

router.patch("/:customerId", requirePermission("records.write_own"), async (request, response) => {
    const customer = await service.update(request.params.customerId, request.body || {}, request.auth.user);
    response.json({ success: true, data: customer });
});

router.delete("/:customerId", requirePermission("records.write_own"), async (request, response) => {
    const result = await service.remove(request.params.customerId, request.auth.user);
    response.json({ success: true, data: result });
});

module.exports = router;
