"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.checkPaymentStatus = exports.handleRazorpayWebhook = exports.getRazorpayWebhookInfo = exports.webhookConfirmedPayments = void 0;
const crypto_1 = __importDefault(require("crypto"));
const prisma_1 = __importDefault(require("../config/prisma"));
const razorpay_1 = require("../config/razorpay");
const mailer_1 = require("../config/mailer");
exports.webhookConfirmedPayments = new Map();
/**
 * GET /api/webhook/razorpay
 * Returns webhook status, exact URL link, and configuration guide for Razorpay Dashboard
 */
const getRazorpayWebhookInfo = (req, res) => {
    const host = req.get("host") || "localhost:5000";
    const protocol = req.protocol === "https" || req.headers["x-forwarded-proto"] === "https" ? "https" : "http";
    const baseUrl = `${protocol}://${host}`;
    const webhookUrl = `${baseUrl}/api/webhook/razorpay`;
    res.status(200).json({
        success: true,
        service: "ZHAEVAAH Luxury Atelier — Razorpay Webhook Gateway",
        status: "active",
        webhookUrl,
        localUrl: `http://localhost:${process.env.PORT || 5000}/api/webhook/razorpay`,
        secretConfigured: Boolean(process.env.RAZORPAY_WEBHOOK_SECRET),
        supportedEvents: [
            "payment.captured",
            "order.paid",
            "payment.failed",
        ],
        dashboardInstructions: {
            step1: "Log in to your Razorpay Dashboard (https://dashboard.razorpay.com).",
            step2: "Navigate to Settings → Webhooks in the left sidebar.",
            step3: "Click '+ Add New Webhook'.",
            step4: `Paste Webhook URL: ${webhookUrl} (or use public ngrok/domain URL if running locally).`,
            step5: "Enter Secret: Match the RAZORPAY_WEBHOOK_SECRET defined in backend/.env.",
            step6: "Check Active Events: 'payment.captured', 'order.paid', and 'payment.failed'.",
            step7: "Click 'Save Webhook'.",
        },
    });
};
exports.getRazorpayWebhookInfo = getRazorpayWebhookInfo;
/**
 * POST /api/webhook/razorpay
 * Processes live Razorpay Webhooks with HMAC SHA256 Signature Verification
 */
