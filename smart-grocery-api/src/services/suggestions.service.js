import { Product, StoreProduct } from "../models/index.js";
import { effectivePrice } from "./pricing.service.js";

export const getSuggestionsForProduct = async (productId) => {
  const source = await Product.findOne({ productId }).lean();
  if (!source) {
    throw Object.assign(new Error("Product not found"), { status: 404 });
  }

  const sourceOffers = await StoreProduct.find({ productId, isAvailable: true }).lean();
  const sourceBest = sourceOffers.reduce((acc, row) => {
    const p = effectivePrice(row);
    return p < acc ? p : acc;
  }, Number.MAX_SAFE_INTEGER);

  const sameCategoryProducts = await Product.find({
    categoryId: source.categoryId,
    productId: { $ne: productId }
  })
    .select({ productId: 1, name_en: 1, name_de: 1, labels: 1, categoryId: 1 })
    .limit(20)
    .lean();

  const candidateIds = sameCategoryProducts.map((p) => p.productId);
  const offers = await StoreProduct.find({
    productId: { $in: candidateIds },
    isAvailable: true
  }).lean();

  const cheapestByProduct = new Map();
  for (const offer of offers) {
    const price = effectivePrice(offer);
    const current = cheapestByProduct.get(offer.productId);
    if (!current || price < current.price) {
      cheapestByProduct.set(offer.productId, { price, storeId: offer.storeId, offer });
    }
  }

  const cheaperAlternatives = [];
  const betterDeals = [];

  for (const product of sameCategoryProducts) {
    const result = cheapestByProduct.get(product.productId);
    if (!result) {
      continue;
    }

    if (result.price < sourceBest) {
      cheaperAlternatives.push({ product, ...result });
    }

    if (result.offer.multiBuy?.type && result.offer.multiBuy.type !== "none") {
      betterDeals.push({ product, ...result });
    }
  }

  return {
    sourceProductId: productId,
    cheaperAlternatives: cheaperAlternatives.slice(0, 10),
    sameCategoryProducts: sameCategoryProducts.slice(0, 10),
    betterDeals: betterDeals.slice(0, 10),
    multiBuyOptimization: betterDeals.slice(0, 5)
  };
};
