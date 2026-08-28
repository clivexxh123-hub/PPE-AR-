const ALLOWED_STATUSES = new Set([
    "preparing",
    "queued",
    "running",
    "succeeded",
    "failed"
]);

function parseJson(value) {
    if (!value) return {};
    if (typeof value === "object") return value;
    try {
        return JSON.parse(value);
    } catch {
        return {};
    }
}

function progressForStatus(status, explicitProgress) {
    const progress = Number(explicitProgress);
    if (Number.isFinite(progress)) return Math.max(0, Math.min(100, Math.round(progress)));
    return { preparing: 0, queued: 5, running: 50, succeeded: 100, failed: 100 }[status] ?? 0;
}

function organizationSnapshot(user) {
    const unit = user?.orgUnit || null;
    if (!unit) return { unit: null, department: null };
    return {
        unit,
        department: unit.parent || (unit.unitType === "department" ? unit : null)
    };
}

class GenerationRecordRepository {
    constructor(executor) {
        this.executor = executor;
    }

    async create({ prepared, actor, batchId = null, product, model, scene, engine = null }) {
        const snapshot = organizationSnapshot(actor);
        const parameters = {
            generationMode: prepared.generationMode || null,
            composition: prepared.composition || null,
            size: prepared.task.parameters.size,
            modelProfileId: prepared.task.modelProfileId,
            workflowVersion: prepared.task.workflowVersion,
            sourceJobId: prepared.sourceJobId || null,
            revisionInstruction: prepared.revisionInstruction || null,
            revisionStrength: Number.isFinite(Number(prepared.revisionStrength))
                ? Number(prepared.revisionStrength)
                : null
        };
        await this.executor.query(
            `INSERT INTO business_generation_records (
                job_id, batch_id, tenant_id, trace_id,
                user_id, user_name_at_event,
                org_unit_id_at_event, org_unit_code_at_event, org_unit_name_at_event,
                department_id_at_event, department_code_at_event, department_name_at_event,
                product_id, product_name, product_code, product_view,
                composition_view, composition_framing, generation_mode,
                model_id, model_name, scene_id, scene_name,
                status, progress, engine, parameters_json
             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'preparing', 0, ?, ?)`,
            [
                prepared.task.jobId,
                batchId,
                prepared.task.tenantId,
                prepared.task.traceId,
                actor.id,
                actor.displayName,
                snapshot.unit?.id || null,
                snapshot.unit?.code || null,
                snapshot.unit?.name || null,
                snapshot.department?.id || null,
                snapshot.department?.code || null,
                snapshot.department?.name || null,
                String(product?.id || "") || null,
                String(product?.product_name || product?.name || "").trim(),
                String(product?.goods_no || "") || null,
                String(product?.viewId || prepared.task.parameters.product_view || "") || null,
                prepared.composition?.view || null,
                prepared.composition?.framing || null,
                prepared.generationMode || null,
                String(model?.id || "") || null,
                String(model?.name || model?.model_name || "") || null,
                String(scene?.id || "") || null,
                String(scene?.name || scene?.scene_name || "") || null,
                String(engine || "").trim().toLowerCase() || null,
                JSON.stringify(parameters)
            ]
        );
    }

    async updateFromTask(jobId, task = {}) {
        const status = ALLOWED_STATUSES.has(String(task.status)) ? String(task.status) : "running";
        await this.executor.query(
            `UPDATE business_generation_records
             SET status=?, progress=?, engine=COALESCE(?, engine),
                 error_code=?, error_message=?
             WHERE job_id=?`,
            [
                status,
                progressForStatus(status, task.progress),
                String(task.engine || "") || null,
                String(task.errorCode || "") || null,
                String(task.errorMessage || "").slice(0, 1000) || null,
                jobId
            ]
        );
    }

    async markFailed(jobId, error) {
        await this.updateFromTask(jobId, {
            status: "failed",
            errorCode: error?.errorCode || "BUSINESS_AI_BRIDGE_FAILED",
            errorMessage: error?.message || String(error)
        });
    }

    async list({ limit = 100, userId, status, jobId } = {}) {
        const safeLimit = Math.min(500, Math.max(1, Number(limit) || 100));
        const where = ["deletion.job_id IS NULL"];
        const values = [];
        if (jobId) {
            where.push("r.job_id=?");
            values.push(String(jobId));
        }
        if (userId) {
            where.push("r.user_id=?");
            values.push(String(userId));
        }
        if (status && ALLOWED_STATUSES.has(String(status))) {
            where.push("r.status=?");
            values.push(String(status));
        }
        const [rows] = await this.executor.query(
            `SELECT r.*
             FROM business_generation_records r
             LEFT JOIN business_generation_record_deletions deletion ON deletion.job_id=r.job_id
             WHERE ${where.join(" AND ")}
             ORDER BY r.created_at DESC
             LIMIT ${safeLimit}`,
            values
        );
        return rows.map((row) => ({
            jobId: row.job_id,
            batchId: row.batch_id,
            tenantId: row.tenant_id,
            traceId: row.trace_id,
            user: { id: row.user_id, displayName: row.user_name_at_event },
            orgUnit: row.org_unit_id_at_event ? {
                id: row.org_unit_id_at_event,
                code: row.org_unit_code_at_event,
                name: row.org_unit_name_at_event
            } : null,
            department: row.department_id_at_event ? {
                id: row.department_id_at_event,
                code: row.department_code_at_event,
                name: row.department_name_at_event
            } : null,
            product: {
                id: row.product_id,
                name: row.product_name,
                code: row.product_code,
                view: row.product_view
            },
            composition: row.composition_view ? {
                view: row.composition_view,
                framing: row.composition_framing
            } : null,
            generationMode: row.generation_mode,
            model: row.model_id ? { id: row.model_id, name: row.model_name } : null,
            scene: row.scene_id ? { id: row.scene_id, name: row.scene_name } : null,
            status: row.status,
            progress: Number(row.progress),
            engine: row.engine,
            errorCode: row.error_code,
            errorMessage: row.error_message,
            parameters: parseJson(row.parameters_json),
            createdAt: row.created_at,
            updatedAt: row.updated_at
        }));
    }

    async findByJobId(jobId) {
        const records = await this.list({ jobId, limit: 1 });
        return records[0] || null;
    }

    async softDelete(jobId, deletedByUserId) {
        const [result] = await this.executor.query(
            `INSERT IGNORE INTO business_generation_record_deletions
                (job_id, deleted_by_user_id)
             VALUES (?, ?)`,
            [String(jobId), String(deletedByUserId)]
        );
        return Number(result.affectedRows || 0) === 1;
    }
}

module.exports = {
    ALLOWED_STATUSES,
    GenerationRecordRepository,
    organizationSnapshot,
    progressForStatus
};
