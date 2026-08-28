const crypto = require("crypto");
const express = require("express");
const fs = require("fs");
const path = require("path");
const { hasPermission, isSuperAdministrator, requirePermission } = require("../services/iam/access");
const { httpError } = require("../services/iam/security");
const pool = require("../db");
const { GenerationRecordRepository } = require("../services/generation-records");
const { IamRepository } = require("../services/iam/repository");

const router = express.Router();
const generationRecords = new GenerationRecordRepository(pool);
const iamRepository = new IamRepository(pool);

const DEFAULT_AI_SERVICE_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_REQUEST_TIMEOUT_MS = 15_000;
const ALLOWED_COMPOSITIONS = new Set([
    "front:half_body",
    "front:full_body",
    "slight_side:half_body",
    "slight_side:full_body"
]);

function positiveInteger(value, fallback) {
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function configuredUrl(name, fallback) {
    const raw = String(process.env[name] || fallback).trim();
    let parsed;

    try {
        parsed = new URL(raw);
    } catch {
        throw new Error(`${name} 必须是绝对 HTTP(S) URL`);
    }

    if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) {
        throw new Error(`${name} 必须是无账号信息的 HTTP(S) URL`);
    }

    return parsed;
}

function aiServiceBaseUrl() {
    return configuredUrl("AI_SERVICE_BASE_URL", DEFAULT_AI_SERVICE_BASE_URL);
}

function localAssetOrigins() {
    const configured = String(process.env.LOCAL_ASSET_ORIGINS || "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
    const defaults = process.env.NODE_ENV === "production"
        ? []
        : [
            `http://127.0.0.1:${positiveInteger(process.env.PORT, 9530)}`,
            `http://localhost:${positiveInteger(process.env.PORT, 9530)}`
        ];

    return new Set([...configured, ...defaults].map((value) => {
        let parsed;
        try {
            parsed = new URL(value);
        } catch {
            throw new Error("LOCAL_ASSET_ORIGINS 必须是逗号分隔的 HTTP(S) Origin");
        }
        if (
            !["http:", "https:"].includes(parsed.protocol) ||
            parsed.username ||
            parsed.password ||
            parsed.pathname !== "/" ||
            parsed.search ||
            parsed.hash
        ) {
            throw new Error("LOCAL_ASSET_ORIGINS 只能包含无路径、账号、查询参数的 HTTP(S) Origin");
        }
        return parsed.origin;
    }));
}

function asTrimmedText(value, fallback = "") {
    return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function normalizeEngine(value) {
    const engine = asTrimmedText(value).toLowerCase();
    return /^[a-z0-9+._-]{1,40}$/.test(engine) ? engine : "unknown";
}

function normalizeComposition(value) {
    if (value == null) return null;
    const view = asTrimmedText(value?.view).toLowerCase();
    const framing = asTrimmedText(value?.framing).toLowerCase();
    if (!ALLOWED_COMPOSITIONS.has(`${view}:${framing}`)) {
        const error = new Error("构图仅支持正面/微侧身与半身/全身四种固定组合");
        error.statusCode = 400;
        throw error;
    }
    return { view, framing };
}

function normalizeBatchId(value) {
    const batchId = asTrimmedText(value);
    if (!batchId) return null;
    if (!/^[A-Za-z0-9_-]{8,64}$/.test(batchId)) {
        const error = new Error("批次 ID 格式无效");
        error.statusCode = 400;
        throw error;
    }
    return batchId;
}

function safeJobId(value) {
    const jobId = asTrimmedText(value);
    if (!/^[A-Za-z0-9_-]{1,128}$/.test(jobId)) {
        const error = new Error("任务 ID 格式无效");
        error.statusCode = 400;
        throw error;
    }
    return jobId;
}

function canReviseRecord(user, record) {
    if (!record || !hasPermission(user, "records.write_own")) return false;
    return isSuperAdministrator(user) || String(record.user?.id || "") === String(user?.id || "");
}

function normalizeAssetUrl(value) {
    const raw = asTrimmedText(value);
    if (!raw) return null;

    let parsed;
    try {
        parsed = new URL(raw);
    } catch {
        const error = new Error("图片地址格式无效");
        error.statusCode = 400;
        throw error;
    }

    if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) {
        const error = new Error("图片地址必须使用 HTTP(S)，且不能包含账号信息");
        error.statusCode = 400;
        throw error;
    }

    return parsed.toString();
}

async function aiFetch(pathname, options = {}) {
    const target = new URL(pathname, aiServiceBaseUrl());
    const timeoutMs = positiveInteger(process.env.AI_SERVICE_TIMEOUT_MS, DEFAULT_REQUEST_TIMEOUT_MS);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    try {
        return await fetch(target, {
            ...options,
            signal: controller.signal,
            headers: {
                accept: "application/json",
                ...(typeof options.body === "string" ? { "content-type": "application/json" } : {}),
                ...(options.headers || {})
            }
        });
    } catch (error) {
        const wrapped = new Error(
            error?.name === "AbortError"
                ? `AI 服务请求超过 ${timeoutMs}ms`
                : `无法连接 AI 服务：${error?.message || error}`
        );
        wrapped.statusCode = error?.name === "AbortError" ? 504 : 502;
        throw wrapped;
    } finally {
        clearTimeout(timeout);
    }
}

function localUploadPath(value) {
    const raw = asTrimmedText(value);
    if (!raw) return null;

    let parsed;
    try {
        parsed = new URL(raw, "http://local-assets.invalid");
    } catch {
        const error = new Error("本地图片路径格式无效");
        error.statusCode = 400;
        throw error;
    }

    const isAbsolute = /^[a-z][a-z0-9+.-]*:/i.test(raw);
    if (isAbsolute && !localAssetOrigins().has(parsed.origin)) return null;

    if (!parsed.pathname.startsWith("/uploads/") || parsed.search || parsed.hash) {
        const error = new Error("本地 AI 输入只能来自 /uploads 目录");
        error.statusCode = 400;
        throw error;
    }

    let relativePath;
    try {
        relativePath = decodeURIComponent(parsed.pathname.slice("/uploads/".length));
    } catch {
        const error = new Error("本地图片路径编码无效");
        error.statusCode = 400;
        throw error;
    }

    const uploadRoot = path.resolve(__dirname, "..", "uploads");
    const target = path.resolve(uploadRoot, relativePath);
    if (target !== uploadRoot && !target.startsWith(`${uploadRoot}${path.sep}`)) {
        const error = new Error("本地图片路径越界");
        error.statusCode = 400;
        throw error;
    }
    return target;
}

function imageMimeType(filename) {
    const extension = path.extname(filename).toLowerCase();
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp"
    }[extension] || "application/octet-stream";
}

