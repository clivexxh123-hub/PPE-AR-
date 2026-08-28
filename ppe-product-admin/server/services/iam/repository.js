const crypto = require("crypto");

function uuid() {
    return crypto.randomUUID();
}

function parseJson(value) {
    if (!value) return null;
    if (typeof value === "object") return value;
    try {
        return JSON.parse(value);
    } catch {
        return null;
    }
}

class IamRepository {
    constructor(executor) {
        this.executor = executor;
    }

    async withTransaction(work) {
        if (typeof this.executor.getConnection !== "function") {
            return work(this);
        }
        const connection = await this.executor.getConnection();
        try {
            await connection.beginTransaction();
            const result = await work(new IamRepository(connection));
            await connection.commit();
            return result;
        } catch (error) {
            await connection.rollback();
            throw error;
        } finally {
            connection.release();
        }
    }

    async findUserByPhone(phone) {
        const [rows] = await this.executor.query(
            "SELECT id, display_name, phone, status FROM iam_users WHERE phone=? LIMIT 1",
            [phone]
        );
        return rows[0] || null;
    }

    async findLoginCredentialByPhone(phone) {
        const [rows] = await this.executor.query(
            `SELECT u.id, u.display_name, u.phone, u.status,
                    credential.password_hash, credential.failed_attempts, credential.locked_until
             FROM iam_users u
             LEFT JOIN iam_password_credentials credential ON credential.user_id=u.id
             WHERE u.phone=?
             LIMIT 1`,
            [phone]
        );
        return rows[0] || null;
    }

    async findUserById(userId) {
        const [rows] = await this.executor.query(
            "SELECT id, display_name, phone, status FROM iam_users WHERE id=? LIMIT 1",
            [userId]
        );
        return rows[0] || null;
    }

    async getUserAccess(userId) {
        const user = await this.findUserById(userId);
        if (!user) return null;

        const [roles] = await this.executor.query(
            `SELECT r.id, r.name
             FROM iam_user_roles ur
             JOIN iam_roles r ON r.id=ur.role_id
             WHERE ur.user_id=?
             ORDER BY r.id`,
            [userId]
        );
        const [permissions] = await this.executor.query(
            `SELECT DISTINCT p.id
             FROM iam_user_roles ur
             JOIN iam_role_permissions rp ON rp.role_id=ur.role_id
             JOIN iam_permissions p ON p.id=rp.permission_id
             WHERE ur.user_id=?
             ORDER BY p.id`,
            [userId]
        );
        const [memberships] = await this.executor.query(
            `SELECT ou.id, ou.code, ou.name, ou.unit_type,
                    parent.id AS parent_id, parent.code AS parent_code, parent.name AS parent_name
             FROM iam_user_org_memberships m
             JOIN iam_org_units ou ON ou.id=m.org_unit_id
             LEFT JOIN iam_org_units parent ON parent.id=ou.parent_id
             WHERE m.user_id=? AND m.valid_to IS NULL
             ORDER BY m.valid_from DESC
             LIMIT 1`,
            [userId]
        );

        return {
            id: user.id,
            displayName: user.display_name,
            phone: user.phone,
            status: user.status,
            roles: roles.map((role) => ({ id: role.id, name: role.name })),
            permissions: permissions.map((permission) => permission.id),
            orgUnit: memberships[0]
                ? {
                    id: memberships[0].id,
                    code: memberships[0].code,
                    name: memberships[0].name,
                    unitType: memberships[0].unit_type,
                    parent: memberships[0].parent_id
                        ? {
                            id: memberships[0].parent_id,
                            code: memberships[0].parent_code,
                            name: memberships[0].parent_name
                        }
                        : null
                }
                : null
        };
    }

    async createSession({ id = uuid(), userId, tokenHash, csrfTokenHash, expiresAt, ipHash, userAgent }) {
        await this.executor.query(
            `INSERT INTO iam_sessions
                (id, user_id, token_hash, csrf_token_hash, expires_at, created_ip_hash, user_agent)
             VALUES (?, ?, ?, ?, ?, ?, ?)`,
            [id, userId, tokenHash, csrfTokenHash, expiresAt, ipHash || null, String(userAgent || "").slice(0, 255) || null]
        );
        return id;
    }

    async findActiveSession(tokenHash) {
        const [rows] = await this.executor.query(
            `SELECT id, user_id, token_hash, csrf_token_hash, expires_at, last_seen_at
             FROM iam_sessions
             WHERE token_hash=? AND revoked_at IS NULL AND expires_at>NOW(3)
             LIMIT 1`,
            [tokenHash]
        );
        return rows[0] || null;
    }

