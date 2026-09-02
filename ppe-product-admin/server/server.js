require("dotenv").config();

const path = require("path");
const express = require("express");
const cors = require("cors");
const { createIamModule } = require("./services/iam");

const productRoutes = require("./routes/product");

const logoRoutes=require("./routes/logo");
const aiResourceRoutes = require("./routes/ai-resource");
const aiGenerationRoutes = require("./routes/ai-generation");
const customerRoutes = require("./routes/customers");
const caseTemplateRoutes = require("./routes/case-templates");
const dashboardRoutes = require("./routes/dashboard");
const { publicErrorPayload } = require("./services/public-error");

const app = express();
const iam = createIamModule();

if (iam.config.nodeEnv === "production") {
    app.set("trust proxy", 1);
}

app.use(cors({
    credentials: true,
    origin(origin, callback) {
        if (!origin || iam.config.allowedOrigins.includes(origin)) {
            return callback(null, true);
        }
        const error = new Error("该 Web 来源不允许访问业务 API");
        error.statusCode = 403;
        error.errorCode = "IAM_403_ORIGIN_DENIED";
        return callback(error);
    }
}));

app.use(express.json({
    limit: "10mb"
}));

app.use(express.urlencoded({
    extended: true,
    limit: "10mb"
}));


app.use("/api/auth", iam.authRouter);

app.use(
    "/uploads",
    iam.middleware.authenticate,
    express.static(path.join(__dirname, "uploads"))
);

app.use("/api", iam.middleware.authenticate, iam.middleware.requireCsrf);
app.use("/api/iam", iam.iamRouter);


app.use(
    "/api",
    productRoutes
);

app.use(
"/api/logos",
logoRoutes
);

app.use(
    "/api",
    aiResourceRoutes
);

app.use(
    "/api/ai",
    aiGenerationRoutes
);

app.use(
    "/api/customers",
    customerRoutes
);

app.use(
    "/api/case-templates",
    caseTemplateRoutes
);

app.use(
    "/api/dashboard",
    dashboardRoutes
);

app.get("/", (req, res) => {
    res.json({
        success: true,
        name: "PPE Product Admin API",
        port: Number(process.env.PORT || 9530),
        auth: iam.config.authEnabled ? "enabled" : "development-bypass"
    });
});


app.use((error, req, res, next) => {
    console.error("global error:", error);

    if (error.code === "LIMIT_FILE_SIZE") {
        return res.status(400).json({
            success: false,
            message: "上传文件不能超过20MB"
        });
    }

    const publicError = publicErrorPayload(error);
    if (publicError.retryAfterSeconds) {
        res.set("Retry-After", String(publicError.retryAfterSeconds));
    }
    res.status(publicError.statusCode).json({
        success: false,
        errorCode: publicError.errorCode,
        message: publicError.message,
        ...(publicError.retryAfterSeconds ? { retryAfterSeconds: publicError.retryAfterSeconds } : {}),
        ...(publicError.retryAt ? { retryAt: publicError.retryAt } : {})
    });
});


const PORT = Number(process.env.PORT || 9530);
const HOST = String(process.env.HOST || "0.0.0.0").trim() || "0.0.0.0";

app.listen(PORT, HOST, () => {
    console.log(`PPE Product Admin API running: http://${HOST}:${PORT}`);
});
