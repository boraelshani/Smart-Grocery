import { ScraperRule } from "../models/index.js";
import { autoUpdateStoreProducts } from "../services/scraper.service.js";

export const runScraperUpdate = async (_req, res, next) => {
  try {
    const summary = await autoUpdateStoreProducts();
    res.json(summary);
  } catch (err) {
    next(err);
  }
};

export const getScraperRules = async (_req, res, next) => {
  try {
    const rows = await ScraperRule.find({}).lean();
    res.json(rows);
  } catch (err) {
    next(err);
  }
};
