import { Router } from "express";
import {
  createProductFromAdmin,
  seedQuickExample,
  upsertBrand,
  upsertCategory,
  upsertScraperRule,
  upsertStore,
  upsertStoreProductFromAdmin,
  validateBrand,
  validateCategory,
  validateProduct,
  validateScraperRule,
  validateStore,
  validateStoreProduct
} from "../controllers/admin.controller.js";
import { requireAdmin } from "../middleware/auth.js";

export const adminRouter = Router();

adminRouter.use(requireAdmin);
adminRouter.post("/stores", validateStore, upsertStore);
adminRouter.post("/brands", validateBrand, upsertBrand);
adminRouter.post("/categories", validateCategory, upsertCategory);
adminRouter.post("/products", validateProduct, createProductFromAdmin);
adminRouter.post("/store-products", validateStoreProduct, upsertStoreProductFromAdmin);
adminRouter.post("/scraper-rules", validateScraperRule, upsertScraperRule);
adminRouter.post("/seed-example", seedQuickExample);
