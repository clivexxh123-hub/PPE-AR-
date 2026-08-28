const assert = require("node:assert/strict");
const test = require("node:test");

const {
    DashboardStatisticsService,
    dateKeys,
    normalizeDays,
    percentage
} = require("../services/dashboard-statistics");

test("dashboard date range is bounded to supported reporting periods", () => {
    assert.equal(normalizeDays("7"), 7);
    assert.equal(normalizeDays("365"), 30);
    assert.deepEqual(
        dateKeys(3, new Date(2026, 7, 27, 12, 0, 0)),
        ["2026-08-25", "2026-08-26", "2026-08-27"]
    );
    assert.equal(percentage(1, 4), 25);
    assert.equal(percentage(0, 0), 0);
});

test("dashboard fills empty dates and normalizes business rankings", async () => {
    const service = new DashboardStatisticsService({
        tenantId: "test-tenant",
        clock: () => new Date(2026, 7, 27, 12, 0, 0),
        repository: {
            async load(filters) {
                assert.deepEqual(filters, {
                    tenantId: "test-tenant",
                    startDate: "2026-08-21 00:00:00"
                });
                return {
                    dailyRows: [{ day: "2026-08-27", customer_count: 2, image_count: 8 }],
                    employeeRows: [{
                        user_id: "u1",
                        user_name_at_event: "销售甲",
                        org_unit_name_at_event: "售前1组",
                        image_count: 8
                    }],
                    groupRows: [{ org_unit_id_at_event: "g1", org_unit_name_at_event: "售前1组", image_count: 8 }],
                    modeRow: { single_product_images: 6, multi_product_images: 2 },
                    productRows: [{
                        product_key: "p1",
                        product_id: "p1",
                        product_name: "安全帽",
                        product_code: "H-1",
                        selection_count: 2,
                        image_count: 8
                    }]
                };
            }
        }
    });
    const result = await service.get({ days: 7 });
    assert.equal(result.daily.length, 7);
    assert.deepEqual(result.daily[0], { date: "2026-08-21", customerCount: 0, imageCount: 0 });
    assert.deepEqual(result.daily[6], { date: "2026-08-27", customerCount: 2, imageCount: 8 });
    assert.deepEqual(result.summary, {
        totalImages: 8,
        servicedCustomerDays: 2,
        singleProductImages: 6,
        singleProductShare: 75,
        multiProductImages: 2,
        multiProductShare: 25
    });
    assert.equal(result.employeeRanking[0].name, "销售甲");
    assert.equal(result.productRanking[0].selectionCount, 2);
});
