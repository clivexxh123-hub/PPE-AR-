const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const test = require("node:test");

const mysql = require("mysql2/promise");

const { GenerationArchiveRepository } = require("../services/generation-archive-repository");

const enabled = String(process.env.RUN_MYSQL_INTEGRATION || "").toLowerCase() === "true";

test("MySQL links a durable generation image to one customer with event snapshots", { skip: !enabled }, async () => {
    const connection = await mysql.createConnection({
        host: process.env.DB_HOST || "127.0.0.1",
        port: Number(process.env.DB_PORT || 3306),
        user: process.env.DB_USER,
        password: process.env.DB_PASSWORD,
        database: process.env.DB_NAME
    });
    const userId = crypto.randomUUID();
    const customerId = crypto.randomUUID();
    const jobId = `archive-${crypto.randomUUID()}`;
    await connection.beginTransaction();
    try {
        await connection.query(
            "INSERT INTO iam_users (id, display_name, phone, status) VALUES (?, ?, ?, 'active')",
            [userId, "归档集成测试", `137${String(Date.now()).slice(-8)}`]
        );
        await connection.query(
            `INSERT INTO business_customers (
                id, tenant_id, customer_name, archive_name, archive_name_standard,
                owner_user_id, owner_user_name_at_create
             ) VALUES (?, 'integration-tenant', '归档客户', ?, 1, ?, '归档集成测试')`,
            [customerId, `TB+归档客户+${Date.now()}`, userId]
        );
        await connection.query(
            `INSERT INTO business_generation_records (
                job_id, tenant_id, trace_id, user_id, user_name_at_event,
                product_name, status, progress, parameters_json
             ) VALUES (?, 'integration-tenant', ?, ?, '归档集成测试', '安全帽', 'succeeded', 100, '{}')`,
            [jobId, crypto.randomUUID(), userId]
        );
        const repository = new GenerationArchiveRepository(connection);
        const created = await repository.create({
            jobId,
            customerId,
            tenantId: "integration-tenant",
            batchId: "batch-integration",
            fileUrl: `/uploads/customer-archives/${customerId}/${jobId}.png`,
            contentType: "image/png",
            fileSize: 2048,
            actor: { id: userId, displayName: "归档集成测试" },
            orgUnit: { id: "jingshan-public-presale-1", name: "售前1组" },
            department: { id: "jingshan-public", name: "京山公域销售" }
        });
        assert.equal(created.customerId, customerId);
        assert.equal(created.product.name, "安全帽");
        assert.equal(created.orgUnit.name, "售前1组");
        const listed = await repository.list(customerId, "integration-tenant");
        assert.equal(listed.length, 1);
        assert.equal(listed[0].fileSize, 2048);
    } finally {
        await connection.rollback();
        await connection.end();
    }
});
