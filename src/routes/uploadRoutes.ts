import { Router } from "express";
import {
  uploadImage,
  uploadMultiple,
  uploadFromUrl,
  deleteImage,
  getAuthParameters,
} from "../controllers/uploadController";
import { uploadMiddleware } from "../middleware/upload";

const router = Router();

// Accept 'image' or 'file' for single upload
const singleImageUpload = uploadMiddleware.fields([
  { name: "image", maxCount: 1 },
  { name: "file", maxCount: 1 },
]);

const normalizeSingleFile = (req: any, _res: any, next: any) => {
  if (!req.file && req.files) {
    req.file = req.files.image?.[0] || req.files.file?.[0];
  }
  next();
};

// Direct root / endpoint (POST /api/upload)
router.post(
  "/",
  singleImageUpload,
  normalizeSingleFile,
  uploadImage
);

// 1. Single image upload with WebP conversion (POST /api/upload/image)
router.post(
  "/image",
  singleImageUpload,
  normalizeSingleFile,
  uploadImage
);

// Fallback alias for field name "file" (POST /api/upload/file)
router.post(
  "/file",
  singleImageUpload,
  normalizeSingleFile,
  uploadImage
);

// 2. Multiple images upload with WebP conversion
router.post(
  "/images",
  uploadMiddleware.array("images", 10),
  uploadMultiple
);

// 3. Remote URL upload with WebP conversion
router.post("/url", uploadFromUrl);

// 4. Delete image by fileId
router.delete("/:fileId", deleteImage);

// 5. Client-side authentication parameters
router.get("/auth", getAuthParameters);

export default router;
