const crypto = require("crypto");

function httpError(statusCode, message, errorCode = "IAM_ERROR") {
    const error = new Error(message);
    error.statusCode = statusCode;
    error.errorCode = errorCode;
    return error;
}

function normalizePhone(value) {
    const phone = String(value || "").replace(/[\s-]/g, "");
    if (!/^1[3-9]\d{9}$/.test(phone)) {
        throw httpError(400, "请输入有效的中国大陆手机号", "IAM_400_PHONE_INVALID");
    }
    return phone;
}

function maskPhone(value) {
    const phone = String(value || "");
    return phone.length === 11 ? `${phone.slice(0, 3)}****${phone.slice(-4)}` : "***";
}

function sha256(value) {
    return crypto.createHash("sha256").update(String(value)).digest("hex");
}

function hmacSha256(secret, value) {
    return crypto.createHmac("sha256", secret).update(String(value)).digest("hex");
}

function randomToken(bytes = 32) {
    return crypto.randomBytes(bytes).toString("base64url");
}

function safeHashEqual(left, right) {
    const a = Buffer.from(String(left || ""), "hex");
    const b = Buffer.from(String(right || ""), "hex");
    return a.length === b.length && a.length > 0 && crypto.timingSafeEqual(a, b);
}

function parseCookies(headerValue) {
    const cookies = {};
    String(headerValue || "")
        .split(";")
        .map((item) => item.trim())
        .filter(Boolean)
        .forEach((item) => {
            const index = item.indexOf("=");
            if (index <= 0) return;
            const name = item.slice(0, index).trim();
            const value = item.slice(index + 1);
            try {
                cookies[name] = decodeURIComponent(value);
            } catch {
                cookies[name] = value;
            }
        });
    return cookies;
}

function requestIpHash(secret, request) {
    const address = request.ip || request.socket?.remoteAddress || "unknown";
    return hmacSha256(secret, address);
}

function requireSecret(value, name) {
    const secret = String(value || "");
    if (secret.length < 32) {
        throw httpError(503, `${name} 未配置或长度不足 32 个字符`, "IAM_503_SECRET_MISSING");
    }
    return secret;
}

module.exports = {
    hmacSha256,
    httpError,
    maskPhone,
    normalizePhone,
    parseCookies,
    randomToken,
    requestIpHash,
    requireSecret,
    safeHashEqual,
    sha256
};
