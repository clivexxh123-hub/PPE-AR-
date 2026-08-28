const crypto = require("crypto");
const { promisify } = require("util");

const { httpError } = require("./security");

const scrypt = promisify(crypto.scrypt);
const SCRYPT_N = 16_384;
const SCRYPT_R = 8;
const SCRYPT_P = 1;
const KEY_LENGTH = 32;
const MAX_MEMORY = 64 * 1024 * 1024;

function validatePassword(value) {
    const password = String(value ?? "");
    if (password.length < 8 || password.length > 72) {
        throw httpError(400, "密码长度必须为8至72位", "IAM_400_PASSWORD_WEAK");
    }
    if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
        throw httpError(400, "密码必须同时包含字母和数字", "IAM_400_PASSWORD_WEAK");
    }
    return password;
}

async function derive(password, salt, parameters = {}) {
    return scrypt(String(password), salt, KEY_LENGTH, {
        N: parameters.N || SCRYPT_N,
        r: parameters.r || SCRYPT_R,
        p: parameters.p || SCRYPT_P,
        maxmem: MAX_MEMORY
    });
}

async function hashPassword(value) {
    const password = validatePassword(value);
    const salt = crypto.randomBytes(16);
    const derived = await derive(password, salt);
    return [
        "scrypt",
        SCRYPT_N,
        SCRYPT_R,
        SCRYPT_P,
        salt.toString("base64url"),
        derived.toString("base64url")
    ].join("$");
}

async function verifyPassword(value, encoded) {
    const parts = String(encoded || "").split("$");
    if (parts.length !== 6 || parts[0] !== "scrypt") return false;
    const [, n, r, p, saltText, hashText] = parts;
    const parameters = { N: Number(n), r: Number(r), p: Number(p) };
    if (![parameters.N, parameters.r, parameters.p].every(Number.isSafeInteger)) return false;

    try {
        const expected = Buffer.from(hashText, "base64url");
        const actual = await derive(String(value ?? ""), Buffer.from(saltText, "base64url"), parameters);
        return expected.length === actual.length && crypto.timingSafeEqual(expected, actual);
    } catch {
        return false;
    }
}

const dummySalt = Buffer.from("ppe-password-dummy", "utf8");
const dummyHash = crypto.scryptSync("invalid-password", dummySalt, KEY_LENGTH, {
    N: SCRYPT_N,
    r: SCRYPT_R,
    p: SCRYPT_P,
    maxmem: MAX_MEMORY
});
const DUMMY_PASSWORD_HASH = [
    "scrypt",
    SCRYPT_N,
    SCRYPT_R,
    SCRYPT_P,
    dummySalt.toString("base64url"),
    dummyHash.toString("base64url")
].join("$");

module.exports = {
    DUMMY_PASSWORD_HASH,
    hashPassword,
    validatePassword,
    verifyPassword
};
