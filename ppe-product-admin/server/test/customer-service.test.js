const assert = require("node:assert/strict");
const test = require("node:test");

const {
    CustomerService,
    createArchiveIdentity,
    normalizeCustomerInput
} = require("../services/customer-service");

const OWNER_ID = "11111111-1111-4111-8111-111111111111";
const OTHER_ID = "22222222-2222-4222-8222-222222222222";
const ADMIN_ID = "33333333-3333-4333-8333-333333333333";
const CUSTOMER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

function actor(id, roles = [{ id: "sales", name: "普通员工" }]) {
    return {
        id,
        displayName: id === OWNER_ID ? "归属员工" : "其他员工",
        roles,
        orgUnit: {
            id: "jingshan-public-presale-1",
            code: "jingshan-public-presale-1",
            name: "售前1组",
            unitType: "group",
            parent: { id: "jingshan-public", code: "jingshan-public", name: "京山公域销售" }
        }
    };
}

class MemoryCustomerRepository {
    constructor() {
        this.customers = [];
        this.audits = [];
    }
    withTransaction(work) { return work(this); }
    async create(customer) {
        const stored = {
            ...customer,
            createdAt: new Date("2026-08-24T01:02:03.004Z"),
            updatedAt: new Date("2026-08-24T01:02:03.004Z"),
            deletedAt: null
        };
        this.customers.push(stored);
        return stored;
    }
    async findById(id, tenantId) {
        return this.customers.find((item) => item.id === id && item.tenantId === tenantId && !item.deletedAt) || null;
    }
    async list({ tenantId, ownerUserId }) {
        const items = this.customers.filter((item) => (
            item.tenantId === tenantId && !item.deletedAt && (!ownerUserId || item.owner.id === ownerUserId)
        ));
        return { items, total: items.length };
    }
    async update(id, tenantId, values) {
        const current = await this.findById(id, tenantId);
        Object.assign(current, values, { updatedAt: new Date("2026-08-24T02:00:00.000Z") });
        return current;
    }
    async softDelete(id, tenantId, actorUserId) {
        const current = await this.findById(id, tenantId);
        if (!current) return false;
        current.deletedAt = new Date();
        current.deletedByUserId = actorUserId;
        return true;
    }
    async createAudit(value) { this.audits.push(value); }
}

test("archive naming directly uses a filesystem-safe Taobao ID or order number", () => {
    assert.deepEqual(
        createArchiveIdentity({ remarkId: "TB/77" }),
        {
            archiveName: "TB_77",
            archiveNameStandard: true
        }
    );
    const fallback = createArchiveIdentity({ remarkId: "" });
    assert.equal(fallback.archiveName, "未填写淘宝ID或订单号");
    assert.equal(fallback.archiveNameStandard, false);
});

test("customer input is bounded and does not accept a browser-selected owner", () => {
    const normalized = normalizeCustomerInput({
        customerName: " 客户甲 ",
        remarkId: " ORDER-1001 ",
        ownerUserId: OTHER_ID,
        companyName: "应被忽略"
    });
    assert.equal(normalized.customerName, "客户甲");
    assert.equal(normalized.remarkId, "ORDER-1001");
    assert.equal(Object.hasOwn(normalized, "ownerUserId"), false);
    assert.equal(Object.hasOwn(normalized, "companyName"), false);
    assert.throws(
        () => normalizeCustomerInput({ customerName: "", remarkId: "ORDER-1001" }),
        (error) => error.statusCode === 400 && error.errorCode === "CUSTOMER_400_VALIDATION_FAILED"
    );
    assert.throws(
        () => normalizeCustomerInput({ customerName: "客户甲", remarkId: "" }),
        (error) => error.statusCode === 400 && error.errorCode === "CUSTOMER_400_VALIDATION_FAILED"
    );
});

test("all employees can read customers but only owner or administrator can mutate", async () => {
    const repository = new MemoryCustomerRepository();
    const service = new CustomerService({
        repository,
        tenantId: "test-tenant",
        clock: () => new Date("2026-08-24T01:02:03.004Z"),
        randomUUID: () => CUSTOMER_ID
    });
    const created = await service.create({
        customerName: "测试客户",
        remarkId: "TB88",
        ownerUserId: OTHER_ID
    }, actor(OWNER_ID));
    assert.equal(created.owner.id, OWNER_ID);

    const visibleToOther = await service.list({}, actor(OTHER_ID));
    assert.equal(visibleToOther.total, 1);
    assert.equal(visibleToOther.items[0].canEdit, false);

    await assert.rejects(
        service.update(CUSTOMER_ID, { customerName: "越权修改" }, actor(OTHER_ID)),
        (error) => error.statusCode === 403 && error.errorCode === "CUSTOMER_403_OWNERSHIP_REQUIRED"
    );

    const updated = await service.update(
        CUSTOMER_ID,
        { customerName: "本人修改", remarkId: "ORDER-9002" },
        actor(OWNER_ID)
    );
    assert.equal(updated.customerName, "本人修改");
    assert.equal(updated.archiveName, "ORDER-9002");
    assert.notEqual(updated.archiveName, created.archiveName);

    const admin = actor(ADMIN_ID, [{ id: "admin", name: "超级管理员" }]);
    const deleted = await service.remove(CUSTOMER_ID, admin);
    assert.equal(deleted.deleted, true);
    assert.deepEqual(
        repository.audits.map((item) => item.action),
        ["customer.create", "customer.list_read", "customer.update", "customer.delete"]
    );
});
