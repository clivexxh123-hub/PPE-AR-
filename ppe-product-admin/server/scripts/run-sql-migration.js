const fs = require("fs");

async function runSqlMigration(pool, migrationPath) {
    const statements = fs
        .readFileSync(migrationPath, "utf8")
        .split(/;\s*(?:\r?\n|$)/)
        .map((statement) => statement.trim())
        .filter(Boolean);

    for (const statement of statements) {
        await pool.query(statement);
    }
}

module.exports = { runSqlMigration };
