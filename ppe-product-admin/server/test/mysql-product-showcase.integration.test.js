const assert = require("node:assert/strict");
const test = require("node:test");

const mysql = require("mysql2/promise");

const { ProductShowcaseRepository } = require("../services/product-showcase-repository");

const enabled = String(process.env.RUN_MYSQL_INTEGRATION || "").toLowerCase() === "true";

test("MySQL persists verified product fields required by long-image export", { skip: !enabled }, async () => {
    const connection = await mysql.createConnection({
        host: process.env.DB_HOST || "127.0.0.1",
        port: Number(process.env.DB_PORT || 3306),
        user: process.env.DB_USER,
        password: process.env.DB_PASSWORD,
        database: process.env.DB_NAME
    });
    await connection.beginTransaction();
    try {
        const [created] = await connection.query(
            "INSERT INTO product_catalog (product_name, goods_no, status) VALUES (?, ?, 1)",
            ["长图集成测试产品", `SHOWCASE-${Date.now()}`]
        );
        const repository = new ProductShowcaseRepository(connection);
        await repository.upsert(created.insertId, {
            material: "ABS",
            unitName: "个",
            specification: "测试规格",
            packagingSpecification: "20个/箱",
            executionStandard: "GB 2811-2019",
            sellingPoints: ["抗冲击", "耐穿刺"]
        });
        const stored = await repository.findByProductId(created.insertId);
        assert.equal(stored.material, "ABS");
        assert.equal(stored.execution_standard, "GB 2811-2019");
        const points = typeof stored.selling_points_json === "string"
            ? JSON.parse(stored.selling_points_json)
            : stored.selling_points_json;
        assert.deepEqual(points, ["抗冲击", "耐穿刺"]);
    } finally {
        await connection.rollback();
        await connection.end();
    }
});
