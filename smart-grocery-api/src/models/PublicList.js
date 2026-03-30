import mongoose from "mongoose";

const PublicListItemSchema = new mongoose.Schema(
  {
    productId: { type: String, required: true },
    storeId: { type: String, default: null },
    quantity: { type: Number, min: 0.01, default: 1 },
    checked: { type: Boolean, default: false },
    unitPrice: { type: Number, default: 0 },
    lineTotal: { type: Number, default: 0 }
  },
  { _id: false }
);

const PublicListSchema = new mongoose.Schema(
  {
    id: { type: String, required: true, unique: true, trim: true },
    type: { type: String, enum: ["template", "user"], required: true },
    name_en: { type: String, required: true, trim: true },
    name_de: { type: String, required: true, trim: true },
    description_en: { type: String, default: null },
    description_de: { type: String, default: null },
    items: { type: [PublicListItemSchema], default: [] },
    creatorUserId: { type: String, default: null, index: true },
    popularityScore: { type: Number, default: 0 }
  },
  { timestamps: { createdAt: true, updatedAt: false } }
);

PublicListSchema.index({ type: 1, popularityScore: -1 });

export const PublicList = mongoose.model("PublicList", PublicListSchema);
