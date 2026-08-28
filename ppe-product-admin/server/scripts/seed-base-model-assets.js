const fs = require("fs");
const path = require("path");

require("dotenv").config();

const pool = require("../db");
const { modelSeeds } = require("../data/ai-resource-seeds");

const modelRoot = path.resolve(__dirname, "..", "uploads", "models");

function validateModelImage(model) {
    const filename = path.resolve(modelRoot, model.image_name);
    if (!filename.startsWith(`${modelRoot}${path.sep}`) || !fs.statSync(filename).isFile()) {
        throw new Error(`模特素材不存在或路径越界：${model.image_name}`);
    }
}

async function upsertModel(connection, model) {
    validateModelImage(model);
    const [rows] = await connection.query(
        "SELECT id FROM ai_model_assets WHERE model_key=? ORDER BY id LIMIT 1",
        [model.model_key]
    );
    const values = [
        model.model_name,
        model.gender,
        model.shot_type,
        model.view_type,
        model.image_name,
        model.image_url,
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
        [model.model_key, ...values]
    );
    return result.insertId;
}

async function main() {
    const connection = await pool.getConnection();
    try {
        await connection.beginTransaction();
        const modelIds = [];
        for (const model of modelSeeds) modelIds.push(await upsertModel(connection, model));
        await connection.commit();
        console.log(JSON.stringify({ count: modelIds.length, modelIds }));
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
