const path = require("path");

const pool = require("../db");
const { runSqlMigration } = require("./run-sql-migration");

async function main() {
    await runSqlMigration(
        pool,
        path.join(__dirname, "..", "migrations", "011_customer_solutions.sql")
    );
    console.log("Customer solutions migration completed.");
}

main()
    .catch((error) => {
        console.error(error);
        process.exitCode = 1;
    })
    .finally(() => pool.end());
