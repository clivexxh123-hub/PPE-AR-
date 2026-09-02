const path = require("path");

const pool = require("../db");
const { runSqlMigration } = require("./run-sql-migration");

async function main() {
    await runSqlMigration(
        pool,
        path.join(__dirname, "..", "migrations", "012_case_template_utf8_repair.sql")
    );
    console.log("Case template UTF-8 repair completed.");
}

main()
    .catch((error) => {
        console.error(error);
        process.exitCode = 1;
    })
    .finally(() => pool.end());
