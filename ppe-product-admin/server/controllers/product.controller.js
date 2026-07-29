const fs = require("fs");
const path = require("path");
const pool = require("../db");


// ======================================================
// 工具函数
// ======================================================

function parseColors(value) {
    if (Array.isArray(value)) {
        return value
            .map(item => String(item).trim())
            .filter(Boolean);
    }

    if (!value) {
        return [];
    }

    try {
        const parsed = JSON.parse(value);

        if (Array.isArray(parsed)) {
            return parsed
                .map(item => String(item).trim())
                .filter(Boolean);
        }
    } catch (error) {
        // 兼容中文逗号、英文逗号分隔
    }

    return String(value)
        .split(/[,，]/)
        .map(item => item.trim())
        .filter(Boolean);
}


function toPositiveInteger(value, defaultValue, maxValue = 200) {
    const number = Number(value);

    if (!Number.isInteger(number) || number < 1) {
        return defaultValue;
    }

    return Math.min(number, maxValue);
}


function decodeQueryValue(value) {
    if (!value) {
        return value;
    }

    try {
        // 兼容终端直接传中文时出现的 UTF-8 乱码
        return decodeURIComponent(escape(value));
    } catch (error) {
        return value;
    }
}


function normalizeProduct(row) {
    if (!row) {
        return row;
    }

    row.colors = parseColors(row.colors);
    row.status = Number(row.status || 0);
    row.has_files = Number(row.has_files || 0);
    row.color_count = Number(row.color_count || 0);
    row.source_count = Number(row.source_count || 0);
    row.file_count = Number(row.file_count || 0);

    return row;
}


// ======================================================
// 分类接口
// GET /api/categories
// ======================================================

exports.getCategories = async (req, res) => {
    try {
        const [rows] = await pool.query(`
            SELECT
                category_level_1,
                category_level_2,
                category_level_3,
                COUNT(*) AS total
            FROM product_catalog
            WHERE status = 1
            GROUP BY
                category_level_1,
                category_level_2,
                category_level_3
            ORDER BY
                category_level_2 ASC,
                total DESC,
                category_level_3 ASC
        `);

        const level2Map = new Map();
        let total = 0;

        for (const row of rows) {
            const level1 = row.category_level_1 || "未分类";
            const level2 = row.category_level_2 || "未分类";
            const level3 = row.category_level_3 || level2;
            const count = Number(row.total || 0);

            total += count;

            if (!level2Map.has(level2)) {
                level2Map.set(level2, {
                    name: level2,
                    level1,
                    count: 0,
                    children: []
                });
            }

            const parent = level2Map.get(level2);

            parent.count += count;

            parent.children.push({
                name: level3,
                count
            });
        }

        res.json({
            success: true,
            total,
            data: [...level2Map.values()]
        });
    } catch (error) {
        console.error("getCategories error:", error);

        res.status(500).json({
            success: false,
            message: "获取商品分类失败",
            error: error.message
        });
    }
};


