import { Router } from "express";
import {
  handleRazorpayWebhook,
  getRazorpayWebhookInfo,
  checkPaymentStatus,
} from "../controllers/webhookController";

const router = Router();

// Webhook endpoints
router.get("/razorpay", getRazorpayWebhookInfo);
router.post("/razorpay", handleRazorpayWebhook);

// Payment confirmation check for frontend
router.get("/payment-status/:idOrNumber", checkPaymentStatus);

export default router;
