import mongoose from "mongoose";

const MultiBuySchema = new mongoose.Schema(
  {
    type: {
      type: String,
      enum: ["none", "x_for_y", "quantity_discount", "percentage_off"],
      default: "none"
    },
    details: { type: mongoose.Schema.Types.Mixed, default: {} }
  },
  { _id: false }
);

const UnitPriceSchema = new mongoose.Schema(
  {
    value: { type: Number, default: null },
    unit: { type: String, default: null }
  },
  { _id: false }
);

const StoreProductSchema = new mongoose.Schema(
  {
    storeProductId: { type: String, required: true, unique: true, trim: true },
    productId: { type: String, required: true, index: true },
    productRef: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Product",
      default: null,
      index: true
    },
    storeId: { type: String, required: true, index: true },
    storeRef: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Store",
      default: null,
      index: true
    },
    productPageUrl: { type: String, required: true },
    extractedImageUrl: { type: String, default: null },
    basePrice: { type: Number, required: true, min: 0 },
    promoPrice: { type: Number, default: null, min: 0 },
    multiBuy: { type: MultiBuySchema, default: () => ({ type: "none", details: {} }) },
    isAvailable: { type: Boolean, default: true },
    lastScrapeStatus: {
      type: String,
      enum: ["ok", "partial", "failed", "blocked", "not_found"],
      default: "ok"
    },
    offerStart: { type: Date, default: null },
    offerEnd: { type: Date, default: null },
    lastPriceUpdate: { type: Date, default: Date.now },
    stockStatus: {
      type: String,
      enum: ["in_stock", "low_stock", "out_of_stock", "unknown"],
      default: "unknown"
    },
    unitPriceComparison: { type: UnitPriceSchema, default: () => ({}) },
    crawlHash: { type: String, default: null }
  },
  { timestamps: true }
);

StoreProductSchema.index({ productId: 1 });
StoreProductSchema.index({ storeId: 1 });
StoreProductSchema.index({ productId: 1, storeId: 1 }, { unique: true });
StoreProductSchema.index({ basePrice: 1, promoPrice: 1 });
StoreProductSchema.index({ isAvailable: 1, lastPriceUpdate: -1 });

export const StoreProduct = mongoose.model("StoreProduct", StoreProductSchema);
