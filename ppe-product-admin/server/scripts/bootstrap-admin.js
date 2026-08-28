require("dotenv").config();

const crypto = require("crypto");

const pool = require("../db");
const { hashPassword } = require("../services/iam/password");
const { IamRepository } = require("../services/iam/repository");
const { maskPhone, normalizePhone } = require("../services/iam/security");
const { requiredText } = require("../services/iam/service");

async function bootstrap() {
    const displayName = requiredText(process.env.IAM_BOOTSTRAP_ADMIN_NAME, "IAM_BOOTSTRAP_ADMIN_NAME", 80);
    const phone = normalizePhone(process.env.IAM_BOOTSTRAP_ADMIN_PHONE);
    const orgUnitCode = requiredText(process.env.IAM_BOOTSTRAP_ADMIN_ORG_CODE, "IAM_BOOTSTRAP_ADMIN_ORG_CODE", 64);
    const password = String(process.env.IAM_BOOTSTRAP_ADMIN_PASSWORD || "");
    const repository = new IamRepository(pool);
    const orgUnit = await repository.getOrgUnitByCode(orgUnitCode);
    if (!orgUnit || !orgUnit.active) throw new Error("IAM_BOOTSTRAP_ADMIN_ORG_CODE 不存在或已停用");

    let user = await repository.findUserByPhone(phone);
    const credential = user ? await repository.findLoginCredentialByPhone(phone) : null;
    if (!password && !credential?.password_hash) {
        throw new Error("首次创建管理员时必须设置 IAM_BOOTSTRAP_ADMIN_PASSWORD");
    }
    const passwordHash = password ? await hashPassword(password) : null;
    const userId = await repository.withTransaction(async (transaction) => {
        const id = user?.id || await transaction.createUser({
            id: crypto.randomUUID(),
            displayName,
            phone,
            status: "active"
        });
        if (user) {
            await transaction.updateUser(id, { displayName, phone, status: "active" });
        }
        if (passwordHash) await transaction.setPasswordCredential(id, passwordHash);
        await transaction.setUserRoles(id, ["admin"], null);
        await transaction.setCurrentOrgMembership(id, orgUnit.id, null);
        await transaction.createAudit({
            actorUserId: null,
            action: "iam.admin_bootstrapped",
            targetType: "user",
            targetId: id,
            metadata: { displayName, phone: maskPhone(phone), orgUnitCode, passwordChanged: Boolean(passwordHash) }
        });
        return id;
    });

    user = await repository.getUserAccess(userId);
    console.log(`Administrator ready: ${user.displayName} ${maskPhone(user.phone)} ${orgUnit.name}`);
}

bootstrap()
    .catch((error) => {
        console.error("Administrator bootstrap failed:", error);
        process.exitCode = 1;
    })
    .finally(async () => {
        await pool.end();
    });
