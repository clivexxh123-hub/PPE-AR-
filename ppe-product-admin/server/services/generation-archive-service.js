const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const { organizationSnapshot } = require("./generation-records");
const { isSuperAdministrator } = require("./iam/access");
const { httpError } = require("./iam/security");

function validCustomerId(value) {
    const id = String(value || "").trim();
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) {
        throw httpError(400, "客户档案 ID 格式无效", "ARCHIVE_400_CUSTOMER_ID_INVALID");
    }
    return id;
}

function validJobId(value) {
    const id = String(value || "").trim();
    if (!/^[A-Za-z0-9_-]{1,128}$/.test(id)) {
        throw httpError(400, "作图任务 ID 格式无效", "ARCHIVE_400_JOB_ID_INVALID");
    }
    return id;
}

function detectImage(buffer) {
    if (!Buffer.isBuffer(buffer) || buffer.length < 12) {
        throw httpError(400, "归档文件不是有效图片", "ARCHIVE_400_IMAGE_INVALID");
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
    throw httpError(400, "归档仅支持真实 PNG、JPEG 或 WEBP 图片", "ARCHIVE_400_IMAGE_INVALID");
}

class GenerationArchiveService {
    constructor({
        repository,
        tenantId = process.env.IAM_TENANT_ID || "shoudun-ppe",
        uploadRoot = path.join(__dirname, "..", "uploads", "customer-archives")
    }) {
        this.repository = repository;
        this.tenantId = tenantId;
        this.uploadRoot = path.resolve(uploadRoot);
    }

    async list(customerId, actor, limit) {
        const normalizedCustomerId = validCustomerId(customerId);
        const customer = await this.repository.findCustomer(normalizedCustomerId, this.tenantId);
        if (!customer) throw httpError(404, "客户档案不存在或已删除", "ARCHIVE_404_CUSTOMER_NOT_FOUND");
        const records = await this.repository.list(normalizedCustomerId, this.tenantId, limit);
        await this.repository.createAudit({
            actorUserId: actor.id,
            action: "customer.generation_archives_read",
            targetType: "customer",
            targetId: normalizedCustomerId,
            metadata: { count: records.length }
        });
        return records;
    }

    async archive({ customerId, jobId, buffer }, actor) {
        const normalizedCustomerId = validCustomerId(customerId);
        const normalizedJobId = validJobId(jobId);
        const image = detectImage(buffer);
        const customer = await this.repository.findCustomer(normalizedCustomerId, this.tenantId);
        if (!customer) throw httpError(404, "客户档案不存在或已删除", "ARCHIVE_404_CUSTOMER_NOT_FOUND");
        if (customer.owner_user_id !== actor.id && !isSuperAdministrator(actor)) {
            throw httpError(403, "只能向本人客户档案归档图片", "ARCHIVE_403_CUSTOMER_OWNERSHIP_REQUIRED");
        }
        const generation = await this.repository.findGeneration(normalizedJobId, this.tenantId);
        if (!generation) throw httpError(404, "作图任务不存在", "ARCHIVE_404_GENERATION_NOT_FOUND");
        if (generation.user_id !== actor.id && !isSuperAdministrator(actor)) {
            throw httpError(403, "不能归档其他员工的作图结果", "ARCHIVE_403_GENERATION_OWNERSHIP_REQUIRED");
        }
        if (generation.status !== "succeeded") {
            throw httpError(409, "只有生成成功的图片可以归档", "ARCHIVE_409_GENERATION_NOT_READY");
        }
        const engine = String(generation.engine || "").trim().toLowerCase();
        if (engine === "mock" || engine.startsWith("mock+")) {
            throw httpError(409, "Mock 占位图不能归档到客户正式资料", "ARCHIVE_409_MOCK_RESULT");
        }
        if (!engine || engine === "unknown") {
            throw httpError(409, "生成引擎未经确认，不能归档到客户正式资料", "ARCHIVE_409_ENGINE_UNVERIFIED");
        }
        const existing = await this.repository.findArchive(normalizedJobId);
        if (existing) {
            if (existing.customerId !== normalizedCustomerId) {
                throw httpError(409, "该作图结果已经归档到其他客户", "ARCHIVE_409_ALREADY_ASSIGNED");
            }
            return { ...existing, idempotent: true };
        }

        const digest = crypto.createHash("sha256").update(buffer).digest("hex").slice(0, 16);
        const directory = path.resolve(this.uploadRoot, normalizedCustomerId);
        if (!directory.startsWith(`${this.uploadRoot}${path.sep}`)) {
            throw httpError(400, "客户归档路径无效", "ARCHIVE_400_PATH_INVALID");
        }
        await fs.promises.mkdir(directory, { recursive: true });
        const filename = `${normalizedJobId}-${digest}.${image.extension}`;
        const target = path.join(directory, filename);
        let createdFile = false;
        try {
            await fs.promises.writeFile(target, buffer, { flag: "wx" });
            createdFile = true;
        } catch (error) {
            if (error?.code !== "EEXIST") throw error;
        }
        const snapshot = organizationSnapshot(actor);
        try {
            return await this.repository.withTransaction(async (transaction) => {
                const created = await transaction.create({
                    jobId: normalizedJobId,
                    customerId: normalizedCustomerId,
                    tenantId: this.tenantId,
                    batchId: generation.batch_id,
                    fileUrl: `/uploads/customer-archives/${normalizedCustomerId}/${filename}`,
                    contentType: image.contentType,
                    fileSize: buffer.length,
                    actor,
                    orgUnit: snapshot.unit,
                    department: snapshot.department
                });
                await transaction.createAudit({
                    actorUserId: actor.id,
                    action: "customer.generation_archived",
                    targetType: "generation_job",
                    targetId: normalizedJobId,
                    metadata: {
                        customerId: normalizedCustomerId,
                        batchId: generation.batch_id,
                        contentType: image.contentType,
                        fileSize: buffer.length
                    }
                });
                return created;
            });
        } catch (error) {
            if (createdFile) await fs.promises.unlink(target).catch(() => {});
            throw error;
        }
    }
}

module.exports = { GenerationArchiveService, detectImage, validCustomerId, validJobId };
