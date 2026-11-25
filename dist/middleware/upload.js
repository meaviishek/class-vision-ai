"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.uploadMultipleFiles = exports.uploadMultipleImages = exports.uploadSingleFile = exports.uploadSingleImage = exports.uploadMiddleware = void 0;
const multer_1 = __importDefault(require("multer"));
// Store uploaded files in memory as Buffers for in-memory sharp optimization
const storage = multer_1.default.memoryStorage();
const allowedMimeTypes = [
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/tiff",
    "image/svg+xml",
    "image/avif",
    "image/heic",
    "image/heif",
];
const fileFilter = (req, file, callback) => {
    if (allowedMimeTypes.includes(file.mimetype.toLowerCase())) {
        callback(null, true);
    }
    else {
        callback(new Error(`Invalid file type: ${file.mimetype}. Only image files (JPEG, PNG, WEBP, GIF, TIFF, SVG, AVIF) are supported.`));
    }
};
exports.uploadMiddleware = (0, multer_1.default)({
    storage,
    fileFilter,
    limits: {
        fileSize: 25 * 1024 * 1024, // 25 MB max
    },
});
exports.uploadSingleImage = exports.uploadMiddleware.single("image");
exports.uploadSingleFile = exports.uploadMiddleware.single("file");
exports.uploadMultipleImages = exports.uploadMiddleware.array("images", 10);
exports.uploadMultipleFiles = exports.uploadMiddleware.array("files", 10);
exports.default = exports.uploadMiddleware;
