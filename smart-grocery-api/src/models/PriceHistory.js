import mongoose from "mongoose";

const PriceHistorySchema = new mongoose.Schema(
  {
    historyId: { type: String, required: true, unique: true, trim: true },
    storeProductId: { type: String, required: true, index: true },
    storeProductRef: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "StoreProduct",
      default: null,
      index: true
    },
    oldPrice: { type: Number, default: null },
    newPrice: { type: Number, required: true },
    promoPrice: { type: Number, default: null },
    timestamp: { type: Date, default: Date.now, index: true }
  },
  { timestamps: false }
);

PriceHistorySchema.index({ storeProductId: 1, timestamp: -1 });

export const PriceHistory = mongoose.model("PriceHistory", PriceHistorySchema);
