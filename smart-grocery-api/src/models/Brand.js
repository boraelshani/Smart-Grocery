import mongoose from "mongoose";

const BrandSchema = new mongoose.Schema(
  {
    brandId: { type: String, required: true, unique: true, trim: true },
    name: { type: String, required: true, trim: true },
    logoUrl: { type: String, default: null },
    website: { type: String, default: null }
  },
  { timestamps: true }
);

BrandSchema.index({ brandId: 1 });
BrandSchema.index({ name: 1 });

export const Brand = mongoose.model("Brand", BrandSchema);
