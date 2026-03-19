import { Router } from "express";
import { getScraperRules, runScraperUpdate } from "../controllers/scraper.controller.js";
import { requireAdmin } from "../middleware/auth.js";

export const scraperRouter = Router();

scraperRouter.get("/rules", requireAdmin, getScraperRules);
scraperRouter.post("/run", requireAdmin, runScraperUpdate);
