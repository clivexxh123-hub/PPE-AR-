const fs = require("fs");
const path = require("path");

require("dotenv").config();

const pool = require("../db");

const DATASET_ID = "20260826";
const datasetRoot = path.resolve(
    process.env.TEST_IMAGE_DATASET_DIR || path.join(__dirname, "..", "..", "..", "图片数据")
);
const uploadRoot = path.resolve(
    __dirname,
    "..",
    "uploads",
    "products",
    `test-dataset-${DATASET_ID}`
);
const manifestPath = path.join(datasetRoot, "db_recommended_materials.json");

const products = [
    ...[
        ["orange", "橘色", ["vest_multiPocket_orange_front.png", "vest_multiPocket_orange_back.png"]],
        ["lightblue", "浅蓝色", ["vest_multiPocket_lightblue_front.png", "vest_multiPocket_lightblue_back.png"]],
        ["deepblue", "深蓝色", ["vest_multiPocket_deepblue_front.png", "vest_multiPocket_deepblue_back.png"]],
        ["red", "红色", ["vest_multiPocket_red_front.png", "vest_multiPocket_red_back.png"]],
        ["green", "绿色", ["vest_multiPocket_green_front.png", "vest_multiPocket_green_back.png"]],
        ["blue", "中蓝色", ["vest_multiPocket_blue_back.png"]],
        ["fluorescentyellow", "荧光黄色", ["vest_multiPocket_fluorescentyellow_back.png"]],
        ["yellow", "黄色", ["vest_multiPocket_yellow_back.png"]],
        ["railwayyellow", "铁路黄色", ["vest_multiPocket_railwayyellow_front.png"]]
    ].map(([key, color, files]) => ({
        key: `vest-${key}`,
        name: `升级加厚多口袋反光马甲（${color}）`,
        category1: "躯干防护",
        category2: "反光马甲",
        color,
        files: files.map((fileName) => ({
            fileName,
            fileType: fileName.endsWith("_front.png") ? "view_front" : "view_back"
        }))
    })),
    {
        key: "helmet-p10-orange",
        goodsNo: "P10",
        name: "P10 安全帽（橙色）",
        category1: "头部防护",
        category2: "安全帽",
        color: "橙色",
        files: [
            { fileName: "helmet_P10_orange_front.png", fileType: "view_front" },
            { fileName: "helmet_P10_orange_left.png", fileType: "view_left" },
            { fileName: "helmet_P10_orange_left_variant.png", fileType: "other" },
            { fileName: "helmet_P10_orange_back.png", fileType: "view_back" }
        ]
    },
    ...[
        ["white", "白色", ["7320", "7321", "7353"]],
        ["red", "红色", ["7326", "7327", "7369", "7370"]],
        ["blue", "蓝色", ["7336", "7337", "7359", "7360"]],
        ["yellow", "黄色", ["7331", "7332", "7341", "7342"]]
    ].map(([key, color, numbers]) => ({
        key: `helmet-p10-${key}-unverified`,
        goodsNo: "P10",
        name: `P10 安全帽（${color}，视角待确认）`,
        category1: "头部防护",
        category2: "安全帽",
        color,
        files: numbers.map((number, index) => ({
            fileName: `helmet_P10_${key}_unverified_${number}.png`,
            fileType: index === 0 ? "cover_image" : "product_image"
        }))
    })),
    ...[
        ["FDZ008", "FDZ008 磨砂手套", "gloves_FDZ008_pair_front.png"],
        ["FM001", "FM001 胶片手套", "gloves_FM001_pair_front.png"],
        ["G705", "G705 发泡手套", "gloves_G705_pair_front.png"],
        ["PVC", "PVC 点塑手套", "gloves_PVC_pair_front.png"],
        ["INSULATED", "绝缘手套", "gloves_insulated_pair_front.png"],
        ["ACID-ALKALI", "耐酸碱手套", "gloves_acidAlkali_pair_front.png"]
    ].map(([key, name, fileName]) => ({
        key: `gloves-${key.toLowerCase()}`,
        goodsNo: ["INSULATED", "ACID-ALKALI"].includes(key) ? null : key,
        name,
        category1: "手部防护",
        category2: "防护手套",
        color: null,
        files: [{ fileName, fileType: "cover_image" }]
    }))
];

function resolveInside(root, ...parts) {
    const target = path.resolve(root, ...parts);
    if (target !== root && !target.startsWith(`${root}${path.sep}`)) {
        throw new Error(`路径越界：${target}`);
    }
    return target;
}

function loadRecommendedFiles() {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    const result = new Map();

    for (const item of manifest) {
        if (item.status !== "RECOMMENDED_DB") continue;
        const fileName = path.win32.basename(String(item.new_path || ""));
        const sourcePath = resolveInside(datasetRoot, item.category, item.view, fileName);
        if (!fs.existsSync(sourcePath) || !fs.statSync(sourcePath).isFile()) {
            throw new Error(`推荐图片不存在：${sourcePath}`);
        }
        result.set(fileName, { ...item, sourcePath });
    }

    return result;
}

