import mongoose from "mongoose";

const ProductMetricsSchema = new mongoose.Schema(
  {
    productId: { type: String, required: true, unique: true, index: true },
    visits: { type: Number, default: 0 },
    addedToLists: { type: Number, default: 0 },
    purchases: { type: Number, default: 0 },
    trendScore: { type: Number, default: 0 },
    popularityScore: { type: Number, default: 0 },
    lastCalculatedAt: { type: Date, default: Date.now }
  },
  { timestamps: true }
);

ProductMetricsSchema.index({ popularityScore: -1 });
ProductMetricsSchema.index({ trendScore: -1 });

export const ProductMetrics = mongoose.model("ProductMetrics", ProductMetricsSchema);
