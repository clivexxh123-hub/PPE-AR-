const crypto = require("crypto");

const { isSuperAdministrator } = require("./iam/access");
const { httpError } = require("./iam/security");
const { organizationSnapshot } = require("./generation-records");

const CUSTOMER_FIELDS = [
    "customerName",
    "companyShortName",
    "industry",
    "remarkId",
    "notes"
];

const FIELD_RULES = {
    customerName: ["客户ID", 120],
    companyShortName: ["客户简称", 80],
    industry: ["所属行业", 100],
    remarkId: ["淘宝ID或订单号", 100],
    notes: ["备注", 4000]
};

function optionalText(value, field) {
    const [label, maxLength] = FIELD_RULES[field];
    const text = String(value ?? "").trim();
    if (text.length > maxLength) {
        throw httpError(400, `${label}不能超过${maxLength}个字符`, "CUSTOMER_400_VALIDATION_FAILED");
    }
    return text || null;
}

function normalizeCustomerInput(input = {}, current = null) {
    const normalized = {};
    for (const field of CUSTOMER_FIELDS) {
        normalized[field] = Object.prototype.hasOwnProperty.call(input, field)
            ? optionalText(input[field], field)
            : current?.[field] ?? null;
    }
    if (!normalized.customerName) {
        throw httpError(400, "客户ID不能为空", "CUSTOMER_400_VALIDATION_FAILED");
    }
    if (!normalized.remarkId) {
        throw httpError(400, "淘宝ID或订单号不能为空", "CUSTOMER_400_VALIDATION_FAILED");
    }
    return normalized;
}

