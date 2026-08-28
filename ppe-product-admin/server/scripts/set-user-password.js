require("dotenv").config();

const pool = require("../db");
const { hashPassword } = require("../services/iam/password");
const { IamRepository } = require("../services/iam/repository");
const { maskPhone, normalizePhone, randomToken } = require("../services/iam/security");

async function main() {
    const phone = normalizePhone(process.env.IAM_PASSWORD_USER_PHONE);
    const suppliedPassword = String(process.env.IAM_PASSWORD_VALUE || "");
    const password = suppliedPassword || `Ppe-${randomToken(9)}-8`;
    const passwordHash = await hashPassword(password);
    const repository = new IamRepository(pool);
    const user = await repository.findUserByPhone(phone);
    if (!user) throw new Error("手机号对应的员工账号不存在");

    await repository.withTransaction(async (transaction) => {
        await transaction.setPasswordCredential(user.id, passwordHash);
        await transaction.revokeUserSessions(user.id);
        await transaction.createAudit({
            actorUserId: null,
            action: "iam.password_initialized",
            targetType: "user",
            targetId: user.id,
            metadata: { phone: maskPhone(phone), generated: !suppliedPassword }
        });
    });

    console.log(JSON.stringify({
        userId: user.id,
        displayName: user.display_name,
        phone,
        password,
        generated: !suppliedPassword
    }, null, 2));
}

main()
    .catch((error) => {
        console.error("Password setup failed:", error.message);
        process.exitCode = 1;
    })
    .finally(async () => {
        await pool.end();
    });
