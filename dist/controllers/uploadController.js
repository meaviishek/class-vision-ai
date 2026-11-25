"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getAuthParameters = exports.deleteImage = exports.uploadFromUrl = exports.uploadMultiple = exports.uploadImage = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const imagekit_1 = require("../config/imagekit");
const imageOptimizationService_1 = require("../services/imageOptimizationService");
const ensureLocalUploadsDir = () => {
    const dir = path_1.default.join(process.cwd(), "public", "uploads");
    if (!fs_1.default.existsSync(dir)) {
        fs_1.default.mkdirSync(dir, { recursive: true });
    }
    return dir;
};
/**
 * Controller to upload a single image, optimize it to WebP, and store in ImageKit with local fallback
 */
const uploadImage = async (req, res) => {
    try {
        const file = req.file;
        if (!file) {
            res.status(400).json({
                success: false,
                message: "No image file provided in request. Please attach an image field.",
            });
            return;
        }
        // Optional parameters from request body
        const folder = (req.body.folder || "/zhaevaah/products").trim();
        const quality = req.body.quality ? Number(req.body.quality) : 85;
        const maxWidth = req.body.maxWidth ? Number(req.body.maxWidth) : 2400;
        const maxHeight = req.body.maxHeight ? Number(req.body.maxHeight) : 2400;
        // 1. Optimize image into WebP format with sharp
        const optimized = await (0, imageOptimizationService_1.optimizeImageToWebP)(file.buffer, {
            quality,
            maxWidth,
            maxHeight,
        });
        // 2. Generate clean WebP filename
        const originalBaseName = file.originalname
            ? file.originalname.replace(/\.[^/.]+$/, "").replace(/[^a-zA-Z0-9_-]/g, "_")
            : "jewellery_photo";
        const uniqueSuffix = `${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
        const webpFileName = `${originalBaseName}_${uniqueSuffix}.webp`;
        let finalUrl = "";
        let fileId = `local_${uniqueSuffix}`;
        let variants = null;
        // Always persist to local uploads directory as guaranteed reliable fallback
        const uploadsDir = ensureLocalUploadsDir();
        const localFilePath = path_1.default.join(uploadsDir, webpFileName);
        fs_1.default.writeFileSync(localFilePath, optimized.buffer);
        const protocol = req.protocol || "http";
        const host = req.get("host") || "localhost:5000";
        const localUrl = `${protocol}://${host}/uploads/${webpFileName}`;
        finalUrl = localUrl;
        // 3. Attempt upload of optimized WebP buffer to ImageKit
        try {
            const uploadResult = await imagekit_1.imagekit.upload({
                file: optimized.buffer,
                fileName: webpFileName,
                folder,
                useUniqueFileName: true,
                tags: ["zhaevaah", "fine-jewellery", "webp", "optimized"],
            });
            if (uploadResult?.url) {
                finalUrl = uploadResult.url;
                fileId = uploadResult.fileId;
                variants = (0, imageOptimizationService_1.generateImageKitVariants)(uploadResult.url);
            }
        }
        catch (ikErr) {
            console.warn("[ImageKit Notice] Cloud upload skipped or failed, using local WebP URL:", ikErr.message || ikErr);
        }
        res.status(200).json({
            success: true,
            message: "Image successfully optimized to WebP and saved.",
            url: finalUrl,
            data: {
                fileId,
                name: webpFileName,
                url: finalUrl,
                thumbnailUrl: finalUrl,
                filePath: `/uploads/${webpFileName}`,
                width: optimized.width,
                height: optimized.height,
                format: "webp",
                originalFormat: optimized.originalFormat,
                originalSize: optimized.originalSize,
                optimizedSize: optimized.optimizedSize,
                savingsBytes: optimized.savingsBytes,
                savingsPercent: optimized.savingsPercent,
                variants: variants || {
                    original: finalUrl,
                    thumbnail: finalUrl,
                    medium: finalUrl,
                    large: finalUrl,
                },
            },
        });
    }
    catch (error) {
        console.error("[ImageKit Upload Error]:", error);
        res.status(500).json({
            success: false,
            message: error.message || "Failed to process and upload image to ImageKit.",
        });
    }
};
exports.uploadImage = uploadImage;
/**
 * Controller to upload multiple images, optimize each into WebP, and store in ImageKit with local fallback
 */
