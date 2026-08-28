const fs = require("fs");
const path = require("path");

require("dotenv").config();

const pool = require("../db");

const PRODUCT_GOODS_ID = "LOCAL-ASSET-YELLOW-HELMET-20260824";
const uploadsRoot = path.resolve(__dirname, "..", "uploads");

const productFiles = [
    {
        fileType: "view_front",
        fileName: "yellow-helmet-front-transparent-generated-v1.png",
        relativePath: "products/yellow-helmet-front-transparent-generated-v1.png",
        width: 1536,
        height: 1024,
        remark: "基于本地黄色安全帽实拍图生成并校验的透明底产品参考图；型号与 SKU 待业务确认"
    },
    {
        fileType: "source_image",
        fileName: "1786089997729-64807510.jpg",
        relativePath: "products/1786089997729-64807510.jpg",
        width: 4096,
        height: 4096,
        remark: "本地现有黄色安全帽正面实拍源图；白底 JPG，不直接作为 AI 透明参考图"
    },
    {
        fileType: "view_back",
        fileName: "1786090091175-733474943.jpg",
        relativePath: "products/1786090091175-733474943.jpg",
        width: 4096,
        height: 4096,
        remark: "本地现有黄色安全帽背面实拍图；型号与 SKU 待业务确认"
    },
    {
        fileType: "reference_side",
        fileName: "1786090084546-423581173.jpg",
        relativePath: "products/1786090084546-423581173.jpg",
        width: 4096,
        height: 4096,
        remark: "本地现有黄色安全帽侧面实拍图；左右方向待业务确认，暂不冒充左视图或右视图"
    }
];

const modelAssets = [
    {
        modelKey: "full_body-male-front-camera-generated-v1",
        modelName: "男性正面全身基础模特",
        gender: "male",
        shotType: "full_body",
        viewType: "front",
        imageName: "male-fullbody-front-generated-v1.png",
        relativePath: "models/male-fullbody-front-generated-v1.png",
        remark: "正面站直，纯色衬衫、长裤、裸手、赤脚；无头盔、背心、手套及鞋类"
    },
    {
        modelKey: "half_body-male-construction-01",
        modelName: "男性正面半身基础模特",
        gender: "male",
        shotType: "half_body",
        viewType: "front",
        imageName: "male-halfbody-construction-01.png",
        relativePath: "models/male-halfbody-construction-01.png",
        remark: "正面站直，纯色衬衫、长裤、裸手；无头盔、背心、手套及鞋类"
    },
    {
        modelKey: "full_body-male-slight-side-generated-v1",
        modelName: "男性微侧身全身基础模特",
        gender: "male",
        shotType: "full_body",
        viewType: "slight_side",
        imageName: "male-fullbody-slight-side-generated-v1.png",
        relativePath: "models/male-fullbody-slight-side-generated-v1.png",
        remark: "约 25° 微侧身站直，纯色衬衫、长裤、裸手、赤脚；无头盔、背心、手套及鞋类"
    },
    {
        modelKey: "half_body-male-construction-02",
        modelName: "男性微侧身半身基础模特",
        gender: "male",
        shotType: "half_body",
        viewType: "slight_side",
        imageName: "male-halfbody-construction-02.png",
        relativePath: "models/male-halfbody-construction-02.png",
        remark: "约 25° 微侧身站直，纯色衬衫、长裤、裸手；无头盔、背心、手套及鞋类"
    },
    {
        modelKey: "full_body-female-front-camera-generated-v1",
        modelName: "女性正面全身基础模特",
        gender: "female",
        shotType: "full_body",
        viewType: "front",
        imageName: "female-fullbody-front-generated-v1.png",
        relativePath: "models/female-fullbody-front-generated-v1.png",
        remark: "正面站直，纯色衬衫、长裤、裸手、赤脚；无头盔、背心、手套及鞋类"
    },
    {
        modelKey: "half_body-female-construction-01",
        modelName: "女性正面半身基础模特",
        gender: "female",
        shotType: "half_body",
        viewType: "front",
        imageName: "female-halfbody-construction-01.png",
        relativePath: "models/female-halfbody-construction-01.png",
        remark: "正面站直，纯色衬衫、长裤、裸手；无头盔、背心、手套及鞋类"
    },
    {
        modelKey: "full_body-female-slight-side-generated-v1",
        modelName: "女性微侧身全身基础模特",
        gender: "female",
        shotType: "full_body",
        viewType: "slight_side",
        imageName: "female-fullbody-slight-side-generated-v1.png",
        relativePath: "models/female-fullbody-slight-side-generated-v1.png",
        remark: "约 25° 微侧身站直，纯色衬衫、长裤、裸手、赤脚；无头盔、背心、手套及鞋类"
    },
    {
        modelKey: "half_body-female-construction-02",
        modelName: "女性微侧身半身基础模特",
        gender: "female",
        shotType: "half_body",
        viewType: "slight_side",
        imageName: "female-halfbody-construction-02.png",
        relativePath: "models/female-halfbody-construction-02.png",
        remark: "约 25° 微侧身站直，纯色衬衫、长裤、裸手；无头盔、背心、手套及鞋类"
    }
];