    async touchSession(sessionId) {
        await this.executor.query(
            "UPDATE iam_sessions SET last_seen_at=NOW(3) WHERE id=? AND revoked_at IS NULL",
            [sessionId]
        );
    }

    async revokeSession(sessionId) {
        await this.executor.query(
            "UPDATE iam_sessions SET revoked_at=NOW(3) WHERE id=? AND revoked_at IS NULL",
            [sessionId]
        );
    }

    async revokeUserSessions(userId) {
        await this.executor.query(
            "UPDATE iam_sessions SET revoked_at=NOW(3) WHERE user_id=? AND revoked_at IS NULL",
            [userId]
        );
    }

    async revokeUserSessionsExcept(userId, sessionId) {
        if (!sessionId) return this.revokeUserSessions(userId);
        await this.executor.query(
            `UPDATE iam_sessions
             SET revoked_at=NOW(3)
             WHERE user_id=? AND id<>? AND revoked_at IS NULL`,
            [userId, sessionId]
        );
    }

    async setPasswordCredential(userId, passwordHash) {
        await this.executor.query(
            `INSERT INTO iam_password_credentials
                (user_id, password_hash, password_changed_at, failed_attempts, locked_until)
             VALUES (?, ?, NOW(3), 0, NULL)
             ON DUPLICATE KEY UPDATE
                password_hash=VALUES(password_hash),
                password_changed_at=NOW(3),
                failed_attempts=0,
                locked_until=NULL`,
            [userId, passwordHash]
        );
    }

    async recordPasswordFailure(userId, maxAttempts, lockMinutes) {
        await this.executor.query(
            `UPDATE iam_password_credentials
             SET failed_attempts=failed_attempts+1,
                 locked_until=CASE
                    WHEN failed_attempts+1>=? THEN DATE_ADD(NOW(3), INTERVAL ? MINUTE)
                    ELSE locked_until
                 END
             WHERE user_id=?`,
            [maxAttempts, lockMinutes, userId]
        );
    }

    async resetPasswordFailures(userId) {
        await this.executor.query(
            `UPDATE iam_password_credentials
             SET failed_attempts=0, locked_until=NULL
             WHERE user_id=?`,
            [userId]
        );
    }

    async listOrgUnits() {
        const [rows] = await this.executor.query(
            `SELECT id, parent_id, code, name, unit_type, active
             FROM iam_org_units
             ORDER BY COALESCE(parent_id, id), unit_type, name`
        );
        return rows.map((row) => ({
            id: row.id,
            parentId: row.parent_id,
            code: row.code,
            name: row.name,
            unitType: row.unit_type,
            active: Boolean(row.active)
        }));
    }

    async getOrgUnitByCode(code) {
        const [rows] = await this.executor.query(
            "SELECT id, code, name, unit_type, active FROM iam_org_units WHERE code=? LIMIT 1",
            [code]
        );
        return rows[0] || null;
    }

    async listRoles() {
        const [rows] = await this.executor.query(
            "SELECT id, name, description, system_role FROM iam_roles ORDER BY id"
        );
        return rows.map((row) => ({
            id: row.id,
            name: row.name,
            description: row.description,
            systemRole: Boolean(row.system_role)
        }));
    }

    async getRolesByIds(roleIds) {
        if (!roleIds.length) return [];
        const placeholders = roleIds.map(() => "?").join(",");
        const [rows] = await this.executor.query(
            `SELECT id, name FROM iam_roles WHERE id IN (${placeholders})`,
            roleIds
        );
        return rows;
    }

    async getUserRoleIds(userId) {
        const [rows] = await this.executor.query(
            "SELECT role_id FROM iam_user_roles WHERE user_id=? ORDER BY role_id",
            [userId]
        );
        return rows.map((row) => row.role_id);
    }

    async countActiveUsersWithRole(roleId) {
        const [rows] = await this.executor.query(
            `SELECT COUNT(DISTINCT u.id) AS count
             FROM iam_users u
             JOIN iam_user_roles ur ON ur.user_id=u.id
             WHERE u.status='active' AND ur.role_id=?`,
            [roleId]
        );
        return Number(rows[0]?.count || 0);
    }

