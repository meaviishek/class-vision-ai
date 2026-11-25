import { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";
import prisma from "../config/prisma";

const JWT_SECRET = process.env.JWT_SECRET || "zhaevaah_super_secret_jwt_key_2026_luxury_fine_jewellery";
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || "7d";

export interface AuthenticatedUser {
  id: string;
  email: string;
  name: string;
  role: string;
  avatar?: string | null;
  phone?: string | null;
}

export interface AuthRequest extends Request {
  user?: AuthenticatedUser;
}

export const generateToken = (payload: { id: string; email: string; role: string }) => {
  return jwt.sign(payload, JWT_SECRET, {
    expiresIn: JWT_EXPIRES_IN as any,
  });
};

export const protect = async (req: AuthRequest, res: Response, next: NextFunction): Promise<void> => {
  let token: string | undefined;

  if (req.headers.authorization && req.headers.authorization.startsWith("Bearer ")) {
    token = req.headers.authorization.split(" ")[1];
  } else if (req.cookies && req.cookies.token) {
    token = req.cookies.token;
  }

  if (!token) {
    res.status(401).json({ success: false, message: "Authentication required. No token provided." });
    return;
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET) as { id: string; email: string; role: string };
    const user = await prisma.user.findUnique({
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
  } catch (err: any) {
    res.status(401).json({ success: false, message: "Invalid or expired authentication token." });
  }
};

export const optionalAuth = async (req: AuthRequest, res: Response, next: NextFunction): Promise<void> => {
  let token: string | undefined;

  if (req.headers.authorization && req.headers.authorization.startsWith("Bearer ")) {
    token = req.headers.authorization.split(" ")[1];
  } else if (req.cookies && req.cookies.token) {
    token = req.cookies.token;
  }

  if (!token) {
    return next();
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET) as { id: string; email: string; role: string };
    const user = await prisma.user.findUnique({
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
  } catch (err) {
    // Ignore error for optional auth
  }

  next();
};

export const adminOnly = (req: AuthRequest, res: Response, next: NextFunction): void => {
  if (!req.user || req.user.role !== "ADMIN") {
    res.status(403).json({ success: false, message: "Access forbidden. Administrator privileges required." });
    return;
  }
  next();
};

