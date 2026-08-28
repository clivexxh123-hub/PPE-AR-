const assert = require("node:assert/strict");
const test = require("node:test");

const { publicErrorPayload } = require("../services/public-error");

test("database connection failures never expose credentials or network topology", () => {
    const payload = publicErrorPayload({
        code: "ER_ACCESS_DENIED_ERROR",
        errno: 1045,
        sqlState: "28000",
        message: "Access denied for user 'private-user'@'172.20.0.1'"
    });

    assert.deepEqual(payload, {
        statusCode: 503,
        errorCode: "DB_503_UNAVAILABLE",
        message: "账号服务暂不可用，请联系管理员检查数据库连接"
    });
    assert.equal(JSON.stringify(payload).includes("private-user"), false);
    assert.equal(JSON.stringify(payload).includes("172.20.0.1"), false);
});

test("domain errors keep their explicit public status and code", () => {
    assert.deepEqual(
        publicErrorPayload({ statusCode: 401, errorCode: "IAM_401_AUTH_REQUIRED", message: "请先登录" }),
        { statusCode: 401, errorCode: "IAM_401_AUTH_REQUIRED", message: "请先登录" }
    );
});

test("rate-limit errors expose only safe retry metadata", () => {
    const error = {
        statusCode: 429,
        errorCode: "IAM_429_RATE_LIMITED",
        message: "请求过于频繁，请在42秒后重试",
        retryAfterSeconds: 42
    };

    assert.deepEqual(publicErrorPayload(error), error);
});
