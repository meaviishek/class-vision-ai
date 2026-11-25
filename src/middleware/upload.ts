import multer, { FileFilterCallback } from "multer";
import { Request } from "express";

// Store uploaded files in memory as Buffers for in-memory sharp optimization
const storage = multer.memoryStorage();

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

const fileFilter = (
  req: Request,
  file: Express.Multer.File,
  callback: FileFilterCallback
) => {
  if (allowedMimeTypes.includes(file.mimetype.toLowerCase())) {
    callback(null, true);
  } else {
    callback(
      new Error(
        `Invalid file type: ${file.mimetype}. Only image files (JPEG, PNG, WEBP, GIF, TIFF, SVG, AVIF) are supported.`
      )
    );
  }
};

export const uploadMiddleware = multer({
  storage,
  fileFilter,
  limits: {
    fileSize: 25 * 1024 * 1024, // 25 MB max
  },
});

export const uploadSingleImage = uploadMiddleware.single("image");
export const uploadSingleFile = uploadMiddleware.single("file");
export const uploadMultipleImages = uploadMiddleware.array("images", 10);
export const uploadMultipleFiles = uploadMiddleware.array("files", 10);

export default uploadMiddleware;
