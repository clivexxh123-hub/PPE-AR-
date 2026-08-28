const path = require("path");

const pool = require("../db");
const { runSqlMigration } = require("./run-sql-migration");

async function migrate() {
    await runSqlMigration(pool, path.join(__dirname, "..", "migrations", "002_iam.sql"));
    await runSqlMigration(pool, path.join(__dirname, "..", "migrations", "003_generation_records.sql"));
    await runSqlMigration(pool, path.join(__dirname, "..", "migrations", "004_super_admin.sql"));
    await runSqlMigration(pool, path.join(__dirname, "..", "migrations", "005_customers.sql"));
    await runSqlMigration(pool, path.join(__dirname, "..", "migrations", "006_product_showcase_profiles.sql"));
    await runSqlMigration(pool, path.join(__dirname, "..", "migrations", "007_customer_generation_archives.sql"));
    await runSqlMigration(pool, path.join(__dirname, "..", "migrations", "008_generation_record_deletions.sql"));
    await runSqlMigration(pool, path.join(__dirname, "..", "migrations", "010_password_auth.sql"));
    console.log("IAM password login, organization, customer, generation and product tables are ready.");
}

migrate()
    .catch((error) => {
        console.error("IAM migration failed:", error);
        process.exitCode = 1;
    })
    .finally(async () => {
        await pool.end();
    });
