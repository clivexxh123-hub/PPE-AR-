const express = require("express");

function createIamRouter({ service, middleware }) {
    const router = express.Router();
    const requireSystemManage = middleware.requirePermission("system.manage");

    router.get("/org-units", requireSystemManage, async (request, response) => {
        response.json({ success: true, data: await service.listOrgUnits() });
    });

    router.get("/roles", requireSystemManage, async (request, response) => {
        response.json({ success: true, data: await service.listRoles() });
    });

    router.get("/users", requireSystemManage, async (request, response) => {
        response.json({ success: true, data: await service.listUsers() });
    });

    router.post("/users", requireSystemManage, async (request, response) => {
        const user = await service.createUser(request.body || {}, request.auth);
        response.status(201).json({ success: true, data: user });
    });

    router.patch("/users/:userId", requireSystemManage, async (request, response) => {
        const user = await service.updateUser(request.params.userId, request.body || {}, request.auth);
        response.json({ success: true, data: user });
    });

    router.get("/audit", requireSystemManage, async (request, response) => {
        response.json({
            success: true,
            data: await service.listAudit(request.query.limit)
        });
    });

    return router;
}

module.exports = { createIamRouter };
