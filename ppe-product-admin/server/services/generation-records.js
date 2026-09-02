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

function safeNameSegment(value, fallback = "") {
    return String(value || fallback || "")
        .replace(/[<>:"/\\|?*+\u0000-\u001f]/g, "_")
        .replace(/\s+/g, " ")
        .replace(/[. ]+$/g, "")
        .trim()
        .slice(0, 80);
}

function dateStamp(value = new Date()) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return "00000000";
    return [date.getFullYear(), date.getMonth() + 1, date.getDate()]
        .map((part, index) => String(part).padStart(index === 0 ? 4 : 2, "0"))
        .join("");
}

function printSummary(parameters = {}) {
    const items = Array.isArray(parameters.outfit_items) ? parameters.outfit_items : [];
    const values = [];
    for (const item of items) {
        if (item?.logo_name) values.push(`${item.logo_name}Logo`);
        if (item?.print_text) values.push(item.print_text);
    }
    const prompt = parameters.prompt_overrides || {};
    if (prompt.logo_name) values.push(`${prompt.logo_name}Logo`);
    if (prompt.print_text) values.push(prompt.print_text);
    return [...new Set(values.map((value) => safeNameSegment(value)).filter(Boolean))]
        .slice(0, 2)
        .join("+") || "无印刷";
}

function buildGenerationDisplayName({
    customer = null,
    product = null,
    caseTemplate = null,
    prepared,
    versionNo = 1,
    now = new Date()
}) {
    const parameters = prepared?.task?.parameters || {};
    const segments = [
        safeNameSegment(customer?.customerName, "未绑定客户"),
        dateStamp(now),
        customer?.companyShortName && customer.companyShortName !== customer.customerName
            ? safeNameSegment(customer.companyShortName)
            : "",
        safeNameSegment(
            caseTemplate?.workScene,
            product?.product_name || product?.name || parameters.product_name || "PPE方案"
        ),
        safeNameSegment(printSummary(parameters)),
        `V${String(Math.max(1, Number(versionNo) || 1)).padStart(2, "0")}`
    ];
    return segments.filter(Boolean).join("-").slice(0, 255);
}

function normalizePrintPreflight(value) {
    const source = value && typeof value === "object" ? value : {};
    const checks = Array.isArray(source.checks) ? source.checks : [];
    return {
        status: ["passed", "warning", "failed"].includes(source.status)
            ? source.status
            : "passed",
        checkedAt: String(source.checkedAt || "").slice(0, 40) || null,
        checks: checks.slice(0, 50).map((check) => ({
            id: String(check?.id || "").slice(0, 80),
            label: String(check?.label || "").slice(0, 120),
            status: ["passed", "warning", "failed"].includes(check?.status)
                ? check.status
                : "warning",
            message: String(check?.message || "").slice(0, 500)
        }))
    };
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

    async create({
        prepared,
        actor,
        batchId = null,
        customer = null,
        caseTemplate = null,
        versionNo = 1,
        product,
        model,
        scene,
        engine = null
    }) {
        const snapshot = organizationSnapshot(actor);
        const printPreflight = normalizePrintPreflight(prepared.printPreflight);
        const displayName = buildGenerationDisplayName({
            customer,
            product,
            caseTemplate,
            prepared,
            versionNo
        });
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
                : null,
            customerId: customer?.id || null,
            caseTemplateId: caseTemplate?.id || null
        };
        await this.executor.query(
            `INSERT INTO business_generation_records (
                job_id, batch_id, tenant_id,
                customer_id, customer_name_at_event, display_name,
                case_template_id, case_template_name_at_event, version_no,
                trace_id,
                user_id, user_name_at_event,
                org_unit_id_at_event, org_unit_code_at_event, org_unit_name_at_event,
                department_id_at_event, department_code_at_event, department_name_at_event,
                product_id, product_name, product_code, product_view,
                composition_view, composition_framing, generation_mode,
                model_id, model_name, scene_id, scene_name,
                status, progress, engine, parameters_json, print_preflight_json
             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'preparing', 0, ?, ?, ?)`,
            [
                prepared.task.jobId,
                batchId,
                prepared.task.tenantId,
                customer?.id || null,
                customer?.customerName || null,
                displayName,
                caseTemplate?.id || null,
                caseTemplate?.name || null,
                Math.max(1, Number(versionNo) || 1),
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
                JSON.stringify(parameters),
                JSON.stringify(printPreflight)
            ]
        );
        return { displayName, versionNo: Math.max(1, Number(versionNo) || 1) };
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

    async list({ limit = 100, userId, status, jobId, customerId, search } = {}) {
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
        if (customerId) {
            where.push("r.customer_id=?");
            values.push(String(customerId));
        }
        if (search) {
            const term = String(search).trim().slice(0, 120);
            if (term) {
                where.push(`(
                    r.display_name LIKE CONCAT('%', ?, '%') OR
                    r.customer_name_at_event LIKE CONCAT('%', ?, '%') OR
                    r.product_name LIKE CONCAT('%', ?, '%') OR
                    r.product_code LIKE CONCAT('%', ?, '%')
                )`);
                values.push(term, term, term, term);
            }
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
            displayName: row.display_name || row.product_name,
            versionNo: Number(row.version_no || 1),
            customer: row.customer_id ? {
                id: row.customer_id,
                name: row.customer_name_at_event
            } : null,
            caseTemplate: row.case_template_id ? {
                id: row.case_template_id,
                name: row.case_template_name_at_event
            } : null,
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
            printPreflight: parseJson(row.print_preflight_json),
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
    buildGenerationDisplayName,
    normalizePrintPreflight,
    organizationSnapshot,
    printSummary,
    progressForStatus
};