const uploadMultiple = async (req, res) => {
    try {
        const files = req.files;
        if (!files || !files.length) {
            res.status(400).json({
                success: false,
                message: "No image files provided in request. Please attach images array.",
            });
            return;
        }
        const folder = (req.body.folder || "/zhaevaah/products").trim();
        const quality = req.body.quality ? Number(req.body.quality) : 85;
        const uploadsDir = ensureLocalUploadsDir();
        const protocol = req.protocol || "http";
        const host = req.get("host") || "localhost:5000";
        // Process all images concurrently
        const uploadPromises = files.map(async (file) => {
            const optimized = await (0, imageOptimizationService_1.optimizeImageToWebP)(file.buffer, { quality });
            const originalBaseName = file.originalname
                ? file.originalname.replace(/\.[^/.]+$/, "").replace(/[^a-zA-Z0-9_-]/g, "_")
                : "jewellery_photo";
            const uniqueSuffix = `${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
            const webpFileName = `${originalBaseName}_${uniqueSuffix}.webp`;
            // Save local copy
            const localFilePath = path_1.default.join(uploadsDir, webpFileName);
            fs_1.default.writeFileSync(localFilePath, optimized.buffer);
            let itemUrl = `${protocol}://${host}/uploads/${webpFileName}`;
            let itemFileId = `local_${uniqueSuffix}`;
            try {
                const uploadResult = await imagekit_1.imagekit.upload({
                    file: optimized.buffer,
                    fileName: webpFileName,
                    folder,
                    useUniqueFileName: true,
                    tags: ["zhaevaah", "fine-jewellery", "webp", "gallery"],
                });
                if (uploadResult?.url) {
                    itemUrl = uploadResult.url;
                    itemFileId = uploadResult.fileId;
                }
            }
            catch (err) {
                console.warn("[ImageKit Multi Upload Notice] Using local WebP URL:", err.message || err);
            }
            return {
                fileId: itemFileId,
                name: webpFileName,
                url: itemUrl,
                thumbnailUrl: itemUrl,
                width: optimized.width,
                height: optimized.height,
                format: "webp",
                originalSize: optimized.originalSize,
                optimizedSize: optimized.optimizedSize,
                savingsPercent: optimized.savingsPercent,
                variants: (0, imageOptimizationService_1.generateImageKitVariants)(itemUrl),
            };
        });
        const results = await Promise.all(uploadPromises);
        res.status(200).json({
            success: true,
            count: results.length,
            message: `Successfully optimized and uploaded ${results.length} images in WebP format.`,
            urls: results.map((r) => r.url),
            files: results,
        });
    }
    catch (error) {
        console.error("[ImageKit Bulk Upload Error]:", error);
        res.status(500).json({
            success: false,
            message: error.message || "Failed to process and upload images to ImageKit.",
        });
    }
};
exports.uploadMultiple = uploadMultiple;
/**
 * Upload remote image URL to ImageKit after optimizing to WebP
 */
const uploadFromUrl = async (req, res) => {
    try {
        const { imageUrl, fileName: customName, folder: reqFolder } = req.body;
        if (!imageUrl) {
            res.status(400).json({
                success: false,
                message: "Remote imageUrl is required in request body.",
            });
            return;
        }
        const folder = (reqFolder || "/zhaevaah/remote").trim();
        // Fetch the remote image
        const response = await fetch(imageUrl);
        if (!response.ok) {
            res.status(400).json({
                success: false,
                message: `Failed to fetch image from remote URL: ${imageUrl}`,
            });
            return;
        }
        const arrayBuffer = await response.arrayBuffer();
        const inputBuffer = Buffer.from(arrayBuffer);
        // Optimize into WebP
        const optimized = await (0, imageOptimizationService_1.optimizeImageToWebP)(inputBuffer);
        const fileName = customName ? `${customName}.webp` : `remote_${Date.now()}.webp`;
        const uploadResult = await imagekit_1.imagekit.upload({
            file: optimized.buffer,
            fileName,
            folder,
            useUniqueFileName: true,
            tags: ["zhaevaah", "remote", "webp"],
        });
        res.status(200).json({
            success: true,
            message: "Remote image converted to WebP and uploaded to ImageKit.",
            data: {
                fileId: uploadResult.fileId,
                url: uploadResult.url,
                width: optimized.width,
                height: optimized.height,
                format: "webp",
                originalSize: optimized.originalSize,
                optimizedSize: optimized.optimizedSize,
                savingsPercent: optimized.savingsPercent,
                variants: (0, imageOptimizationService_1.generateImageKitVariants)(uploadResult.url),
            },
        });
    }
    catch (error) {
        console.error("[ImageKit URL Upload Error]:", error);
        res.status(500).json({
            success: false,
            message: error.message || "Failed to process remote image.",
        });
    }
};
exports.uploadFromUrl = uploadFromUrl;
/**
 * Delete image from ImageKit by fileId
 */
const deleteImage = async (req, res) => {
    try {
        const { fileId } = req.params;
        if (!fileId) {
            res.status(400).json({
                success: false,
                message: "fileId parameter is required to delete an image.",
            });
            return;
        }
        await imagekit_1.imagekit.deleteFile(fileId);
        res.status(200).json({
            success: true,
            message: `Image with ID ${fileId} deleted from ImageKit successfully.`,
        });
    }
    catch (error) {
        console.error("[ImageKit Delete Error]:", error);
        res.status(500).json({
            success: false,
            message: error.message || "Failed to delete image from ImageKit.",
        });
    }
};
exports.deleteImage = deleteImage;
/**
 * Get ImageKit authentication parameters for client-side direct uploads
 */
const getAuthParameters = (req, res) => {
    try {
        const authenticationParameters = imagekit_1.imagekit.getAuthenticationParameters();
        res.status(200).json({
            success: true,
            ...authenticationParameters,
            publicKey: process.env.IMAGEKIT_PUBLIC_KEY,
            urlEndpoint: process.env.IMAGEKIT_URL_ENDPOINT,
        });
    }
    catch (error) {
        res.status(500).json({
            success: false,
            message: error.message || "Failed to generate ImageKit authentication parameters.",
        });
    }
};
exports.getAuthParameters = getAuthParameters;
