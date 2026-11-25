import ImageKit from "imagekit";

const publicKey =
  process.env.IMAGEKIT_PUBLIC_KEY || "public_bAZTn/7Z+W6H7p6+YpViQFOIKEc=";
const privateKey =
  process.env.IMAGEKIT_PRIVATE_KEY || "private_MFQIGe0oB6z5ohWQjXdIG0bMlgQ=";
const id = process.env.IMAGEKIT_ID || "itsgcsspk";
const urlEndpoint =
  process.env.IMAGEKIT_URL_ENDPOINT || `https://ik.imagekit.io/${id}`;

export const imagekit = new ImageKit({
  publicKey,
  privateKey,
  urlEndpoint,
});

export const getImageKitClient = (): ImageKit => imagekit;

export const getImageKitUrlEndpoint = (): string => urlEndpoint;

export const getImageKitAuthParams = () => {
  return imagekit.getAuthenticationParameters();
};

export default imagekit;
