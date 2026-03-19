import mongoose from "mongoose";

const FeedbackSchema = new mongoose.Schema(
  {
    feedbackId: { type: String, required: true, unique: true, trim: true },
    userId: { type: String, default: null, index: true },
    productId: { type: String, default: null, index: true },
    storeProductId: { type: String, default: null, index: true },
    type: {
      type: String,
      enum: [
        "wrong_price",
        "missing_product",
        "wrong_store",
        "image_issue",
        "feature_request",
        "other"
      ],
      required: true,
      index: true
    },
    message: { type: String, required: true, trim: true, maxlength: 2000 },
    status: {
      type: String,
      enum: ["pending", "reviewed", "resolved"],
      default: "pending",
      index: true
    },
    createdAt: { type: Date, default: Date.now }
  },
  { timestamps: false }
);

FeedbackSchema.index({ type: 1, status: 1 });

export const Feedback = mongoose.model("Feedback", FeedbackSchema);