const handleRazorpayWebhook = async (req, res) => {
    try {
        const signature = req.headers["x-razorpay-signature"];
        const webhookSecret = (0, razorpay_1.getRazorpayWebhookSecret)();
        // 1. Signature Verification
        const rawBody = req.rawBody
            ? req.rawBody.toString("utf8")
            : JSON.stringify(req.body);
        if (signature && webhookSecret) {
            const generatedSignature = crypto_1.default
                .createHmac("sha256", webhookSecret)
                .update(rawBody)
                .digest("hex");
            const isSignatureValid = crypto_1.default.timingSafeEqual(Buffer.from(generatedSignature, "utf8"), Buffer.from(signature, "utf8"));
            if (!isSignatureValid) {
                console.warn("[Razorpay Webhook Warning]: Webhook signature mismatch.");
                // In strict production mode reject invalid signatures
                if (process.env.NODE_ENV === "production") {
                    res.status(400).json({ success: false, message: "Invalid Razorpay Webhook signature." });
                    return;
                }
            }
        }
        const event = req.body.event;
        const payload = req.body.payload || {};
        console.log(`[Razorpay Webhook] Received Event: "${event}"`);
        // Extract Entities
        const paymentEntity = payload.payment?.entity;
        const orderEntity = payload.order?.entity;
        const razorpayOrderId = paymentEntity?.order_id || orderEntity?.id;
        const razorpayPaymentId = paymentEntity?.id;
        const orderNumber = orderEntity?.receipt ||
            paymentEntity?.notes?.orderNumber ||
            orderEntity?.notes?.orderNumber;
        // 2. Handle Payment Success (order.paid or payment.captured)
        if (event === "order.paid" || event === "payment.captured") {
            const record = {
                orderNumber,
                razorpayOrderId,
                razorpayPaymentId,
                amount: (paymentEntity?.amount || orderEntity?.amount || 0) / 100,
                paymentStatus: "PAID",
                event,
                confirmedAt: new Date().toISOString(),
            };
            // Store in memory cache for immediate frontend polling confirmation
            if (orderNumber)
                exports.webhookConfirmedPayments.set(orderNumber, record);
            if (razorpayOrderId)
                exports.webhookConfirmedPayments.set(razorpayOrderId, record);
            if (razorpayPaymentId)
                exports.webhookConfirmedPayments.set(razorpayPaymentId, record);
            // Search & update Order in MongoDB Database
            let order = await prisma_1.default.order.findFirst({
                where: {
                    OR: [
                        ...(orderNumber ? [{ orderNumber }] : []),
                        ...(razorpayOrderId ? [{ razorpayOrderId }] : []),
                        ...(razorpayPaymentId ? [{ razorpayPaymentId }] : []),
                    ],
                },
            });
            if (order) {
                const wasAlreadyPaid = order.paymentStatus === "PAID";
                order = await prisma_1.default.order.update({
                    where: { id: order.id },
                    data: {
                        paymentStatus: "PAID",
                        orderStatus: order.orderStatus === "PENDING" ? "CONFIRMED" : order.orderStatus,
                        razorpayPaymentId: razorpayPaymentId || order.razorpayPaymentId,
                        razorpayOrderId: razorpayOrderId || order.razorpayOrderId,
                        paymentMethod: paymentEntity?.method ? paymentEntity.method.toUpperCase() : "RAZORPAY",
                    },
                });
                console.log(`[Razorpay Webhook] ✓ Confirmed & Updated Order #${order.orderNumber} to PAID.`);
                // Dispatch confirmation email if not sent yet
                if (!wasAlreadyPaid) {
                    (0, mailer_1.sendOrderConfirmationEmail)({
                        orderNumber: order.orderNumber,
                        customerName: order.customerName,
                        customerEmail: order.customerEmail,
                        customerPhone: order.customerPhone,
                        shippingAddress: order.shippingAddress,
                        items: order.items,
                        subtotal: order.subtotal,
                        discount: order.discount,
                        shippingFee: order.shippingFee,
                        totalAmount: order.totalAmount,
                        paymentMethod: order.paymentMethod,
                        paymentStatus: "PAID",
                        trackingNumber: order.trackingNumber || undefined,
                    }).catch((err) => {
                        console.error("[Razorpay Webhook] Error sending order confirmation email:", err);
                    });
                }
            }
            else {
                console.log(`[Razorpay Webhook] Order #${orderNumber || razorpayOrderId} not yet stored in DB. Payment verified in cache.`);
            }
            res.status(200).json({
                success: true,
                received: true,
                event,
                message: "Payment successfully captured and confirmed.",
            });
            return;
        }
        // 3. Handle Payment Failed
        if (event === "payment.failed") {
            const record = {
                orderNumber,
                razorpayOrderId,
                razorpayPaymentId,
                paymentStatus: "FAILED",
                event,
                confirmedAt: new Date().toISOString(),
            };
            if (orderNumber)
                exports.webhookConfirmedPayments.set(orderNumber, record);
            if (razorpayOrderId)
                exports.webhookConfirmedPayments.set(razorpayOrderId, record);
            if (orderNumber || razorpayOrderId) {
                await prisma_1.default.order.updateMany({
                    where: {
                        OR: [
                            ...(orderNumber ? [{ orderNumber }] : []),
                            ...(razorpayOrderId ? [{ razorpayOrderId }] : []),
                        ],
                    },
                    data: {
                        paymentStatus: "FAILED",
                    },
                });
            }
            console.log(`[Razorpay Webhook] ✕ Payment failed for ${orderNumber || razorpayOrderId}`);
            res.status(200).json({
                success: true,
                received: true,
                event,
                message: "Payment failure recorded.",
            });
            return;
        }
        // Other events acknowledge 200
        res.status(200).json({ success: true, received: true, event });
    }
    catch (error) {
        console.error("[Razorpay Webhook Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Failed to process webhook." });
    }
};
exports.handleRazorpayWebhook = handleRazorpayWebhook;
/**
 * GET /api/webhook/payment-status/:idOrNumber
 * Allows frontend to poll and verify whether payment has been confirmed via Webhook or DB
 */
const checkPaymentStatus = async (req, res) => {
    try {
        const { idOrNumber } = req.params;
        const razorpayOrderId = req.query.razorpayOrderId || "";
        // 1. Check in-memory webhook cache first
        let cached = exports.webhookConfirmedPayments.get(idOrNumber) ||
            (razorpayOrderId ? exports.webhookConfirmedPayments.get(razorpayOrderId) : undefined);
        // 2. Query MongoDB Order (only query id if valid 24-char hex ObjectID)
        const isObjectId = /^[0-9a-fA-F]{24}$/.test(idOrNumber);
        const order = await prisma_1.default.order.findFirst({
            where: {
                OR: [
                    { orderNumber: idOrNumber },
                    ...(isObjectId ? [{ id: idOrNumber }] : []),
                    ...(razorpayOrderId ? [{ razorpayOrderId }] : []),
                ],
            },
        });
        const isPaid = order?.paymentStatus === "PAID" || cached?.paymentStatus === "PAID";
        res.status(200).json({
            success: true,
            confirmed: isPaid,
            paymentStatus: isPaid ? "PAID" : order?.paymentStatus || cached?.paymentStatus || "PENDING",
            webhookConfirmed: Boolean(cached && cached.paymentStatus === "PAID"),
            orderNumber: order?.orderNumber || cached?.orderNumber || idOrNumber,
            razorpayPaymentId: order?.razorpayPaymentId || cached?.razorpayPaymentId,
            order: order || undefined,
        });
    }
    catch (error) {
        console.error("[Check Payment Status Error]:", error);
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.checkPaymentStatus = checkPaymentStatus;
