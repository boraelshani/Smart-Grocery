import Joi from "joi";
import { randomUUID } from "crypto";
import { Brand, Category, ScraperRule, Store } from "../models/index.js";
import { validateBody } from "../middleware/validate.js";
import { buildCategoryPath } from "../services/category.service.js";
import { createOrUpdateStoreProduct, createProduct } from "../services/product.service.js";

const storeSchema = Joi.object({
  storeId: Joi.string().required(),
  name: Joi.string().required(),
  logoUrl: Joi.string().allow(null).optional(),
  website: Joi.string().allow(null).optional(),
  country: Joi.string().required(),
  languages_available: Joi.array().items(Joi.string().valid("en", "de")).required(),
  apiAvailable: Joi.boolean().required(),
  scrapingRequired: Joi.boolean().required()
});

const brandSchema = Joi.object({
  brandId: Joi.string().required(),
  name: Joi.string().required(),
  logoUrl: Joi.string().allow(null).optional(),
  website: Joi.string().allow(null).optional()
});

const categorySchema = Joi.object({
  categoryId: Joi.string().required(),
  name_en: Joi.string().required(),
  name_de: Joi.string().required(),
  slug: Joi.string().required(),
  parentId: Joi.string().allow(null).optional()
});

const productSchema = Joi.object({
  productId: Joi.string().required(),
  name_en: Joi.string().required(),
  name_de: Joi.string().required(),
  brandId: Joi.string().required(),
  categoryId: Joi.string().required(),
  unitSize: Joi.string().allow(null).optional(),
  barcode: Joi.string().allow(null).optional(),
  defaultImageUrl: Joi.string().allow(null).optional(),
  legalImageStatus: Joi.string().valid("open-source", "user-submitted", "placeholder").required(),
  labels: Joi.array().items(Joi.string()).default([]),
  description_en: Joi.string().allow(null).optional(),
  description_de: Joi.string().allow(null).optional()
});

const storeProductSchema = Joi.object({
  storeProductId: Joi.string().required(),
  productId: Joi.string().required(),
  storeId: Joi.string().required(),
  productPageUrl: Joi.string().required(),
  extractedImageUrl: Joi.string().allow(null).optional(),
  basePrice: Joi.number().min(0).required(),
  promoPrice: Joi.number().min(0).allow(null).optional(),
  multiBuy: Joi.object({
    type: Joi.string().valid("none", "x_for_y", "quantity_discount", "percentage_off").required(),
    details: Joi.object().default({})
  }).required(),
  isAvailable: Joi.boolean().required(),
  lastScrapeStatus: Joi.string().valid("ok", "partial", "failed", "blocked", "not_found").required(),
  offerStart: Joi.date().allow(null).optional(),
  offerEnd: Joi.date().allow(null).optional(),
  stockStatus: Joi.string().valid("in_stock", "low_stock", "out_of_stock", "unknown").required(),
  unitPriceComparison: Joi.object({
    value: Joi.number().allow(null).optional(),
    unit: Joi.string().allow(null).optional()
  }).required()
});

const scraperRuleSchema = Joi.object({
  storeId: Joi.string().required(),
  productNameSelector: Joi.string().required(),
  basePriceSelector: Joi.string().required(),
  promoPriceSelector: Joi.string().allow(null).optional(),
  availabilitySelector: Joi.string().required(),
  imageSelector: Joi.string().allow(null).optional(),
  offerSelector: Joi.string().allow(null).optional(),
  multiBuySelector: Joi.string().allow(null).optional(),
  requiresJSRendering: Joi.boolean().required()
});

export const validateStore = validateBody(storeSchema);
export const validateBrand = validateBody(brandSchema);
export const validateCategory = validateBody(categorySchema);
export const validateProduct = validateBody(productSchema);
export const validateStoreProduct = validateBody(storeProductSchema);
export const validateScraperRule = validateBody(scraperRuleSchema);

export const upsertStore = async (req, res, next) => {
  try {
    await Store.updateOne({ storeId: req.body.storeId }, { $set: req.body }, { upsert: true });
    const row = await Store.findOne({ storeId: req.body.storeId }).lean();
    res.status(201).json(row);
  } catch (err) {
    next(err);
  }
};

export const upsertBrand = async (req, res, next) => {
  try {
    await Brand.updateOne({ brandId: req.body.brandId }, { $set: req.body }, { upsert: true });
    const row = await Brand.findOne({ brandId: req.body.brandId }).lean();
    res.status(201).json(row);
  } catch (err) {
    next(err);
  }
};

export const upsertCategory = async (req, res, next) => {
  try {
    await Category.updateOne({ categoryId: req.body.categoryId }, { $set: req.body }, { upsert: true });
    const pathData = await buildCategoryPath(req.body.categoryId);
    await Category.updateOne({ categoryId: req.body.categoryId }, { $set: pathData });
    const row = await Category.findOne({ categoryId: req.body.categoryId }).lean();
    res.status(201).json(row);
  } catch (err) {
    next(err);
  }
};

export const createProductFromAdmin = async (req, res, next) => {
  try {
    const row = await createProduct(req.body);
    res.status(201).json(row);
  } catch (err) {
    next(err);
  }
};

export const upsertStoreProductFromAdmin = async (req, res, next) => {
  try {
    const row = await createOrUpdateStoreProduct(req.body);
    res.status(201).json(row);
  } catch (err) {
    next(err);
  }
};

export const upsertScraperRule = async (req, res, next) => {
  try {
    await ScraperRule.updateOne(
      { storeId: req.body.storeId },
      { $set: { ...req.body, updatedAt: new Date() } },
      { upsert: true }
    );

    const row = await ScraperRule.findOne({ storeId: req.body.storeId }).lean();
    res.status(201).json(row);
  } catch (err) {
    next(err);
  }
};

export const seedQuickExample = async (_req, res, next) => {
  try {
    const payload = {
      categoryId: `cat_${randomUUID().slice(0, 8)}`,
      name_en: "Dairy",
      name_de: "Molkerei",
      slug: `dairy-${Date.now()}`,
      parentId: null
    };

    await Category.create(payload);
    const row = await Category.findOne({ categoryId: payload.categoryId }).lean();
    res.status(201).json(row);
  } catch (err) {
    next(err);
  }
};
