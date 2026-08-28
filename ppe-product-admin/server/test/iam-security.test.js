const assert = require("node:assert/strict");
const test = require("node:test");

const { loadIamConfig } = require("../services/iam/config");
const { hasPermission } = require("../services/iam/access");
const { hashPassword, validatePassword, verifyPassword } = require("../services/iam/password");
const { maskPhone, normalizePhone, parseCookies } = require("../services/iam/security");

test("phone normalization and masking do not expose invalid input", () => {
    assert.equal(normalizePhone("138 0013-8000"), "13800138000");
    assert.equal(maskPhone("13800138000"), "138****8000");
    assert.throws(() => normalizePhone("123"), /有效的中国大陆手机号/);
});

test("password hashes are salted and never store plaintext", async () => {
    const first = await hashPassword("SecurePass123");
    const second = await hashPassword("SecurePass123");
    assert.notEqual(first, second);
    assert.equal(first.includes("SecurePass123"), false);
    assert.equal(await verifyPassword("SecurePass123", first), true);
    assert.equal(await verifyPassword("WrongPass123", first), false);
});

test("password policy requires length, letters and numbers", () => {
    assert.equal(validatePassword("SecurePass123"), "SecurePass123");
    assert.throws(() => validatePassword("short1"), /8至72位/);
    assert.throws(() => validatePassword("onlyletters"), /字母和数字/);
    assert.throws(() => validatePassword("12345678"), /字母和数字/);
});

test("admin role has full permission including future permission identifiers", () => {
    assert.equal(hasPermission({ roles: [{ id: "admin" }], permissions: [] }, "future.manage"), true);
    assert.equal(hasPermission({ roles: [{ id: "sales" }], permissions: [] }, "future.manage"), false);
});

test("cookie parser keeps encoded values and ignores malformed entries", () => {
    assert.deepEqual(parseCookies("ppe_session=a%2Fb; ppe_csrf=test; malformed"), {
        ppe_session: "a/b",
        ppe_csrf: "test"
    });
});

test("unsafe production authentication configuration is rejected", () => {
    assert.throws(
        () => loadIamConfig({ NODE_ENV: "production", AUTH_ENABLED: "false" }),
        /不能关闭/
    );
    const config = loadIamConfig({
        NODE_ENV: "production",
        AUTH_ENABLED: "true",
        IAM_PASSWORD_MAX_ATTEMPTS: "6",
        IAM_PASSWORD_LOCK_MINUTES: "20"
    });
    assert.equal(config.passwordMaxAttempts, 6);
    assert.equal(config.passwordLockMinutes, 20);
});
