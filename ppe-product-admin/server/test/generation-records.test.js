const assert = require("node:assert/strict");
const test = require("node:test");

const {
    GenerationRecordRepository,
    organizationSnapshot,
    progressForStatus
} = require("../services/generation-records");

test("organization snapshots preserve the department above a sales group", () => {
    const snapshot = organizationSnapshot({
        orgUnit: {
            id: "group-2",
            code: "presale-2",
            name: "售前2组",
            unitType: "group",
            parent: {
                id: "department-public",
                code: "jingshan-public",
                name: "京山公域销售"
            }
        }
    });
    assert.equal(snapshot.unit.code, "presale-2");
    assert.equal(snapshot.department.code, "jingshan-public");
});

test("status progress is deterministic and bounded", () => {
    assert.equal(progressForStatus("queued"), 5);
    assert.equal(progressForStatus("succeeded"), 100);
    assert.equal(progressForStatus("running", 155), 100);
    assert.equal(progressForStatus("running", -5), 0);
});

test("generation records store user and organization values at event time", async () => {
    const calls = [];
    const repository = new GenerationRecordRepository({
        async query(sql, values) {
            calls.push({ sql, values });
            return [[]];
        }
    });
    const actor = {
        id: "employee-7",
        displayName: "销售七",
        orgUnit: {
            id: "group-2",
            code: "presale-2",
            name: "售前2组",
            unitType: "group",
            parent: {
                id: "department-public",
                code: "jingshan-public",
                name: "京山公域销售"
            }
        }
    };
    const prepared = {
        generationMode: "human_wearing",
        composition: { view: "front", framing: "half_body" },
        task: {
            jobId: "job-1",
            tenantId: "shoudun-ppe",
            traceId: "trace-1",
            modelProfileId: "ppe-v1",
            workflowVersion: "v1",
            parameters: { size: "1024x1024", product_view: "front" }
        }
    };
    await repository.create({
        prepared,
        actor,
        batchId: "batch-12345678",
        product: { id: "product-1", product_name: "安全帽", goods_no: "H-1" },
        model: { id: "model-1", name: "模特一" },
        scene: { id: "scene-1", name: "建筑工地" },
        engine: "comfyui"
    });

    assert.equal(calls.length, 1);
    const values = calls[0].values;
    assert.equal(values[0], "job-1");
    assert.equal(values[4], "employee-7");
    assert.equal(values[5], "销售七");
    assert.equal(values[7], "presale-2");
    assert.equal(values[10], "jingshan-public");
    assert.equal(values[16], "front");
    assert.equal(values[17], "half_body");
    assert.equal(values[23], "comfyui");
});

test("super administrator deletion creates an auditable tombstone", async () => {
    const calls = [];
    const repository = new GenerationRecordRepository({
        async query(sql, values) {
            calls.push({ sql, values });
            return [{ affectedRows: 1 }];
        }
    });

    assert.equal(await repository.softDelete("job-1", "admin-1"), true);
    assert.match(calls[0].sql, /business_generation_record_deletions/);
    assert.deepEqual(calls[0].values, ["job-1", "admin-1"]);
});
