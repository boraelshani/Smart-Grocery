import mongoose from "mongoose";

const CategoryPathNameSchema = new mongoose.Schema(
  {
    categoryId: { type: String, required: true },
    name_en: { type: String, required: true },
    name_de: { type: String, required: true },
    slug: { type: String, required: true }
  },
  { _id: false }
);

const CategorySchema = new mongoose.Schema(
  {
    categoryId: { type: String, required: true, unique: true, trim: true },
    name_en: { type: String, required: true, trim: true },
    name_de: { type: String, required: true, trim: true },
    slug: { type: String, required: true, unique: true, trim: true },
    parentId: { type: String, default: null, index: true },
    parentRef: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Category",
      default: null,
      index: true
    },
    path: { type: [String], default: [] },
    fullPathNames: { type: [CategoryPathNameSchema], default: [] }
  },
  { timestamps: true }
);

CategorySchema.index({ categoryId: 1 });
CategorySchema.index({ path: 1 });
CategorySchema.index({ slug: 1 });

export const Category = mongoose.model("Category", CategorySchema);
