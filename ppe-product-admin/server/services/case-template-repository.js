const crypto = require("crypto");

function parseJson(value, fallback) {
    if (value == null || value === "") return fallback;
    if (typeof value === "object") return value;
    try {
        return JSON.parse(value);
    } catch {
        return fallback;
    }
}

function mapCaseTemplate(row) {
    if (!row) return null;
    return {
        id: row.id,
        sourceType: row.source_type || "standard",
        customerId: row.customer_id || null,
        customerName: row.customer_name_at_create || null,
        createdBy: row.created_by_user_id ? {
            id: row.created_by_user_id,
            displayName: row.created_by_user_name_at_create
        } : null,
        name: row.name,
        industry: row.industry,
        workScene: row.work_scene,
        description: row.description,
        standardReference: row.standard_reference,
        standardReviewStatus: row.standard_review_status,
        selection: parseJson(row.selection_json, {}),
        printRules: parseJson(row.print_rules_json, {}),
        previewUrl: row.preview_url,
        status: row.status,
        versionNo: Number(row.version_no || 1),
        updatedAt: row.updated_at
    };
}

class CaseTemplateRepository {
    constructor(executor) {
        this.executor = executor;
    }

    async withTransaction(work) {
        if (typeof this.executor.getConnection !== "function") return work(this);
        const connection = await this.executor.getConnection();
        try {
            await connection.beginTransaction();
            const result = await work(new CaseTemplateRepository(connection));
            await connection.commit();
            return result;
        } catch (error) {
            await connection.rollback();
            throw error;
        } finally {
            connection.release();
        }
    }

    async listPublished(tenantId, {
        industry = null,
        workScene = null,
        actorUserId = null,
        includeAllCustomerCases = false
    } = {}) {
        const where = ["tenant_id=?", "status='published'"];
        const values = [tenantId];
        if (!includeAllCustomerCases) {
            where.push(`(
                source_type='standard' OR
                created_by_user_id=? OR
                customer_id IN (
                    SELECT id FROM business_customers
                    WHERE tenant_id=? AND owner_user_id=? AND deleted_at IS NULL
                )
            )`);
            values.push(actorUserId, tenantId, actorUserId);
        }
        if (industry) {
            where.push("industry=?");
            values.push(String(industry));
        }
        if (workScene) {
            where.push("work_scene=?");
            values.push(String(workScene));
        }
        const [rows] = await this.executor.query(
            `SELECT * FROM business_case_templates
             WHERE ${where.join(" AND ")}
             ORDER BY sort_order ASC, updated_at DESC`,
            values
        );
        return rows.map(mapCaseTemplate);
    }

    async findPublishedById(id, tenantId, {
        actorUserId = null,
        includeAllCustomerCases = false
    } = {}) {
        const visibility = includeAllCustomerCases
            ? ""
            : `AND (
                source_type='standard' OR
                created_by_user_id=? OR
                customer_id IN (
                    SELECT id FROM business_customers
                    WHERE tenant_id=? AND owner_user_id=? AND deleted_at IS NULL
                )
            )`;
        const values = [String(id), tenantId];
        if (!includeAllCustomerCases) values.push(actorUserId, tenantId, actorUserId);
        const [rows] = await this.executor.query(
            `SELECT * FROM business_case_templates
             WHERE id=? AND tenant_id=? AND status='published'
             ${visibility}
             LIMIT 1`,
            values
        );
        return mapCaseTemplate(rows[0]);
    }

    async create(template) {
        await this.executor.query(
            `INSERT INTO business_case_templates (
                id, tenant_id, source_type,
                customer_id, customer_name_at_create,
                created_by_user_id, created_by_user_name_at_create,
                name, industry, work_scene, description,
                standard_reference, standard_review_status,
                selection_json, print_rules_json, preview_url,
                status, version_no, sort_order
             ) VALUES (?, ?, 'customer', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', ?, ?, ?, 'published', 1, 1000)`,
            [
                template.id,
                template.tenantId,
                template.customerId,
                template.customerName,
                template.createdBy.id,
                template.createdBy.displayName,
                template.name,
                template.industry,
                template.workScene,
                template.description,
                template.standardReference,
                JSON.stringify(template.selection),
                JSON.stringify(template.printRules),
                template.previewUrl
            ]
        );
        const [rows] = await this.executor.query(
            "SELECT * FROM business_case_templates WHERE id=? AND tenant_id=? LIMIT 1",
            [template.id, template.tenantId]
        );
        return mapCaseTemplate(rows[0]);
    }

    async createAudit({ actorUserId, action, targetType, targetId, metadata }) {
        await this.executor.query(
            `INSERT INTO iam_audit_logs
                (id, actor_user_id, action, target_type, target_id, metadata_json)
             VALUES (?, ?, ?, ?, ?, ?)`,
            [
                crypto.randomUUID(),
                actorUserId || null,
                action,
                targetType || null,
                targetId || null,
                metadata ? JSON.stringify(metadata) : null
            ]
        );
    }
}

module.exports = { CaseTemplateRepository, mapCaseTemplate, parseJson };