async function uploadLocalAsset(filename) {
    let stat;
    try {
        stat = await fs.promises.stat(filename);
    } catch {
        const error = new Error(`本地图片不存在：${path.basename(filename)}`);
        error.statusCode = 400;
        throw error;
    }

    if (!stat.isFile() || stat.size < 1 || stat.size > 25 * 1024 * 1024) {
        const error = new Error("本地图片必须是 1 byte 到 25 MB 的普通文件");
        error.statusCode = 400;
        throw error;
    }

    const bytes = await fs.promises.readFile(filename);
    const form = new FormData();
    form.append("file", new Blob([bytes], { type: imageMimeType(filename) }), path.basename(filename));
    const response = await aiFetch("/files", { method: "POST", body: form });
    const payload = await readAiJson(response);
    const fileId = asTrimmedText(payload.file_id);
    if (!fileId) {
        const error = new Error("AI 服务没有返回上传文件 ID");
        error.statusCode = 502;
        throw error;
    }
    return { file_id: fileId };
}

async function materializeImageSource(value) {
    const localPath = localUploadPath(value);
    if (localPath) return { imageSource: await uploadLocalAsset(localPath), auditUrl: null };

    const url = normalizeAssetUrl(value);
    if (!url) {
        const error = new Error("图片地址不能为空");
        error.statusCode = 400;
        throw error;
    }
    return { imageSource: { url }, auditUrl: url };
}

async function readAiJson(response) {
    const text = await response.text();
    let payload = null;

    if (text) {
        try {
            payload = JSON.parse(text);
        } catch {
            payload = { detail: text.slice(0, 500) };
        }
    }

    if (!response.ok) {
        const detail = payload?.detail;
        const message = Array.isArray(detail)
            ? detail.map((item) => item?.msg || JSON.stringify(item)).join("；")
            : asTrimmedText(detail, `AI 服务返回 HTTP ${response.status}`);
        const error = new Error(message);
        error.statusCode = response.status >= 500 ? 502 : response.status;
        throw error;
    }

    return payload || {};
}

