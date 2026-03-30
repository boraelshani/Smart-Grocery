import mongoose from "mongoose";

const labelEnum = [
  "new",
  "popular",
  "on_sale",
  "limited",
  "eco_friendly",
  "trending"
];

const ProductSchema = new mongoose.Schema(
  {
    productId: { type: String, required: true, unique: true, trim: true },
    name_en: { type: String, required: true, trim: true },
    name_de: { type: String, required: true, trim: true },
    brandId: { type: String, required: true, index: true },
    brandRef: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Brand",
      default: null,
      index: true
    },
    categoryId: { type: String, required: true, index: true },
    categoryRef: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Category",
      default: null,
      index: true
    },
    categoryPath: { type: [String], default: [] },
    unitSize: { type: String, default: null },
    barcode: { type: String, default: null },
    defaultImageUrl: { type: String, default: null },
    legalImageStatus: {
      type: String,
      enum: ["open-source", "user-submitted", "placeholder"],
      default: "placeholder"
    },
    labels: { type: [String], enum: labelEnum, default: [] },
    description_en: { type: String, default: null },
    description_de: { type: String, default: null },
    searchKeywords: { type: [String], default: [] },
    cheapestStoreProductId: { type: String, default: null },
    cheapestPrice: { type: Number, default: null }
  },
  { timestamps: true }
);

ProductSchema.index({ barcode: 1 });
ProductSchema.index({ categoryId: 1 });
ProductSchema.index({ labels: 1 });
ProductSchema.index({ name_en: "text", name_de: "text", description_en: "text", description_de: "text" });

export const Product = mongoose.model("Product", ProductSchema);
