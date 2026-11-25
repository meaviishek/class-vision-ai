import { Router } from "express";
import {
  createRazorpayOrder,
  verifyPaymentAndPlaceOrder,
  getMyOrders,
  getOrderById,
} from "../controllers/orderController";
import { checkPaymentStatus } from "../controllers/webhookController";
import { protect, optionalAuth } from "../middleware/auth";

const router = Router();

// Payment & Checkout (supports guest checkout with optional auth, or authenticated checkout)
router.post("/razorpay/create", optionalAuth, createRazorpayOrder);
router.post("/razorpay/verify", optionalAuth, verifyPaymentAndPlaceOrder);
router.get("/payment-status/:idOrNumber", optionalAuth, checkPaymentStatus);

// User orders
router.get("/my-orders", protect, getMyOrders);
router.get("/:idOrNumber", optionalAuth, getOrderById);

export default router;