async function loadAiHealth() {
    const response = await aiFetch("/health");
    const payload = await readAiJson(response);
    return {
        connected: true,
        service: payload.service || "PPE AI Service",
        status: payload.status || "ok",
        engine: normalizeEngine(payload.engine)
    };
}

function categoryOf(product) {
    return asTrimmedText(
        product?.category_level_3,
        asTrimmedText(
            product?.category_level_2,
            asTrimmedText(product?.category_level_1, "PPE 安全防护用品")
        )
    );
}

function ppeCategoryOf(product, requested = "") {
    const normalized = asTrimmedText(requested).toLowerCase();
    if (["helmet", "vest", "goggles", "gloves", "boots"].includes(normalized)) {
        return normalized;
    }
    const source = `${asTrimmedText(product?.product_name, asTrimmedText(product?.name))} ${categoryOf(product)}`.toLowerCase();
    if (/安全帽|头盔|helmet|hard hat/.test(source)) return "helmet";
    if (/反光马甲|反光背心|马甲|背心|vest|waistcoat/.test(source)) return "vest";
    if (/护目镜|眼镜|goggle|eyewear|glasses/.test(source)) return "goggles";
    if (/手套|glove/.test(source)) return "gloves";
    if (/安全鞋|劳保鞋|工作鞋|靴子|鞋|shoe|boot|footwear/.test(source)) return "boots";
    return "unknown";
}

function productSurfaceOf(product, view) {
    const source = `${asTrimmedText(product?.product_name, asTrimmedText(product?.name))} ${categoryOf(product)}`.toLowerCase();
    if (/反光马甲|反光背心|马甲|背心|reflective vest|safety vest|hi-vis/.test(source)) return "vest";
    if (/护目镜|眼镜|goggle|eyewear|glasses/.test(source)) return "eyewear";
    if (/手套|glove/.test(source)) return "gloves";
    if (/安全鞋|劳保鞋|工作鞋|靴子|鞋|shoe|boot|footwear/.test(source)) return "boots";
    if (/安全帽|头盔|helmet|hard hat/.test(source)) return "helmet";
    return asTrimmedText(view?.surface, "ppe");
}

function buildSceneDescription(scene) {
    const parts = [scene?.name, scene?.scene_name, scene?.industry]
        .map((value) => asTrimmedText(value))
        .filter(Boolean);
    return parts.length ? [...new Set(parts)].join("，") : "专业工业作业现场";
}

function buildBusinessTask(body, actor = null) {
    const product = body?.product || {};
    const view = body?.view || {};
    const model = body?.model || {};
    const scene = body?.scene || {};
    const logo = body?.logo || view?.logo || {};
    const composition = normalizeComposition(body?.composition);
    const productName = asTrimmedText(product.product_name, asTrimmedText(product.name));
    const productImage = asTrimmedText(view.image, asTrimmedText(body?.productImage));
    const logoImage = asTrimmedText(logo.image, asTrimmedText(logo.logo_url));
    const humanImage = asTrimmedText(model.image, asTrimmedText(model.image_url));
    const generationMode = asTrimmedText(body?.generationMode).toLowerCase() || (
        humanImage ? "human_wearing" : ""
    );
    const ppeCategory = ppeCategoryOf(product, body?.ppeCategory);

    if (!productName) {
        const error = new Error("缺少产品名称");
        error.statusCode = 400;
        throw error;
    }
    if (!productImage) {
        const error = new Error("当前产品视图没有可供 AI 使用的图片");
        error.statusCode = 400;
        throw error;
    }
    if (generationMode && generationMode !== "human_wearing") {
        const error = new Error("当前人物方案只支持 human_wearing 生成模式");
        error.statusCode = 400;
        throw error;
    }
    if (generationMode === "human_wearing" && !humanImage) {
        const error = new Error("人物穿戴模式必须选择带图片的模特");
        error.statusCode = 400;
        throw error;
    }
    if (generationMode === "human_wearing" && ppeCategory === "unknown") {
        const error = new Error("无法识别 PPE 穿戴类别；仅支持安全帽、背心、护目镜、手套和鞋子");
        error.statusCode = 400;
        throw error;
    }
    if (generationMode === "human_wearing" && ppeCategory === "boots" && composition?.framing !== "full_body") {
        const error = new Error("鞋子只能使用全身构图生成");
        error.statusCode = 400;
        throw error;
    }

    const jobId = crypto.randomUUID();
    const traceId = crypto.randomUUID();
    const inputAssets = [
        {
            assetId: `product-${asTrimmedText(product.id, "local")}-${asTrimmedText(view.id, "view")}`,
            role: "product_reference",
            version: 1
        }
    ];

    if (logoImage) {
        inputAssets.push({
            assetId: `logo-${asTrimmedText(logo.id, "local")}`,
            role: "logo",
            version: 1
        });
    }

    const parameters = {
        product_name: productName,
        product_category: categoryOf(product),
        scene: buildSceneDescription(scene),
        style: asTrimmedText(
            body?.style,
            "真实、专业的工业 PPE 商业摄影，产品结构准确，印刷内容清晰"
        ),
        size: asTrimmedText(body?.size, "1024x1024"),
        output_format: "png",
        sync: false,
        ...(generationMode ? { generation_mode: generationMode } : {}),
        ...(generationMode === "human_wearing" ? { ppe_category: ppeCategory } : {}),
        ...(composition || {}),
        product_view: asTrimmedText(view.id, "front"),
        requested_by_user_id: asTrimmedText(actor?.id, "anonymous"),
        requested_by_org_code: asTrimmedText(actor?.orgUnit?.code, "unassigned"),
        prompt_overrides: {
            product_code: asTrimmedText(product.goods_no),
            view_name: asTrimmedText(view.name, asTrimmedText(view.id, "正面")),
            product_surface: productSurfaceOf(product, view),
            ppe_category: ppeCategory,
            print_text: asTrimmedText(view.printText),
            logo_name: asTrimmedText(logo.name, asTrimmedText(logo.company_name)),
            model_name: asTrimmedText(model.name, asTrimmedText(model.model_name)),
            model_gender: asTrimmedText(model.gender),
            model_shot_type: asTrimmedText(model.shot_type),
            model_remark: asTrimmedText(model.remark),
            target_gender: asTrimmedText(body?.targetGender, asTrimmedText(model.gender)),
            gaze_direction: composition?.view === "front"
                ? "looking directly at the camera; face and torso straight-on"
                : "natural gaze aligned with the slight-side pose",
            composition_view: composition?.view || "",
            composition_framing: composition?.framing || "",
            scene_name: asTrimmedText(scene.name, asTrimmedText(scene.scene_name)),
            scene_industry: asTrimmedText(scene.industry)
        }
    };

    return {
        task: {
            jobId,
            type: "image_generation",
            tenantId: asTrimmedText(process.env.IAM_TENANT_ID, "shoudun-ppe"),
            traceId,
            attempt: 0,
            modelProfileId: asTrimmedText(process.env.AI_MODEL_PROFILE_ID, "ppe-marketing-v1"),
            workflowVersion: asTrimmedText(process.env.AI_WORKFLOW_VERSION, "v1"),
            inputAssets,
            parameters,
            callback: null,
            output: null
        },
        productImage,
        logoImage,
        humanImage,
        composition,
        generationMode
    };
}

function attachSourceRecord(prepared, sourceRecord) {
    prepared.sourceJobId = sourceRecord.jobId;
    prepared.task.parameters.source_job_id = sourceRecord.jobId;
    return prepared;
}

async function prepareTaskSources(prepared) {
    const productSource = await materializeImageSource(prepared.productImage);
    prepared.task.parameters.product_image = productSource.imageSource;
    if (productSource.auditUrl) prepared.task.inputAssets[0].url = productSource.auditUrl;

    if (prepared.logoImage) {
        const logoSource = await materializeImageSource(prepared.logoImage);
        prepared.task.parameters.logo_image = logoSource.imageSource;
        if (logoSource.auditUrl && prepared.task.inputAssets[1]) {
            prepared.task.inputAssets[1].url = logoSource.auditUrl;
        }
    }

    if (prepared.generationMode === "human_wearing") {
        const humanSource = await materializeImageSource(prepared.humanImage);
        prepared.task.parameters.human_reference = humanSource.imageSource;
        prepared.task.parameters.ppe_reference = productSource.imageSource;
    }
    return prepared.task;
}

function publicTaskPayload(payload, engine = null) {
    const jobId = safeJobId(payload?.jobId || payload?.task_id);
    const status = asTrimmedText(payload?.status, "queued");
    const observedEngine = engine || payload?.engine || null;

    return {
        jobId,
        status,
        engine: observedEngine ? normalizeEngine(observedEngine) : null,
        message: asTrimmedText(payload?.message),
        errorCode: payload?.errorCode || null,
        errorMessage: payload?.errorMessage || null,
        retryable: payload?.retryable ?? null,
        resultUrl: status === "succeeded" ? `/api/ai/generations/${jobId}/result` : null,
        pollUrl: `/api/ai/generations/${jobId}`
    };
}

async function loadBusinessTask(jobId) {
    const response = await aiFetch(`/ai/tasks/${encodeURIComponent(safeJobId(jobId))}`);
    return readAiJson(response);
}

router.get("/health", async (req, res, next) => {
    try {
        const health = await loadAiHealth();
        res.json({
            success: true,
            data: health
        });
    } catch (error) {
        next(error);
    }
});

router.post("/generations", requirePermission("generation.use"), async (req, res, next) => {
    let prepared;
    let recordCreated = false;
    try {
        prepared = buildBusinessTask(req.body, req.auth?.user);
        if (req.body?.sourceJobId) {
            const sourceJobId = safeJobId(req.body.sourceJobId);
            const sourceRecord = await generationRecords.findByJobId(sourceJobId);
            if (!sourceRecord) {
                throw httpError(404, "原始作图记录不存在", "GENERATION_404_RECORD_NOT_FOUND");
            }
            if (!canReviseRecord(req.auth.user, sourceRecord)) {
                throw httpError(403, "只能基于本人生成的图片重新作图", "GENERATION_403_REVISION_OWNERSHIP_REQUIRED");
            }
            if (sourceRecord.status !== "succeeded") {
                throw httpError(409, "只有已完成的记录可以用于重新作图", "GENERATION_409_REVISION_STATUS_INVALID");
            }
            attachSourceRecord(prepared, sourceRecord);
        }
        const aiRuntime = await loadAiHealth();
        await generationRecords.create({
            prepared,
            actor: req.auth.user,
            batchId: normalizeBatchId(req.body?.batchId),
            product: req.body?.product,
            model: req.body?.model,
            scene: req.body?.scene,
            engine: aiRuntime.engine
        });
        recordCreated = true;
        const task = await prepareTaskSources(prepared);

        const response = await aiFetch("/ai/tasks", {
            method: "POST",
            body: JSON.stringify(task),
            headers: { "x-trace-id": task.traceId }
        });
        const payload = await readAiJson(response);
        const publicPayload = publicTaskPayload(payload, aiRuntime.engine);
        await generationRecords.updateFromTask(task.jobId, publicPayload);
        res.status(202).json({ success: true, data: publicPayload });
    } catch (error) {
        if (recordCreated && prepared?.task?.jobId) {
            try {
                await generationRecords.markFailed(prepared.task.jobId, error);
            } catch (recordError) {
                console.error("generation record failure update failed:", recordError);
            }
        }
        next(error);
    }
});

router.get(
    "/generation-records",
    requirePermission("records.read_all"),
    async (req, res, next) => {
        try {
            const records = await generationRecords.list({
                limit: req.query.limit,
                userId: req.query.userId,
                status: req.query.status
            });
            const visibleRecords = records.map((record) => ({
                ...record,
                canEdit: record.status === "succeeded" && canReviseRecord(req.auth.user, record)
            }));
            await iamRepository.createAudit({
                actorUserId: req.auth.user.id,
                action: "generation.records_read",
                targetType: "generation_record_list",
                targetId: null,
                metadata: {
                    count: visibleRecords.length,
                    filters: {
                        userId: req.query.userId || null,
                        status: req.query.status || null
                    }
                }
            });
            res.json({ success: true, data: visibleRecords });
        } catch (error) {
            next(error);
        }
    }
);

router.get(
    "/generation-records/:jobId/edit-context",
    requirePermission("records.read_all"),
    async (req, res, next) => {
        try {
            const jobId = safeJobId(req.params.jobId);
            const record = await generationRecords.findByJobId(jobId);
            if (!record) {
                throw httpError(404, "原始作图记录不存在", "GENERATION_404_RECORD_NOT_FOUND");
            }
            if (!canReviseRecord(req.auth.user, record)) {
                throw httpError(403, "只能基于本人生成的图片重新作图", "GENERATION_403_REVISION_OWNERSHIP_REQUIRED");
            }
            if (record.status !== "succeeded") {
                throw httpError(409, "只有已完成的记录可以修改", "GENERATION_409_REVISION_STATUS_INVALID");
            }
            res.json({
                success: true,
                data: {
                    ...record,
                    canEdit: true,
                    resultUrl: `/api/ai/generations/${jobId}/result`
                }
            });
        } catch (error) {
            next(error);
        }
    }
);

router.delete(
    "/generation-records/:jobId",
    requirePermission("system.manage"),
    async (req, res, next) => {
        try {
            if (!isSuperAdministrator(req.auth.user)) {
                throw httpError(403, "只有超级管理员可以删除作图记录", "GENERATION_403_DELETE_ADMIN_REQUIRED");
            }
            const jobId = safeJobId(req.params.jobId);
            const record = await generationRecords.findByJobId(jobId);
            if (!record) {
                throw httpError(404, "作图记录不存在或已删除", "GENERATION_404_RECORD_NOT_FOUND");
            }
            const deleted = await generationRecords.softDelete(jobId, req.auth.user.id);
            if (!deleted) {
                throw httpError(409, "作图记录已经删除", "GENERATION_409_RECORD_ALREADY_DELETED");
            }
            await iamRepository.createAudit({
                actorUserId: req.auth.user.id,
                action: "generation.record_deleted",
                targetType: "generation_job",
                targetId: jobId,
                metadata: {
                    ownerUserId: record.user?.id || null,
                    productId: record.product?.id || null,
                    status: record.status
                }
            });
            res.json({ success: true, data: { jobId, deleted: true } });
        } catch (error) {
            next(error);
        }
    }
);

router.get("/generations/:jobId", async (req, res, next) => {
    try {
        const payload = await loadBusinessTask(req.params.jobId);
        const publicPayload = publicTaskPayload(payload);
        await generationRecords.updateFromTask(req.params.jobId, publicPayload);
        res.json({ success: true, data: publicPayload });
    } catch (error) {
        next(error);
    }
});

router.get("/generations/:jobId/result", async (req, res, next) => {
    try {
        const jobId = safeJobId(req.params.jobId);
        const task = await loadBusinessTask(jobId);
        const resultPath = asTrimmedText(task?.result_url);
        const expectedPrefix = `/outputs/${jobId}/`;

        if (task?.status !== "succeeded" || !resultPath.startsWith(expectedPrefix)) {
            const error = new Error(task?.errorMessage || "AI 任务尚未生成可下载结果");
            error.statusCode = task?.status === "failed" ? 422 : 409;
            throw error;
        }

        const response = await aiFetch(resultPath, { headers: { accept: "image/*" } });
        if (!response.ok) {
            await readAiJson(response);
        }

        const bytes = Buffer.from(await response.arrayBuffer());
        await iamRepository.createAudit({
            actorUserId: req.auth.user.id,
            action: "generation.result_read",
            targetType: "generation_job",
            targetId: jobId,
            metadata: { contentType: response.headers.get("content-type") || "image/png" }
        });
        res.setHeader("content-type", response.headers.get("content-type") || "image/png");
        res.setHeader("content-length", String(bytes.length));
        res.setHeader("cache-control", "private, max-age=300");
        res.send(bytes);
    } catch (error) {
        next(error);
    }
});

module.exports = router;
module.exports.ALLOWED_COMPOSITIONS = ALLOWED_COMPOSITIONS;
module.exports.buildBusinessTask = buildBusinessTask;
module.exports.normalizeComposition = normalizeComposition;
module.exports.normalizeEngine = normalizeEngine;
module.exports.ppeCategoryOf = ppeCategoryOf;
module.exports.publicTaskPayload = publicTaskPayload;
module.exports.localAssetOrigins = localAssetOrigins;
module.exports.localUploadPath = localUploadPath;
module.exports.attachSourceRecord = attachSourceRecord;
module.exports.canReviseRecord = canReviseRecord;