// ======================================================
// 商品列表
// GET /api/products
exports.getProducts = async (req, res) => {
    try {
        const page = Math.max(
            parseInt(req.query.page, 10) || 1,
            1
        );

        const size = Math.min(
            Math.max(parseInt(req.query.size, 10) || 20, 1),
            100
        );

        const offset = (page - 1) * size;

        const keyword = String(
            req.query.keyword || ""
        ).trim();

        const categoryLevel1 = String(
            req.query.category_level_1 ||
            req.query.level1 ||
            req.query.category1 ||
            ""
        ).trim();

        const categoryLevel2 = String(
            req.query.category_level_2 ||
            req.query.level2 ||
            req.query.category2 ||
            ""
        ).trim();

        const categoryLevel3 = String(
            req.query.category_level_3 ||
            req.query.level3 ||
            req.query.category3 ||
            ""
        ).trim();

        const status =
            req.query.status === undefined ||
            req.query.status === ""
                ? null
                : Number(req.query.status);

        const hasFiles =
            req.query.has_files === undefined ||
            req.query.has_files === ""
                ? null
                : Number(req.query.has_files);

        console.log("[GET /api/products filters]", {
            keyword,
            categoryLevel1,
            categoryLevel2,
            categoryLevel3,
            status,
            hasFiles,
            page,
            size
        });

        const where = [];
        const params = [];

        if (keyword) {
            const likeValue = `%${keyword}%`;

            where.push(`(
                p.product_name LIKE ?
                OR p.goods_no LIKE ?
                OR p.goods_id LIKE ?
                OR p.brand_name LIKE ?
                OR p.cate_full_name LIKE ?
            )`);

            params.push(
                likeValue,
                likeValue,
                likeValue,
                likeValue,
                likeValue
            );
        }

        if (categoryLevel1) {
            where.push("p.category_level_1 = ?");
            params.push(categoryLevel1);
        }

        if (categoryLevel2) {
            where.push("p.category_level_2 = ?");
            params.push(categoryLevel2);
        }

        if (categoryLevel3) {
            where.push("p.category_level_3 = ?");
            params.push(categoryLevel3);
        }

        if (status === 0 || status === 1) {
            where.push("p.status = ?");
            params.push(status);
        }

        if (hasFiles === 1) {
            where.push(`
                EXISTS (
                    SELECT 1
                    FROM product_files pf_filter
                    WHERE pf_filter.product_id = p.id
                )
            `);
        }

        if (hasFiles === 0) {
            where.push(`
                NOT EXISTS (
                    SELECT 1
                    FROM product_files pf_filter
                    WHERE pf_filter.product_id = p.id
                )
            `);
        }

        const whereSql = where.length
            ? `WHERE ${where.join(" AND ")}`
            : "";

        const countSql = `
            SELECT COUNT(*) AS total
            FROM product_catalog p
            ${whereSql}
        `;

        const listSql = `
            SELECT
                p.*,

                (
                    SELECT COUNT(*)
                    FROM product_files pf_count
                    WHERE pf_count.product_id = p.id
                ) AS file_count,

                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM product_files pf_exists
                        WHERE pf_exists.product_id = p.id
                    )
                    THEN 1
                    ELSE 0
                END AS has_files

            FROM product_catalog p
            ${whereSql}

            ORDER BY
                p.updated_at DESC,
                p.id DESC

            LIMIT ?
            OFFSET ?
        `;

        const [countRows] = await pool.query(
            countSql,
            params
        );

        const [rows] = await pool.query(
            listSql,
            [...params, size, offset]
        );

        const list = rows.map((row) => {
            let colors = row.colors;

            if (typeof colors === "string") {
                try {
                    colors = JSON.parse(colors);
                } catch (error) {
                    colors = colors
                        .split(/[,，、/]/)
                        .map((item) => item.trim())
                        .filter(Boolean);
                }
            }

            if (!Array.isArray(colors)) {
                colors = [];
            }

            return {
                ...row,
                colors,
                color_count: Number(
                    row.color_count ?? colors.length
                ),
                source_count: Number(row.source_count || 0),
                file_count: Number(row.file_count || 0),
                has_files: Number(row.has_files || 0)
            };
        });

        return res.json({
            success: true,
            total: Number(countRows[0]?.total || 0),
            page,
            size,
            list
        });
    } catch (error) {
        console.error(
            "GET /api/products failed:",
            error
        );

        return res.status(500).json({
            success: false,
            message: "商品列表查询失败",
            error: error.message
        });
    }
};

// GET /api/products/:id
// ======================================================

