const fs = require("fs");
const path = require("path");

require("dotenv").config();

const pool = require("../db");

const PRODUCTS = [
    "升级加厚多口袋反光马甲（铁路黄色）",
    "PVC 点塑手套",
    "P10 安全帽（橙色）"
];

const VEST_BACK_URL = "/uploads/products/test-dataset-20260826/vest_multiPocket_yellow_back.png";
const DEMO_ASSETS = [
    "female-half-front.png",
    "female-half-slight-side.png",
    "female-full-front.png",
    "female-full-slight-side.png",
    "state-grid-logo.png"
];

function uploadPath(url) {
    const relative = String(url || "").replace(/^\/+uploads\//, "");
    const root = path.resolve(__dirname, "..", "uploads");
    const target = path.resolve(root, relative);
    if (target !== root && !target.startsWith(`${root}${path.sep}`)) {
        throw new Error(`演示素材路径越界：${target}`);
    }
    return target;
}

function verifyStaticAssets() {
    const root = path.resolve(__dirname, "..", "uploads", "client-demo");
    for (const fileName of DEMO_ASSETS) {
        const target = path.resolve(root, fileName);
        if (!target.startsWith(`${root}${path.sep}`) || !fs.existsSync(target)) {
            throw new Error(`固定演示素材缺失：${fileName}`);
        }
    }
}

async function main() {
    verifyStaticAssets();
    const connection = await pool.getConnection();
    const summary = { products: {}, vestBackInserted: false, demoAssets: DEMO_ASSETS.length };
    try {
        await connection.beginTransaction();
        for (const productName of PRODUCTS) {
            const [rows] = await connection.query(
                "SELECT id, product_name FROM product_catalog WHERE product_name=? LIMIT 1 FOR UPDATE",
                [productName]
            );
            if (!rows.length) throw new Error(`数据库缺少演示产品：${productName}`);
            summary.products[productName] = rows[0].id;
        }

        const vestId = summary.products[PRODUCTS[0]];
        const [backRows] = await connection.query(
            "SELECT id FROM product_files WHERE product_id=? AND file_type='view_back' LIMIT 1 FOR UPDATE",
            [vestId]
        );
        if (!backRows.length) {
            const absolutePath = uploadPath(VEST_BACK_URL);
            if (!fs.existsSync(absolutePath)) throw new Error(`马甲背面底图缺失：${absolutePath}`);
            const stats = fs.statSync(absolutePath);
            await connection.query(
                `INSERT INTO product_files
                    (product_id, file_type, file_name, file_url, file_size, remark, status)
                 VALUES (?, 'view_back', ?, ?, ?, ?, 1)`,
                [
                    vestId,
                    "升级加厚多口袋反光马甲（铁路黄色）-背面.png",
                    VEST_BACK_URL,
                    stats.size,
                    "甲方固定演示：铁路黄色同款马甲背面底图"
                ]
            );
            await connection.query("UPDATE product_catalog SET has_files=1 WHERE id=?", [vestId]);
            summary.vestBackInserted = true;
        }
        await connection.commit();
        console.log(JSON.stringify(summary, null, 2));
    } catch (error) {
        await connection.rollback();
        throw error;
    } finally {
        connection.release();
        await pool.end();
    }
}

main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
});
