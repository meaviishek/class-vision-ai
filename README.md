# ZHAEVAAH Luxury Fine Jewellery — Backend API

RESTful API backend for **ZHAEVAAH Fine Jewellery** built with **Express**, **TypeScript**, **Prisma ORM**, **Google Auth**, **Razorpay**, and **Nodemailer**.

---

## ⚡ Quick Start

### 1. Install & Setup Environment
```bash
cd backend
npm install
```
A `.env` file is already created. You can customize your database connection, Razorpay keys, and Google OAuth credentials in `backend/.env`.

### 2. Dual Database Switching (MongoDB ↔ PostgreSQL)
By default, the backend is configured for **MongoDB**:
```env
DATABASE_URL="mongodb://localhost:27017/zhaevaah?authSource=admin"
```

To switch to **PostgreSQL**, simply change `DATABASE_URL` in `.env` to your PostgreSQL connection string:
```env
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/zhaevaah?schema=public"
```
The automated DB Switcher (`scripts/switch-db.js`) detects the protocol prefix on startup and automatically updates `prisma/schema.prisma` and runs `prisma generate`.

You can also switch manually at any time:
```bash
npm run db:switch postgres
# or
npm run db:switch mongo
```

### 3. Seed Luxury Products, Banners & Demo Accounts
Populate your database with the initial catalog, hero carousel slides, and ad banners:
```bash
npm run db:seed
```
This sets up:
- **Admin account**: `admin@zhaevaah.com` (Password: `ZhaevaahAdmin2026!`)
- **Customer account**: `ananya.sharma@example.com` (Password: `Password123!`)
- **7+ Fine Jewellery Products** with full IGI / BIS specifications and stone options
- **8 Promotional Banners** (Hero carousel, Double Ads, Top Sold Week Bracelet, Single Ad)
- **Demo Order** with active BlueDart Air Waybill tracking

### 4. Start Development Server
```bash
npm run dev
```
The server will start on `http://localhost:5000`.

---

## 📚 API Endpoints Summary

### Public Storefront Routes
- `GET /` — API root & service health overview
- `GET /health` — Database connection status check
- `GET /api/products` — Product catalog (category, price range, rating, metal, sort, pagination 20/page)
- `GET /api/products/:idOrSlug` — Detailed product view with full specifications & options
- `GET /api/products/:idOrSlug/related` — Related products in category
- `GET /api/products/categories` — Categories with item counts
- `GET /api/banners` — Active hero slides and ad banners grouped by section

### Authentication & Profile Routes
- `POST /api/auth/google` — Google OAuth ID token login & account provisioning
- `POST /api/auth/register` — Standard email & password registration
- `POST /api/auth/login` — Account sign in
- `GET /api/auth/me` — Current authenticated user profile
- `POST /api/auth/logout` — Clear session
- `GET /api/users/profile` — User profile with orders count & addresses
- `PUT /api/users/profile` — Update name, phone, birthday, anniversary
- `GET /api/users/addresses` — Saved addresses list
- `POST /api/users/addresses` — Add delivery address
- `PUT /api/users/addresses/:id` — Edit delivery address
- `DELETE /api/users/addresses/:id` — Delete delivery address

### Checkout & Razorpay Payment
- `POST /api/orders/razorpay/create` — Generate Razorpay Order with INR amount
- `POST /api/orders/razorpay/verify` — Verify HMAC signature, save order, and **send order confirmation email with CC to Admin and User**
- `GET /api/orders/my-orders` — Customer order history with tracking
- `GET /api/orders/:idOrNumber` — Single order tracking status with BlueDart AWB

### Admin Routes (Protected: Admin Only)
- `GET /api/admin/analytics` — Revenue, orders count, pending shipments
- `GET /api/admin/products` — Manage products catalog
- `POST /api/admin/products` — Create new product with all specifications and images
- `PUT /api/admin/products/:id` — Edit product details and stock
- `DELETE /api/admin/products/:id` — Delete product
- `GET /api/admin/banners` — Manage hero slides & ad banners
- `POST /api/admin/banners` — Add new banner placement
- `PUT /api/admin/banners/:id` — Edit banner image, links, and status
- `DELETE /api/admin/banners/:id` — Delete banner
- `GET /api/admin/orders` — View all customer orders with filters
- `PUT /api/admin/orders/:id/status` — **Mark order status** (`CONFIRMED`, `PROCESSING`, `HALLMARKED`, `SHIPPED`, `IN_TRANSIT`, `DELIVERED`, `CANCELLED`)
- `PUT /api/admin/orders/:id/tracking` — **Update BlueDart Air Waybill (AWB)** and carrier info

---

## 🖥️ Running All 3 Services Together
1. **Backend**:
   ```bash
   cd backend && npm run dev
   # Runs on http://localhost:5000
   ```
2. **Frontend Storefront**:
   ```bash
   cd frontend && npm run dev
   # Runs on http://localhost:3000
   ```
3. **Admin Control Center**:
   ```bash
   cd admin && npm run dev
   # Runs on http://localhost:3001
   ```

