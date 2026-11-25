import sharp from "sharp";

export interface OptimizedImageResult {
  buffer: Buffer;
  originalSize: number;
  optimizedSize: number;
  savingsBytes: number;
  savingsPercent: string;
  width: number;
  height: number;
  format: "webp";
  mimeType: "image/webp";
  originalFormat: string;
}

export interface OptimizationOptions {
  maxWidth?: number;
  maxHeight?: number;
  quality?: number;
  lossless?: boolean;
}

/**
 * Optimizes an image buffer by:
 * 1. Auto-orienting EXIF rotation
 * 2. Constraining excessive dimensions (e.g. max 2400px for fine jewellery display)
 * 3. Converting to ultra-efficient WebP format with high chroma fidelity
 */
export const optimizeImageToWebP = async (
  inputBuffer: Buffer,
  options: OptimizationOptions = {}
): Promise<OptimizedImageResult> => {
  const originalSize = inputBuffer.length;
  const {
    maxWidth = 2400,
    maxHeight = 2400,
    quality = 85,
    lossless = false,
  } = options;

  const sharpInstance = sharp(inputBuffer);
  const metadata = await sharpInstance.metadata();
  const originalFormat = metadata.format || "unknown";

  // Build transformation pipeline
  let pipeline = sharp(inputBuffer).rotate(); // auto-rotate based on EXIF

  // Resize if image exceeds maximum display boundaries (without upscaling smaller images)
  if (
    (metadata.width && metadata.width > maxWidth) ||
    (metadata.height && metadata.height > maxHeight)
  ) {
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
  const finalMeta = await sharp(optimizedBuffer).metadata();
  const optimizedSize = optimizedBuffer.length;
  const savingsBytes = Math.max(0, originalSize - optimizedSize);
  const savingsPercent =
    originalSize > 0
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

/**
 * Generates responsive image variant URLs using ImageKit real-time transformation query parameters
 */
export const generateImageKitVariants = (baseCdnUrl: string) => {
  const cleanUrl = baseCdnUrl.split("?")[0];
  return {
    original: cleanUrl,
    thumbnail: `${cleanUrl}?tr=w-300,h-300,c-at_max,q-80`,
    catalog: `${cleanUrl}?tr=w-600,h-600,c-at_max,q-85`,
    detail: `${cleanUrl}?tr=w-1200,h-1200,c-at_max,q-90`,
    zoom: `${cleanUrl}?tr=w-2000,h-2000,c-at_max,q-95`,
  };
};
