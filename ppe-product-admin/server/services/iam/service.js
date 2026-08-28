const {
    httpError,
    maskPhone,
    normalizePhone,
    randomToken,
    requireSecret,
    safeHashEqual,
    sha256
} = require("./security");
const {
    DUMMY_PASSWORD_HASH,
    hashPassword,
    validatePassword,
    verifyPassword
} = require("./password");

function requiredText(value, field, maxLength = 100) {
    const text = String(value || "").trim();
    if (!text || text.length > maxLength) {
        throw httpError(400, `${field}不能为空且不能超过${maxLength}个字符`, "IAM_400_VALIDATION_FAILED");
    }
    return text;
}

function normalizeStatus(value) {
    const status = String(value || "active").trim().toLowerCase();
    if (!["active", "disabled"].includes(status)) {
        throw httpError(400, "账号状态仅支持 active 或 disabled", "IAM_400_VALIDATION_FAILED");
    }
    return status;
}

function normalizeRoleIds(value) {
    const roleIds = [...new Set((Array.isArray(value) ? value : []).map((item) => String(item).trim()).filter(Boolean))];
    if (roleIds.length !== 1) {
        throw httpError(400, "必须且只能选择一个系统角色", "IAM_400_VALIDATION_FAILED");
    }
    return roleIds;
}

function publicUser(user) {
    return {
        id: user.id,
        displayName: user.displayName,
        phone: maskPhone(user.phone),
        status: user.status,
        roles: user.roles,
        permissions: user.permissions,
        orgUnit: user.orgUnit
    };
}

class IamService {
    constructor({ repository, config, now = () => new Date() }) {
        this.repository = repository;
        this.config = config;
        this.now = now;
    }

    sessionSecret() {
        return requireSecret(this.config.sessionSecret, "IAM_SESSION_SECRET");
    }

    async login({ phone: inputPhone, password: inputPassword, ipHash, userAgent }) {
        const phone = normalizePhone(inputPhone);
        const user = await this.repository.findLoginCredentialByPhone(phone);
        const locked = Boolean(
            user?.locked_until && new Date(user.locked_until).getTime() > this.now().getTime()
        );
        const passwordMatches = await verifyPassword(
            inputPassword,
            user?.password_hash || DUMMY_PASSWORD_HASH
        );
        const accepted = Boolean(
            user && user.status === "active" && user.password_hash && !locked && passwordMatches
        );

        if (!accepted) {
            if (user?.password_hash && user.status === "active" && !locked) {
                await this.repository.recordPasswordFailure(
                    user.id,
                    this.config.passwordMaxAttempts,
                    this.config.passwordLockMinutes
                );
            }
            if (user) {
                await this.repository.createAudit({
                    actorUserId: user.id,
                    action: "auth.login_failed",
                    targetType: "user",
                    targetId: user.id,
                    metadata: {
                        reason: locked
                            ? "password_locked"
                            : user.status !== "active"
                                ? "user_disabled"
                                : "password_mismatch"
                    },
                    ipHash
                });
            }
            throw httpError(401, "手机号或密码错误", "IAM_401_LOGIN_INVALID");
        }

        const sessionToken = randomToken(32);
        const csrfToken = randomToken(24);
        const expiresAt = new Date(this.now().getTime() + this.config.sessionHours * 60 * 60_000);
        await this.repository.withTransaction(async (transaction) => {
            await transaction.resetPasswordFailures(user.id);
            await transaction.createSession({
                userId: user.id,
                tokenHash: sha256(`${this.sessionSecret()}:${sessionToken}`),
                csrfTokenHash: sha256(`${this.sessionSecret()}:${csrfToken}`),
                expiresAt,
                ipHash,
                userAgent
            });
            await transaction.createAudit({
                actorUserId: user.id,
                action: "auth.login_succeeded",
                targetType: "user",
                targetId: user.id,
                metadata: { expiresAt: expiresAt.toISOString() },
                ipHash
            });
        });

        const access = await this.repository.getUserAccess(user.id);
        return { sessionToken, csrfToken, expiresAt, user: publicUser(access) };
    }

    async authenticate(sessionToken) {
        if (!sessionToken) {
            throw httpError(401, "请先登录", "IAM_401_AUTH_REQUIRED");
        }
        const tokenHash = sha256(`${this.sessionSecret()}:${sessionToken}`);
        const session = await this.repository.findActiveSession(tokenHash);
        if (!session) {
            throw httpError(401, "登录状态已失效，请重新登录", "IAM_401_SESSION_INVALID");
        }
        const user = await this.repository.getUserAccess(session.user_id);
        if (!user || user.status !== "active") {
            await this.repository.revokeSession(session.id);
            throw httpError(403, "账号已停用", "IAM_403_USER_DISABLED");
        }
        await this.repository.touchSession(session.id);
        return {
            session: {
                id: session.id,
                csrfTokenHash: session.csrf_token_hash,
                expiresAt: session.expires_at
            },
            user: publicUser(user)
        };
    }

    verifyCsrf(auth, csrfToken) {
        const actual = sha256(`${this.sessionSecret()}:${String(csrfToken || "")}`);
        if (!safeHashEqual(actual, auth.session.csrfTokenHash)) {
            throw httpError(403, "安全校验失败，请刷新页面后重试", "IAM_403_CSRF_INVALID");
        }
    }

    async logout(auth, ipHash) {
        await this.repository.withTransaction(async (transaction) => {
            await transaction.revokeSession(auth.session.id);
            await transaction.createAudit({
                actorUserId: auth.user.id,
                action: "auth.logout",
                targetType: "user",
                targetId: auth.user.id,
                metadata: null,
                ipHash
            });
        });
    }

