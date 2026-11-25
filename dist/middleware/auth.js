"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.adminOnly = exports.optionalAuth = exports.protect = exports.generateToken = void 0;
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const prisma_1 = __importDefault(require("../config/prisma"));
const JWT_SECRET = process.env.JWT_SECRET || "zhaevaah_super_secret_jwt_key_2026_luxury_fine_jewellery";
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || "7d";
const generateToken = (payload) => {
    return jsonwebtoken_1.default.sign(payload, JWT_SECRET, {
        expiresIn: JWT_EXPIRES_IN,
    });
};
exports.generateToken = generateToken;
const protect = async (req, res, next) => {
    let token;
    if (req.headers.authorization && req.headers.authorization.startsWith("Bearer ")) {
        token = req.headers.authorization.split(" ")[1];
    }
    else if (req.cookies && req.cookies.token) {
        token = req.cookies.token;
    }
    if (!token) {
        res.status(401).json({ success: false, message: "Authentication required. No token provided." });
        return;
    }
    try {
        const decoded = jsonwebtoken_1.default.verify(token, JWT_SECRET);
        const user = await prisma_1.default.user.findUnique({
            where: { id: decoded.id },
            select: {
                id: true,
                email: true,
                name: true,
                role: true,
                avatar: true,
                phone: true,
            },
        });
        if (!user) {
            res.status(401).json({ success: false, message: "User account no longer exists." });
            return;
        }
        req.user = user;
        next();
    }
    catch (err) {
        res.status(401).json({ success: false, message: "Invalid or expired authentication token." });
    }
};
exports.protect = protect;
const optionalAuth = async (req, res, next) => {
    let token;
    if (req.headers.authorization && req.headers.authorization.startsWith("Bearer ")) {
        token = req.headers.authorization.split(" ")[1];
    }
    else if (req.cookies && req.cookies.token) {
        token = req.cookies.token;
    }
    if (!token) {
        return next();
    }
    try {
        const decoded = jsonwebtoken_1.default.verify(token, JWT_SECRET);
        const user = await prisma_1.default.user.findUnique({
            where: { id: decoded.id },
            select: {
                id: true,
                email: true,
                name: true,
                role: true,
                avatar: true,
                phone: true,
            },
        });
        if (user) {
            req.user = user;
        }
    }
    catch (err) {
        // Ignore error for optional auth
    }
    next();
};
exports.optionalAuth = optionalAuth;
const adminOnly = (req, res, next) => {
    if (!req.user || req.user.role !== "ADMIN") {
        res.status(403).json({ success: false, message: "Access forbidden. Administrator privileges required." });
        return;
    }
    next();
};
exports.adminOnly = adminOnly;
