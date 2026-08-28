const assert = require("node:assert/strict");
const test = require("node:test");

const { hashPassword } = require("../services/iam/password");
const { IamService, normalizeRoleIds } = require("../services/iam/service");

class FakeRepository {
    constructor(now) {
        this.now = now;
        this.user = {
            id: "user-1",
            display_name: "测试员工",
            phone: "13800138000",
            status: "active"
        };
        this.credential = { password_hash: null, failed_attempts: 0, locked_until: null };
        this.session = null;
        this.audits = [];
    }

    async withTransaction(work) { return work(this); }
    async findLoginCredentialByPhone(phone) {
        return phone === this.user.phone ? { ...this.user, ...this.credential } : null;
    }
    async recordPasswordFailure(userId, maxAttempts, lockMinutes) {
        assert.equal(userId, this.user.id);
        this.credential.failed_attempts += 1;
        if (this.credential.failed_attempts >= maxAttempts) {
            this.credential.locked_until = new Date(this.now().getTime() + lockMinutes * 60_000);
        }
    }
    async resetPasswordFailures() {
        this.credential.failed_attempts = 0;
        this.credential.locked_until = null;
    }
    async createSession(value) {
        this.session = {
            id: "session-1",
            user_id: value.userId,
            token_hash: value.tokenHash,
            csrf_token_hash: value.csrfTokenHash,
            expires_at: value.expiresAt,
            last_seen_at: this.now(),
            revoked_at: null
        };
    }
    async findActiveSession(tokenHash) {
        return this.session && this.session.token_hash === tokenHash && !this.session.revoked_at
            ? this.session
            : null;
    }
    async touchSession() { this.session.last_seen_at = this.now(); }
    async revokeSession() { this.session.revoked_at = this.now(); }
    async createAudit(value) { this.audits.push(value); }
    async getUserAccess() {
        return {
            id: this.user.id,
            displayName: this.user.display_name,
            phone: this.user.phone,
            status: this.user.status,
            roles: [{ id: "sales", name: "普通账号" }],
            permissions: ["generation.use", "records.read_all", "records.write_own"],
            orgUnit: { id: "group-1", code: "group-1", name: "测试组", unitType: "group", parent: null }
        };
    }
}

function loginService(repository, now) {
    return new IamService({
        repository,
        config: {
            sessionSecret: "s".repeat(32),
            sessionHours: 12,
            passwordMaxAttempts: 5,
            passwordLockMinutes: 15
        },
        now: () => new Date(now)
    });
}

test("password login creates an opaque session and CSRF binding", async () => {
    const now = new Date("2026-08-27T00:00:00.000Z");
    const repository = new FakeRepository(() => new Date(now));
    repository.credential.password_hash = await hashPassword("SecurePass123");
    const service = loginService(repository, now);

    await assert.rejects(
        service.login({ phone: "13800138000", password: "WrongPass123", ipHash: "ip" }),
        /手机号或密码错误/
    );
    assert.equal(repository.credential.failed_attempts, 1);

    const loggedIn = await service.login({
        phone: "13800138000",
        password: "SecurePass123",
        ipHash: "ip",
        userAgent: "node-test"
    });
    assert.equal(loggedIn.user.phone, "138****8000");
    assert.ok(loggedIn.sessionToken.length > 30);
    assert.ok(loggedIn.csrfToken.length > 20);
    assert.equal(repository.credential.failed_attempts, 0);

    const auth = await service.authenticate(loggedIn.sessionToken);
    assert.equal(auth.user.id, "user-1");
    assert.doesNotThrow(() => service.verifyCsrf(auth, loggedIn.csrfToken));
    assert.throws(() => service.verifyCsrf(auth, "wrong"), /安全校验失败/);

    await service.logout(auth, "ip");
    await assert.rejects(service.authenticate(loggedIn.sessionToken), /登录状态已失效/);
});

test("unknown phone and wrong password use the same public login error", async () => {
    const now = new Date("2026-08-27T00:00:00.000Z");
    const repository = new FakeRepository(() => new Date(now));
    repository.credential.password_hash = await hashPassword("SecurePass123");
    const service = loginService(repository, now);

    for (const attempt of [
        { phone: "13900139000", password: "SecurePass123" },
        { phone: "13800138000", password: "WrongPass123" }
    ]) {
        await assert.rejects(
            service.login({ ...attempt, ipHash: "ip" }),
            (error) => error.errorCode === "IAM_401_LOGIN_INVALID" && error.message === "手机号或密码错误"
        );
    }
});

