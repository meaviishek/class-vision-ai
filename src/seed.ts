import bcrypt from "bcryptjs";
import prisma from "./config/prisma";

async function main() {
  console.log("\n======================================================");
  console.log("🌱 Seeding ZHAEVAAH Database with Luxury Products & Banners...");
  console.log("======================================================\n");

  // 1. Seed Admin User
  const adminEmail = (process.env.ADMIN_EMAIL || "admin@zhaevaah.com").toLowerCase();
  const adminPassword = await bcrypt.hash("ZhaevaahAdmin2026!", 10);

  const admin = await prisma.user.upsert({
    where: { email: adminEmail },
    update: { role: "ADMIN" },
    create: {
      email: adminEmail,
      name: "ZHAEVAAH Head Curator",
      password: adminPassword,
      role: "ADMIN",
      phone: "+91 98201 00000",
    },
  });
  console.log(`✓ Admin User configured: ${admin.email} (${admin.role})`);

  // 1.5 Seed Default Order Mail Settings
  await prisma.setting.upsert({
    where: { key: "order_mail_settings" },
    update: {
      value: {
        receivers: ["zhaevaah@gmail.com"],
        defaultAdminEmail: "zhaevaah@gmail.com",
        enableOrderConfirmationCustomer: true,
        enableOrderAlertAdmin: true,
        enableWelcomeEmail: true,
        supportEmail: "concierge@zhaevaah.com",
        updatedAt: new Date().toISOString(),
      },
    },
    create: {
      key: "order_mail_settings",
      value: {
        receivers: ["zhaevaah@gmail.com"],
        defaultAdminEmail: "zhaevaah@gmail.com",
        enableOrderConfirmationCustomer: true,
        enableOrderAlertAdmin: true,
        enableWelcomeEmail: true,
        supportEmail: "concierge@zhaevaah.com",
        updatedAt: new Date().toISOString(),
      },
      description: "Store email dispatch configuration and order alert receivers",
      updatedBy: "system",
    },
  });
  console.log(`✓ Order Mail Settings configured with default receiver: zhaevaah@gmail.com`);

  // 2. Seed Demo Customer User
  const customerEmail = "ananya.sharma@example.com";
  const customerPassword = await bcrypt.hash("Password123!", 10);

  const customer = await prisma.user.upsert({
    where: { email: customerEmail },
    update: {
      phone: "+91 98201 54321",
      gender: "Female",
      dateOfBirth: "1994-08-16",
      anniversary: "2021-11-28",
      whatsappUpdates: true,
      smsAlerts: true,
      catalogNewsletter: false,
      loyaltyPoints: 4850,
      tier: "Gold Privilege Tier",
      twoFactorEnabled: true,
      savedPaymentMethods: {
        cards: [
          {
            id: "card_1",
            bank: "HDFC Bank Regalia",
            brand: "VISA",
            last4: "4892",
            holder: "ANANYA SHARMA",
            expiry: "08/29",
            isDefault: true,
          },
          {
            id: "card_2",
            bank: "ICICI Bank Sapphiro",
            brand: "Mastercard",
            last4: "1034",
            holder: "ANANYA SHARMA",
            expiry: "11/28",
            isDefault: false,
          },
        ],
        upi: [
          { id: "upi_1", handle: "ananya.sharma@okaxis", label: "Primary UPI Handle", isDefault: true },
          { id: "upi_2", handle: "ananya@okhdfcbank", label: "Secondary Account", isDefault: false },
        ],
      },
    },
    create: {
      email: customerEmail,
      name: "Ananya Sharma",
      password: customerPassword,
      role: "USER",
      phone: "+91 98201 54321",
      gender: "Female",
      dateOfBirth: "1994-08-16",
      anniversary: "2021-11-28",
      whatsappUpdates: true,
      smsAlerts: true,
      catalogNewsletter: false,
      loyaltyPoints: 4850,
      tier: "Gold Privilege Tier",
      twoFactorEnabled: true,
      savedPaymentMethods: {
        cards: [
          {
            id: "card_1",
            bank: "HDFC Bank Regalia",
            brand: "VISA",
            last4: "4892",
            holder: "ANANYA SHARMA",
            expiry: "08/29",
            isDefault: true,
          },
          {
            id: "card_2",
            bank: "ICICI Bank Sapphiro",
            brand: "Mastercard",
            last4: "1034",
            holder: "ANANYA SHARMA",
            expiry: "11/28",
            isDefault: false,
          },
        ],
        upi: [
          { id: "upi_1", handle: "ananya.sharma@okaxis", label: "Primary UPI Handle", isDefault: true },
          { id: "upi_2", handle: "ananya@okhdfcbank", label: "Secondary Account", isDefault: false },
        ],
      },
    },
  });
  console.log(`✓ Customer User configured: ${customer.email}`);

  // Seed addresses for customer
  const addressCount = await prisma.address.count({ where: { userId: customer.id } });
  if (addressCount === 0) {
    await prisma.address.createMany({
      data: [
        {
          userId: customer.id,
          name: "Ananya Sharma",
          phone: "+91 98201 54321",
          street: "Flat 1402, Tower B, Oberoi Sky Heights",
          locality: "Lokhandwala Complex, Andheri West",
          city: "Mumbai",
          state: "Maharashtra",
          pincode: "400053",
          type: "Home",
          isDefault: true,
        },
        {
          userId: customer.id,
          name: "Ananya Sharma",
          phone: "+91 98201 54321",
          street: "Unit 504, 5th Floor, Signature Business Park",
          locality: "BKC, Bandra East",
          city: "Mumbai",
          state: "Maharashtra",
          pincode: "400051",
          type: "Office",
          isDefault: false,
        },
      ],
    });
    console.log(`✓ Customer Addresses seeded for ${customer.name}`);
  }

  // 2.5 Seed Categories matching frontend menu
  console.log("\nSeeding Menu Categories...");
  const categoriesToSeed = [
    { name: "Diamond Rings", slug: "diamond-rings", image: "/images/category_rings.jpg", badge: "HOT", gender: "women", order: 1 },
    { name: "Solitaire Rings", slug: "solitaire-rings", image: "/images/product_3_main.png", badge: null, gender: "women", order: 2 },
    { name: "Diamond Bracelets", slug: "diamond-bracelets", image: "/images/category_bracelet.jpg", badge: "SALE", gender: "women", order: 3 },
    { name: "Necklaces & Pendants", slug: "necklaces-pendants", image: "/images/category_pendant.jpg", badge: null, gender: "women", order: 4 },
    { name: "Earrings", slug: "earrings", image: "/images/ring_blue_topaz_thumb3.jpg", badge: null, gender: "women", order: 5 },
    { name: "Men's Rings", slug: "mens-rings", image: "/images/product_4_main.png", badge: "HOT", gender: "men", order: 6 },
    { name: "Men's Bracelets & Kadas", slug: "mens-bracelets-kadas", image: "/images/bracelet_hotsell_jewel.jpg", badge: null, gender: "men", order: 7 },
    { name: "Chains & Pendants", slug: "chains-pendants", image: "/images/category_pendant.jpg", badge: null, gender: "men", order: 8 },
    { name: "Cufflinks & Accents", slug: "cufflinks-accents", image: "/images/product_4_hover.jpg", badge: "NEW", gender: "men", order: 9 },
  ];

  for (const cat of categoriesToSeed) {
    await prisma.category.upsert({
      where: { slug: cat.slug },
      update: cat,
      create: cat,
    });
    console.log(`✓ Seeded Category: ${cat.name}`);
  }
  console.log("\nSeeding Banners & Ad Placements...");
  const existingBanners = await prisma.banner.count();
  if (existingBanners === 0) {
    await prisma.banner.createMany({
      data: [
        // Hero Slide
        {
          title: "Woman In Golden Rings And Necklaces",
          subtitle: "Awesome products for the dynamic urban lifestyle",
          type: "HERO",
          image: "/images/hero_woman.jpg",
          link: "/shop",
          ctaText: "SHOP NOW",
          badge: "THIS WEEK'S HIGHLIGHTS",
          position: 1,
          isActive: true,
        },
        {
          title: "Timeless 18kt Solitaires & Bridal Pavé",
          subtitle: "Handcrafted natural diamond creations designed for eternity",
          type: "HERO",
          image: "/images/ZhaevaahHero.jpg",
          link: "/shop",
          ctaText: "DISCOVER COLLECTION",
          badge: "NEW COUTURE ARRIVALS",
          position: 2,
          isActive: true,
        },
        // Ad Banner Double (from reference image)
        {
          title: "Yellow Gold & Diamond Ring",
          subtitle: "Diamond Rings",
          type: "AD_DOUBLE",
          image: "/images/ad_banner_ring_full.jpg",
          productImage: "/images/ad_ring.png",
          link: "/shop?category=Diamond%20Rings",
          ctaText: "SHOP NOW",
          position: 1,
          isActive: true,
        },
        {
          title: "Infinity Diamond Bracelet",
          subtitle: "Diamond Bracelets",
          type: "AD_DOUBLE",
          image: "/images/ad_banner_double_source.jpg",
          productImage: "/images/ad_necklace.png",
          link: "/shop?category=Diamond%20Bracelets",
          ctaText: "SHOP NOW",
          position: 2,
          isActive: true,
        },
        {
          title: "Teardrop Diamond Pendant",
          subtitle: "Diamond Pendant",
          type: "AD_DOUBLE",
          image: "/images/ad_banner_necklace_full.jpg",
          productImage: "/images/category_pendant.jpg",
          link: "/shop?category=Diamond%20Pendant",
          ctaText: "SHOP NOW",
          position: 3,
          isActive: true,
        },
        // Single Ad Banners
        {
          title: "Sterling Silver Rose Gold Love Beckons Ring",
          subtitle: "Couture Stackable Bands in 18kt Rose Gold",
          type: "AD_SINGLE",
          image: "/images/ring_beckons_banner.jpg",
          link: "/shop?category=Diamond%20Rings",
          ctaText: "SHOP NOW",
          position: 1,
          isActive: true,
        },
        {
          title: "Top Sold Product of This Week",
          subtitle: "The Royal Mirage 18kt Rose Gold Bracelet with G-H Color SI Clarity Diamonds",
          type: "BRACELET_HOTSELL",
          image: "/images/bracelet_hotsell_banner.jpg",
          productImage: "/images/bracelet_hotsell_jewel.jpg",
          link: "/shop?category=Diamond%20Bracelets",
          ctaText: "SHOP NOW",
          discount: "5% OFF",
          position: 1,
          isActive: true,
        },
        {
          title: "Complimentary Insured Delivery Across India",
          subtitle: "Free shipping world wide for all orders over ₹15,000",
          type: "PROMO_TOP",
          image: "",
          link: "/shop",
          ctaText: "Shop Now",
          position: 1,
          isActive: true,
        },
      ],
    });
    console.log(`✓ 8 Promotional & Hero banners seeded!`);
  } else {
    console.log(`✓ Banners already exist (${existingBanners} records).`);
  }

  // 4. Seed Products
  console.log("\nSeeding Fine Jewellery Products...");
  const productsToSeed = [
    {
      slug: "blue-topaz-ring",
      title: "Blue Topaz Diamond Engagement Wedding Ring",
      price: "₹18,500 – ₹24,900",
      compareAtPrice: "₹28,000",
      priceNum: 21000,
      rating: 4.8,
      reviewsCount: 38,
      primaryImage: "/images/ring_blue_topaz_main.jpg",
      hoverImage: "/images/ring_blue_topaz_thumb2.jpg",
      additionalImages: [
        "/images/ring_blue_topaz_main.jpg",
        "/images/ring_blue_topaz_thumb1.jpg",
        "/images/ring_blue_topaz_thumb2.jpg",
        "/images/ring_blue_topaz_thumb3.jpg",
      ],
      galleryImages: [
        "/images/ring_blue_topaz_main.jpg",
        "/images/ring_blue_topaz_thumb1.jpg",
        "/images/ring_blue_topaz_thumb2.jpg",
        "/images/ring_blue_topaz_thumb3.jpg",
        "/images/ring_blue_topaz_thumb4.jpg",
      ],
      category: "Diamond Rings",
      gender: "women",
      metal: "14 KT Yellow Gold",
      gemstone: "Blue Topaz & Diamond",
      description:
        "Dharie Diamond Drop Earrings & Ring For Women. Set in 14 KT Yellow Gold with Diamond/Gemstone (0.141 Ct, IJ-SI). The beautiful jewelry is crafted based on Seven Stone theme ideal for Evening.",
      aboutItem:
        "Indulge in the allure of timeless elegance with our Blue Topaz Diamond Ring. Whether worn as a symbol of love, a celebration of achievements, or simply as a daily indulgence, this creation is a testament to enduring beauty and refined style. Your Timeless Elegance Diamond Ring arrives in an elegant jewelry box, making it a perfect gift for a loved one or a treasured addition to your own collection. Each ring is accompanied by a certificate of authenticity, guaranteeing the quality of the diamonds and gold.",
      soldCount: 5,
      soldHours: 19,
      stock: 407,
      viewingCount: 20,
      stoneColors: [
        { name: "Sky Blue Topaz", hex: "#0077B6", image: "/images/ring_blue_topaz_main.jpg" },
        { name: "Emerald Forest", hex: "#1B4332", image: "/images/product_2_main.png" },
        { name: "Canary Yellow", hex: "#FACC15", image: "/images/product_3_main.png" },
        { name: "Royal Sapphire", hex: "#1E3A8A", image: "/images/product_4_main.png" },
      ],
      stoneShapes: [
        { name: "Brilliant Round", shapeId: "round" },
        { name: "Emerald Step Cut", shapeId: "emerald" },
        { name: "Oval Halo", shapeId: "oval" },
      ],
      specifications: [
        { label: "Gold Purity", value: "14 KT Yellow Gold (BIS Hallmarked 585)" },
        { label: "Diamond Weight", value: "0.141 Carat Total Weight" },
        { label: "Diamond Clarity & Color", value: "IJ Color, SI Clarity Natural Diamonds" },
        { label: "Center Stone", value: "Natural Faceted Swiss Blue Topaz (1.20 Ct)" },
        { label: "Setting Type", value: "Micro-Prong Halo Pavé Setting" },
        { label: "Certification", value: "IGI (International Gemological Institute)" },
      ],
      isAvailable: true,
      isFeatured: true,
      isBestSeller: true,
    },
    {
      slug: "prod-1",
      title: "Real Diamond Jewellery Gold Diamond Ring",
      brand: "ZHAEVAAH FINE JEWELLERY",
      price: "₹24,999 – ₹54,999",
      compareAtPrice: "₹28,500",
      discountBadge: "-12%",
      priceNum: 24999,
      rating: 4.5,
      reviewsCount: 18,
      primaryImage: "/images/product_1_main.png",
      hoverImage: "/images/product_1_hover.jpg",
      additionalImages: [
        "/images/product_1_main.png",
        "/images/product_1_hover.jpg",
        "/images/category_rings.jpg",
      ],
      galleryImages: [
        "/images/product_1_main.png",
        "/images/product_1_hover.jpg",
        "/images/category_rings.jpg",
      ],
      category: "Diamond Rings",
      gender: "women",
      metal: "18kt Yellow Gold",
      gemstone: "Natural Diamond",
      description:
        "A harmonious blend of fine 18kt yellow gold and round brilliant cut diamonds, delicately curved to embrace your finger with majestic warmth and sparkle.",
      aboutItem:
        "Handcrafted by master goldsmiths, this swirling crossover bypass ring radiates luxury. Each diamond is calibrated to perfection, illuminating your hands with incomparable fire.",
      stock: 9,
      soldCount: 8,
      soldHours: 14,
      viewingCount: 18,
      stoneColors: [
        { name: "Yellow Gold", hex: "#E5C278", image: "/images/product_1_main.png" },
        { name: "Rose Gold", hex: "#B76E79", image: "/images/product_1_hover.jpg" },
        { name: "White Gold", hex: "#E0E0E0", image: "/images/product_1_main.png" },
      ],
      stoneShapes: [
        { name: "Round Brilliant", shapeId: "round" },
        { name: "Cushion Halo", shapeId: "cushion" },
        { name: "Emerald Cut", shapeId: "emerald" },
      ],
      sizes: ["10", "12", "14", "16", "18", "20"],
      purityOptions: ["14KT", "18KT", "22KT"],
      specifications: [
        { label: "Product Code", value: "ZH-PROD-1" },
        { label: "Gold Purity", value: "18 KT Yellow Gold (BIS Hallmarked)" },
        { label: "Diamond Clarity & Color", value: "IJ Color, SI Clarity Natural Diamonds" },
        { label: "Certification", value: "IGI Certificate & BIS Hallmark Guarantee" },
      ],
      isAvailable: true,
      isFeatured: true,
      isBestSeller: true,
    },
    {
      slug: "prod-2",
      title: "The Sinead Ring 18kt Diamond Yellow Gold Ring",
      brand: "ZHAEVAAH FINE JEWELLERY",
      price: "₹19,999 – ₹21,500",
      compareAtPrice: "₹23,000",
      discountBadge: "-13%",
      priceNum: 19999,
      rating: 5.0,
      reviewsCount: 32,
      primaryImage: "/images/product_2_main.png",
      hoverImage: "/images/product_2_hover.jpg",
      additionalImages: [
        "/images/product_2_main.png",
        "/images/product_2_hover.jpg",
        "/images/hero_woman.jpg",
      ],
      galleryImages: [
        "/images/product_2_main.png",
        "/images/product_2_hover.jpg",
        "/images/hero_woman.jpg",
      ],
      category: "Diamond Rings",
      gender: "women",
      metal: "18kt Yellow Gold",
      gemstone: "Natural Diamond",
      description:
        "Inspired by organic botanical curves, this 18kt yellow gold statement ring features cluster pavé diamond leaves extending into a radiant blooming blossom.",
      aboutItem:
        "The Sinead Ring captures nature in freeze-frame elegance. Delicate laurel leaves encrusted with VVS diamonds wrap around an asymmetric open cuff.",
      stock: 14,
      soldCount: 12,
      soldHours: 19,
      viewingCount: 22,
      stoneColors: [
        { name: "Yellow Gold", hex: "#E5C278", image: "/images/product_2_main.png" },
        { name: "Rose Gold", hex: "#B76E79", image: "/images/product_2_hover.jpg" },
        { name: "White Gold", hex: "#E0E0E0", image: "/images/product_2_main.png" },
      ],
      stoneShapes: [
        { name: "Round Brilliant", shapeId: "round" },
        { name: "Oval Halo", shapeId: "oval" },
      ],
      sizes: ["10", "12", "14", "16", "18", "20"],
      purityOptions: ["14KT", "18KT", "22KT"],
      specifications: [
        { label: "Product Code", value: "ZH-PROD-2" },
        { label: "Gold Purity", value: "18 KT Yellow Gold (BIS Hallmarked 750)" },
        { label: "Diamond Clarity & Color", value: "GH-SI Certified Natural Diamonds" },
        { label: "Certification", value: "IGI (International Gemological Institute)" },
      ],
      isAvailable: true,
      isFeatured: true,
      isBestSeller: true,
    },
    {
      slug: "prod-3",
      title: "Erina Solitaire Ring Kisna White Gold Ring",
      brand: "ZHAEVAAH FINE JEWELLERY",
      price: "₹23,995",
      compareAtPrice: "₹27,000",
      discountBadge: "-11%",
      priceNum: 23995,
      rating: 4.8,
      reviewsCount: 14,
      primaryImage: "/images/product_3_main.png",
      hoverImage: "/images/product_3_hover.jpg",
      additionalImages: [
        "/images/product_3_main.png",
        "/images/product_3_hover.jpg",
        "/images/category_rings.jpg",
      ],
      galleryImages: [
        "/images/product_3_main.png",
        "/images/product_3_hover.jpg",
        "/images/category_rings.jpg",
      ],
      category: "Solitaire Rings",
      gender: "women",
      metal: "18kt White Gold",
      gemstone: "Solitaire Diamond",
      description:
        "Featuring a prominent center solitaire surrounded by a split pavé shank in lustrous rhodium-finished 18kt white gold.",
      aboutItem:
        "A pinnacle of modern glamour, the Erina Solitaire elevates any wardrobe. Designed for maximum light return with cathedral prongs.",
      stock: 7,
      soldCount: 9,
      soldHours: 18,
      viewingCount: 15,
      stoneColors: [
        { name: "White Gold", hex: "#E0E0E0", image: "/images/product_3_main.png" },
        { name: "Yellow Gold", hex: "#E5C278", image: "/images/product_3_main.png" },
        { name: "Platinum 950", hex: "#D4D4D8", image: "/images/product_3_main.png" },
      ],
      stoneShapes: [
        { name: "Round Brilliant", shapeId: "round" },
        { name: "Emerald Cut", shapeId: "emerald" },
      ],
      sizes: ["10", "12", "14", "16", "18", "20"],
      purityOptions: ["14KT", "18KT", "Platinum 950"],
      specifications: [
        { label: "Product Code", value: "ZH-PROD-3" },
        { label: "Gold Purity", value: "18 KT White Gold / Platinum 950" },
        { label: "Center Solitaire", value: "0.50 Ct Solitaire Natural Diamond" },
        { label: "Certification", value: "GIA / IGI Dual Certified" },
      ],
      isAvailable: true,
      isFeatured: true,
      isBestSeller: false,
    },
    {
      slug: "prod-4",
      title: "Casual Thomas Diamond Ring Yellow Gold",
      brand: "ZHAEVAAH FINE JEWELLERY",
      price: "₹12,499 – ₹22,500",
      compareAtPrice: "₹15,000",
      discountBadge: "-5%",
      priceNum: 12499,
      rating: 4.9,
      reviewsCount: 29,
      primaryImage: "/images/product_4_main.png",
      hoverImage: "/images/product_4_hover.jpg",
      additionalImages: [
        "/images/product_4_main.png",
        "/images/product_4_hover.jpg",
        "/images/category_rings.jpg",
      ],
      galleryImages: [
        "/images/product_4_main.png",
        "/images/product_4_hover.jpg",
        "/images/category_rings.jpg",
      ],
      category: "Men's Rings",
      gender: "men",
      metal: "18kt Yellow Gold",
      gemstone: "Natural Diamond",
      description:
        "A masculine signet ring with a geometric square diamond grid panel flanked by engraved openwork sides.",
      aboutItem:
        "Bold, charismatic, and substantial in weight. Ideal for gentlemen with an appreciation for refined jewelry artistry.",
      stock: 11,
      soldCount: 6,
      soldHours: 24,
      viewingCount: 14,
      stoneColors: [
        { name: "Yellow Gold", hex: "#E5C278", image: "/images/product_4_main.png" },
        { name: "White Gold", hex: "#E0E0E0", image: "/images/product_4_main.png" },
      ],
      stoneShapes: [
        { name: "Square Princess", shapeId: "cushion" },
        { name: "Round Brilliant", shapeId: "round" },
      ],
      sizes: ["16", "18", "20", "22", "24"],
      purityOptions: ["18KT", "22KT"],
      specifications: [
        { label: "Product Code", value: "ZH-PROD-4" },
        { label: "Gold Purity", value: "22 KT Hallmarked Yellow Gold" },
        { label: "Diamonds", value: "0.25 Ct Natural Diamonds" },
      ],
      isAvailable: true,
      isFeatured: true,
      isBestSeller: false,
    },
    {
      slug: "infinity-bracelet",
      title: "Infinity Diamond Bracelet In Rose Gold",
      price: "₹58,999",
      compareAtPrice: "₹65,000",
      priceNum: 58999,
      rating: 5.0,
      reviewsCount: 42,
      primaryImage: "/images/ad_necklace.png",
      hoverImage: "/images/bracelet_hotsell_jewel.jpg",
      additionalImages: [
        "/images/ad_necklace.png",
        "/images/bracelet_hotsell_jewel.jpg",
        "/images/category_bracelet.jpg",
      ],
      galleryImages: [
        "/images/ad_necklace.png",
        "/images/bracelet_hotsell_jewel.jpg",
        "/images/category_bracelet.jpg",
      ],
      category: "Diamond Bracelets",
      gender: "women",
      metal: "18kt Rose Gold",
      gemstone: "Natural Diamond",
      description:
        "Interlocking oval paperclip link bracelet set with micropavé brilliant round cut diamonds and signature logo charm.",
      aboutItem:
        "An exquisite everyday statement of understated luxury. Precision articulated links contour smoothly against the wrist.",
      stock: 18,
      isAvailable: true,
      isFeatured: true,
      isBestSeller: true,
    },
    {
      slug: "teardrop-pendant",
      title: "Teardrop Pear Diamond Pendant Necklace",
      price: "₹34,500",
      compareAtPrice: "₹39,000",
      priceNum: 34500,
      rating: 4.9,
      reviewsCount: 27,
      primaryImage: "/images/category_pendant.jpg",
      hoverImage: "/images/ad_banner_necklace_full.jpg",
      additionalImages: [
        "/images/category_pendant.jpg",
        "/images/ad_banner_necklace_full.jpg",
      ],
      galleryImages: [
        "/images/category_pendant.jpg",
        "/images/ad_banner_necklace_full.jpg",
      ],
      category: "Necklaces & Pendants",
      gender: "women",
      metal: "18kt Rose Gold",
      gemstone: "Natural Diamond",
      description:
        "A magnificent pear cut natural diamond suspended gracefully on an 18kt rose gold diamond-cut cable chain.",
      aboutItem:
        "Timeless drop elegance that accentuates the collarbone. Comes with adjustable 16-18 inch delicate link chain.",
      stock: 22,
      isAvailable: true,
      isFeatured: true,
      isBestSeller: true,
    },
    {
      slug: "mens-monarch-signet",
      title: "The Monarch 18kt Diamond Men's Signet Ring",
      brand: "ZHAEVAAH FINE JEWELLERY",
      price: "₹38,500 – ₹58,000",
      compareAtPrice: "₹45,000",
      discountBadge: "-14%",
      priceNum: 38500,
      rating: 5.0,
      reviewsCount: 38,
      primaryImage: "/images/product_4_main.png",
      hoverImage: "/images/product_4_hover.jpg",
      additionalImages: [
        "/images/product_4_main.png",
        "/images/product_4_hover.jpg",
        "/images/category_rings.jpg",
      ],
      galleryImages: [
        "/images/product_4_main.png",
        "/images/product_4_hover.jpg",
      ],
      category: "Men's Rings",
      gender: "men",
      metal: "18kt Yellow Gold",
      gemstone: "Natural Diamond",
      description:
        "The Sovereign Monarch Signet Ring, featuring an imperial crest studded with brilliant natural diamonds set in heavy 18kt gold.",
      aboutItem:
        "Engineered with a solid interior comfort-fit shank. An heirloom statement of authority, refinement, and legacy.",
      stock: 12,
      soldCount: 9,
      soldHours: 16,
      viewingCount: 24,
      sizes: ["16", "18", "20", "22", "24"],
      purityOptions: ["18KT", "22KT"],
      isAvailable: true,
      isFeatured: true,
      isBestSeller: true,
    },
    {
      slug: "mens-royal-cuban-kada",
      title: "Royal Men's 18kt Gold & Diamond Cuban Link Kada",
      brand: "ZHAEVAAH FINE JEWELLERY",
      price: "₹76,000 – ₹98,000",
      compareAtPrice: "₹88,000",
      discountBadge: "-12%",
      priceNum: 76000,
      rating: 4.9,
      reviewsCount: 22,
      primaryImage: "/images/bracelet_hotsell_jewel.jpg",
      hoverImage: "/images/bracelet_hotsell_banner.jpg",
      additionalImages: [
        "/images/bracelet_hotsell_jewel.jpg",
        "/images/category_bracelet.jpg",
      ],
      galleryImages: [
        "/images/bracelet_hotsell_jewel.jpg",
        "/images/bracelet_hotsell_banner.jpg",
      ],
      category: "Men's Bracelets & Kadas",
      gender: "men",
      metal: "18kt Yellow Gold",
      gemstone: "Natural Diamond",
      description:
        "A commanding handcrafted solid gold Cuban link Kada with precision diamond-pavé clasp bar.",
      aboutItem:
        "Features a dual-safety hinge lock mechanism. Weighs substantial grams with flawless mirror polish.",
      stock: 8,
      soldCount: 5,
      soldHours: 24,
      viewingCount: 19,
      purityOptions: ["18KT", "22KT"],
      isAvailable: true,
      isFeatured: true,
      isBestSeller: true,
    },
    {
      slug: "mens-sovereign-curb-chain",
      title: "Heritage 18kt Gold Diamond Curb Chain",
      brand: "ZHAEVAAH FINE JEWELLERY",
      price: "₹64,500 – ₹82,000",
      compareAtPrice: "₹74,000",
      discountBadge: "-12%",
      priceNum: 64500,
      rating: 4.8,
      reviewsCount: 17,
      primaryImage: "/images/category_pendant.jpg",
      hoverImage: "/images/ad_banner_necklace_full.jpg",
      additionalImages: [
        "/images/category_pendant.jpg",
        "/images/ad_banner_necklace_full.jpg",
      ],
      galleryImages: [
        "/images/category_pendant.jpg",
        "/images/ad_banner_necklace_full.jpg",
      ],
      category: "Chains & Pendants",
      gender: "men",
      metal: "18kt Yellow Gold",
      gemstone: "Natural Diamond",
      description:
        "Heavy diamond-cut curb links forged in 18kt yellow gold, reflecting light with bold masculine brilliance.",
      aboutItem:
        "22-inch length with fortified lobster clasp. Finished with micro-pavé diamond accent links.",
      stock: 14,
      soldCount: 8,
      soldHours: 20,
      viewingCount: 21,
      purityOptions: ["18KT", "22KT"],
      isAvailable: true,
      isFeatured: true,
      isBestSeller: false,
    },
    {
      slug: "mens-imperial-cufflinks",
      title: "Imperial Onyx & Diamond Tuxedo Cufflinks",
      brand: "ZHAEVAAH FINE JEWELLERY",
      price: "₹29,999",
      compareAtPrice: "₹35,000",
      discountBadge: "-14%",
      priceNum: 29999,
      rating: 5.0,
      reviewsCount: 15,
      primaryImage: "/images/product_4_hover.jpg",
      hoverImage: "/images/product_4_main.png",
      additionalImages: [
        "/images/product_4_hover.jpg",
        "/images/product_4_main.png",
      ],
      galleryImages: [
        "/images/product_4_hover.jpg",
        "/images/product_4_main.png",
      ],
      category: "Cufflinks & Accents",
      gender: "men",
      metal: "18kt White Gold",
      gemstone: "Natural Diamond & Black Onyx",
      description:
        "Octagonal black onyx cabochons bordered by a halo of micro-prong brilliant diamonds in 18kt white gold.",
      aboutItem:
        "The consummate black-tie formal accessory. Engineered with smooth swivel-back closures.",
      stock: 16,
      soldCount: 11,
      soldHours: 18,
      viewingCount: 16,
      purityOptions: ["18KT White Gold", "Platinum 950"],
      isAvailable: true,
      isFeatured: true,
      isBestSeller: true,
    },
    {
      slug: "womens-rose-gold-necklace",
      title: "Women's Rose Gold Flower Clover Diamond Necklace",
      brand: "ZHAEVAAH FINE JEWELLERY",
      price: "₹38,500 – ₹42,000",
      compareAtPrice: "₹46,000",
      discountBadge: "-10%",
      priceNum: 38500,
      rating: 5.0,
      reviewsCount: 41,
      primaryImage: "/images/ad_necklace.png",
      hoverImage: "/images/ad_banner_necklace_full.jpg",
      additionalImages: [
        "/images/ad_necklace.png",
        "/images/ad_banner_necklace_full.jpg",
      ],
      galleryImages: [
        "/images/ad_necklace.png",
        "/images/ad_banner_necklace_full.jpg",
      ],
      category: "Necklaces & Pendants",
      gender: "women",
      metal: "18kt Rose Gold",
      gemstone: "Natural Diamond",
      description:
        "An iconic 4-leaf clover motif encrusted with brilliant pavé diamonds around a floating solitaire center.",
      aboutItem:
        "Symbolizing luck, prosperity, and everlasting grace. Delicately hangs on a 18kt rose gold Singapore chain.",
      stock: 25,
      soldCount: 19,
      soldHours: 12,
      viewingCount: 35,
      purityOptions: ["18KT Rose Gold", "18KT Yellow Gold"],
      isAvailable: true,
      isFeatured: true,
      isBestSeller: true,
    },
    {
      slug: "womens-celestial-earrings",
      title: "Celestial 18kt White Gold Diamond Stud Earrings",
      brand: "ZHAEVAAH FINE JEWELLERY",
      price: "₹27,500",
      compareAtPrice: "₹32,000",
      discountBadge: "-14%",
      priceNum: 27500,
      rating: 4.9,
      reviewsCount: 26,
      primaryImage: "/images/ring_blue_topaz_thumb3.jpg",
      hoverImage: "/images/ring_blue_topaz_thumb4.jpg",
      additionalImages: [
        "/images/ring_blue_topaz_thumb3.jpg",
        "/images/ring_blue_topaz_thumb4.jpg",
      ],
      galleryImages: [
        "/images/ring_blue_topaz_thumb3.jpg",
        "/images/ring_blue_topaz_thumb4.jpg",
      ],
      category: "Earrings",
      gender: "women",
      metal: "18kt White Gold",
      gemstone: "Natural Diamond",
      description:
        "Floral starburst diamond cluster studs set in 18kt white gold with secure screw-back posts.",
      aboutItem:
        "Effortless day-to-night sparkle. Perfect for sensitive skin with certified hypoallergenic hallmarked gold.",
      stock: 20,
      soldCount: 14,
      soldHours: 20,
      viewingCount: 28,
      purityOptions: ["14KT", "18KT"],
      isAvailable: true,
      isFeatured: true,
      isBestSeller: true,
    },
  ];

  for (const item of productsToSeed) {
    await prisma.product.upsert({
      where: { slug: item.slug },
      update: item,
      create: item,
    });
    console.log(`✓ Seeded Product: ${item.title}`);
  }

  // 5. Seed Demo Order for Customer
  const existingOrders = await prisma.order.count({ where: { userId: customer.id } });
  if (existingOrders === 0) {
    await prisma.order.create({
      data: {
        orderNumber: "ZH-94821",
        userId: customer.id,
        customerName: customer.name,
        customerEmail: customer.email,
        customerPhone: customer.phone || "+91 98201 54321",
        shippingAddress: {
          name: customer.name,
          street: "Flat 1402, Tower B, Oberoi Sky Heights",
          locality: "Lokhandwala Complex, Andheri West",
          city: "Mumbai",
          state: "Maharashtra",
          pincode: "400053",
          type: "Home",
        },
        items: [
          {
            productId: "prod-1",
            title: "Real Diamond Jewellery Gold Diamond Ring",
            image: "/images/product_1_main.png",
            price: 24999,
            quantity: 1,
            specs: "18kt Yellow Gold • Size 14 • IGI Certified IJ-SI",
          },
        ],
        subtotal: 24999,
        discount: 0,
        shippingFee: 0,
        totalAmount: 24999,
        currency: "INR",
        paymentMethod: "Credit Card (HDFC Regalia)",
        paymentStatus: "PAID",
        orderStatus: "IN_TRANSIT",
        carrier: "BlueDart Air",
        trackingNumber: "BLUEDART-AIR-94820194",
        deliveryEstimate: "Tomorrow by 2:00 PM",
        trackingTimeline: [
          {
            status: "CONFIRMED",
            title: "Order Placed & Confirmed",
            description: "Your order has been verified and registered into ZHAEVAAH atelier queue.",
            timestamp: "2026-11-10T09:30:00.000Z",
            completed: true,
          },
          {
            status: "PROCESSING",
            title: "BIS Hallmark Certification",
            description: "Artisans certifying 18kt purity and natural diamond grading.",
            timestamp: "2026-11-11T11:15:00.000Z",
            completed: true,
          },
          {
            status: "SHIPPED",
            title: "Dispatched via BlueDart Air Priority",
            description: "Insured secure delivery parcel with AWB #BLUEDART-AIR-94820194.",
            timestamp: "2026-11-11T16:45:00.000Z",
            completed: true,
          },
          {
            status: "IN_TRANSIT",
            title: "In Transit to Mumbai Sorting Facility",
            description: "Flight departed Mumbai Air Cargo Hub.",
            timestamp: "2026-11-12T03:20:00.000Z",
            completed: true,
            current: true,
          },
          {
            status: "DELIVERED",
            title: "Delivered & Signed",
            description: "Tamper-proof signature delivery at your doorstep.",
            timestamp: "",
            completed: false,
          },
        ],
      },
    });
    console.log(`✓ Seeded Demo Order #ZH-94821 for ${customer.name}`);
  }

  console.log("\n======================================================");
  console.log("✨ ZHAEVAAH Database Seeding Completed Successfully!");
  console.log("======================================================\n");
}

main()
  .catch((e) => {
    console.error("Seeding failed:", e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });

