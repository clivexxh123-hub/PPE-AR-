const pool = require("../db");
const {
    modelSeeds,
    sceneSeeds
} = require("../data/ai-resource-seeds");

function keywordValue(value) {
    return String(value || "").trim();
}

function decodeMultipartFilename(value) {
    const name = String(value || "");

    if (!name || Array.from(name).some((char) => char.charCodeAt(0) > 255)) {
        return name;
    }

    const decoded = Buffer.from(name, "latin1").toString("utf8");

    return decoded.includes("�") ? name : decoded;
}

function containsKeyword(item, keyword, fields) {
    if (!keyword) {
        return true;
    }

    const normalizedKeyword = keyword.toLowerCase();

    return fields.some((field) => (
        String(item[field] || "").toLowerCase().includes(normalizedKeyword)
    ));
}

function filteredModelSeeds(query = {}) {
    const keyword = keywordValue(query.keyword);
    const gender = keywordValue(query.gender);
    const shotType = keywordValue(query.shot_type);
    const viewType = keywordValue(query.view_type || query.view);

    return modelSeeds.filter((item) => (
        containsKeyword(item, keyword, ["model_name", "model_key", "remark"]) &&
        (!gender || item.gender === gender) &&
        (!shotType || item.shot_type === shotType) &&
        (!viewType || item.view_type === viewType)
    ));
}

function filteredSceneSeeds(query = {}) {
    const keyword = keywordValue(query.keyword);
    const industry = keywordValue(query.industry);

    return sceneSeeds.filter((item) => (
        containsKeyword(item, keyword, ["scene_name", "scene_key", "industry", "remark"]) &&
        (!industry || item.industry === industry)
    ));
}

function mergeResources(rows, seeds, key) {
    const existingKeys = new Set(rows.map((item) => item[key]));

    return [
        ...rows,
        ...seeds.filter((item) => !existingKeys.has(item[key]))
    ];
}

exports.getModels = async (req, res) => {
    try {
        const keyword = keywordValue(req.query.keyword);
        const gender = keywordValue(req.query.gender);
        const shotType = keywordValue(req.query.shot_type);
        const viewType = keywordValue(req.query.view_type || req.query.view);
        const where = [];
        const params = [];

        if (keyword) {
            const like = `%${keyword}%`;
            where.push("(model_name LIKE ? OR model_key LIKE ? OR remark LIKE ?)");
            params.push(like, like, like);
        }

        if (["male", "female", "unisex"].includes(gender)) {
            where.push("gender = ?");
            params.push(gender);
        }

        if (["full_body", "half_body"].includes(shotType)) {
            where.push("shot_type = ?");
            params.push(shotType);
        }

        if (["front", "slight_side"].includes(viewType)) {
            where.push("view_type = ?");
            params.push(viewType);
        }

        const [rows] = await pool.query(
            `
                SELECT *
                FROM ai_model_assets
                ${where.length ? `WHERE ${where.join(" AND ")}` : ""}
                ORDER BY id DESC
            `,
            params
        );

        return res.json({
            success: true,
            list: mergeResources(
                rows,
                filteredModelSeeds(req.query),
                "model_key"
            ),
            source: "database+seed"
        });
    } catch (error) {
        console.warn("GET /api/models using local seed resources:", error.message);
        return res.json({
            success: true,
            list: filteredModelSeeds(req.query),
            source: "seed"
        });
    }
};

exports.createModel = async (req, res) => {
    try {
        const modelName = keywordValue(req.body.model_name);
        const gender = keywordValue(req.body.gender);
        const shotType = keywordValue(req.body.shot_type);
        const viewType = keywordValue(req.body.view_type) || "front";
        const remark = keywordValue(req.body.remark);

        if (
            !modelName ||
            !["male", "female", "unisex"].includes(gender) ||
            !["full_body", "half_body"].includes(shotType) ||
            !["front", "slight_side"].includes(viewType) ||
            !req.file
        ) {
            return res.status(400).json({
                success: false,
                message: "请填写模特名称、性别、景别、视角并上传图片"
            });
        }

        const imageName = decodeMultipartFilename(req.file.originalname);
        const imageUrl = `/uploads/models/${req.file.filename}`;
        const modelKey = `${shotType}-${gender}-${modelName}`;

        const [result] = await pool.query(
            `
                INSERT INTO ai_model_assets
                    (model_key, model_name, gender, shot_type, view_type, image_name, image_url, remark)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            `,
            [modelKey, modelName, gender, shotType, viewType, imageName, imageUrl, remark || null]
        );

        return res.status(201).json({
            success: true,
            id: result.insertId
        });
    } catch (error) {
        console.error("POST /api/models failed:", error);
        return res.status(500).json({
            success: false,
            message: error.message
        });
    }
};

exports.getScenes = async (req, res) => {
    try {
        const keyword = keywordValue(req.query.keyword);
        const industry = keywordValue(req.query.industry);
        const where = [];
        const params = [];

        if (keyword) {
            const like = `%${keyword}%`;
            where.push("(scene_name LIKE ? OR scene_key LIKE ? OR industry LIKE ? OR remark LIKE ?)");
            params.push(like, like, like, like);
        }

        if (industry) {
            where.push("industry = ?");
            params.push(industry);
        }

        const [rows] = await pool.query(
            `
                SELECT *
                FROM ai_scene_assets
                ${where.length ? `WHERE ${where.join(" AND ")}` : ""}
                ORDER BY id DESC
            `,
            params
        );

        return res.json({
            success: true,
            list: mergeResources(
                rows,
                filteredSceneSeeds(req.query),
                "scene_key"
            ),
            source: "database+seed"
        });
    } catch (error) {
        console.warn("GET /api/scenes using local seed resources:", error.message);
        return res.json({
            success: true,
            list: filteredSceneSeeds(req.query),
            source: "seed"
        });
    }
};

exports.createScene = async (req, res) => {
    try {
        const sceneName = keywordValue(req.body.scene_name);
        const industry = keywordValue(req.body.industry);
        const remark = keywordValue(req.body.remark);

        if (!sceneName || !industry || !req.file) {
            return res.status(400).json({
                success: false,
                message: "请填写场景名称、行业标签并上传图片"
            });
        }

        const imageName = decodeMultipartFilename(req.file.originalname);
        const imageUrl = `/uploads/scenes/${req.file.filename}`;
        const sceneKey = `${industry}-${sceneName}`;

        const [result] = await pool.query(
            `
                INSERT INTO ai_scene_assets
                    (scene_key, scene_name, industry, image_name, image_url, remark)
                VALUES (?, ?, ?, ?, ?, ?)
            `,
            [sceneKey, sceneName, industry, imageName, imageUrl, remark || null]
        );

        return res.status(201).json({
            success: true,
            id: result.insertId
        });
    } catch (error) {
        console.error("POST /api/scenes failed:", error);
        return res.status(500).json({
            success: false,
            message: error.message
        });
    }
};
