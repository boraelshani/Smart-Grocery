import dotenv from "dotenv";

dotenv.config();

export const env = {
  nodeEnv: process.env.NODE_ENV || "development",
  port: Number(process.env.PORT || 5050),
  mongoUri: process.env.MONGODB_URI,
  jwtSecret: process.env.JWT_SECRET || "dev-secret",
  adminJwtSecret: process.env.ADMIN_JWT_SECRET || process.env.JWT_SECRET || "dev-admin-secret",
  redisUrl: process.env.REDIS_URL || "redis://localhost:6379",
  enableRedis: String(process.env.ENABLE_REDIS || "false") === "true",
  scrapeConcurrency: Number(process.env.SCRAPE_CONCURRENCY || 5),
  defaultLanguage: process.env.DEFAULT_LANGUAGE || "en"
};
