require("dotenv").config();

const path = require("path");
const express = require("express");
const cors = require("cors");

const productRoutes = require("./routes/product");

const app = express();

app.use(cors());

app.use(express.json({
    limit: "10mb"
}));

app.use(express.urlencoded({
    extended: true,
    limit: "10mb"
}));


app.use(
    "/uploads",
    express.static(
        path.join(__dirname, "uploads")
    )
);


app.use(
    "/api",
    productRoutes
);


app.get("/", (req, res) => {
    res.json({
        success: true,
        name: "PPE Product Admin API",
        port: Number(process.env.PORT || 9530)
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

    res.status(500).json({
        success: false,
        message: error.message || "服务器内部错误"
    });
});


const PORT = Number(process.env.PORT || 9530);

app.listen(PORT, "0.0.0.0", () => {
    console.log(`PPE Product Admin API running: ${PORT}`);
});
