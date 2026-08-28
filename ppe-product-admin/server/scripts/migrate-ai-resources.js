const fs = require("fs");
const path = require("path");
const pool = require("../db");

async function migrate() {
    const migrationPath = path.join(
        __dirname,
        "..",
        "migrations",
        "001_ai_resource_assets.sql"
    );

    const statements = fs
        .readFileSync(migrationPath, "utf8")
        .split(/;\s*(?:\r?\n|$)/)
        .map((statement) => statement.trim())
        .filter(Boolean);

    for (const statement of statements) {
        await pool.query(statement);
    }

    const [shotTypeColumns] = await pool.query(
        "SHOW COLUMNS FROM ai_model_assets LIKE 'shot_type'"
    );

    if (!shotTypeColumns.length) {
        await pool.query(`
            ALTER TABLE ai_model_assets
            ADD COLUMN shot_type ENUM('full_body', 'half_body')
            NOT NULL DEFAULT 'full_body'
            AFTER gender
        `);
    }

    const [shotTypeIndexes] = await pool.query(
        "SHOW INDEX FROM ai_model_assets WHERE Key_name = 'idx_ai_model_assets_shot_type'"
    );

    if (!shotTypeIndexes.length) {
        await pool.query(`
            CREATE INDEX idx_ai_model_assets_shot_type
            ON ai_model_assets (shot_type)
        `);
    }

    const [viewTypeColumns] = await pool.query(
        "SHOW COLUMNS FROM ai_model_assets LIKE 'view_type'"
    );

    if (!viewTypeColumns.length) {
        await pool.query(`
            ALTER TABLE ai_model_assets
            ADD COLUMN view_type ENUM('front', 'slight_side')
            NOT NULL DEFAULT 'front'
            AFTER shot_type
        `);
        await pool.query(`
            UPDATE ai_model_assets
            SET view_type = 'slight_side'
            WHERE LOWER(model_key) REGEXP 'slight[-_ ]?side|three[-_ ]?quarter'
               OR remark LIKE '%微侧%'
               OR remark LIKE '%侧前方%'
        `);
    }

    const [viewTypeIndexes] = await pool.query(
        "SHOW INDEX FROM ai_model_assets WHERE Key_name = 'idx_ai_model_assets_view_type'"
    );

    if (!viewTypeIndexes.length) {
        await pool.query(`
            CREATE INDEX idx_ai_model_assets_view_type
            ON ai_model_assets (view_type)
        `);
    }

    console.log("AI resource tables are ready.");
}

migrate()
    .catch((error) => {
        console.error("AI resource migration failed:", error);
        process.exitCode = 1;
    })
    .finally(async () => {
        await pool.end();
    });
