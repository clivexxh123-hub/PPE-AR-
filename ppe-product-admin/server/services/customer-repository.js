const crypto = require("crypto");

function parseBoolean(value) {
    return Boolean(Number(value));
}

function mapCustomer(row) {
    if (!row) return null;
    return {
        id: row.id,
        tenantId: row.tenant_id,
        customerName: row.customer_name,
        companyShortName: row.company_short_name,
        industry: row.industry,
        remarkId: row.remark_id,
        notes: row.notes,
        archiveName: row.archive_name,
        archiveNameStandard: parseBoolean(row.archive_name_standard),
        owner: {
            id: row.owner_user_id,
            displayName: row.owner_user_name_at_create
        },
        orgUnit: row.org_unit_id_at_create ? {
            id: row.org_unit_id_at_create,
            code: row.org_unit_code_at_create,
            name: row.org_unit_name_at_create
        } : null,
        department: row.department_id_at_create ? {
            id: row.department_id_at_create,
            code: row.department_code_at_create,
            name: row.department_name_at_create
        } : null,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
        deletedAt: row.deleted_at,
        generationRecordCount: Number(row.generation_record_count || 0),
        latestGenerationAt: row.latest_generation_at || null
    };
}

class CustomerRepository {
    constructor(executor) {
        this.executor = executor;
    }

    async withTransaction(work) {
        if (typeof this.executor.getConnection !== "function") return work(this);
        const connection = await this.executor.getConnection();
        try {
            await connection.beginTransaction();
            const result = await work(new CustomerRepository(connection));
            await connection.commit();
            return result;
        } catch (error) {
            await connection.rollback();
            throw error;
        } finally {
            connection.release();
        }
    }

    async create(customer) {
        await this.executor.query(
            `INSERT INTO business_customers (
                id, tenant_id, customer_name, company_short_name, industry, remark_id, notes,
                archive_name, archive_name_standard,
                owner_user_id, owner_user_name_at_create,
                org_unit_id_at_create, org_unit_code_at_create, org_unit_name_at_create,
                department_id_at_create, department_code_at_create, department_name_at_create
             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [
                customer.id,
                customer.tenantId,
                customer.customerName,
                customer.companyShortName,
                customer.industry,
                customer.remarkId,
                customer.notes,
                customer.archiveName,
                customer.archiveNameStandard ? 1 : 0,
                customer.owner.id,
                customer.owner.displayName,
                customer.orgUnit?.id || null,
                customer.orgUnit?.code || null,
                customer.orgUnit?.name || null,
                customer.department?.id || null,
                customer.department?.code || null,
                customer.department?.name || null
            ]
        );
        return this.findById(customer.id, customer.tenantId);
    }

    async findById(customerId, tenantId, { includeDeleted = false, forUpdate = false } = {}) {
        const [rows] = await this.executor.query(
            `SELECT * FROM business_customers
             WHERE id=? AND tenant_id=? ${includeDeleted ? "" : "AND deleted_at IS NULL"}
             LIMIT 1 ${forUpdate ? "FOR UPDATE" : ""}`,
            [customerId, tenantId]
        );
        return mapCustomer(rows[0]);
    }

    async list({ tenantId, search, ownerUserId, limit = 100, offset = 0 }) {
        const safeLimit = Math.min(500, Math.max(1, Number(limit) || 100));
        const safeOffset = Math.max(0, Number(offset) || 0);
        const where = ["customer.tenant_id=?", "customer.deleted_at IS NULL"];
        const values = [tenantId];
        if (ownerUserId) {
            where.push("customer.owner_user_id=?");
            values.push(ownerUserId);
        }
        if (search) {
            where.push(`(
                customer.customer_name LIKE CONCAT('%', ?, '%') OR
                customer.company_short_name LIKE CONCAT('%', ?, '%') OR
                customer.industry LIKE CONCAT('%', ?, '%') OR
                customer.remark_id LIKE CONCAT('%', ?, '%') OR
                customer.notes LIKE CONCAT('%', ?, '%') OR
                customer.archive_name LIKE CONCAT('%', ?, '%')
            )`);
            values.push(search, search, search, search, search, search);
        }
        const clause = where.join(" AND ");
        const [countRows] = await this.executor.query(
            `SELECT COUNT(*) AS total FROM business_customers customer WHERE ${clause}`,
            values
        );
        const [rows] = await this.executor.query(
            `SELECT customer.*,
                    (
                        SELECT COUNT(*)
                        FROM business_generation_records record
                        LEFT JOIN business_generation_record_deletions deletion
                            ON deletion.job_id=record.job_id
                        WHERE record.customer_id=customer.id AND deletion.job_id IS NULL
                    ) AS generation_record_count,
                    (
                        SELECT MAX(record.created_at)
                        FROM business_generation_records record
                        LEFT JOIN business_generation_record_deletions deletion
                            ON deletion.job_id=record.job_id
                        WHERE record.customer_id=customer.id AND deletion.job_id IS NULL
                    ) AS latest_generation_at
             FROM business_customers customer
             WHERE ${clause}
             ORDER BY customer.created_at DESC
             LIMIT ${safeLimit} OFFSET ${safeOffset}`,
            values
        );
        return { items: rows.map(mapCustomer), total: Number(countRows[0]?.total || 0) };
    }

    async update(customerId, tenantId, values) {
        await this.executor.query(
            `UPDATE business_customers
             SET customer_name=?, company_short_name=?, industry=?, remark_id=?, notes=?, archive_name=?, archive_name_standard=?
             WHERE id=? AND tenant_id=? AND deleted_at IS NULL`,
            [
                values.customerName,
                values.companyShortName,
                values.industry,
                values.remarkId,
                values.notes,
                values.archiveName,
                values.archiveNameStandard ? 1 : 0,
                customerId,
                tenantId
            ]
        );
        return this.findById(customerId, tenantId);
    }

    async softDelete(customerId, tenantId, actorUserId) {
        const [result] = await this.executor.query(
            `UPDATE business_customers
             SET deleted_at=NOW(3), deleted_by_user_id=?
             WHERE id=? AND tenant_id=? AND deleted_at IS NULL`,
            [actorUserId, customerId, tenantId]
        );
        return Number(result.affectedRows || 0) === 1;
    }

    async createAudit({ actorUserId, action, targetType, targetId, metadata, ipHash }) {
        await this.executor.query(
            `INSERT INTO iam_audit_logs
                (id, actor_user_id, action, target_type, target_id, metadata_json, ip_hash)
             VALUES (?, ?, ?, ?, ?, ?, ?)`,
            [
                crypto.randomUUID(),
                actorUserId || null,
                action,
                targetType || null,
                targetId || null,
                metadata ? JSON.stringify(metadata) : null,
                ipHash || null
            ]
        );
    }
}

module.exports = { CustomerRepository, mapCustomer };
