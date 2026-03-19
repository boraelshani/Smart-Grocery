import { normalizeLanguage } from "../helpers/localization.js";
import { sanitizePaging } from "../helpers/sanitize.js";
import { getSuggestionsForProduct } from "../services/suggestions.service.js";
import { exploreProducts, getProductDetail } from "../services/product.service.js";

export const getProductById = async (req, res, next) => {
  try {
    const product = await getProductDetail(req.params.productId);
    const lang = normalizeLanguage(req.query.lang);
    res.json({
      ...product,
      displayName: lang === "de" ? product.name_de : product.name_en,
      displayDescription: lang === "de" ? product.description_de : product.description_en
    });
  } catch (err) {
    next(err);
  }
};

export const getProductSuggestions = async (req, res, next) => {
  try {
    const suggestions = await getSuggestionsForProduct(req.params.productId);
    res.json(suggestions);
  } catch (err) {
    next(err);
  }
};

export const exploreCategoryProducts = async (req, res, next) => {
  try {
    const { page, limit, skip } = sanitizePaging(req.query);
    const labels = req.query.labels ? String(req.query.labels).split(",").filter(Boolean) : [];

    const items = await exploreProducts({
      categoryPath: req.query.categoryPath ? String(req.query.categoryPath).split(",").filter(Boolean) : [],
      brandId: req.query.brandId || null,
      labels,
      minPrice: req.query.minPrice ? Number(req.query.minPrice) : undefined,
      maxPrice: req.query.maxPrice ? Number(req.query.maxPrice) : undefined,
      storeId: req.query.storeId || null,
      sortBy: req.query.sortBy || "cheapest",
      skip,
      limit
    });

    res.json({ page, limit, items });
  } catch (err) {
    next(err);
  }
};
