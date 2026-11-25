"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const webhookController_1 = require("../controllers/webhookController");
const router = (0, express_1.Router)();
// Webhook endpoints
router.get("/razorpay", webhookController_1.getRazorpayWebhookInfo);
router.post("/razorpay", webhookController_1.handleRazorpayWebhook);
// Payment confirmation check for frontend
router.get("/payment-status/:idOrNumber", webhookController_1.checkPaymentStatus);
exports.default = router;