exports.getProductDetail = async (req, res) => {
    try {
        const productId = Number(req.params.id);

        if (!Number.isInteger(productId) || productId < 1) {
            return res.status(400).json({
                success: false,
                message: "商品ID不正确"
            });
        }

        const [productRows] = await pool.query(
            `
                SELECT
                    p.*,
                    (
                        SELECT COUNT(*)
                        FROM product_files f
                        WHERE f.product_id = p.id
                    ) AS file_count
                FROM product_catalog p
                WHERE p.id = ?
                LIMIT 1
            `,
            [productId]
        );

        if (!productRows.length) {
            return res.status(404).json({
                success: false,
                message: "商品不存在"
            });
        }

        const [fileRows] = await pool.query(
            `
                SELECT
                    id,
                    product_id,
                    file_type,
                    file_name,
                    file_url,
                    file_size,
                    file_width,
                    file_height,
                    remark,
                    status,
                    created_at,
                    updated_at
                FROM product_files
                WHERE product_id = ?
                ORDER BY
                    created_at DESC,
                    id DESC
            `,
            [productId]
        );

        res.json({
            success: true,
            data: {
                ...normalizeProduct(productRows[0]),
                files: fileRows
            }
        });
    } catch (error) {
        console.error("getProductDetail error:", error);

        res.status(500).json({
            success: false,
            message: "获取商品详情失败",
            error: error.message
        });
    }
};


// ======================================================
// 编辑商品
// PUT /api/products/:id
// ======================================================

exports.updateProduct = async (req, res) => {
    const connection = await pool.getConnection();

    try {
        const productId = Number(req.params.id);

        if (!Number.isInteger(productId) || productId < 1) {
            return res.status(400).json({
                success: false,
                message: "商品ID不正确"
            });
        }

        const {
            product_name,
            category_level_1,
            category_level_2,
            category_level_3,
            brand_name,
            colors,
            status
        } = req.body;

        if (!String(product_name || "").trim()) {
            return res.status(400).json({
                success: false,
                message: "商品名称不能为空"
            });
        }

        const level1 = String(category_level_1 || "").trim();
        const level2 = String(category_level_2 || "").trim();
        const level3 = String(category_level_3 || "").trim();

        const colorList = [...new Set(parseColors(colors))];

        const fullCategory = [
            level1,
            level2,
            level3
        ]
            .filter(Boolean)
            .join("/");

        const normalizedStatus = Number(status) === 0 ? 0 : 1;

        await connection.beginTransaction();

        const [result] = await connection.query(
            `
                UPDATE product_catalog
                SET
                    product_name = ?,
                    category_level_1 = ?,
                    category_level_2 = ?,
                    category_level_3 = ?,
                    cate_full_name = ?,
                    brand_name = ?,
                    colors = ?,
                    color_count = ?,
                    status = ?
                WHERE id = ?
            `,
            [
                String(product_name).trim(),
                level1 || null,
                level2 || null,
                level3 || null,
                fullCategory || null,
                String(brand_name || "").trim() || null,
                JSON.stringify(colorList),
                colorList.length,
                normalizedStatus,
                productId
            ]
        );

        if (!result.affectedRows) {
            await connection.rollback();

            return res.status(404).json({
                success: false,
                message: "商品不存在"
            });
        }

        await connection.commit();

        res.json({
            success: true,
            message: "商品信息已保存"
        });
    } catch (error) {
        await connection.rollback();

        console.error("updateProduct error:", error);

        res.status(500).json({
            success: false,
            message: "保存商品信息失败",
            error: error.message
        });
    } finally {
        connection.release();
    }
};


// ======================================================
// 上传商品文件
// POST /api/products/:id/files
//
// multipart/form-data：
// file                文件
// file_type           文件类型
// remark              备注
// status              状态
//
// 商品字段可以同时提交：
// category_level_1
// category_level_2
// category_level_3
// product_name
// brand_name
// colors
// ======================================================

