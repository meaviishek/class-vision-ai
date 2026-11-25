"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const uploadController_1 = require("../controllers/uploadController");
const upload_1 = require("../middleware/upload");
const router = (0, express_1.Router)();
// Accept 'image' or 'file' for single upload
const singleImageUpload = upload_1.uploadMiddleware.fields([
    { name: "image", maxCount: 1 },
    { name: "file", maxCount: 1 },
]);
const normalizeSingleFile = (req, _res, next) => {
    if (!req.file && req.files) {
        req.file = req.files.image?.[0] || req.files.file?.[0];
    }
    next();
};
// Direct root / endpoint (POST /api/upload)
router.post("/", singleImageUpload, normalizeSingleFile, uploadController_1.uploadImage);
// 1. Single image upload with WebP conversion (POST /api/upload/image)
router.post("/image", singleImageUpload, normalizeSingleFile, uploadController_1.uploadImage);
// Fallback alias for field name "file" (POST /api/upload/file)
router.post("/file", singleImageUpload, normalizeSingleFile, uploadController_1.uploadImage);
// 2. Multiple images upload with WebP conversion
router.post("/images", upload_1.uploadMiddleware.array("images", 10), uploadController_1.uploadMultiple);
// 3. Remote URL upload with WebP conversion
router.post("/url", uploadController_1.uploadFromUrl);
// 4. Delete image by fileId
router.delete("/:fileId", uploadController_1.deleteImage);
// 5. Client-side authentication parameters
router.get("/auth", uploadController_1.getAuthParameters);
exports.default = router;