test("consecutive password failures temporarily lock the account", async () => {
    const now = new Date("2026-08-27T00:00:00.000Z");
    const repository = new FakeRepository(() => new Date(now));
    repository.credential.password_hash = await hashPassword("SecurePass123");
    const service = loginService(repository, now);

    for (let attempt = 0; attempt < 5; attempt += 1) {
        await assert.rejects(
            service.login({ phone: "13800138000", password: "WrongPass123", ipHash: "ip" }),
            /手机号或密码错误/
        );
    }
    assert.ok(repository.credential.locked_until > now);
    await assert.rejects(
        service.login({ phone: "13800138000", password: "SecurePass123", ipHash: "ip" }),
        /手机号或密码错误/
    );
});

function accountAccess(overrides = {}) {
    return {
        id: "admin-1",
        displayName: "系统管理员",
        phone: "13800138000",
        status: "active",
        roles: [{ id: "admin", name: "超级管理员" }],
        permissions: ["system.manage"],
        orgUnit: { id: "group-1", code: "group-1", name: "一组" },
        ...overrides
    };
}

function accountService(current, adminCount = 1) {
    const writes = [];
    const repository = {
        async getUserAccess() { return current; },
        async getRolesByIds(roleIds) { return roleIds.map((id) => ({ id, name: id })); },
        async getOrgUnitByCode(code) { return { id: code, code, name: code, active: true }; },
        async countActiveUsersWithRole() { return adminCount; },
        async withTransaction(work) { return work(this); },
        async updateUser(...args) { writes.push(["user", ...args]); },
        async setUserRoles(...args) { writes.push(["roles", ...args]); },
        async setCurrentOrgMembership(...args) { writes.push(["org", ...args]); },
        async setPasswordCredential(...args) { writes.push(["password", ...args]); },
        async revokeUserSessions(...args) { writes.push(["revoke", ...args]); },
        async revokeUserSessionsExcept(...args) { writes.push(["revoke-except", ...args]); },
        async createAudit(...args) { writes.push(["audit", ...args]); }
    };
    return { writes, service: new IamService({ repository, config: {} }) };
}

test("one account can only have one system role", () => {
    assert.deepEqual(normalizeRoleIds(["sales"]), ["sales"]);
    assert.throws(
        () => normalizeRoleIds(["admin", "sales"]),
        (error) => error.errorCode === "IAM_400_VALIDATION_FAILED"
            && error.message === "必须且只能选择一个系统角色"
    );
});

test("new employee accounts require a password", async () => {
    const { service } = accountService(accountAccess(), 2);
    await assert.rejects(
        service.validateAccountInput({
            displayName: "销售甲",
            phone: "13900139000",
            orgUnitCode: "group-1",
            roleIds: ["sales"]
        }),
        (error) => error.errorCode === "IAM_400_PASSWORD_REQUIRED"
    );
});

test("administrator cannot disable the current login account", async () => {
    const current = accountAccess();
    const { service, writes } = accountService(current, 2);
    await assert.rejects(
        service.updateUser(current.id, { status: "disabled" }, { user: { id: current.id } }),
        (error) => error.errorCode === "IAM_409_CANNOT_DISABLE_SELF"
    );
    assert.equal(writes.length, 0);
});

test("system always retains one enabled administrator", async () => {
    const current = accountAccess();
    const { service, writes } = accountService(current, 1);
    await assert.rejects(
        service.updateUser(current.id, { roleIds: ["sales"] }, { user: { id: "admin-2" } }),
        (error) => error.errorCode === "IAM_409_LAST_ADMIN"
    );
    assert.equal(writes.length, 0);
});

test("moving an employee delegates membership history preservation to the repository", async () => {
    const current = accountAccess({ id: "sales-1", roles: [{ id: "sales", name: "普通账号" }] });
    const { service, writes } = accountService(current, 2);
    await service.updateUser(
        current.id,
        { orgUnitCode: "group-2", roleIds: ["sales"] },
        { user: { id: "admin-1" } }
    );
    assert.ok(writes.some((entry) => (
        entry[0] === "org" && entry[1] === current.id && entry[2] === "group-2"
    )));
});
