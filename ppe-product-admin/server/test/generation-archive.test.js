const assert = require("node:assert/strict");
const test = require("node:test");

const {
    GenerationArchiveService,
    detectImage,
    validCustomerId,
    validJobId
} = require("../services/generation-archive-service");

const CUSTOMER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const OWNER_ID = "11111111-1111-4111-8111-111111111111";
const OTHER_ID = "22222222-2222-4222-8222-222222222222";

function pngBuffer() {
    return Buffer.concat([
        Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
        Buffer.alloc(8)
    ]);
}

test("generation archive validates identifiers and image bytes, not MIME claims", () => {
    assert.equal(validCustomerId("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
    assert.equal(validJobId("job-safe_123"), "job-safe_123");
    assert.throws(() => validCustomerId("../customer"), /ID 格式无效/);
    assert.throws(() => validJobId("../job"), /ID 格式无效/);

    assert.deepEqual(detectImage(pngBuffer()), { extension: "png", contentType: "image/png" });
    assert.throws(
        () => detectImage(Buffer.from("<svg><script>alert(1)</script></svg>")),
        (error) => error.statusCode === 400 && error.errorCode === "ARCHIVE_400_IMAGE_INVALID"
    );
});

test("ordinary employees cannot archive into another employee's customer", async () => {
    const repository = {
        async findCustomer() {
            return { id: CUSTOMER_ID, owner_user_id: OWNER_ID };
        }
    };
    const service = new GenerationArchiveService({ repository, tenantId: "test-tenant" });
    await assert.rejects(
        service.archive({ customerId: CUSTOMER_ID, jobId: "job-1", buffer: pngBuffer() }, {
            id: OTHER_ID,
            displayName: "其他员工",
            roles: [{ id: "sales", name: "普通员工" }]
        }),
        (error) => error.statusCode === 403 && error.errorCode === "ARCHIVE_403_CUSTOMER_OWNERSHIP_REQUIRED"
    );
});

test("customer owner still cannot archive another employee's generation", async () => {
    const repository = {
        async findCustomer() {
            return { id: CUSTOMER_ID, owner_user_id: OWNER_ID };
        },
        async findGeneration() {
            return { job_id: "job-2", user_id: OTHER_ID, status: "succeeded" };
        }
    };
    const service = new GenerationArchiveService({ repository, tenantId: "test-tenant" });
    await assert.rejects(
        service.archive({ customerId: CUSTOMER_ID, jobId: "job-2", buffer: pngBuffer() }, {
            id: OWNER_ID,
            displayName: "客户归属员工",
            roles: [{ id: "sales", name: "普通员工" }]
        }),
        (error) => error.statusCode === 403 && error.errorCode === "ARCHIVE_403_GENERATION_OWNERSHIP_REQUIRED"
    );
});

test("mock and unverified results cannot enter customer formal archives", async () => {
    const actor = {
        id: OWNER_ID,
        displayName: "客户归属员工",
        roles: [{ id: "sales", name: "普通员工" }]
    };
    for (const [engine, errorCode] of [
        ["mock", "ARCHIVE_409_MOCK_RESULT"],
        [null, "ARCHIVE_409_ENGINE_UNVERIFIED"]
    ]) {
        const repository = {
            async findCustomer() {
                return { id: CUSTOMER_ID, owner_user_id: OWNER_ID };
            },
            async findGeneration() {
                return { job_id: "job-safe", user_id: OWNER_ID, status: "succeeded", engine };
            }
        };
        const service = new GenerationArchiveService({ repository, tenantId: "test-tenant" });
        await assert.rejects(
            service.archive({ customerId: CUSTOMER_ID, jobId: "job-safe", buffer: pngBuffer() }, actor),
            (error) => error.statusCode === 409 && error.errorCode === errorCode
        );
    }
});
