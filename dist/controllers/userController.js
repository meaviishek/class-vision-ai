"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.deleteAddress = exports.updateAddress = exports.createAddress = exports.getAddresses = exports.changePassword = exports.updateProfile = exports.getProfile = void 0;
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const prisma_1 = __importDefault(require("../config/prisma"));
const getProfile = async (req, res) => {
    try {
        const userId = req.user.id;
        const user = await prisma_1.default.user.findUnique({
            where: { id: userId },
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
                whatsappUpdates: true,
                smsAlerts: true,
                catalogNewsletter: true,
                loyaltyPoints: true,
                tier: true,
                twoFactorEnabled: true,
                isVerified: true,
                savedPaymentMethods: true,
                createdAt: true,
                addresses: {
                    orderBy: [{ isDefault: "desc" }, { createdAt: "desc" }],
                },
                orders: {
                    orderBy: { createdAt: "desc" },
                    take: 10,
                },
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
        res.status(200).json({ success: true, profile: user });
    }
    catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.getProfile = getProfile;
const updateProfile = async (req, res) => {
    try {
        const userId = req.user.id;
        const { name, phone, gender, dateOfBirth, anniversary, avatar, whatsappUpdates, smsAlerts, catalogNewsletter, twoFactorEnabled, loyaltyPoints, tier, savedPaymentMethods, } = req.body;
        const updated = await prisma_1.default.user.update({
            where: { id: userId },
            data: {
                ...(name !== undefined && { name }),
                ...(phone !== undefined && { phone }),
                ...(gender !== undefined && { gender }),
                ...(dateOfBirth !== undefined && { dateOfBirth }),
                ...(anniversary !== undefined && { anniversary }),
                ...(avatar !== undefined && { avatar }),
                ...(whatsappUpdates !== undefined && { whatsappUpdates: Boolean(whatsappUpdates) }),
                ...(smsAlerts !== undefined && { smsAlerts: Boolean(smsAlerts) }),
                ...(catalogNewsletter !== undefined && { catalogNewsletter: Boolean(catalogNewsletter) }),
                ...(twoFactorEnabled !== undefined && { twoFactorEnabled: Boolean(twoFactorEnabled) }),
                ...(loyaltyPoints !== undefined && { loyaltyPoints: Number(loyaltyPoints) }),
                ...(tier !== undefined && { tier: String(tier) }),
                ...(savedPaymentMethods !== undefined && { savedPaymentMethods }),
            },
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
                whatsappUpdates: true,
                smsAlerts: true,
                catalogNewsletter: true,
                loyaltyPoints: true,
                tier: true,
                twoFactorEnabled: true,
                isVerified: true,
                savedPaymentMethods: true,
                updatedAt: true,
            },
        });
        res.status(200).json({ success: true, message: "Profile updated successfully", user: updated });
    }
    catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.updateProfile = updateProfile;
const changePassword = async (req, res) => {
    try {
        const userId = req.user.id;
        const { currentPassword, newPassword } = req.body;
        if (!newPassword || newPassword.length < 8) {
            res.status(400).json({ success: false, message: "New password must be at least 8 characters long." });
            return;
        }
        const user = await prisma_1.default.user.findUnique({
            where: { id: userId },
            select: { id: true, password: true },
        });
        if (!user) {
            res.status(404).json({ success: false, message: "User not found." });
            return;
        }
        // If user has an existing password, verify current password
        if (user.password) {
            if (!currentPassword) {
                res.status(400).json({ success: false, message: "Current password is required." });
                return;
            }
            const isMatch = await bcryptjs_1.default.compare(currentPassword, user.password);
            if (!isMatch) {
                res.status(400).json({ success: false, message: "Incorrect current password." });
                return;
            }
        }
        const salt = await bcryptjs_1.default.genSalt(10);
        const hashedPassword = await bcryptjs_1.default.hash(newPassword, salt);
        await prisma_1.default.user.update({
            where: { id: userId },
            data: { password: hashedPassword },
        });
        res.status(200).json({ success: true, message: "Password updated successfully." });
    }
    catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.changePassword = changePassword;
const getAddresses = async (req, res) => {
    try {
        const userId = req.user.id;
        const addresses = await prisma_1.default.address.findMany({
            where: { userId },
            orderBy: [{ isDefault: "desc" }, { createdAt: "desc" }],
        });
        res.status(200).json({ success: true, addresses });
    }
    catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.getAddresses = getAddresses;
const createAddress = async (req, res) => {
    try {
        const userId = req.user.id;
        const { name, phone, street, locality, city, state, pincode, type, isDefault } = req.body;
        if (!name || !phone || !street || !city || !state || !pincode) {
            res.status(400).json({ success: false, message: "Please provide all required address fields." });
            return;
        }
        // If marked as default, unset other default addresses
        if (isDefault) {
            await prisma_1.default.address.updateMany({
                where: { userId, isDefault: true },
                data: { isDefault: false },
            });
        }
        // Check if this is the user's first address; if so, make it default automatically
        const count = await prisma_1.default.address.count({ where: { userId } });
        const newAddress = await prisma_1.default.address.create({
            data: {
                userId,
                name,
                phone,
                street,
                locality: locality || null,
                city,
                state,
                pincode,
                type: type || "Home",
                isDefault: isDefault || count === 0,
            },
        });
        res.status(201).json({ success: true, message: "Address added successfully", address: newAddress });
    }
    catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.createAddress = createAddress;
const updateAddress = async (req, res) => {
    try {
        const userId = req.user.id;
        const { id } = req.params;
        const { name, phone, street, locality, city, state, pincode, type, isDefault } = req.body;
        const existing = await prisma_1.default.address.findFirst({
            where: { id, userId },
        });
        if (!existing) {
            res.status(404).json({ success: false, message: "Address not found." });
            return;
        }
        if (isDefault) {
            await prisma_1.default.address.updateMany({
                where: { userId, isDefault: true },
                data: { isDefault: false },
            });
        }
        const updated = await prisma_1.default.address.update({
            where: { id },
            data: {
                ...(name && { name }),
                ...(phone && { phone }),
                ...(street && { street }),
                ...(locality !== undefined && { locality }),
                ...(city && { city }),
                ...(state && { state }),
                ...(pincode && { pincode }),
                ...(type && { type }),
                ...(isDefault !== undefined && { isDefault }),
            },
        });
        res.status(200).json({ success: true, message: "Address updated successfully", address: updated });
    }
    catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.updateAddress = updateAddress;
const deleteAddress = async (req, res) => {
    try {
        const userId = req.user.id;
        const { id } = req.params;
        const existing = await prisma_1.default.address.findFirst({
            where: { id, userId },
        });
        if (!existing) {
            res.status(404).json({ success: false, message: "Address not found." });
            return;
        }
        await prisma_1.default.address.delete({
            where: { id },
        });
        // If deleted address was default, set another address as default if exists
        if (existing.isDefault) {
            const nextAddress = await prisma_1.default.address.findFirst({
                where: { userId },
                orderBy: { createdAt: "desc" },
            });
            if (nextAddress) {
                await prisma_1.default.address.update({
                    where: { id: nextAddress.id },
                    data: { isDefault: true },
                });
            }
        }
        res.status(200).json({ success: true, message: "Address removed successfully" });
    }
    catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.deleteAddress = deleteAddress;