    async listUsers() {
        const [rows] = await this.executor.query(
            `SELECT u.id, u.display_name, u.phone, u.status, u.created_at, u.updated_at,
                    credential.user_id AS credential_user_id,
                    GROUP_CONCAT(DISTINCT r.id ORDER BY r.id SEPARATOR ',') AS role_ids,
                    GROUP_CONCAT(DISTINCT r.name ORDER BY r.id SEPARATOR ',') AS role_names,
                    ou.id AS org_unit_id, ou.code AS org_unit_code, ou.name AS org_unit_name,
                    parent.id AS department_id, parent.code AS department_code, parent.name AS department_name
             FROM iam_users u
             LEFT JOIN iam_user_roles ur ON ur.user_id=u.id
             LEFT JOIN iam_roles r ON r.id=ur.role_id
             LEFT JOIN iam_user_org_memberships m ON m.user_id=u.id AND m.valid_to IS NULL
             LEFT JOIN iam_org_units ou ON ou.id=m.org_unit_id
             LEFT JOIN iam_org_units parent ON parent.id=ou.parent_id
             LEFT JOIN iam_password_credentials credential ON credential.user_id=u.id
             GROUP BY u.id, u.display_name, u.phone, u.status, u.created_at, u.updated_at,
                      credential.user_id,
                      ou.id, ou.code, ou.name, parent.id, parent.code, parent.name
             ORDER BY u.created_at DESC`
        );
        return rows.map((row) => ({
            id: row.id,
            displayName: row.display_name,
            phone: row.phone,
            status: row.status,
            hasPassword: Boolean(row.credential_user_id),
            roles: String(row.role_ids || "").split(",").filter(Boolean).map((id, index) => ({
                id,
                name: String(row.role_names || "").split(",")[index] || id
            })),
            orgUnit: row.org_unit_id
                ? { id: row.org_unit_id, code: row.org_unit_code, name: row.org_unit_name }
                : null,
            department: row.department_id
                ? { id: row.department_id, code: row.department_code, name: row.department_name }
                : null,
            createdAt: row.created_at,
            updatedAt: row.updated_at
        }));
    }

    async createUser({ id = uuid(), displayName, phone, status = "active" }) {
        await this.executor.query(
            "INSERT INTO iam_users (id, display_name, phone, status) VALUES (?, ?, ?, ?)",
            [id, displayName, phone, status]
        );
        return id;
    }

    async updateUser(userId, { displayName, phone, status }) {
        await this.executor.query(
            "UPDATE iam_users SET display_name=?, phone=?, status=? WHERE id=?",
            [displayName, phone, status, userId]
        );
    }

    async setUserRoles(userId, roleIds, actorUserId) {
        await this.executor.query("DELETE FROM iam_user_roles WHERE user_id=?", [userId]);
        for (const roleId of roleIds) {
            await this.executor.query(
                "INSERT INTO iam_user_roles (user_id, role_id, assigned_by) VALUES (?, ?, ?)",
                [userId, roleId, actorUserId || null]
            );
        }
    }

    async setCurrentOrgMembership(userId, orgUnitId, actorUserId) {
        const [rows] = await this.executor.query(
            `SELECT id, org_unit_id
             FROM iam_user_org_memberships
             WHERE user_id=? AND valid_to IS NULL
             ORDER BY valid_from DESC
             LIMIT 1 FOR UPDATE`,
            [userId]
        );
        const current = rows[0];
        if (current?.org_unit_id === orgUnitId) return;
        if (current) {
            await this.executor.query(
                "UPDATE iam_user_org_memberships SET valid_to=NOW(3), changed_by=? WHERE id=?",
                [actorUserId || null, current.id]
            );
        }
        await this.executor.query(
            `INSERT INTO iam_user_org_memberships
                (id, user_id, org_unit_id, valid_from, changed_by)
             VALUES (?, ?, ?, NOW(3), ?)`,
            [uuid(), userId, orgUnitId, actorUserId || null]
        );
    }

    async createAudit({ actorUserId, action, targetType, targetId, metadata, ipHash }) {
        await this.executor.query(
            `INSERT INTO iam_audit_logs
                (id, actor_user_id, action, target_type, target_id, metadata_json, ip_hash)
             VALUES (?, ?, ?, ?, ?, ?, ?)`,
            [
                uuid(),
                actorUserId || null,
                action,
                targetType || null,
                targetId || null,
                metadata ? JSON.stringify(metadata) : null,
                ipHash || null
            ]
        );
    }

    async listAudit(limit = 100) {
        const safeLimit = Math.min(500, Math.max(1, Number(limit) || 100));
        const [rows] = await this.executor.query(
            `SELECT a.id, a.actor_user_id, u.display_name AS actor_name, a.action,
                    a.target_type, a.target_id, a.metadata_json, a.created_at
             FROM iam_audit_logs a
             LEFT JOIN iam_users u ON u.id=a.actor_user_id
             ORDER BY a.created_at DESC
             LIMIT ${safeLimit}`
        );
        return rows.map((row) => ({
            id: row.id,
            actorUserId: row.actor_user_id,
            actorName: row.actor_name,
            action: row.action,
            targetType: row.target_type,
            targetId: row.target_id,
            metadata: parseJson(row.metadata_json),
            createdAt: row.created_at
        }));
    }
}

module.exports = { IamRepository };
