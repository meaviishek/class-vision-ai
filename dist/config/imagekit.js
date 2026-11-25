"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getImageKitAuthParams = exports.getImageKitUrlEndpoint = exports.getImageKitClient = exports.imagekit = void 0;
const imagekit_1 = __importDefault(require("imagekit"));
const publicKey = process.env.IMAGEKIT_PUBLIC_KEY || "public_bAZTn/7Z+W6H7p6+YpViQFOIKEc=";
const privateKey = process.env.IMAGEKIT_PRIVATE_KEY || "private_MFQIGe0oB6z5ohWQjXdIG0bMlgQ=";
const id = process.env.IMAGEKIT_ID || "itsgcsspk";
const urlEndpoint = process.env.IMAGEKIT_URL_ENDPOINT || `https://ik.imagekit.io/${id}`;
exports.imagekit = new imagekit_1.default({
    publicKey,
    privateKey,
    urlEndpoint,
});
const getImageKitClient = () => exports.imagekit;
exports.getImageKitClient = getImageKitClient;
const getImageKitUrlEndpoint = () => urlEndpoint;
exports.getImageKitUrlEndpoint = getImageKitUrlEndpoint;
const getImageKitAuthParams = () => {
    return exports.imagekit.getAuthenticationParameters();
};
exports.getImageKitAuthParams = getImageKitAuthParams;
exports.default = exports.imagekit;
