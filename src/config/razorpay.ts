import Razorpay from "razorpay";

export const getRazorpayKeyId = (): string => {
  const envKey = process.env.RAZORPAY_KEY_ID || "";
  return envKey.replace(/['"]/g, "").trim() || "rzp_test_U3YKwrIwErjZRa";
};

export const getRazorpayKeySecret = (): string => {
  const envSecret = process.env.RAZORPAY_KEY_SECRET || "";
  return envSecret.replace(/['"]/g, "").trim() || "F0dlSq1jfDyHZe0cW2aHHYKe";
};

export const getRazorpayWebhookSecret = (): string => {
  const envSecret = process.env.RAZORPAY_WEBHOOK_SECRET || "";
  return envSecret.replace(/['"]/g, "").trim() || "zhaevaah_razorpay_secret_2026";
};

export const getRazorpayInstance = (): Razorpay => {
  return new Razorpay({
    key_id: getRazorpayKeyId(),
    key_secret: getRazorpayKeySecret(),
  });
};

export const razorpayInstance = getRazorpayInstance();

export default razorpayInstance;