function archiveSegment(value, fallback) {
    const normalized = String(value || fallback || "")
        .replace(/[<>:"/\\|?*+\u0000-\u001f]/g, "_")
        .replace(/\s+/g, " ")
        .replace(/[. ]+$/g, "")
        .trim();
    return (normalized || "未命名").slice(0, 80);
}

function createArchiveIdentity(customer) {
    const reference = archiveSegment(customer.remarkId, "未填写淘宝ID或订单号");
    return {
        archiveName: reference,
        archiveNameStandard: Boolean(customer.remarkId)
    };
}

function canManageCustomer(actor, customer) {
    return Boolean(actor?.id && (actor.id === customer?.owner?.id || isSuperAdministrator(actor)));
}

function customerNotFound() {
    return httpError(404, "客户档案不存在或已删除", "CUSTOMER_404_NOT_FOUND");
}

function normalizeCustomerId(value) {
    const id = String(value || "").trim();
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) {
        throw httpError(400, "客户档案 ID 格式无效", "CUSTOMER_400_ID_INVALID");
    }
    return id;
}

class CustomerService {
    constructor({
        repository,
        tenantId = process.env.IAM_TENANT_ID || "shoudun-ppe",
        clock = () => new Date(),
        randomUUID = () => crypto.randomUUID()
    }) {
        this.repository = repository;
        this.tenantId = String(tenantId || "").trim();
        this.clock = clock;
        this.randomUUID = randomUUID;
        if (!this.tenantId || this.tenantId.length > 64) {
            throw new Error("IAM_TENANT_ID 必须是 1 到 64 个字符");
        }
    }

    async list(query, actor, ipHash = null) {
        const filters = {
            tenantId: this.tenantId,
            search: String(query?.search || "").trim().slice(0, 120) || null,
            ownerUserId: query?.mine === "true" || query?.mine === "1" ? actor.id : null,
            limit: query?.limit,
            offset: query?.offset
        };
        const result = await this.repository.list(filters);
        await this.repository.createAudit({
            actorUserId: actor.id,
            action: "customer.list_read",
            targetType: "customer_list",
            targetId: null,
            metadata: {
                count: result.items.length,
                total: result.total,
                filters: { search: filters.search, mine: Boolean(filters.ownerUserId) }
            },
            ipHash
        });
        return {
            total: result.total,
            items: result.items.map((customer) => ({
                ...customer,
                canEdit: canManageCustomer(actor, customer),
                canDelete: canManageCustomer(actor, customer)
            }))
        };
    }

    async get(customerId, actor, ipHash = null) {
        const normalizedId = normalizeCustomerId(customerId);
        const customer = await this.repository.findById(normalizedId, this.tenantId);
        if (!customer) throw customerNotFound();
        await this.repository.createAudit({
            actorUserId: actor.id,
            action: "customer.detail_read",
            targetType: "customer",
            targetId: customer.id,
            metadata: { ownerUserId: customer.owner.id, archiveName: customer.archiveName },
            ipHash
        });
        return {
            ...customer,
            canEdit: canManageCustomer(actor, customer),
            canDelete: canManageCustomer(actor, customer)
        };
    }

    async create(input, actor, ipHash = null) {
        const values = normalizeCustomerInput(input);
        const identity = createArchiveIdentity(values);
        const snapshot = organizationSnapshot(actor);
        const customer = {
            id: this.randomUUID(),
            tenantId: this.tenantId,
            ...values,
            ...identity,
            owner: { id: actor.id, displayName: actor.displayName },
            orgUnit: snapshot.unit,
            department: snapshot.department
        };
        try {
            return await this.repository.withTransaction(async (transaction) => {
                const created = await transaction.create(customer);
                await transaction.createAudit({
                    actorUserId: actor.id,
                    action: "customer.create",
                    targetType: "customer",
                    targetId: customer.id,
                    metadata: {
                        archiveName: customer.archiveName,
                        archiveNameStandard: customer.archiveNameStandard,
                        customerName: customer.customerName,
                        archiveReference: customer.remarkId,
                        ownerUserId: actor.id,
                        orgUnitIdAtCreate: snapshot.unit?.id || null
                    },
                    ipHash
                });
                return { ...created, canEdit: true, canDelete: true };
            });
        } catch (error) {
            if (error?.code === "ER_DUP_ENTRY") {
                throw httpError(409, "该淘宝ID或订单号已经存在", "CUSTOMER_409_ARCHIVE_EXISTS");
            }
            throw error;
        }
    }

    async update(customerId, input, actor, ipHash = null) {
        const normalizedId = normalizeCustomerId(customerId);
        try {
            return await this.repository.withTransaction(async (transaction) => {
                const current = await transaction.findById(normalizedId, this.tenantId, { forUpdate: true });
                if (!current) throw customerNotFound();
                if (!canManageCustomer(actor, current)) {
                    throw httpError(403, "只能修改本人客户档案", "CUSTOMER_403_OWNERSHIP_REQUIRED");
                }
                const values = normalizeCustomerInput(input, current);
                const identity = createArchiveIdentity(values);
                const changedFields = CUSTOMER_FIELDS.filter((field) => values[field] !== current[field]);
                if (!changedFields.length) return { ...current, canEdit: true, canDelete: true };
                const updated = await transaction.update(normalizedId, this.tenantId, { ...values, ...identity });
                await transaction.createAudit({
                    actorUserId: actor.id,
                    action: "customer.update",
                    targetType: "customer",
                    targetId: normalizedId,
                    metadata: {
                        changedFields,
                        ownerUserId: current.owner.id,
                        archiveNameBefore: current.archiveName,
                        archiveNameAfter: identity.archiveName
                    },
                    ipHash
                });
                return { ...updated, canEdit: true, canDelete: true };
            });
        } catch (error) {
            if (error?.code === "ER_DUP_ENTRY") {
                throw httpError(409, "该淘宝ID或订单号已经存在", "CUSTOMER_409_ARCHIVE_EXISTS");
            }
            throw error;
        }
    }

    async remove(customerId, actor, ipHash = null) {
        const normalizedId = normalizeCustomerId(customerId);
        return this.repository.withTransaction(async (transaction) => {
            const current = await transaction.findById(normalizedId, this.tenantId, { forUpdate: true });
            if (!current) throw customerNotFound();
            if (!canManageCustomer(actor, current)) {
                throw httpError(403, "只能删除本人客户档案", "CUSTOMER_403_OWNERSHIP_REQUIRED");
            }
            if (!await transaction.softDelete(normalizedId, this.tenantId, actor.id)) throw customerNotFound();
            await transaction.createAudit({
                actorUserId: actor.id,
                action: "customer.delete",
                targetType: "customer",
                targetId: normalizedId,
                metadata: {
                    customerName: current.customerName,
                    archiveName: current.archiveName,
                    ownerUserId: current.owner.id
                },
                ipHash
            });
            return { id: normalizedId, deleted: true };
        });
    }
}

module.exports = {
    CUSTOMER_FIELDS,
    CustomerService,
    archiveSegment,
    canManageCustomer,
    createArchiveIdentity,
    normalizeCustomerId,
    normalizeCustomerInput
};