function validateDefinitions(recommendedFiles) {
    const definedNames = products.flatMap((product) => product.files.map((file) => file.fileName));
    const duplicates = definedNames.filter((name, index) => definedNames.indexOf(name) !== index);
    const missing = definedNames.filter((name) => !recommendedFiles.has(name));
    const unassigned = [...recommendedFiles.keys()].filter((name) => !definedNames.includes(name));

    if (duplicates.length || missing.length || unassigned.length) {
        throw new Error(JSON.stringify({ duplicates, missing, unassigned }, null, 2));
    }
}

function copyAssets(recommendedFiles) {
    fs.mkdirSync(uploadRoot, { recursive: true });
    for (const [fileName, metadata] of recommendedFiles) {
        const destination = resolveInside(uploadRoot, fileName);
        fs.copyFileSync(metadata.sourcePath, destination);
    }
}

async function upsertProduct(connection, product) {
    const goodsId = `TEST-IMAGE-${DATASET_ID}-${product.key.toUpperCase()}`;
    const colors = product.color ? JSON.stringify([product.color]) : null;
    const categoryPath = `${product.category1} > ${product.category2}`;
    const [rows] = await connection.query(
        "SELECT id FROM product_catalog WHERE goods_id=? LIMIT 1 FOR UPDATE",
        [goodsId]
    );

    if (rows.length) {
        await connection.query(
            `UPDATE product_catalog
             SET goods_no=?, product_name=?, category_level_1=?, category_level_2=?,
                 category_level_3=NULL, cate_full_name=?, brand_name=NULL, colors=?,
                 status=1, has_files=1, source_updated_at=NOW()
             WHERE id=?`,
            [product.goodsNo || null, product.name, product.category1, product.category2, categoryPath, colors, rows[0].id]
        );
        return { id: rows[0].id, inserted: false };
    }

    const [result] = await connection.query(
        `INSERT INTO product_catalog
            (goods_id, goods_no, product_name, category_level_1, category_level_2,
             cate_full_name, colors, status, has_files, source_updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, NOW())`,
        [goodsId, product.goodsNo || null, product.name, product.category1, product.category2, categoryPath, colors]
    );
    return { id: result.insertId, inserted: true };
}

async function upsertProductFile(connection, productId, file, metadata) {
    const storedPath = resolveInside(uploadRoot, file.fileName);
    const fileUrl = `/uploads/products/test-dataset-${DATASET_ID}/${file.fileName}`;
    const fileStats = fs.statSync(storedPath);
    const sourceName = String(metadata.filename || file.fileName);
    const viewNote = metadata.view === "pair"
        ? "拍摄视角尚未确认，仅作为产品参考图"
        : `素材视图：${metadata.view}`;
    const remark = `测试图片数据 ${DATASET_ID}；${viewNote}；${metadata.reason}`.slice(0, 500);
    const [rows] = await connection.query(
        "SELECT id FROM product_files WHERE product_id=? AND file_url=? LIMIT 1 FOR UPDATE",
        [productId, fileUrl]
    );
    const values = [
        file.fileType,
        sourceName,
        fileStats.size,
        Number(metadata.width) || null,
        Number(metadata.height) || null,
        remark
    ];

    if (rows.length) {
        await connection.query(
            `UPDATE product_files
             SET file_type=?, file_name=?, file_size=?, file_width=?, file_height=?, remark=?, status=1
             WHERE id=?`,
            [...values, rows[0].id]
        );
        return { id: rows[0].id, inserted: false };
    }

    const [result] = await connection.query(
        `INSERT INTO product_files
            (product_id, file_type, file_name, file_url, file_size,
             file_width, file_height, remark, status)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)`,
        [productId, file.fileType, sourceName, fileUrl, fileStats.size, values[3], values[4], remark]
    );
    return { id: result.insertId, inserted: true };
}

async function main() {
    const recommendedFiles = loadRecommendedFiles();
    validateDefinitions(recommendedFiles);
    copyAssets(recommendedFiles);

    const connection = await pool.getConnection();
    const summary = {
        datasetRoot,
        uploadRoot,
        recommendedImages: recommendedFiles.size,
        productsInserted: 0,
        productsUpdated: 0,
        filesInserted: 0,
        filesUpdated: 0,
        productIds: []
    };

    try {
        await connection.beginTransaction();
        for (const product of products) {
            const savedProduct = await upsertProduct(connection, product);
            summary[savedProduct.inserted ? "productsInserted" : "productsUpdated"] += 1;
            summary.productIds.push(savedProduct.id);

            for (const file of product.files) {
                const savedFile = await upsertProductFile(
                    connection,
                    savedProduct.id,
                    file,
                    recommendedFiles.get(file.fileName)
                );
                summary[savedFile.inserted ? "filesInserted" : "filesUpdated"] += 1;
            }
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
    console.error(error);
    process.exitCode = 1;
});
