"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.prisma = void 0;
const client_1 = require("@prisma/client");
const dotenv_1 = __importDefault(require("dotenv"));
const path_1 = __importDefault(require("path"));
// 1. Ensure .env is explicitly loaded before PrismaClient initializes
dotenv_1.default.config({ path: path_1.default.join(__dirname, "..", "..", ".env") });
// 2. Guarantee valid MongoDB database name in Atlas connection string
let dbUrl = process.env.DATABASE_URL ||
    "mongodb+srv://zhaevaah_db_user:Xui9zh5RKUYkg5F8@zhaevaah.kmbt1ox.mongodb.net/zhaevaah?retryWrites=true&w=majority";
if (dbUrl.includes("mongodb.net") && !dbUrl.includes("mongodb.net/zhaevaah")) {
    if (dbUrl.includes("mongodb.net/?")) {
        dbUrl = dbUrl.replace("mongodb.net/?", "mongodb.net/zhaevaah?");
    }
    else if (dbUrl.endsWith("mongodb.net/")) {
        dbUrl = `${dbUrl}zhaevaah?retryWrites=true&w=majority`;
    }
    else if (dbUrl.endsWith("mongodb.net")) {
        dbUrl = `${dbUrl}/zhaevaah?retryWrites=true&w=majority`;
    }
}
process.env.DATABASE_URL = dbUrl;
exports.prisma = global.__prisma ||
    new client_1.PrismaClient({
        datasources: {
            db: {
                url: dbUrl,
            },
        },
        log: process.env.NODE_ENV === "development" ? ["warn", "error"] : ["error"],
    });
if (process.env.NODE_ENV !== "production") {
    global.__prisma = exports.prisma;
}
exports.default = exports.prisma;
