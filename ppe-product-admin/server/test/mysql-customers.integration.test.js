const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const test = require("node:test");

const mysql = require("mysql2/promise");

const { CustomerRepository } = require("../services/customer-repository");
const { CustomerService } = require("../services/customer-service");

const enabled = String(process.env.RUN_MYSQL_INTEGRATION || "").toLowerCase() === "true";

test("MySQL keeps customer ownership, archive identity and soft deletion auditable", { skip: !enabled }, async () => {
    const connection = await mysql.createConnection({
        host: process.env.DB_HOST || "127.0.0.1",
        port: Number(process.env.DB_PORT || 3306),
        user: process.env.DB_USER,
        password: process.env.DB_PASSWORD,
        database: process.env.DB_NAME
    });
    const userId = crypto.randomUUID();
    const customerId = crypto.randomUUID();
    await connection.beginTransaction();
    try {
        await connection.query(
            "INSERT INTO iam_users (id, display_name, phone, status) VALUES (?, ?, ?, 'active')",
            [userId, "客户集成测试", `138${String(Date.now()).slice(-8)}`]
        );
        const service = new CustomerService({
            repository: new CustomerRepository(connection),
            tenantId: "integration-tenant",
            clock: () => new Date("2026-08-24T01:02:03.004Z"),
            randomUUID: () => customerId
        });
        const currentUser = {
            id: userId,
            displayName: "客户集成测试",
            roles: [{ id: "sales", name: "普通员工" }],
            orgUnit: {
                id: "jingshan-public-presale-2",
                code: "jingshan-public-presale-2",
                name: "售前2组",
                unitType: "group",
                parent: { id: "jingshan-public", code: "jingshan-public", name: "京山公域销售" }
            }
        };
        const created = await service.create({
            customerName: "集成客户",
            remarkId: "TB-INTEGRATION"
        }, currentUser);
        assert.equal(created.owner.id, userId);
        assert.equal(created.orgUnit.name, "售前2组");
        assert.equal(created.archiveNameStandard, true);

        const renamed = await service.update(customerId, { remarkId: "ORDER-INTEGRATION" }, currentUser);
        assert.equal(renamed.archiveName, "ORDER-INTEGRATION");
        assert.notEqual(renamed.archiveName, created.archiveName);

        await service.remove(customerId, currentUser);
        assert.equal(await new CustomerRepository(connection).findById(customerId, "integration-tenant"), null);
        const [audits] = await connection.query(
            "SELECT action FROM iam_audit_logs WHERE target_id=? ORDER BY created_at",
            [customerId]
        );
        assert.deepEqual(audits.map((item) => item.action), ["customer.create", "customer.update", "customer.delete"]);
    } finally {
        await connection.rollback();
        await connection.end();
    }
});
