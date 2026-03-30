import axios from "axios";
import { load } from "cheerio";
import { randomUUID } from "crypto";
import { PriceHistory, ScraperRule, StoreProduct } from "../models/index.js";
import { createOrUpdateStoreProduct } from "./product.service.js";
import { refreshListPricesByProduct } from "./pricing.service.js";
import { recalculateProductLabels } from "./label.service.js";

const toPrice = (raw) => {
  if (!raw) {
    return null;
  }
  const normalized = String(raw).replace(/[^0-9.,-]/g, "").replace(",", ".");
  const value = Number(normalized);
  return Number.isFinite(value) ? value : null;
};

const toMultiBuy = (text) => {
  if (!text) {
    return { type: "none", details: {} };
  }

  const lower = text.toLowerCase();
  const xForY = lower.match(/(\d+)\s*for\s*(\d+)/);
  if (xForY) {
    return { type: "x_for_y", details: { buy: Number(xForY[1]), pay: Number(xForY[2]) } };
  }

  const percent = lower.match(/(\d+)\s*%/);
  if (percent) {
    return { type: "percentage_off", details: { percent: Number(percent[1]) } };
  }

  return { type: "quantity_discount", details: { raw: text } };
};

export const scrapeStoreProduct = async (storeProduct, rule) => {
  const response = await axios.get(storeProduct.productPageUrl, { timeout: 12000 });
  const $ = load(response.data);

  const basePrice = toPrice($(rule.basePriceSelector).first().text());
  const promoPrice = toPrice($(rule.promoPriceSelector).first().text());
  const availableText = $(rule.availabilitySelector).first().text().toLowerCase();
  const isAvailable = !availableText.includes("out") && !availableText.includes("nicht");
  const imageUrl = rule.imageSelector ? $(rule.imageSelector).first().attr("src") || null : null;
  const offerText = rule.offerSelector ? $(rule.offerSelector).first().text().trim() : "";
  const multiBuyText = rule.multiBuySelector ? $(rule.multiBuySelector).first().text().trim() : "";

  return {
    extractedImageUrl: imageUrl,
    basePrice: basePrice ?? storeProduct.basePrice,
    promoPrice,
    isAvailable,
    multiBuy: toMultiBuy(multiBuyText || offerText),
    lastScrapeStatus: "ok",
    offerStart: null,
    offerEnd: null,
    stockStatus: isAvailable ? "in_stock" : "out_of_stock"
  };
};

export const autoUpdateStoreProducts = async () => {
  // Pseudocode execution model:
  // 1) Read all active store products
  // 2) Load scraper rules by store
  // 3) Scrape each product page
  // 4) Persist price changes to PriceHistory
  // 5) Update StoreProducts collection
  // 6) Recalculate impacted user list totals
  // 7) Recompute labels and cheapest projections
  const storeProducts = await StoreProduct.find({}).lean();
  const rules = await ScraperRule.find({}).lean();
  const ruleMap = new Map(rules.map((rule) => [rule.storeId, rule]));

  const summary = {
    total: storeProducts.length,
    updated: 0,
    unchanged: 0,
    failed: 0
  };

  for (const row of storeProducts) {
    const rule = ruleMap.get(row.storeId);
    if (!rule) {
      summary.failed += 1;
      continue;
    }

    try {
      const scraped = await scrapeStoreProduct(row, rule);
      const oldEffective = row.promoPrice ?? row.basePrice;
      const newEffective = scraped.promoPrice ?? scraped.basePrice;
      const changed =
        oldEffective !== newEffective ||
        row.isAvailable !== scraped.isAvailable ||
        row.lastScrapeStatus !== scraped.lastScrapeStatus;

      if (!changed) {
        summary.unchanged += 1;
        continue;
      }

      await PriceHistory.create({
        historyId: `hist_${randomUUID()}`,
        storeProductId: row.storeProductId,
        oldPrice: oldEffective,
        newPrice: newEffective,
        promoPrice: scraped.promoPrice,
        timestamp: new Date()
      });

      await createOrUpdateStoreProduct({
        ...row,
        ...scraped,
        storeProductId: row.storeProductId,
        productId: row.productId,
        storeId: row.storeId,
        productPageUrl: row.productPageUrl
      });

      await refreshListPricesByProduct(row.productId);
      await recalculateProductLabels(row.productId);

      summary.updated += 1;
    } catch (_err) {
      summary.failed += 1;
      await StoreProduct.updateOne(
        { storeProductId: row.storeProductId },
        { $set: { lastScrapeStatus: "failed" } }
      );
    }
  }

  return summary;
};
