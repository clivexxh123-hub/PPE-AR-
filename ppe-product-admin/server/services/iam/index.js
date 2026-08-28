const pool = require("../../db");
const { createAuthRouter } = require("../../routes/auth");
const { createIamRouter } = require("../../routes/iam");
const { loadIamConfig } = require("./config");
const { createIamMiddleware } = require("./middleware");
const { IamRepository } = require("./repository");
const { IamService } = require("./service");

function createIamModule({ environment = process.env, logger = console } = {}) {
    const config = loadIamConfig(environment);
    const repository = new IamRepository(pool);
    const service = new IamService({ repository, config });
    const middleware = createIamMiddleware(service, config);
    return {
        config,
        service,
        middleware,
        authRouter: createAuthRouter({ service, middleware, config }),
        iamRouter: createIamRouter({ service, middleware })
    };
}

module.exports = { createIamModule };
