import mongoose from "mongoose";

const ScraperRuleSchema = new mongoose.Schema(
  {
    storeId: { type: String, required: true, unique: true, index: true },
    productNameSelector: { type: String, required: true },
    basePriceSelector: { type: String, required: true },
    promoPriceSelector: { type: String, default: null },
    availabilitySelector: { type: String, required: true },
    imageSelector: { type: String, default: null },
    offerSelector: { type: String, default: null },
    multiBuySelector: { type: String, default: null },
    requiresJSRendering: { type: Boolean, default: false },
    updatedAt: { type: Date, default: Date.now }
  },
  { timestamps: false }
);

export const ScraperRule = mongoose.model("ScraperRule", ScraperRuleSchema);