exports.uploadProductFile = async (req, res) => {
    const connection = await pool.getConnection();

    try {
        const productId = Number(req.params.id);

        if (!Number.isInteger(productId) || productId < 1) {
            if (req.file?.path && fs.existsSync(req.file.path)) {
                fs.unlinkSync(req.file.path);
            }

            return res.status(400).json({
                success: false,
                message: "商品ID不正确"
            });
        }

        if (!req.file) {
            return res.status(400).json({
                success: false,
                message: "请选择需要上传的文件"
            });
        }

        const [productRows] = await connection.query(
            `
                SELECT id
                FROM product_catalog
                WHERE id = ?
                LIMIT 1
            `,
            [productId]
        );

        if (!productRows.length) {
            if (fs.existsSync(req.file.path)) {
                fs.unlinkSync(req.file.path);
            }

            return res.status(404).json({
                success: false,
                message: "商品不存在"
            });
        }

        const fileType = String(
            req.body.file_type || "product_image"
        ).trim();

        const allowedFileTypes = new Set([
            "cover",
            "product_image",
            "detail_image",
            "white_image",
            "other"
        ]);

        const normalizedFileType = allowedFileTypes.has(fileType)
            ? fileType
            : "other";

        const status = Number(req.body.status) === 0 ? 0 : 1;

        const relativeUrl = `/uploads/products/${req.file.filename}`;

        await connection.beginTransaction();

        const [result] = await connection.query(
            `
                INSERT INTO product_files
                (
                    product_id,
                    file_type,
                    file_name,
                    file_url,
                    file_size,
                    remark,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            `,
            [
                productId,
                normalizedFileType,
                req.file.originalname,
                relativeUrl,
                req.file.size,
                String(req.body.remark || "").trim() || null,
                status
            ]
        );

        await connection.query(
            `
                UPDATE product_catalog
                SET has_files = 1
                WHERE id = ?
            `,
            [productId]
        );

        await connection.commit();

        res.json({
            success: true,
            message: "文件上传成功",
            data: {
                id: result.insertId,
                product_id: productId,
                file_type: normalizedFileType,
                file_name: req.file.originalname,
                file_url: relativeUrl,
                file_size: req.file.size,
                remark: String(req.body.remark || "").trim(),
                status
            }
        });
    } catch (error) {
        await connection.rollback();

        if (req.file?.path && fs.existsSync(req.file.path)) {
            fs.unlinkSync(req.file.path);
        }

        console.error("uploadProductFile error:", error);

        res.status(500).json({
            success: false,
            message: "文件上传失败",
            error: error.message
        });
    } finally {
        connection.release();
    }
};


// ======================================================
// 删除商品文件
// DELETE /api/files/:id
// ======================================================

exports.deleteProductFile = async (req, res) => {
    const connection = await pool.getConnection();

    try {
        const fileId = Number(req.params.id);

        if (!Number.isInteger(fileId) || fileId < 1) {
            return res.status(400).json({
                success: false,
                message: "文件ID不正确"
            });
        }

        const [rows] = await connection.query(
            `
                SELECT
                    id,
                    product_id,
                    file_url
                FROM product_files
                WHERE id = ?
                LIMIT 1
            `,
            [fileId]
        );

        if (!rows.length) {
            return res.status(404).json({
                success: false,
                message: "文件不存在"
            });
        }

        const fileInfo = rows[0];

        await connection.beginTransaction();

        await connection.query(
            `
                DELETE FROM product_files
                WHERE id = ?
            `,
            [fileId]
        );

        const [countRows] = await connection.query(
            `
                SELECT COUNT(*) AS total
                FROM product_files
                WHERE product_id = ?
            `,
            [fileInfo.product_id]
        );

        const remainingFiles = Number(countRows[0].total || 0);

        await connection.query(
            `
                UPDATE product_catalog
                SET has_files = ?
                WHERE id = ?
            `,
            [
                remainingFiles > 0 ? 1 : 0,
                fileInfo.product_id
            ]
        );

        await connection.commit();

        const relativePath = String(fileInfo.file_url || "")
            .replace(/^\/+/, "");

        const absolutePath = path.join(
            __dirname,
            "..",
            relativePath
        );

        if (
            relativePath &&
            fs.existsSync(absolutePath)
        ) {
            fs.unlinkSync(absolutePath);
        }

        res.json({
            success: true,
            message: "文件已删除"
        });
    } catch (error) {
        await connection.rollback();

        console.error("deleteProductFile error:", error);

        res.status(500).json({
            success: false,
            message: "删除文件失败",
            error: error.message
        });
    } finally {
        connection.release();
    }
};
