const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

process.env.DOTENV_CONFIG_QUIET = "true";
require("dotenv").config({ quiet: true });

const pool = require("../db");

const LOGO_DIRECTORY = path.resolve(__dirname, "..", "uploads", "logos");
const BACKUP_FILE = path.resolve(
    __dirname,
    "..",
    "backups",
    "ai_logo_assets-before-legacy-sync-20260827.json"
);
const SUPPORTED_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".webp", ".svg"]);

function repairLegacyText(value) {
    const text = String(value || "");
    if (!text || /[\u3400-\u9fff]/u.test(text)) return text;
    const repaired = Buffer.from(text, "latin1").toString("utf8");
    return repaired.includes("�") ? text : repaired;
}

function parseLegacyLogoFilename(fileName) {
    const extension = path.extname(fileName).toLowerCase();
    if (!SUPPORTED_EXTENSIONS.has(extension)) return null;
    const rawStem = path.basename(fileName, extension).replace(/^\d+-/, "");
    const stem = repairLegacyText(rawStem);
    const segments = stem.split("-").map(item => item.trim()).filter(Boolean);
    if (segments.length < 2) return null;
    const region = segments.pop();
    const companyName = segments.join("-");
    const timestamp = path.basename(fileName, extension).match(/^\d+/)?.[0] || "legacy";
    const normalizedFileName = `${timestamp}-${companyName}-${region}${extension}`;
    return {
        sourceFileName: fileName,
        normalizedFileName,
        companyName,
        region,
        logoKey: `${region}-${companyName}`,
        logoName: `${companyName}-${region}${extension}`,
        logoUrl: `/uploads/logos/${normalizedFileName}`
    };
}

function sha256(filePath) {
    return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function collectLegacyLogos(directory = LOGO_DIRECTORY) {
    if (!fs.existsSync(directory)) throw new Error(`旧 Logo 目录不存在：${directory}`);
    const byKey = new Map();
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
        if (!entry.isFile()) continue;
        const parsed = parseLegacyLogoFilename(entry.name);
        if (!parsed) continue;
        const sourcePath = path.resolve(directory, entry.name);
        if (!sourcePath.startsWith(`${directory}${path.sep}`)) {
            throw new Error(`Logo 文件路径越界：${entry.name}`);
        }
        const candidate = {
            ...parsed,
            sourcePath,
            targetPath: path.resolve(directory, parsed.normalizedFileName),
            hash: sha256(sourcePath)
        };
        const existing = byKey.get(candidate.logoKey);
        const sourceIsNormalized = candidate.sourceFileName === candidate.normalizedFileName;
        const existingIsNormalized = existing?.sourceFileName === existing?.normalizedFileName;
        if (!existing || (sourceIsNormalized && !existingIsNormalized)) {
            byKey.set(candidate.logoKey, candidate);
        }
    }
    return [...byKey.values()].sort((a, b) => a.logoKey.localeCompare(b.logoKey, "zh-CN"));
}

function ensureNormalizedFile(candidate) {
    if (candidate.sourcePath === candidate.targetPath) return false;
    if (fs.existsSync(candidate.targetPath)) {
        if (sha256(candidate.targetPath) !== candidate.hash) {
            throw new Error(`规范化文件已存在但内容不同：${candidate.normalizedFileName}`);
        }
        return false;
    }
    fs.copyFileSync(candidate.sourcePath, candidate.targetPath, fs.constants.COPYFILE_EXCL);
    if (sha256(candidate.targetPath) !== candidate.hash) {
        throw new Error(`Logo 文件复制校验失败：${candidate.normalizedFileName}`);
    }
    return true;
}

async function backupTargetRows(connection) {
    if (fs.existsSync(BACKUP_FILE)) return false;
    const [rows] = await connection.query("SELECT * FROM ai_logo_assets ORDER BY id");
    fs.mkdirSync(path.dirname(BACKUP_FILE), { recursive: true });
    fs.writeFileSync(
        BACKUP_FILE,
        `${JSON.stringify({ createdAt: new Date().toISOString(), rows }, null, 2)}\n`,
        { encoding: "utf8", flag: "wx" }
    );
    return true;
}

async function syncLegacyLogos({ apply = false } = {}) {
    const candidates = collectLegacyLogos();
    const connection = await pool.getConnection();
    const summary = {
        mode: apply ? "apply" : "dry-run",
        sourceCount: candidates.length,
        inserted: 0,
        skipped: 0,
        copiedFiles: 0,
        backupFile: apply ? BACKUP_FILE : null,
        logos: []
    };
    try {
        await connection.beginTransaction();
        if (apply) await backupTargetRows(connection);
        for (const candidate of candidates) {
            const [existing] = await connection.query(
                "SELECT id, logo_key, logo_url FROM ai_logo_assets WHERE logo_key=? OR logo_url=? LIMIT 1",
                [candidate.logoKey, candidate.logoUrl]
            );
            if (existing.length) {
                summary.skipped += 1;
                summary.logos.push({ companyName: candidate.companyName, region: candidate.region, status: "skipped" });
                continue;
            }
            if (!apply) {
                summary.inserted += 1;
                summary.logos.push({ companyName: candidate.companyName, region: candidate.region, status: "pending" });
                continue;
            }
            if (ensureNormalizedFile(candidate)) summary.copiedFiles += 1;
            await connection.query(
                `INSERT INTO ai_logo_assets
                    (logo_key, region, company_name, logo_name, logo_url, remark)
                 VALUES (?, ?, ?, ?, ?, ?)`,
                [
                    candidate.logoKey,
                    candidate.region,
                    candidate.companyName,
                    candidate.logoName,
                    candidate.logoUrl,
                    `旧版 Logo 素材同步；SHA256=${candidate.hash}`
                ]
            );
            summary.inserted += 1;
            summary.logos.push({ companyName: candidate.companyName, region: candidate.region, status: "inserted" });
        }
        if (apply) await connection.commit();
        else await connection.rollback();
        return summary;
    } catch (error) {
        await connection.rollback();
        throw error;
    } finally {
        connection.release();
    }
}

async function main() {
    try {
        const summary = await syncLegacyLogos({ apply: process.argv.includes("--apply") });
        console.log(JSON.stringify(summary, null, 2));
    } finally {
        await pool.end();
    }
}

if (require.main === module) {
    main().catch((error) => {
        console.error(error.message);
        process.exitCode = 1;
    });
}

module.exports = {
    collectLegacyLogos,
    parseLegacyLogoFilename,
    repairLegacyText,
    syncLegacyLogos
};
