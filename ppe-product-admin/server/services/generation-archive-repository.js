const crypto = require("crypto");

function mapArchive(row) {
    if (!row) return null;
    return {
        jobId: row.job_id,
        batchId: row.batch_id,
        customerId: row.customer_id,
        fileUrl: row.archived_file_url,
        contentType: row.content_type,
        fileSize: Number(row.file_size || 0),
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
        model: row.model_id ? { id: row.model_id, name: row.model_name } : null,
        scene: row.scene_id ? { id: row.scene_id, name: row.scene_name } : null,
        archivedBy: {
            id: row.archived_by_user_id,
            displayName: row.archived_by_user_name
        },
        orgUnit: row.org_unit_id_at_event ? {
            id: row.org_unit_id_at_event,
            name: row.org_unit_name_at_event
        } : null,
        department: row.department_id_at_event ? {
            id: row.department_id_at_event,
            name: row.department_name_at_event
        } : null,
        createdAt: row.created_at
    };
}

class GenerationArchiveRepository {
    constructor(executor) {
        this.executor = executor;
    }

    async withTransaction(work) {
        if (typeof this.executor.getConnection !== "function") return work(this);
        const connection = await this.executor.getConnection();
        try {
            await connection.beginTransaction();
            const result = await work(new GenerationArchiveRepository(connection));
            await connection.commit();
            return result;
        } catch (error) {
            await connection.rollback();
            throw error;
        } finally {
            connection.release();
        }
    }

    async findCustomer(customerId, tenantId, { forUpdate = false } = {}) {
        const [rows] = await this.executor.query(
            `SELECT id, owner_user_id, customer_name, archive_name
             FROM business_customers
             WHERE id=? AND tenant_id=? AND deleted_at IS NULL
             LIMIT 1 ${forUpdate ? "FOR UPDATE" : ""}`,
            [customerId, tenantId]
        );
        return rows[0] || null;
    }

    async findGeneration(jobId, tenantId) {
        const [rows] = await this.executor.query(
            `SELECT job_id, batch_id, user_id, status, product_id, product_name, product_code,
                    product_view, composition_view, composition_framing,
                    model_id, model_name, scene_id, scene_name, engine
             FROM business_generation_records
             WHERE job_id=? AND tenant_id=? LIMIT 1`,
            [jobId, tenantId]
        );
        return rows[0] || null;
    }

    async findArchive(jobId) {
        const [rows] = await this.executor.query(
            `SELECT archive.*, record.product_id, record.product_name, record.product_code,
                    record.product_view, record.composition_view, record.composition_framing,
                    record.model_id, record.model_name, record.scene_id, record.scene_name
             FROM business_customer_generation_archives archive
             JOIN business_generation_records record ON record.job_id=archive.job_id
             WHERE archive.job_id=? LIMIT 1`,
            [jobId]
        );
        return mapArchive(rows[0]);
    }

    async create(value) {
        await this.executor.query(
            `INSERT INTO business_customer_generation_archives (
                job_id, customer_id, tenant_id, batch_id, archived_file_url,
                content_type, file_size, archived_by_user_id, archived_by_user_name,
                org_unit_id_at_event, org_unit_name_at_event,
                department_id_at_event, department_name_at_event
             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [
                value.jobId,
                value.customerId,
                value.tenantId,
                value.batchId,
                value.fileUrl,
                value.contentType,
                value.fileSize,
                value.actor.id,
                value.actor.displayName,
                value.orgUnit?.id || null,
                value.orgUnit?.name || null,
                value.department?.id || null,
                value.department?.name || null
            ]
        );
        return this.findArchive(value.jobId);
    }

    async list(customerId, tenantId, limit = 100) {
        const safeLimit = Math.min(500, Math.max(1, Number(limit) || 100));
        const [rows] = await this.executor.query(
            `SELECT archive.*, record.product_id, record.product_name, record.product_code,
                    record.product_view, record.composition_view, record.composition_framing,
                    record.model_id, record.model_name, record.scene_id, record.scene_name
             FROM business_customer_generation_archives archive
             JOIN business_generation_records record ON record.job_id=archive.job_id
             WHERE archive.customer_id=? AND archive.tenant_id=?
             ORDER BY archive.created_at DESC
             LIMIT ${safeLimit}`,
            [customerId, tenantId]
        );
        return rows.map(mapArchive);
    }

    async createAudit({ actorUserId, action, targetType, targetId, metadata }) {
        await this.executor.query(
            `INSERT INTO iam_audit_logs
                (id, actor_user_id, action, target_type, target_id, metadata_json)
             VALUES (?, ?, ?, ?, ?, ?)`,
            [
                crypto.randomUUID(),
                actorUserId,
                action,
                targetType,
                targetId,
                metadata ? JSON.stringify(metadata) : null
            ]
        );
    }
}

module.exports = { GenerationArchiveRepository, mapArchive };
