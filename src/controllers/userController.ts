import { Response } from "express";
import bcrypt from "bcryptjs";
import prisma from "../config/prisma";
import { AuthRequest } from "../middleware/auth";

export const getProfile = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const userId = req.user!.id;

    const user = await prisma.user.findUnique({
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
  } catch (error: any) {
    res.status(500).json({ success: false, message: error.message });
  }
};

export const updateProfile = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const userId = req.user!.id;
    const {
      name,
      phone,
      gender,
      dateOfBirth,
      anniversary,
      avatar,
      whatsappUpdates,
      smsAlerts,
      catalogNewsletter,
      twoFactorEnabled,
      loyaltyPoints,
      tier,
      savedPaymentMethods,
    } = req.body;

    const updated = await prisma.user.update({
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
  } catch (error: any) {
    res.status(500).json({ success: false, message: error.message });
  }
};

export const changePassword = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const userId = req.user!.id;
    const { currentPassword, newPassword } = req.body;

    if (!newPassword || newPassword.length < 8) {
      res.status(400).json({ success: false, message: "New password must be at least 8 characters long." });
      return;
    }

    const user = await prisma.user.findUnique({
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
      const isMatch = await bcrypt.compare(currentPassword, user.password);
      if (!isMatch) {
        res.status(400).json({ success: false, message: "Incorrect current password." });
        return;
      }
    }

    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(newPassword, salt);

    await prisma.user.update({
      where: { id: userId },
      data: { password: hashedPassword },
    });

    res.status(200).json({ success: true, message: "Password updated successfully." });
  } catch (error: any) {
    res.status(500).json({ success: false, message: error.message });
  }
};

export const getAddresses = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const userId = req.user!.id;
    const addresses = await prisma.address.findMany({
      where: { userId },
      orderBy: [{ isDefault: "desc" }, { createdAt: "desc" }],
    });

    res.status(200).json({ success: true, addresses });
  } catch (error: any) {
    res.status(500).json({ success: false, message: error.message });
  }
};

export const createAddress = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const userId = req.user!.id;
    const { name, phone, street, locality, city, state, pincode, type, isDefault } = req.body;

    if (!name || !phone || !street || !city || !state || !pincode) {
      res.status(400).json({ success: false, message: "Please provide all required address fields." });
      return;
    }

    // If marked as default, unset other default addresses
    if (isDefault) {
      await prisma.address.updateMany({
        where: { userId, isDefault: true },
        data: { isDefault: false },
      });
    }

    // Check if this is the user's first address; if so, make it default automatically
    const count = await prisma.address.count({ where: { userId } });

    const newAddress = await prisma.address.create({
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
  } catch (error: any) {
    res.status(500).json({ success: false, message: error.message });
  }
};

export const updateAddress = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const userId = req.user!.id;
    const { id } = req.params;
    const { name, phone, street, locality, city, state, pincode, type, isDefault } = req.body;

    const existing = await prisma.address.findFirst({
      where: { id, userId },
    });

    if (!existing) {
      res.status(404).json({ success: false, message: "Address not found." });
      return;
    }

    if (isDefault) {
      await prisma.address.updateMany({
        where: { userId, isDefault: true },
        data: { isDefault: false },
      });
    }

    const updated = await prisma.address.update({
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
  } catch (error: any) {
    res.status(500).json({ success: false, message: error.message });
  }
};

export const deleteAddress = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const userId = req.user!.id;
    const { id } = req.params;

    const existing = await prisma.address.findFirst({
      where: { id, userId },
    });

    if (!existing) {
      res.status(404).json({ success: false, message: "Address not found." });
      return;
    }

    await prisma.address.delete({
      where: { id },
    });

    // If deleted address was default, set another address as default if exists
    if (existing.isDefault) {
      const nextAddress = await prisma.address.findFirst({
        where: { userId },
        orderBy: { createdAt: "desc" },
      });
      if (nextAddress) {
        await prisma.address.update({
          where: { id: nextAddress.id },
          data: { isDefault: true },
        });
      }
    }

    res.status(200).json({ success: true, message: "Address removed successfully" });
  } catch (error: any) {
    res.status(500).json({ success: false, message: error.message });
  }
};

