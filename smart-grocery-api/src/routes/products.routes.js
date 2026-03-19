import { Router } from "express";
import {
  exploreCategoryProducts,
  getProductById,
  getProductSuggestions
} from "../controllers/products.controller.js";

export const productsRouter = Router();

productsRouter.get("/explore", exploreCategoryProducts);
productsRouter.get("/:productId", getProductById);
productsRouter.get("/:productId/suggestions", getProductSuggestions);
