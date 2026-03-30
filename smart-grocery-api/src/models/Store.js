import mongoose from "mongoose";

const StoreSchema = new mongoose.Schema(
  {
    storeId: { type: String, required: true, unique: true, trim: true },
    name: { type: String, required: true, trim: true },
    logoUrl: { type: String, default: null },
    website: { type: String, default: null },
    country: { type: String, required: true, trim: true },
    languages_available: {
      type: [String],
      enum: ["en", "de"],
      default: ["en"]
    },
    apiAvailable: { type: Boolean, default: false },
    scrapingRequired: { type: Boolean, default: true }
  },
  { timestamps: true }
);

StoreSchema.index({ storeId: 1 });
StoreSchema.index({ name: 1 });

export const Store = mongoose.model("Store", StoreSchema);
