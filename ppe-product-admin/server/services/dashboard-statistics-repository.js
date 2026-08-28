class DashboardStatisticsRepository {
    constructor(executor) {
        this.executor = executor;
    }

    async load({ tenantId, startDate }) {
        const baseWhere = `r.tenant_id=?
            AND r.status='succeeded'
            AND r.created_at>=?
            AND deletion.job_id IS NULL`;
        const parameters = [tenantId, startDate];

        const [dailyRows] = await this.executor.query(
            `SELECT DATE_FORMAT(r.created_at, '%Y-%m-%d') AS day,
                    COUNT(*) AS image_count,
                    COUNT(DISTINCT archive.customer_id) AS customer_count
             FROM business_generation_records r
             LEFT JOIN business_generation_record_deletions deletion ON deletion.job_id=r.job_id
             LEFT JOIN business_customer_generation_archives archive
                    ON archive.job_id=r.job_id AND archive.tenant_id=r.tenant_id
             WHERE ${baseWhere}
             GROUP BY DATE_FORMAT(r.created_at, '%Y-%m-%d')
             ORDER BY DATE_FORMAT(r.created_at, '%Y-%m-%d')`,
            parameters
        );

        const [employeeRows] = await this.executor.query(
            `SELECT r.user_id, r.user_name_at_event,
                    r.org_unit_id_at_event, r.org_unit_name_at_event,
                    r.department_id_at_event, r.department_name_at_event,
                    COUNT(*) AS image_count
             FROM business_generation_records r
             LEFT JOIN business_generation_record_deletions deletion ON deletion.job_id=r.job_id
             WHERE ${baseWhere}
             GROUP BY r.user_id, r.user_name_at_event,
                      r.org_unit_id_at_event, r.org_unit_name_at_event,
                      r.department_id_at_event, r.department_name_at_event
             ORDER BY image_count DESC, r.user_name_at_event
             LIMIT 10`,
            parameters
        );

        const [groupRows] = await this.executor.query(
            `SELECT r.org_unit_id_at_event, r.org_unit_name_at_event,
                    r.department_id_at_event, r.department_name_at_event,
                    COUNT(*) AS image_count
             FROM business_generation_records r
             LEFT JOIN business_generation_record_deletions deletion ON deletion.job_id=r.job_id
             WHERE ${baseWhere}
             GROUP BY r.org_unit_id_at_event, r.org_unit_name_at_event,
                      r.department_id_at_event, r.department_name_at_event
             ORDER BY image_count DESC, r.org_unit_name_at_event`,
            parameters
        );

        const [modeRows] = await this.executor.query(
            `SELECT
                COALESCE(SUM(CASE WHEN product_count<=1 THEN image_count ELSE 0 END), 0)
                    AS single_product_images,
                COALESCE(SUM(CASE WHEN product_count>1 THEN image_count ELSE 0 END), 0)
                    AS multi_product_images
             FROM (
                SELECT COALESCE(NULLIF(r.batch_id, ''), r.job_id) AS batch_key,
                       COUNT(DISTINCT COALESCE(NULLIF(r.product_id, ''), CONCAT('name:', r.product_name)))
                           AS product_count,
                       COUNT(*) AS image_count
                FROM business_generation_records r
                LEFT JOIN business_generation_record_deletions deletion ON deletion.job_id=r.job_id
                WHERE ${baseWhere}
                GROUP BY COALESCE(NULLIF(r.batch_id, ''), r.job_id)
             ) AS batches`,
            parameters
        );

        const [productRows] = await this.executor.query(
            `SELECT COALESCE(NULLIF(r.product_id, ''), CONCAT('name:', r.product_name)) AS product_key,
                    MAX(r.product_id) AS product_id,
                    r.product_name,
                    MAX(r.product_code) AS product_code,
                    COUNT(DISTINCT COALESCE(NULLIF(r.batch_id, ''), r.job_id)) AS selection_count,
                    COUNT(*) AS image_count
             FROM business_generation_records r
             LEFT JOIN business_generation_record_deletions deletion ON deletion.job_id=r.job_id
             WHERE ${baseWhere}
               AND (NULLIF(r.product_id, '') IS NOT NULL OR NULLIF(r.product_name, '') IS NOT NULL)
             GROUP BY COALESCE(NULLIF(r.product_id, ''), CONCAT('name:', r.product_name)), r.product_name
             ORDER BY selection_count DESC, image_count DESC, r.product_name
             LIMIT 10`,
            parameters
        );

        return {
            dailyRows,
            employeeRows,
            groupRows,
            modeRow: modeRows[0] || {},
            productRows
        };
    }
}

module.exports = { DashboardStatisticsRepository };
