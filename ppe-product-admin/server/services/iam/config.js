const { httpError } = require("./security");

function positiveInteger(value, fallback) {
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function booleanFlag(value, fallback = false) {
    if (value === undefined || value === null || value === "") return fallback;
    return ["1", "true", "yes", "on"].includes(String(value).trim().toLowerCase());
}

function loadIamConfig(environment = process.env) {
    const nodeEnv = String(environment.NODE_ENV || "development").trim().toLowerCase();
    const authEnabled = booleanFlag(environment.AUTH_ENABLED, true);

    if (nodeEnv === "production" && !authEnabled) {
        throw httpError(500, "生产环境不能关闭 AUTH_ENABLED", "IAM_500_UNSAFE_CONFIG");
    }

    return {
        nodeEnv,
        authEnabled,
        sessionSecret: environment.IAM_SESSION_SECRET,
        sessionHours: positiveInteger(environment.IAM_SESSION_HOURS, 12),
        passwordMaxAttempts: positiveInteger(environment.IAM_PASSWORD_MAX_ATTEMPTS, 5),
        passwordLockMinutes: positiveInteger(environment.IAM_PASSWORD_LOCK_MINUTES, 15),
        allowedOrigins: String(environment.ALLOWED_WEB_ORIGINS || "http://127.0.0.1:9531,http://localhost:9531")
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
        secureCookies: nodeEnv === "production" || booleanFlag(environment.AUTH_SECURE_COOKIES, false)
    };
}

module.exports = { loadIamConfig };
