const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const test = require("node:test");

const mysql = require("mysql2/promise");

const { GenerationRecordRepository } = require("../services/generation-records");

const enabled = String(process.env.RUN_MYSQL_INTEGRATION || "").toLowerCase() === "true";

test("MySQL persists immutable organization snapshots for generation records", { skip: !enabled }, async () => {
    const connection = await mysql.createConnection({
        host: process.env.DB_HOST || "127.0.0.1",
        port: Number(process.env.DB_PORT || 3306),
        user: process.env.DB_USER,
        password: process.env.DB_PASSWORD,
        database: process.env.DB_NAME
    });
    const userId = crypto.randomUUID();
    const jobId = `mysql-job-${crypto.randomUUID()}`;
    await connection.beginTransaction();
    try {
        await connection.query(
            "INSERT INTO iam_users (id, display_name, phone, status) VALUES (?, ?, ?, 'active')",
            [userId, "迁移集成测试", `139${String(Date.now()).slice(-8)}`]
        );
        const repository = new GenerationRecordRepository(connection);
        await repository.create({
            prepared: {
                generationMode: "human_wearing",
                composition: { view: "slight_side", framing: "full_body" },
                task: {
                    jobId,
                    tenantId: "integration-tenant",
                    traceId: crypto.randomUUID(),
                    modelProfileId: "ppe-integration-v1",
                    workflowVersion: "v1",
                    parameters: { size: "1024x1024", product_view: "front" }
                }
            },
            actor: {
                id: userId,
                displayName: "迁移集成测试",
                orgUnit: {
                    id: "jingshan-public-presale-2",
                    code: "jingshan-public-presale-2",
                    name: "售前2组",
                    unitType: "group",
                    parent: {
                        id: "jingshan-public",
                        code: "jingshan-public",
                        name: "京山公域销售"
                    }
                }
            },
            batchId: `batch-${crypto.randomUUID()}`,
            product: { id: "product-1", product_name: "安全帽", goods_no: "H-1" },
            model: { id: "model-1", name: "模特一" },
            scene: { id: "scene-1", name: "建筑工地" }
        });
        await repository.updateFromTask(jobId, { status: "succeeded", progress: 100, engine: "comfyui" });
        const rows = await repository.list({ userId, limit: 5 });
        assert.equal(rows.length, 1);
        assert.equal(rows[0].orgUnit.name, "售前2组");
        assert.equal(rows[0].department.name, "京山公域销售");
        assert.equal(rows[0].composition.view, "slight_side");
        assert.equal(rows[0].status, "succeeded");
        assert.equal(rows[0].engine, "comfyui");
    } finally {
        await connection.rollback();
        await connection.end();
    }
});
