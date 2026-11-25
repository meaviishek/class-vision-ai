import { Router } from "express";
import {
  getProducts,
  getMensProducts,
  getWomensProducts,
  getProductByIdOrSlug,
  getRelatedProducts,
  getCategories,
} from "../controllers/productController";

const router = Router();

router.get("/", getProducts);
router.get("/men", getMensProducts);
router.get("/women", getWomensProducts);
router.get("/categories", getCategories);
router.get("/:idOrSlug", getProductByIdOrSlug);
router.get("/:idOrSlug/related", getRelatedProducts);

export default router;

