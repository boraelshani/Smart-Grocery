import mongoose from "mongoose";

const ListItemSchema = new mongoose.Schema(
  {
    productId: { type: String, required: true, index: true },
    storeId: { type: String, default: null, index: true },
    quantity: { type: Number, min: 0.01, default: 1 },
    checked: { type: Boolean, default: false },
    unitPrice: { type: Number, default: 0 },
    lineTotal: { type: Number, default: 0 }
  },
  { _id: false }
);

const ListSchema = new mongoose.Schema(
  {
    listId: { type: String, required: true, unique: true, trim: true },
    userId: { type: String, required: true, index: true },
    userRef: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      default: null,
      index: true
    },
    name: { type: String, required: true, trim: true, maxlength: 100 },
    items: { type: [ListItemSchema], default: [] },
    totalPrice: { type: Number, default: 0 },
    shared: { type: Boolean, default: false },
    shareCode: { type: String, default: null, index: true }
  },
  { timestamps: true }
);

ListSchema.index({ userId: 1 });
ListSchema.index({ shareCode: 1 }, { sparse: true });

export const List = mongoose.model("List", ListSchema);
