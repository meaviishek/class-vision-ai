"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.generateImageKitVariants = exports.optimizeImageToWebP = void 0;
const sharp_1 = __importDefault(require("sharp"));
/**
 * Optimizes an image buffer by:
 * 1. Auto-orienting EXIF rotation
 * 2. Constraining excessive dimensions (e.g. max 2400px for fine jewellery display)
 * 3. Converting to ultra-efficient WebP format with high chroma fidelity
 */
const optimizeImageToWebP = async (inputBuffer, options = {}) => {
    const originalSize = inputBuffer.length;
    const { maxWidth = 2400, maxHeight = 2400, quality = 85, lossless = false, } = options;
    const sharpInstance = (0, sharp_1.default)(inputBuffer);
    const metadata = await sharpInstance.metadata();
    const originalFormat = metadata.format || "unknown";
    // Build transformation pipeline
    let pipeline = (0, sharp_1.default)(inputBuffer).rotate(); // auto-rotate based on EXIF
    // Resize if image exceeds maximum display boundaries (without upscaling smaller images)
    if ((metadata.width && metadata.width > maxWidth) ||
        (metadata.height && metadata.height > maxHeight)) {
        pipeline = pipeline.resize({
            width: maxWidth,
            height: maxHeight,
            fit: "inside",
            withoutEnlargement: true,
        });
    }
    // Convert to high-performance WebP
    const optimizedBuffer = await pipeline
        .webp({
        quality,
        effort: 4,
        lossless,
        smartSubsample: true,
    })
        .toBuffer();
    // Get resulting dimensions
    const finalMeta = await (0, sharp_1.default)(optimizedBuffer).metadata();
    const optimizedSize = optimizedBuffer.length;
    const savingsBytes = Math.max(0, originalSize - optimizedSize);
    const savingsPercent = originalSize > 0
        ? `${Math.round((savingsBytes / originalSize) * 100)}%`
        : "0%";
    return {
        buffer: optimizedBuffer,
        originalSize,
        optimizedSize,
        savingsBytes,
        savingsPercent,
        width: finalMeta.width || metadata.width || 0,
        height: finalMeta.height || metadata.height || 0,
        format: "webp",
        mimeType: "image/webp",
        originalFormat,
    };
};
exports.optimizeImageToWebP = optimizeImageToWebP;
/**
 * Generates responsive image variant URLs using ImageKit real-time transformation query parameters
 */
const generateImageKitVariants = (baseCdnUrl) => {
    const cleanUrl = baseCdnUrl.split("?")[0];
    return {
        original: cleanUrl,
        thumbnail: `${cleanUrl}?tr=w-300,h-300,c-at_max,q-80`,
        catalog: `${cleanUrl}?tr=w-600,h-600,c-at_max,q-85`,
        detail: `${cleanUrl}?tr=w-1200,h-1200,c-at_max,q-90`,
        zoom: `${cleanUrl}?tr=w-2000,h-2000,c-at_max,q-95`,
    };
};
exports.generateImageKitVariants = generateImageKitVariants;
