"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const adminController_1 = require("../controllers/adminController");
const auth_1 = require("../middleware/auth");
const router = (0, express_1.Router)();
// Protect all admin routes
router.use(auth_1.protect, auth_1.adminOnly);
// Analytics
router.get("/analytics", adminController_1.getAdminAnalytics);
// Product Management
router.get("/products", adminController_1.getAdminProducts);
router.post("/products", adminController_1.createProduct);
router.put("/products/:id", adminController_1.updateProduct);
router.delete("/products/:id", adminController_1.deleteProduct);
// Categories Management (Front-end menu sync)
router.get("/categories", adminController_1.getAdminCategories);
router.post("/categories", adminController_1.createCategory);
router.put("/categories/:id", adminController_1.updateCategory);
router.delete("/categories/:id", adminController_1.deleteCategory);
// Banner & Ads Management
router.get("/banners", adminController_1.getAdminBanners);
router.post("/banners", adminController_1.createBanner);
router.put("/banners/:id", adminController_1.updateBanner);
router.delete("/banners/:id", adminController_1.deleteBanner);
// Order & Tracking Management
router.get("/orders", adminController_1.getAdminOrders);
router.put("/orders/:id/status", adminController_1.updateOrderStatus);
router.put("/orders/:id/tracking", adminController_1.updateOrderTracking);
// Users List & Profile Management
router.get("/users", adminController_1.getAdminUsers);
router.get("/users/:id", adminController_1.getAdminUserDetails);
router.put("/users/:id", adminController_1.updateAdminUser);
// Audit Logs & Transactions
router.get("/audit-logs", adminController_1.getAdminAuditLogs);
router.get("/transactions", adminController_1.getAdminTransactions);
// Store Settings & Order Email Receivers
router.get("/settings", adminController_1.getAdminSettings);
router.put("/settings/order-mail", adminController_1.updateAdminOrderMailSettings);
router.post("/settings/test-email", adminController_1.sendTestEmail);
exports.default = router;
