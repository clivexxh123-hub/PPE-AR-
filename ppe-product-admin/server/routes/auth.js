const express = require("express");

const { requestIpHash } = require("../services/iam/security");

function cookieOptions(config, httpOnly) {
    return {
        httpOnly,
        secure: config.secureCookies,
        sameSite: "strict",
        path: "/",
        maxAge: config.sessionHours * 60 * 60 * 1000
    };
}

function clearAuthCookies(response, config) {
    const base = { secure: config.secureCookies, sameSite: "strict", path: "/" };
    response.clearCookie("ppe_session", { ...base, httpOnly: true });
    response.clearCookie("ppe_csrf", { ...base, httpOnly: false });
}

function createAuthRouter({ service, middleware, config }) {
    const router = express.Router();

    router.post("/login", async (request, response) => {
        const result = await service.login({
            phone: request.body?.phone,
            password: request.body?.password,
            ipHash: requestIpHash(service.sessionSecret(), request),
            userAgent: request.headers["user-agent"]
        });
        response.cookie("ppe_session", result.sessionToken, cookieOptions(config, true));
        response.cookie("ppe_csrf", result.csrfToken, cookieOptions(config, false));
        response.json({
            success: true,
            data: { user: result.user, expiresAt: result.expiresAt }
        });
    });

    router.get("/me", middleware.authenticate, (request, response) => {
        response.json({ success: true, data: { user: request.auth.user } });
    });

    router.post(
        "/logout",
        middleware.authenticate,
        middleware.requireCsrf,
        async (request, response) => {
            if (!request.auth.developmentBypass) {
                await service.logout(
                    request.auth,
                    requestIpHash(service.sessionSecret(), request)
                );
            }
            clearAuthCookies(response, config);
            response.json({ success: true });
        }
    );

    return router;
}

module.exports = { clearAuthCookies, createAuthRouter };
