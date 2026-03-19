import { Product, ProductMetrics, StoreProduct } from "../models/index.js";

const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;

export const computeLabelsForProduct = async (product) => {
  const labels = new Set(product.labels || []);
  const isNew = Date.now() - new Date(product.createdAt).getTime() < THIRTY_DAYS_MS;

  if (isNew) {
    labels.add("new");
  } else {
    labels.delete("new");
  }

  const onSaleCount = await StoreProduct.countDocuments({
    productId: product.productId,
    promoPrice: { $ne: null },
    isAvailable: true
  });

  if (onSaleCount > 0) {
    labels.add("on_sale");
  } else {
    labels.delete("on_sale");
  }

  const metrics = await ProductMetrics.findOne({ productId: product.productId }).lean();

  if ((metrics?.popularityScore || 0) >= 70) {
    labels.add("popular");
  } else {
    labels.delete("popular");
  }

  if ((metrics?.trendScore || 0) >= 60) {
    labels.add("trending");
  } else {
    labels.delete("trending");
  }

  return [...labels];
};

export const recalculateProductLabels = async (productId) => {
  const product = await Product.findOne({ productId });
  if (!product) {
    return null;
  }

  const labels = await computeLabelsForProduct(product.toObject());
  product.labels = labels;
  await product.save();
  return product.toObject();
};
