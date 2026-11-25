"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const userController_1 = require("../controllers/userController");
const auth_1 = require("../middleware/auth");
const router = (0, express_1.Router)();
// User Profile
router.get("/profile", auth_1.protect, userController_1.getProfile);
router.put("/profile", auth_1.protect, userController_1.updateProfile);
router.post("/change-password", auth_1.protect, userController_1.changePassword);
// User Addresses
router.get("/addresses", auth_1.protect, userController_1.getAddresses);
router.post("/addresses", auth_1.protect, userController_1.createAddress);
router.put("/addresses/:id", auth_1.protect, userController_1.updateAddress);
router.delete("/addresses/:id", auth_1.protect, userController_1.deleteAddress);
exports.default = router;
