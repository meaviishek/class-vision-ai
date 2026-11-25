"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.razorpayInstance = exports.getRazorpayInstance = exports.getRazorpayWebhookSecret = exports.getRazorpayKeySecret = exports.getRazorpayKeyId = void 0;
const razorpay_1 = __importDefault(require("razorpay"));
const getRazorpayKeyId = () => {
    const envKey = process.env.RAZORPAY_KEY_ID || "";
    return envKey.replace(/['"]/g, "").trim() || "rzp_test_U3YKwrIwErjZRa";
};
exports.getRazorpayKeyId = getRazorpayKeyId;
const getRazorpayKeySecret = () => {
    const envSecret = process.env.RAZORPAY_KEY_SECRET || "";
    return envSecret.replace(/['"]/g, "").trim() || "F0dlSq1jfDyHZe0cW2aHHYKe";
};
exports.getRazorpayKeySecret = getRazorpayKeySecret;
const getRazorpayWebhookSecret = () => {
    const envSecret = process.env.RAZORPAY_WEBHOOK_SECRET || "";
    return envSecret.replace(/['"]/g, "").trim() || "zhaevaah_razorpay_secret_2026";
};
exports.getRazorpayWebhookSecret = getRazorpayWebhookSecret;
const getRazorpayInstance = () => {
    return new razorpay_1.default({
        key_id: (0, exports.getRazorpayKeyId)(),
        key_secret: (0, exports.getRazorpayKeySecret)(),
    });
};
exports.getRazorpayInstance = getRazorpayInstance;
exports.razorpayInstance = (0, exports.getRazorpayInstance)();
exports.default = exports.razorpayInstance;
