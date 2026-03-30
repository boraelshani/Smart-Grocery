import { buildCategoryExplorerPipeline } from "../aggregations/pipelines.js";
import { cache } from "../config/cache.js";
import { Product, StoreProduct } from "../models/index.js";
import { buildCategoryPath } from "./category.service.js";
import { recalculateProductLabels } from "./label.service.js";
import { updateCheapestStoreProjection } from "./pricing.service.js";

export const createProduct = async (payload) => {
  const category = await buildCategoryPath(payload.categoryId);

  const product = await Product.create({
    ...payload,
    categoryPath: category.path
  });

  await recalculateProductLabels(product.productId);
  return product.toObject();
};

export const createOrUpdateStoreProduct = async (payload) => {
  const now = new Date();
  const update = {
    ...payload,
    lastPriceUpdate: now
  };

  await StoreProduct.updateOne(
    { storeProductId: payload.storeProductId },
    { $set: update },
    { upsert: true }
  );

  await updateCheapestStoreProjection(payload.productId);
  await recalculateProductLabels(payload.productId);

  await cache.del(`product:${payload.productId}`);
  return StoreProduct.findOne({ storeProductId: payload.storeProductId }).lean();
};

export const getProductDetail = async (productId) => {
  const cacheKey = `product:${productId}`;
  const cached = await cache.get(cacheKey);
  if (cached) {
    return cached;
  }

  const product = await Product.findOne({ productId }).lean();
  if (!product) {
    throw Object.assign(new Error("Product not found"), { status: 404 });
  }

  const offers = await StoreProduct.find({ productId, isAvailable: true })
    .sort({ promoPrice: 1, basePrice: 1 })
    .lean();

  const result = { ...product, offers };
  await cache.set(cacheKey, result, 180);
  return result;
};

export const exploreProducts = async (filters) => {
  const pipeline = buildCategoryExplorerPipeline(filters);
  return Product.aggregate(pipeline);
};