function localFile(relativePath) {
    const filename = path.resolve(uploadsRoot, relativePath);
    if (!filename.startsWith(`${uploadsRoot}${path.sep}`) || !fs.statSync(filename).isFile()) {
        throw new Error(`素材文件不存在或路径越界：${relativePath}`);
    }
    return filename;
}

async function upsertModel(connection, model) {
    const imagePath = localFile(model.relativePath);
    const imageUrl = `/uploads/${model.relativePath.replaceAll(path.sep, "/")}`;
    const [rows] = await connection.query(
        "SELECT id FROM ai_model_assets WHERE model_key=? ORDER BY id LIMIT 1",
        [model.modelKey]
    );
    const values = [
        model.modelName,
        model.gender,
        model.shotType,
        model.viewType,
        model.imageName,
        imageUrl,
        model.remark
    ];
    if (rows.length) {
        await connection.query(
            `UPDATE ai_model_assets
             SET model_name=?, gender=?, shot_type=?, view_type=?, image_name=?, image_url=?, remark=?
             WHERE id=?`,
            [...values, rows[0].id]
        );
        return rows[0].id;
    }
    const [result] = await connection.query(
        `INSERT INTO ai_model_assets
            (model_key, model_name, gender, shot_type, view_type, image_name, image_url, remark)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        [model.modelKey, ...values]
    );
    return result.insertId;
}

async function main() {
    const connection = await pool.getConnection();
    try {
        await connection.beginTransaction();
        const [products] = await connection.query(
            "SELECT id FROM product_catalog WHERE goods_id=? LIMIT 1 FOR UPDATE",
            [PRODUCT_GOODS_ID]
        );
        let productId = products[0]?.id;
        if (productId) {
            await connection.query(
                `UPDATE product_catalog
                 SET product_name=?, category_level_1=?, category_level_2=?, cate_full_name=?,
                     colors=?, status=1, has_files=1, source_updated_at=NOW()
                 WHERE id=?`,
                ["黄色安全帽（型号待确认）", "头部防护", "安全帽", "头部防护 > 安全帽", JSON.stringify(["黄色"]), productId]
            );
        } else {
            const [result] = await connection.query(
                `INSERT INTO product_catalog
                    (goods_id, goods_no, product_name, category_level_1, category_level_2,
                     cate_full_name, colors, status, has_files, source_updated_at)
                 VALUES (?, NULL, ?, ?, ?, ?, ?, 1, 1, NOW())`,
                [PRODUCT_GOODS_ID, "黄色安全帽（型号待确认）", "头部防护", "安全帽", "头部防护 > 安全帽", JSON.stringify(["黄色"])]
            );
            productId = result.insertId;
        }

        const productFileIds = [];
        for (const file of productFiles) {
            const filename = localFile(file.relativePath);
            const fileUrl = `/uploads/${file.relativePath.replaceAll(path.sep, "/")}`;
            const [rows] = await connection.query(
                "SELECT id FROM product_files WHERE product_id=? AND file_url=? ORDER BY id LIMIT 1",
                [productId, fileUrl]
            );
            const values = [
                file.fileType,
                file.fileName,
                fs.statSync(filename).size,
                file.width,
                file.height,
                file.remark
            ];
            if (rows.length) {
                await connection.query(
                    `UPDATE product_files
                     SET file_type=?, file_name=?, file_size=?, file_width=?, file_height=?, remark=?, status=1
                     WHERE id=?`,
                    [...values, rows[0].id]
                );
                productFileIds.push(rows[0].id);
            } else {
                const [result] = await connection.query(
                    `INSERT INTO product_files
                        (product_id, file_type, file_name, file_url, file_size, file_width, file_height, remark, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)`,
                    [productId, file.fileType, file.fileName, fileUrl, values[2], file.width, file.height, file.remark]
                );
                productFileIds.push(result.insertId);
            }
        }

        const modelIds = [];
        for (const model of modelAssets) modelIds.push(await upsertModel(connection, model));
        await connection.commit();
        console.log(JSON.stringify({ productId, productFileIds, modelIds }));
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
