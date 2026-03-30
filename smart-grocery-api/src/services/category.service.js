import { Category } from "../models/index.js";

export const buildCategoryPath = async (categoryId) => {
  const category = await Category.findOne({ categoryId }).lean();
  if (!category) {
    throw Object.assign(new Error("Category not found"), { status: 404 });
  }

  if (category.path?.length && category.fullPathNames?.length) {
    return { path: category.path, fullPathNames: category.fullPathNames };
  }

  const trail = [];
  const fullPathNames = [];
  let cursor = category;

  while (cursor) {
    trail.unshift(cursor.categoryId);
    fullPathNames.unshift({
      categoryId: cursor.categoryId,
      name_en: cursor.name_en,
      name_de: cursor.name_de,
      slug: cursor.slug
    });

    if (!cursor.parentId) {
      break;
    }

    cursor = await Category.findOne({ categoryId: cursor.parentId }).lean();
  }

  await Category.updateOne(
    { categoryId },
    { $set: { path: trail, fullPathNames } }
  );

  return { path: trail, fullPathNames };
};

export const getCategoryTree = async () => {
  const categories = await Category.find().sort({ path: 1, name_en: 1 }).lean();
  return categories;
};
