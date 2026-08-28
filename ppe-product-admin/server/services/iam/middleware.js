const { httpError, parseCookies } = require("./security");
const { hasPermission } = require("./access");

function bearerToken(request) {
    const authorization = String(request.headers.authorization || "");
    const match = authorization.match(/^Bearer\s+([^\s]+)$/i);
    return match ? match[1] : null;
}

function sessionToken(request) {
    return parseCookies(request.headers.cookie).ppe_session || bearerToken(request);
}

function createIamMiddleware(service, config) {
    async function authenticate(request, response, next) {
        try {
            if (!config.authEnabled) {
                request.auth = {
                    developmentBypass: true,
                    session: { id: "development-bypass", csrfTokenHash: null },
                    user: {
                        id: "development-bypass",
                        displayName: "开发模式",
                        phone: "***",
                        status: "active",
                        roles: [{ id: "admin", name: "超级管理员（开发模式）" }],
                        permissions: [
                            "system.manage",
                            "catalog.manage",
                            "generation.use",
                            "records.read_all",
                            "records.write_own",
                            "dashboard.view_admin"
                        ],
                        orgUnit: null
                    }
                };
                response.setHeader("x-iam-development-bypass", "true");
                return next();
            }
            request.auth = await service.authenticate(sessionToken(request));
            return next();
        } catch (error) {
            return next(error);
        }
    }

    function requireCsrf(request, response, next) {
        if (["GET", "HEAD", "OPTIONS"].includes(request.method) || request.auth?.developmentBypass) {
            return next();
        }
        try {
            service.verifyCsrf(request.auth, request.headers["x-csrf-token"]);
            return next();
        } catch (error) {
            return next(error);
        }
    }

    function requirePermission(permission) {
        return (request, response, next) => {
            if (!hasPermission(request.auth?.user, permission)) {
                return next(httpError(403, "没有执行该操作的权限", "IAM_403_PERMISSION_DENIED"));
            }
            return next();
        };
    }

    function requireOwnerOrPermission(ownerId, permission = "system.manage") {
        return (request, response, next) => {
            const resolvedOwnerId = typeof ownerId === "function" ? ownerId(request) : ownerId;
            if (
                request.auth?.user?.id === resolvedOwnerId ||
                hasPermission(request.auth?.user, permission)
            ) {
                return next();
            }
            return next(httpError(403, "只能修改或删除本人数据", "IAM_403_OWNERSHIP_REQUIRED"));
        };
    }

    return { authenticate, requireCsrf, requireOwnerOrPermission, requirePermission };
}

module.exports = { bearerToken, createIamMiddleware, sessionToken };
