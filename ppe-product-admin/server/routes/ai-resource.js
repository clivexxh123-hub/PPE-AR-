const fs = require("fs");
const path = require("path");
const express = require("express");
const multer = require("multer");
const controller = require("../controllers/ai-resource.controller");
const { requirePermission } = require("../services/iam/access");

const router = express.Router();

function createImageUpload(folderName) {
    const uploadDirectory = path.join(
        __dirname,
        "..",
        "uploads",
        folderName
    );

    fs.mkdirSync(uploadDirectory, {
        recursive: true
    });

    return multer({
        storage: multer.diskStorage({
            destination(req, file, callback) {
                callback(null, uploadDirectory);
            },
            filename(req, file, callback) {
                const extension = path.extname(file.originalname).toLowerCase();
                const suffix = Math.round(Math.random() * 1e9);
                callback(null, `${Date.now()}-${suffix}${extension}`);
            }
        }),
        limits: {
            fileSize: 20 * 1024 * 1024
        },
        fileFilter(req, file, callback) {
            if (!String(file.mimetype || "").startsWith("image/")) {
                return callback(new Error("仅支持图片文件"));
            }

            return callback(null, true);
        }
    });
}

const modelUpload = createImageUpload("models");
const sceneUpload = createImageUpload("scenes");

router.get("/models", controller.getModels);
router.post("/models", requirePermission("catalog.manage"), modelUpload.single("image"), controller.createModel);

router.get("/scenes", controller.getScenes);
router.post("/scenes", requirePermission("catalog.manage"), sceneUpload.single("image"), controller.createScene);

module.exports = router;
