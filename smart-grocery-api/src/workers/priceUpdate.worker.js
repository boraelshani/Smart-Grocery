import { env } from "../config/env.js";
import { autoUpdateStoreProducts } from "../services/scraper.service.js";

let timer;

export const startPriceUpdateWorker = () => {
  const intervalMs = Math.max(5, env.scrapeConcurrency) * 60 * 1000;

  const run = async () => {
    try {
      await autoUpdateStoreProducts();
    } catch (_err) {
      // Intentionally swallow to keep worker alive.
    }
  };

  timer = setInterval(run, intervalMs);
  run();
};

export const stopPriceUpdateWorker = () => {
  if (timer) {
    clearInterval(timer);
  }
};
