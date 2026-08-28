const DATABASE_UNAVAILABLE_CODES = new Set([
    "ECONNREFUSED",
    "ECONNRESET",
    "ENOTFOUND",
    "ER_ACCESS_DENIED_ERROR",
    "PROTOCOL_CONNECTION_LOST",
    "ETIMEDOUT"
]);

function publicErrorPayload(error) {
    if (
        DATABASE_UNAVAILABLE_CODES.has(String(error?.code || "")) ||
        Number(error?.errno) === 1045 ||
        String(error?.sqlState || "") === "28000"
    ) {
        return {
            statusCode: 503,
            errorCode: "DB_503_UNAVAILABLE",
            message: "账号服务暂不可用，请联系管理员检查数据库连接"
        };
    }

    const payload = {
        statusCode: Number(error?.statusCode) || 500,
        errorCode: error?.errorCode || "INTERNAL_ERROR",
        message: error?.message || "服务器内部错误"
    };
    if (Number.isSafeInteger(error?.retryAfterSeconds) && error.retryAfterSeconds > 0) {
        payload.retryAfterSeconds = error.retryAfterSeconds;
    }
    if (typeof error?.retryAt === "string" && error.retryAt) {
        payload.retryAt = error.retryAt;
    }
    return payload;
}

module.exports = { publicErrorPayload };
