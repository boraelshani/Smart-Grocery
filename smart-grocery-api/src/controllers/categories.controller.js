import { cache } from "../config/cache.js";
import { getCategoryTree } from "../services/category.service.js";

export const getCategories = async (_req, res, next) => {
  try {
    const key = "category-tree";
    const cached = await cache.get(key);
    if (cached) {
      return res.json(cached);
    }

    const rows = await getCategoryTree();
    await cache.set(key, rows, 600);
    return res.json(rows);
  } catch (err) {
    return next(err);
  }
};
