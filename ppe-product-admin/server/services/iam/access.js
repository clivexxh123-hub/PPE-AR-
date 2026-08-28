const { httpError } = require("./security");

function isSuperAdministrator(user) {
    return Boolean(user?.roles?.some((role) => role.id === "admin"));
}

function hasPermission(user, permission) {
    return isSuperAdministrator(user) || Boolean(user?.permissions?.includes(permission));
}

function requirePermission(permission) {
    return (request, response, next) => {
        if (!hasPermission(request.auth?.user, permission)) {
            return next(httpError(403, "没有执行该操作的权限", "IAM_403_PERMISSION_DENIED"));
        }
        return next();
    };
}

module.exports = { hasPermission, isSuperAdministrator, requirePermission };