    async listUsers() {
        return this.repository.listUsers();
    }

    async listOrgUnits() {
        return this.repository.listOrgUnits();
    }

    async listRoles() {
        return this.repository.listRoles();
    }

    async listAudit(limit) {
        return this.repository.listAudit(limit);
    }

    async validateAccountInput(payload, existing = null) {
        const displayName = requiredText(payload.displayName ?? existing?.displayName, "员工姓名", 80);
        const phone = normalizePhone(payload.phone ?? existing?.phone);
        const status = normalizeStatus(payload.status ?? existing?.status ?? "active");
        const roleIds = normalizeRoleIds(payload.roleIds ?? existing?.roles?.map((role) => role.id));
        const orgUnitCode = requiredText(payload.orgUnitCode ?? existing?.orgUnit?.code, "组织/小组", 64);
        const passwordProvided = payload.password !== undefined && payload.password !== null && String(payload.password).length > 0;
        const password = passwordProvided ? validatePassword(payload.password) : null;
        if (!existing && !password) {
            throw httpError(400, "新增账号必须设置登录密码", "IAM_400_PASSWORD_REQUIRED");
        }

        const roles = await this.repository.getRolesByIds(roleIds);
        if (roles.length !== roleIds.length) {
            throw httpError(400, "包含不存在的角色", "IAM_400_ROLE_INVALID");
        }
        const orgUnit = await this.repository.getOrgUnitByCode(orgUnitCode);
        if (!orgUnit || !orgUnit.active) {
            throw httpError(400, "组织/小组不存在或已停用", "IAM_400_ORG_INVALID");
        }
        return { displayName, phone, status, roleIds, orgUnit, password };
    }

    async createUser(payload, actor) {
        const input = await this.validateAccountInput(payload);
        const passwordHash = await hashPassword(input.password);
        try {
            const userId = await this.repository.withTransaction(async (transaction) => {
                const id = await transaction.createUser(input);
                await transaction.setPasswordCredential(id, passwordHash);
                await transaction.setUserRoles(id, input.roleIds, actor.user.id);
                await transaction.setCurrentOrgMembership(id, input.orgUnit.id, actor.user.id);
                await transaction.createAudit({
                    actorUserId: actor.user.id,
                    action: "iam.user_created",
                    targetType: "user",
                    targetId: id,
                    metadata: {
                        displayName: input.displayName,
                        phone: maskPhone(input.phone),
                        roleIds: input.roleIds,
                        orgUnitCode: input.orgUnit.code,
                        passwordSet: true
                    }
                });
                return id;
            });
            return this.repository.getUserAccess(userId);
        } catch (error) {
            if (error?.code === "ER_DUP_ENTRY") {
                throw httpError(409, "该手机号已绑定其他账号", "IAM_409_PHONE_EXISTS");
            }
            throw error;
        }
    }

    async updateUser(userId, payload, actor) {
        const current = await this.repository.getUserAccess(userId);
        if (!current) throw httpError(404, "员工账号不存在", "IAM_404_USER_NOT_FOUND");
        const input = await this.validateAccountInput(payload, current);
        const passwordHash = input.password ? await hashPassword(input.password) : null;

        if (userId === actor.user.id && input.status === "disabled") {
            throw httpError(409, "不能停用当前登录账号", "IAM_409_CANNOT_DISABLE_SELF");
        }
        const wasAdmin = current.roles.some((role) => role.id === "admin");
        const remainsAdmin = input.status === "active" && input.roleIds.includes("admin");
        if (wasAdmin && !remainsAdmin && await this.repository.countActiveUsersWithRole("admin") <= 1) {
            throw httpError(409, "系统必须保留至少一个启用的管理员", "IAM_409_LAST_ADMIN");
        }

        try {
            await this.repository.withTransaction(async (transaction) => {
                await transaction.updateUser(userId, input);
                await transaction.setUserRoles(userId, input.roleIds, actor.user.id);
                await transaction.setCurrentOrgMembership(userId, input.orgUnit.id, actor.user.id);
                if (input.status === "disabled") await transaction.revokeUserSessions(userId);
                if (passwordHash) {
                    await transaction.setPasswordCredential(userId, passwordHash);
                    await transaction.revokeUserSessionsExcept(userId, actor.session?.id);
                }
                await transaction.createAudit({
                    actorUserId: actor.user.id,
                    action: "iam.user_updated",
                    targetType: "user",
                    targetId: userId,
                    metadata: {
                        before: {
                            displayName: current.displayName,
                            phone: maskPhone(current.phone),
                            status: current.status,
                            roleIds: current.roles.map((role) => role.id),
                            orgUnitCode: current.orgUnit?.code || null
                        },
                        after: {
                            displayName: input.displayName,
                            phone: maskPhone(input.phone),
                            status: input.status,
                            roleIds: input.roleIds,
                            orgUnitCode: input.orgUnit.code,
                            passwordChanged: Boolean(passwordHash)
                        }
                    }
                });
            });
            return this.repository.getUserAccess(userId);
        } catch (error) {
            if (error?.code === "ER_DUP_ENTRY") {
                throw httpError(409, "该手机号已绑定其他账号", "IAM_409_PHONE_EXISTS");
            }
            throw error;
        }
    }
}

module.exports = { IamService, normalizeRoleIds, normalizeStatus, publicUser, requiredText };
