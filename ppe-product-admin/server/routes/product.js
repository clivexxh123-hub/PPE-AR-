const express = require("express");
const multer = require("multer");
const path = require("path");
const fs = require("fs");

const controller = require("../controllers/product.controller");
const { requirePermission } = require("../services/iam/access");

const router = express.Router();

const uploadDirectory = path.join(
    __dirname,
    "..",
    "uploads",
    "products"
);

fs.mkdirSync(uploadDirectory, {
    recursive: true
});


const storage = multer.diskStorage({
    destination(req, file, callback) {
        callback(null, uploadDirectory);
    },

    filename(req, file, callback) {
        const extension = path.extname(file.originalname || "");
        const random = Math.round(Math.random() * 1e9);

        callback(
            null,
            `${Date.now()}-${random}${extension}`
        );
    }
});


const upload = multer({
    storage,

    limits: {
        fileSize: 20 * 1024 * 1024
    },

    fileFilter(req, file, callback) {
        const allowedTypes = new Set([
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/gif",
            "application/pdf"
        ]);

        if (!allowedTypes.has(file.mimetype)) {
            return callback(
                new Error("仅支持 JPG、PNG、WEBP、GIF、PDF 文件")
            );
        }

        callback(null, true);
    }
});


router.get(
    "/categories",
    controller.getCategories
);


router.get(
    "/products",
    controller.getProducts
);

router.get(
"/ai/products",
controller.getAIProducts
);


router.get(
    "/products/:id",
    controller.getProductDetail
);


router.put(
    "/products/:id",
    requirePermission("catalog.manage"),
    controller.updateProduct
);


router.post(
    "/products/:id/files",
    requirePermission("catalog.manage"),
    upload.single("file"),
    controller.uploadProductFile
);


router.delete(
    "/files/:id",
    requirePermission("catalog.manage"),
    controller.deleteProductFile
);


module.exports = router;
