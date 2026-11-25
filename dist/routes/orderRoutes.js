"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const orderController_1 = require("../controllers/orderController");
const webhookController_1 = require("../controllers/webhookController");
const auth_1 = require("../middleware/auth");
const router = (0, express_1.Router)();
// Payment & Checkout (supports guest checkout with optional auth, or authenticated checkout)
router.post("/razorpay/create", auth_1.optionalAuth, orderController_1.createRazorpayOrder);
router.post("/razorpay/verify", auth_1.optionalAuth, orderController_1.verifyPaymentAndPlaceOrder);
router.get("/payment-status/:idOrNumber", auth_1.optionalAuth, webhookController_1.checkPaymentStatus);
// User orders
router.get("/my-orders", auth_1.protect, orderController_1.getMyOrders);
router.get("/:idOrNumber", auth_1.optionalAuth, orderController_1.getOrderById);
exports.default = router;
