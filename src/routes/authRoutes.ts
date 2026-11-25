import { Router } from "express";
import {
  googleAuth,
  register,
  verifyRegistrationOtp,
  resendVerificationOtp,
  login,
  verifyLoginOtp,
  resendLoginOtp,
  forgotPassword,
  verifyResetOtp,
  resetPassword,
  completeProfile,
  getMe,
  logout,
} from "../controllers/authController";
import { protect } from "../middleware/auth";

const router = Router();

router.post("/google", googleAuth);
router.post("/register", register);
router.post("/verify-registration-otp", verifyRegistrationOtp);
router.post("/resend-verification-otp", resendVerificationOtp);
router.post("/login", login);
router.post("/verify-login-otp", verifyLoginOtp);
router.post("/resend-login-otp", resendLoginOtp);
router.post("/forgot-password", forgotPassword);
router.post("/verify-reset-otp", verifyResetOtp);
router.post("/reset-password", resetPassword);
router.post("/complete-profile", completeProfile);
router.get("/me", protect, getMe);
router.post("/logout", logout);

export default router;

