function normalizeDays(value) {
    const days = Number(value);
    return [7, 30, 90].includes(days) ? days : 30;
}

function localDateKey(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function dateKeys(days, now) {
    const end = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Array.from({ length: days }, (_, index) => {
        const date = new Date(end);
        date.setDate(end.getDate() - (days - index - 1));
        return localDateKey(date);
    });
}

function percentage(value, total) {
    if (!total) return 0;
    return Number(((Number(value) / Number(total)) * 100).toFixed(1));
}

class DashboardStatisticsService {
    constructor({
        repository,
        tenantId = process.env.IAM_TENANT_ID || "shoudun-ppe",
        clock = () => new Date()
    }) {
        this.repository = repository;
        this.tenantId = String(tenantId || "").trim();
        this.clock = clock;
    }

    async get(query = {}) {
        const days = normalizeDays(query.days);
        const keys = dateKeys(days, this.clock());
        const result = await this.repository.load({
            tenantId: this.tenantId,
            startDate: `${keys[0]} 00:00:00`
        });
        const dailyByDate = new Map(result.dailyRows.map((row) => [String(row.day), row]));
        const daily = keys.map((date) => {
            const row = dailyByDate.get(date) || {};
            return {
                date,
                customerCount: Number(row.customer_count || 0),
                imageCount: Number(row.image_count || 0)
            };
        });
        const singleProductImages = Number(result.modeRow.single_product_images || 0);
        const multiProductImages = Number(result.modeRow.multi_product_images || 0);
        const totalImages = singleProductImages + multiProductImages;

        return {
            range: {
                days,
                startDate: keys[0],
                endDate: keys[keys.length - 1]
            },
            summary: {
                totalImages,
                servicedCustomerDays: daily.reduce((sum, row) => sum + row.customerCount, 0),
                singleProductImages,
                singleProductShare: percentage(singleProductImages, totalImages),
                multiProductImages,
                multiProductShare: percentage(multiProductImages, totalImages)
            },
            daily,
            employeeRanking: result.employeeRows.map((row) => ({
                userId: row.user_id,
                name: row.user_name_at_event,
                orgUnitId: row.org_unit_id_at_event,
                orgUnitName: row.org_unit_name_at_event || "未分组",
                departmentId: row.department_id_at_event,
                departmentName: row.department_name_at_event || null,
                imageCount: Number(row.image_count || 0)
            })),
            groupRanking: result.groupRows.map((row) => ({
                orgUnitId: row.org_unit_id_at_event,
                name: row.org_unit_name_at_event || "未分组",
                departmentId: row.department_id_at_event,
                departmentName: row.department_name_at_event || null,
                imageCount: Number(row.image_count || 0)
            })),
            productRanking: result.productRows.map((row) => ({
                productKey: row.product_key,
                productId: row.product_id,
                name: row.product_name,
                code: row.product_code,
                selectionCount: Number(row.selection_count || 0),
                imageCount: Number(row.image_count || 0)
            }))
        };
    }
}

module.exports = {
    DashboardStatisticsService,
    dateKeys,
    normalizeDays,
    percentage
};
