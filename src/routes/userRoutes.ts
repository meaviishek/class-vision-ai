import { Router } from "express";
import {
  getProfile,
  updateProfile,
  changePassword,
  getAddresses,
  createAddress,
  updateAddress,
  deleteAddress,
} from "../controllers/userController";
import { protect } from "../middleware/auth";

const router = Router();

// User Profile
router.get("/profile", protect, getProfile);
router.put("/profile", protect, updateProfile);
router.post("/change-password", protect, changePassword);

// User Addresses
router.get("/addresses", protect, getAddresses);
router.post("/addresses", protect, createAddress);
router.put("/addresses/:id", protect, updateAddress);
router.delete("/addresses/:id", protect, deleteAddress);

export default router;

