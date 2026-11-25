"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.logout = exports.getMe = exports.completeProfile = exports.resetPassword = exports.verifyResetOtp = exports.forgotPassword = exports.resendLoginOtp = exports.verifyLoginOtp = exports.login = exports.resendVerificationOtp = exports.verifyRegistrationOtp = exports.register = exports.googleAuth = exports.ensureDefaultAdmins = void 0;
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const google_auth_library_1 = require("google-auth-library");
const prisma_1 = __importDefault(require("../config/prisma"));
const auth_1 = require("../middleware/auth");
const mailer_1 = require("../config/mailer");
const googleClient = new google_auth_library_1.OAuth2Client(process.env.GOOGLE_CLIENT_ID || "");
const ADMIN_EMAIL = (process.env.ADMIN_EMAIL || "zhaevaah@gmail.com").toLowerCase();
const ensureDefaultAdmins = async () => {
    try {
        const salt = await bcryptjs_1.default.genSalt(10);
        const hashedPassword = await bcryptjs_1.default.hash("ZhaevaahAdmin2026!", salt);
        // 1. zhaevaah@gmail.com
        await prisma_1.default.user.upsert({
            where: { email: "zhaevaah@gmail.com" },
            update: {
                role: "ADMIN",
                password: hashedPassword,
                name: "ZHAEVAAH Master Admin",
                isVerified: true,
            },
            create: {
                email: "zhaevaah@gmail.com",
                role: "ADMIN",
                password: hashedPassword,
                name: "ZHAEVAAH Master Admin",
                isVerified: true,
            },
        });
        // 2. admin@zhaevaah.com (testing account)
        await prisma_1.default.user.upsert({
            where: { email: "admin@zhaevaah.com" },
            update: {
                role: "ADMIN",
                password: hashedPassword,
                name: "ZHAEVAAH Test Admin",
                isVerified: true,
            },
            create: {
                email: "admin@zhaevaah.com",
                role: "ADMIN",
                password: hashedPassword,
                name: "ZHAEVAAH Test Admin",
                isVerified: true,
            },
        });
        console.log("[Auth] Default admins confirmed in database (zhaevaah@gmail.com & admin@zhaevaah.com)");
    }
    catch (err) {
        console.warn("[Auth] Admin upsert note:", err.message);
    }
};
exports.ensureDefaultAdmins = ensureDefaultAdmins;
const googleAuth = async (req, res) => {
    try {
        const { credential, email: directEmail, name: directName, picture: directPicture } = req.body;
        let email = directEmail;
        let name = directName;
        let avatar = directPicture;
        let googleId;
        // If ID token is passed, verify with Google Auth Library
        if (credential) {
            try {
                const ticket = await googleClient.verifyIdToken({
                    idToken: credential,
                    audience: process.env.GOOGLE_CLIENT_ID || undefined,
                });
                const payload = ticket.getPayload();
                if (payload) {
                    email = payload.email;
                    name = payload.name || payload.given_name || "ZHAEVAAH Customer";
                    avatar = payload.picture;
                    googleId = payload.sub;
                }
            }
            catch (err) {
                console.warn("[Google Auth] verifyIdToken failed, falling back to body params:", err.message);
                // If Google Client ID is placeholder in dev, allow fallback to direct email/name if provided
            }
        }
        if (!email) {
            res.status(400).json({ success: false, message: "Valid email address is required from Google authentication." });
            return;
        }
        email = email.toLowerCase().trim();
        // Check if user exists
        let user = await prisma_1.default.user.findUnique({
            where: { email },
        });
        const isSystemAdmin = email === ADMIN_EMAIL;
        if (!user) {
            // Create new user
            user = await prisma_1.default.user.create({
                data: {
                    email,
                    name: name || "ZHAEVAAH Customer",
                    avatar: avatar || null,
                    googleId: googleId || null,
                    role: isSystemAdmin ? "ADMIN" : "USER",
                    isVerified: true,
                    phone: null,
                    gender: null,
                    dateOfBirth: null,
                },
            });
            console.log(`[Google Auth] Created new user: ${email} (${user.role})`);
            // Send royal welcome email to first-time customer
            (0, mailer_1.sendWelcomeEmail)({ name: user.name, email: user.email }).catch((wErr) => {
                console.error("[Google Auth] Welcome email error:", wErr);
            });
        }
        else {
            // Update existing user with googleId/avatar/role if needed
            user = await prisma_1.default.user.update({
                where: { id: user.id },
                data: {
                    avatar: avatar || user.avatar,
                    googleId: googleId || user.googleId,
                    role: isSystemAdmin ? "ADMIN" : user.role,
                    isVerified: true,
                },
            });
        }
        const token = (0, auth_1.generateToken)({
            id: user.id,
            email: user.email,
            role: user.role,
        });
        res.cookie("token", token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
            sameSite: "lax",
        });
        const requiresProfileCompletion = !Boolean(user.phone && user.dateOfBirth && user.gender);
        res.status(200).json({
            success: true,
            message: "Google login successful",
            token,
            requiresProfileCompletion,
            user: {
                id: user.id,
                email: user.email,
                name: user.name,
                avatar: user.avatar,
                role: user.role,
                phone: user.phone,
                gender: user.gender,
                dateOfBirth: user.dateOfBirth,
                isVerified: true,
            },
        });
    }
    catch (error) {
        console.error("[Google Auth Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Failed to process Google login." });
    }
};
exports.googleAuth = googleAuth;
const register = async (req, res) => {
    try {
        const { name, email, password, phone, gender, dateOfBirth } = req.body;
        if (!name || !email || !password) {
            res.status(400).json({ success: false, message: "Name, email, and password are required." });
            return;
        }
        const normalizedEmail = email.toLowerCase().trim();
        const existingUser = await prisma_1.default.user.findUnique({
            where: { email: normalizedEmail },
        });
        if (existingUser && (existingUser.isVerified || existingUser.role === "ADMIN" || Boolean(existingUser.googleId))) {
            res.status(400).json({ success: false, message: "An account with this email address already exists. Please log in." });
            return;
        }
        const salt = await bcryptjs_1.default.genSalt(10);
        const hashedPassword = await bcryptjs_1.default.hash(password, salt);
        const isSystemAdmin = normalizedEmail === ADMIN_EMAIL;
        // Generate 6-digit verification OTP
        const otp = Math.floor(100000 + Math.random() * 900000).toString();
        const otpExpiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes
        let user;
        if (existingUser && !existingUser.isVerified) {
            // User registered previously but never verified
            user = await prisma_1.default.user.update({
                where: { id: existingUser.id },
                data: {
                    name,
                    password: hashedPassword,
                    phone: phone || existingUser.phone,
                    gender: gender || existingUser.gender,
                    dateOfBirth: dateOfBirth || existingUser.dateOfBirth,
                    isVerified: false,
                    verificationOtp: otp,
                    verificationOtpExpiresAt: otpExpiresAt,
                },
            });
        }
        else {
            user = await prisma_1.default.user.create({
                data: {
                    name,
                    email: normalizedEmail,
                    password: hashedPassword,
                    phone: phone || null,
                    gender: gender || "Female",
                    dateOfBirth: dateOfBirth || null,
                    role: isSystemAdmin ? "ADMIN" : "USER",
                    isVerified: false,
                    verificationOtp: otp,
                    verificationOtpExpiresAt: otpExpiresAt,
                },
            });
        }
        // Send verification OTP email
        (0, mailer_1.sendVerificationOtpEmail)({ email: user.email, name: user.name, otp }).catch((err) => {
            console.error("[Register] Verification OTP email error:", err);
        });
        res.status(200).json({
            success: true,
            requiresVerification: true,
            email: user.email,
            message: `A 6-digit verification code has been sent to ${user.email}. Please verify to complete your registration.`,
        });
    }
    catch (error) {
        console.error("[Register Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Failed to register account." });
    }
};
exports.register = register;
const verifyRegistrationOtp = async (req, res) => {
    try {
        const { email, otp } = req.body;
        if (!email || !otp) {
            res.status(400).json({ success: false, message: "Email and verification code are required." });
            return;
        }
        const normalizedEmail = email.toLowerCase().trim();
        const user = await prisma_1.default.user.findUnique({
            where: { email: normalizedEmail },
        });
        if (!user) {
            res.status(404).json({ success: false, message: "No account found with this email address." });
            return;
        }
        if (user.isVerified) {
            res.status(400).json({ success: false, message: "Your email is already verified. Please log in." });
            return;
        }
        if (!user.verificationOtp || user.verificationOtp !== String(otp).trim()) {
            res.status(400).json({ success: false, message: "Invalid verification code. Please check your email and try again." });
            return;
        }
        if (user.verificationOtpExpiresAt && new Date() > user.verificationOtpExpiresAt) {
            res.status(400).json({ success: false, message: "Verification code has expired. Please request a new code." });
            return;
        }
        // Update user to verified
        const updatedUser = await prisma_1.default.user.update({
            where: { id: user.id },
            data: {
                isVerified: true,
                verificationOtp: null,
                verificationOtpExpiresAt: null,
            },
        });
        // Send royal welcome email now that user is verified
        (0, mailer_1.sendWelcomeEmail)({ name: updatedUser.name, email: updatedUser.email }).catch((wErr) => {
            console.error("[Verify OTP] Welcome email error:", wErr);
        });
        const token = (0, auth_1.generateToken)({
            id: updatedUser.id,
            email: updatedUser.email,
            role: updatedUser.role,
        });
        res.cookie("token", token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            maxAge: 7 * 24 * 60 * 60 * 1000,
            sameSite: "lax",
        });
        res.status(200).json({
            success: true,
            message: "Email verified successfully! Welcome to ZHAEVAAH.",
            token,
            user: {
                id: updatedUser.id,
                email: updatedUser.email,
                name: updatedUser.name,
                avatar: updatedUser.avatar,
                role: updatedUser.role,
                phone: updatedUser.phone,
                isVerified: true,
            },
        });
    }
    catch (error) {
        console.error("[Verify Registration OTP Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Failed to verify registration code." });
    }
};
exports.verifyRegistrationOtp = verifyRegistrationOtp;
const resendVerificationOtp = async (req, res) => {
    try {
        const { email } = req.body;
        if (!email) {
            res.status(400).json({ success: false, message: "Email is required." });
            return;
        }
        const normalizedEmail = email.toLowerCase().trim();
        const user = await prisma_1.default.user.findUnique({
            where: { email: normalizedEmail },
        });
        if (!user) {
            res.status(404).json({ success: false, message: "No account found with this email address." });
            return;
        }
        if (user.isVerified) {
            res.status(400).json({ success: false, message: "Your account is already verified. Please log in." });
            return;
        }
        const otp = Math.floor(100000 + Math.random() * 900000).toString();
        const otpExpiresAt = new Date(Date.now() + 10 * 60 * 1000);
        await prisma_1.default.user.update({
            where: { id: user.id },
            data: {
                verificationOtp: otp,
                verificationOtpExpiresAt: otpExpiresAt,
            },
        });
        (0, mailer_1.sendVerificationOtpEmail)({ email: user.email, name: user.name, otp }).catch(console.error);
        res.status(200).json({
            success: true,
            message: `A fresh 6-digit verification code has been sent to ${user.email}.`,
        });
    }
    catch (error) {
        console.error("[Resend OTP Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Failed to resend verification code." });
    }
};
exports.resendVerificationOtp = resendVerificationOtp;
const login = async (req, res) => {
    try {
        const { email, password } = req.body;
        if (!email || !password) {
            res.status(400).json({ success: false, message: "Please enter both email and password." });
            return;
        }
        const normalizedEmail = email.toLowerCase().trim();
        let user = await prisma_1.default.user.findUnique({
            where: { email: normalizedEmail },
        });
        // Auto-seed admin if logging in for the first time
        if (!user && (normalizedEmail === "zhaevaah@gmail.com" || normalizedEmail === "admin@zhaevaah.com")) {
            const salt = await bcryptjs_1.default.genSalt(10);
            const hashedPassword = await bcryptjs_1.default.hash("ZhaevaahAdmin2026!", salt);
            user = await prisma_1.default.user.create({
                data: {
                    email: normalizedEmail,
                    name: normalizedEmail === "zhaevaah@gmail.com" ? "ZHAEVAAH Master Admin" : "ZHAEVAAH Test Admin",
                    password: hashedPassword,
                    role: "ADMIN",
                    isVerified: true,
                },
            });
        }
        if (!user || !user.password) {
            res.status(401).json({
                success: false,
                message: "Invalid credentials. If you registered with Google, please use Google Login.",
            });
            return;
        }
        const isMatch = await bcryptjs_1.default.compare(password, user.password);
        if (!isMatch) {
            res.status(401).json({ success: false, message: "Invalid email or password." });
            return;
        }
        // ── Enforce Email Verification: Do not let unverified users log in ──
        if (!user.isVerified && user.role !== "ADMIN" && normalizedEmail !== "admin@zhaevaah.com") {
            const otp = Math.floor(100000 + Math.random() * 900000).toString();
            const otpExpiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes
            await prisma_1.default.user.update({
                where: { id: user.id },
                data: {
                    verificationOtp: otp,
                    verificationOtpExpiresAt: otpExpiresAt,
                },
            });
            (0, mailer_1.sendVerificationOtpEmail)({ email: user.email, name: user.name, otp }).catch((err) => {
                console.error("[Login Unverified Email Error]:", err);
            });
            res.status(403).json({
                success: false,
                requiresVerification: true,
                email: user.email,
                message: "Your email address is not verified yet. We have sent a 6-digit verification code to your email. Please verify your OTP to complete login.",
            });
            return;
        }
        // ── Testing Admin Account (admin@zhaevaah.com): SKIPS OTP for easy testing ──
        if (normalizedEmail === "admin@zhaevaah.com") {
            const token = (0, auth_1.generateToken)({
                id: user.id,
                email: user.email,
                role: user.role,
            });
            res.cookie("token", token, {
                httpOnly: true,
                secure: process.env.NODE_ENV === "production",
                maxAge: 7 * 24 * 60 * 60 * 1000,
                sameSite: "lax",
            });
            res.status(200).json({
                success: true,
                message: "Logged in successfully (Test Admin - OTP Skipped)",
                token,
                user: {
                    id: user.id,
                    email: user.email,
                    name: user.name,
                    avatar: user.avatar,
                    role: user.role,
                    phone: user.phone,
                    isVerified: true,
                },
            });
            return;
        }
        // ── For all other users (including zhaevaah@gmail.com): REQUIRE OTP TO LOGIN ──
        const otp = Math.floor(100000 + Math.random() * 900000).toString();
        const otpExpiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes
        await prisma_1.default.user.update({
            where: { id: user.id },
            data: {
                verificationOtp: otp,
                verificationOtpExpiresAt: otpExpiresAt,
            },
        });
        (0, mailer_1.sendLoginOtpEmail)({ email: user.email, name: user.name, otp }).catch((err) => {
            console.error("[Login OTP Email Error]:", err);
        });
        res.status(200).json({
            success: true,
            requiresOtp: true,
            email: user.email,
            message: `A 6-digit login verification code has been sent to ${user.email}. Please enter it to complete sign in.`,
        });
    }
    catch (error) {
        console.error("[Login Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Login failed." });
    }
};
exports.login = login;
const verifyLoginOtp = async (req, res) => {
    try {
        const { email, otp } = req.body;
        if (!email || !otp) {
            res.status(400).json({ success: false, message: "Email and verification code are required." });
            return;
        }
        const normalizedEmail = email.toLowerCase().trim();
        const user = await prisma_1.default.user.findUnique({
            where: { email: normalizedEmail },
        });
        if (!user) {
            res.status(404).json({ success: false, message: "No account found with this email address." });
            return;
        }
        if (!user.verificationOtp || user.verificationOtp !== String(otp).trim()) {
            res.status(400).json({ success: false, message: "Invalid verification code. Please check your email and try again." });
            return;
        }
        if (user.verificationOtpExpiresAt && new Date() > user.verificationOtpExpiresAt) {
            res.status(400).json({ success: false, message: "Verification code has expired. Please log in again to receive a fresh code." });
            return;
        }
        // Clear OTP fields upon successful verification and mark verified
        const updatedUser = await prisma_1.default.user.update({
            where: { id: user.id },
            data: {
                verificationOtp: null,
                verificationOtpExpiresAt: null,
                isVerified: true,
            },
        });
        const token = (0, auth_1.generateToken)({
            id: updatedUser.id,
            email: updatedUser.email,
            role: updatedUser.role,
        });
        res.cookie("token", token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            maxAge: 7 * 24 * 60 * 60 * 1000,
            sameSite: "lax",
        });
        res.status(200).json({
            success: true,
            message: "Logged in successfully",
            token,
            user: {
                id: updatedUser.id,
                email: updatedUser.email,
                name: updatedUser.name,
                avatar: updatedUser.avatar,
                role: updatedUser.role,
                phone: updatedUser.phone,
                isVerified: true,
            },
        });
    }
    catch (error) {
        console.error("[Verify Login OTP Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Failed to verify login code." });
    }
};
exports.verifyLoginOtp = verifyLoginOtp;
const resendLoginOtp = async (req, res) => {
    try {
        const { email } = req.body;
        if (!email) {
            res.status(400).json({ success: false, message: "Email is required." });
            return;
        }
        const normalizedEmail = email.toLowerCase().trim();
        const user = await prisma_1.default.user.findUnique({
            where: { email: normalizedEmail },
        });
        if (!user) {
            res.status(404).json({ success: false, message: "No account found with this email address." });
            return;
        }
        const otp = Math.floor(100000 + Math.random() * 900000).toString();
        const otpExpiresAt = new Date(Date.now() + 10 * 60 * 1000);
        await prisma_1.default.user.update({
            where: { id: user.id },
            data: {
                verificationOtp: otp,
                verificationOtpExpiresAt: otpExpiresAt,
            },
        });
        (0, mailer_1.sendLoginOtpEmail)({ email: user.email, name: user.name, otp }).catch(console.error);
        res.status(200).json({
            success: true,
            message: `A new 6-digit verification code has been sent to ${user.email}.`,
        });
    }
    catch (error) {
        console.error("[Resend Login OTP Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Failed to resend login code." });
    }
};
exports.resendLoginOtp = resendLoginOtp;
const forgotPassword = async (req, res) => {
    try {
        const { email } = req.body;
        if (!email) {
            res.status(400).json({ success: false, message: "Email is required." });
            return;
        }
        const normalizedEmail = email.toLowerCase().trim();
        const user = await prisma_1.default.user.findUnique({
            where: { email: normalizedEmail },
        });
        if (!user) {
            res.status(404).json({ success: false, message: "No account found with this email address." });
            return;
        }
        // Generate 6-digit reset OTP
        const otp = Math.floor(100000 + Math.random() * 900000).toString();
        const otpExpiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes
        await prisma_1.default.user.update({
            where: { id: user.id },
            data: {
                resetPasswordOtp: otp,
                resetPasswordOtpExpiresAt: otpExpiresAt,
            },
        });
        (0, mailer_1.sendPasswordResetOtpEmail)({ email: user.email, name: user.name, otp }).catch(console.error);
        res.status(200).json({
            success: true,
            message: `A password reset code has been sent to ${user.email}.`,
        });
    }
    catch (error) {
        console.error("[Forgot Password Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Failed to process forgot password request." });
    }
};
exports.forgotPassword = forgotPassword;
const verifyResetOtp = async (req, res) => {
    try {
        const { email, otp } = req.body;
        if (!email || !otp) {
            res.status(400).json({ success: false, message: "Email and reset code are required." });
            return;
        }
        const normalizedEmail = email.toLowerCase().trim();
        const user = await prisma_1.default.user.findUnique({
            where: { email: normalizedEmail },
        });
        if (!user) {
            res.status(404).json({ success: false, message: "No account found with this email address." });
            return;
        }
        if (!user.resetPasswordOtp || user.resetPasswordOtp !== String(otp).trim()) {
            res.status(400).json({ success: false, message: "Invalid reset code. Please check your email and try again." });
            return;
        }
        if (user.resetPasswordOtpExpiresAt && new Date() > user.resetPasswordOtpExpiresAt) {
            res.status(400).json({ success: false, message: "Reset code has expired. Please request a new code." });
            return;
        }
        res.status(200).json({
            success: true,
            message: "Reset code verified successfully. You may now set a new password.",
        });
    }
    catch (error) {
        console.error("[Verify Reset OTP Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Failed to verify reset code." });
    }
};
exports.verifyResetOtp = verifyResetOtp;
const resetPassword = async (req, res) => {
    try {
        const { email, otp, newPassword } = req.body;
        if (!email || !otp || !newPassword) {
            res.status(400).json({ success: false, message: "Email, reset code, and new password are required." });
            return;
        }
        if (newPassword.length < 8) {
            res.status(400).json({ success: false, message: "New password must be at least 8 characters long." });
            return;
        }
        const normalizedEmail = email.toLowerCase().trim();
        const user = await prisma_1.default.user.findUnique({
            where: { email: normalizedEmail },
        });
        if (!user) {
            res.status(404).json({ success: false, message: "No account found with this email address." });
            return;
        }
        if (!user.resetPasswordOtp || user.resetPasswordOtp !== String(otp).trim()) {
            res.status(400).json({ success: false, message: "Invalid reset code. Please check your email and try again." });
            return;
        }
        if (user.resetPasswordOtpExpiresAt && new Date() > user.resetPasswordOtpExpiresAt) {
            res.status(400).json({ success: false, message: "Reset code has expired. Please request a new code." });
            return;
        }
        const salt = await bcryptjs_1.default.genSalt(10);
        const hashedPassword = await bcryptjs_1.default.hash(newPassword, salt);
        await prisma_1.default.user.update({
            where: { id: user.id },
            data: {
                password: hashedPassword,
                resetPasswordOtp: null,
                resetPasswordOtpExpiresAt: null,
                isVerified: true, // Also mark verified since they just proved ownership of the email
            },
        });
        res.status(200).json({
            success: true,
            message: "Your password has been reset successfully. You can now log in with your new password.",
        });
    }
    catch (error) {
        console.error("[Reset Password Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Failed to reset password." });
    }
};
exports.resetPassword = resetPassword;
const completeProfile = async (req, res) => {
    try {
        const { email, phone, gender, dateOfBirth } = req.body;
        let userId = req.user?.id;
        if (!userId && email) {
            const normalizedEmail = String(email).toLowerCase().trim();
            const existingUser = await prisma_1.default.user.findUnique({
                where: { email: normalizedEmail },
            });
            if (existingUser) {
                userId = existingUser.id;
            }
        }
        if (!userId) {
            res.status(401).json({ success: false, message: "User identification required to complete profile." });
            return;
        }
        const updatedUser = await prisma_1.default.user.update({
            where: { id: userId },
            data: {
                phone: phone ? String(phone).trim() : undefined,
                gender: gender ? String(gender).trim() : undefined,
                dateOfBirth: dateOfBirth ? String(dateOfBirth).trim() : undefined,
            },
        });
        const token = (0, auth_1.generateToken)({
            id: updatedUser.id,
            email: updatedUser.email,
            role: updatedUser.role,
        });
        res.cookie("token", token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            maxAge: 7 * 24 * 60 * 60 * 1000,
            sameSite: "lax",
        });
        res.status(200).json({
            success: true,
            message: "Atelier profile updated successfully.",
            token,
            user: {
                id: updatedUser.id,
                email: updatedUser.email,
                name: updatedUser.name,
                avatar: updatedUser.avatar,
                role: updatedUser.role,
                phone: updatedUser.phone,
                gender: updatedUser.gender,
                dateOfBirth: updatedUser.dateOfBirth,
                isVerified: updatedUser.isVerified,
            },
        });
    }
    catch (error) {
        console.error("[Complete Profile Error]:", error);
        res.status(500).json({ success: false, message: error.message || "Failed to update profile details." });
    }
};
exports.completeProfile = completeProfile;
const getMe = async (req, res) => {
    try {
        if (!req.user) {
            res.status(401).json({ success: false, message: "Not authenticated" });
            return;
        }
        const user = await prisma_1.default.user.findUnique({
            where: { id: req.user.id },
            select: {
                id: true,
                email: true,
                name: true,
                avatar: true,
                role: true,
                phone: true,
                gender: true,
                dateOfBirth: true,
                anniversary: true,
                isVerified: true,
                createdAt: true,
                _count: {
                    select: {
                        orders: true,
                        addresses: true,
                    },
                },
            },
        });
        if (!user) {
            res.status(404).json({ success: false, message: "User not found" });
            return;
        }
        res.status(200).json({
            success: true,
            user: {
                ...user,
                ordersCount: user._count.orders,
                addressesCount: user._count.addresses,
            },
        });
    }
    catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.getMe = getMe;
const logout = (req, res) => {
    res.clearCookie("token");
    res.status(200).json({ success: true, message: "Logged out successfully" });
};
exports.logout = logout;
