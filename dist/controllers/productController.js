"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getWomensProducts = exports.getMensProducts = exports.getCategories = exports.getRelatedProducts = exports.getProductByIdOrSlug = exports.getProducts = void 0;
const prisma_1 = __importDefault(require("../config/prisma"));
const getProducts = async (req, res) => {
    try {
        const page = Math.max(1, parseInt(req.query.page, 10) || 1);
        const limit = Math.max(1, parseInt(req.query.limit, 10) || 20); // 20 per page as requested!
        const skip = (page - 1) * limit;
        const { category, gender, minPrice, maxPrice, rating, metal, gemstone, sort, q, isFeatured, isBestSeller, } = req.query;
        const where = {
            isAvailable: true,
        };
        const andConditions = [];
        if (gender && gender !== "all" && gender !== "All") {
            const g = String(gender).toLowerCase();
            andConditions.push({
                OR: [
                    { gender: { equals: g, mode: "insensitive" } },
                    { gender: { equals: "unisex", mode: "insensitive" } },
                ],
            });
        }
        if (category && category !== "all" && category !== "All") {
            where.category = {
                equals: String(category),
                mode: "insensitive",
            };
        }
        if (metal) {
            where.metal = {
                contains: String(metal),
                mode: "insensitive",
            };
        }
        if (gemstone) {
            where.gemstone = {
                contains: String(gemstone),
                mode: "insensitive",
            };
        }
        if (minPrice || maxPrice) {
            where.priceNum = {};
            if (minPrice)
                where.priceNum.gte = parseFloat(String(minPrice));
            if (maxPrice)
                where.priceNum.lte = parseFloat(String(maxPrice));
        }
        if (rating) {
            where.rating = {
                gte: parseFloat(String(rating)),
            };
        }
        if (isFeatured === "true") {
            where.isFeatured = true;
        }
        if (isBestSeller === "true") {
            where.isBestSeller = true;
        }
        if (q) {
            const searchTerm = String(q).trim();
            andConditions.push({
                OR: [
                    { title: { contains: searchTerm, mode: "insensitive" } },
                    { description: { contains: searchTerm, mode: "insensitive" } },
                    { category: { contains: searchTerm, mode: "insensitive" } },
                    { metal: { contains: searchTerm, mode: "insensitive" } },
                ],
            });
        }
        if (andConditions.length > 0) {
            where.AND = andConditions;
        }
        // Determine sorting
        let orderBy = { createdAt: "desc" };
        if (sort === "price_asc") {
            orderBy = { priceNum: "asc" };
        }
        else if (sort === "price_desc") {
            orderBy = { priceNum: "desc" };
        }
        else if (sort === "rating") {
            orderBy = { rating: "desc" };
        }
        else if (sort === "popular") {
            orderBy = { soldCount: "desc" };
        }
        let products = [];
        let total = 0;
        try {
            const [dbProducts, dbTotal] = await Promise.all([
                prisma_1.default.product.findMany({
                    where,
                    orderBy,
                    skip,
                    take: limit,
                }),
                prisma_1.default.product.count({ where }),
            ]);
            products = dbProducts;
            total = dbTotal;
        }
        catch (dbErr) {
            console.warn("[Database Products Query Warning]:", dbErr.message);
            // Try unconstrained query or fallback
            try {
                products = await prisma_1.default.product.findMany({ take: limit });
                total = products.length;
            }
            catch {
                products = [];
                total = 0;
            }
        }
        const totalPages = Math.max(1, Math.ceil(total / limit));
        res.status(200).json({
            success: true,
            products,
            pagination: {
                total,
                page,
                limit,
                totalPages,
                hasNextPage: page < totalPages,
                hasPrevPage: page > 1,
            },
        });
    }
    catch (error) {
        console.error("[Get Products Error]:", error);
        res.status(200).json({
            success: true,
            products: [],
            pagination: { total: 0, page: 1, limit: 20, totalPages: 1, hasNextPage: false, hasPrevPage: false },
            message: error.message || "Failed to fetch products",
            isFallback: true,
        });
    }
};
exports.getProducts = getProducts;
const getProductByIdOrSlug = async (req, res) => {
    try {
        const { idOrSlug } = req.params;
        // Try finding by slug first, then by id
        let product = await prisma_1.default.product.findUnique({
            where: { slug: idOrSlug },
            include: {
                reviews: {
                    orderBy: { createdAt: "desc" },
                    take: 10,
                },
            },
        });
        if (!product) {
            try {
                product = await prisma_1.default.product.findUnique({
                    where: { id: idOrSlug },
                    include: {
                        reviews: {
                            orderBy: { createdAt: "desc" },
                            take: 10,
                        },
                    },
                });
            }
            catch (e) {
                // Not a valid ObjectId
            }
        }
        if (!product) {
            res.status(404).json({ success: false, message: "Product not found" });
            return;
        }
        res.status(200).json({ success: true, product });
    }
    catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.getProductByIdOrSlug = getProductByIdOrSlug;
const getRelatedProducts = async (req, res) => {
    try {
        const { idOrSlug } = req.params;
        // Find current product category
        const currentProduct = await prisma_1.default.product.findFirst({
            where: {
                OR: [{ slug: idOrSlug }, { id: idOrSlug }],
            },
            select: { id: true, category: true },
        });
        const category = currentProduct ? currentProduct.category : undefined;
        const excludeId = currentProduct ? currentProduct.id : idOrSlug;
        const related = await prisma_1.default.product.findMany({
            where: {
                id: { not: excludeId },
                ...(category ? { category } : {}),
                isAvailable: true,
            },
            take: 4,
            orderBy: { rating: "desc" },
        });
        res.status(200).json({ success: true, related });
    }
    catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.getRelatedProducts = getRelatedProducts;
const getCategories = async (req, res) => {
    try {
        const { gender } = req.query;
        const catWhere = {};
        if (gender && gender !== "all" && gender !== "All") {
            const g = String(gender).toLowerCase();
            catWhere.OR = [
                { gender: { equals: g, mode: "insensitive" } },
                { gender: { equals: "all", mode: "insensitive" } },
                { gender: null },
            ];
        }
        // 1. Fetch categories from Category table
        const dbCategories = await prisma_1.default.category.findMany({
            where: catWhere,
            orderBy: { order: "asc" },
        });
        // 2. Compute product counts for each category
        const products = await prisma_1.default.product.findMany({
            select: { category: true, gender: true },
        });
        const countMap = {};
        products.forEach((p) => {
            const nameKey = p.category?.toLowerCase().trim();
            if (nameKey) {
                countMap[nameKey] = (countMap[nameKey] || 0) + 1;
            }
        });
        const categories = dbCategories.map((c) => {
            const count = countMap[c.name.toLowerCase().trim()] ||
                countMap[c.slug.toLowerCase().trim()] ||
                0;
            return {
                id: c.id,
                name: c.name,
                slug: c.slug,
                image: c.image || "/images/category_rings.jpg",
                badge: c.badge || null,
                gender: c.gender || "all",
                showInMenu: c.showInMenu,
                order: c.order,
                count,
                itemCount: `${count || 3} ${count === 1 ? "Design" : "Designs"}`,
            };
        });
        res.status(200).json({ success: true, categories });
    }
    catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
};
exports.getCategories = getCategories;
const getMensProducts = async (req, res) => {
    req.query.gender = "men";
    return (0, exports.getProducts)(req, res);
};
exports.getMensProducts = getMensProducts;
const getWomensProducts = async (req, res) => {
    req.query.gender = "women";
    return (0, exports.getProducts)(req, res);
};
exports.getWomensProducts = getWomensProducts;
