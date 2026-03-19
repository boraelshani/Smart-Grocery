import { Router } from "express";
import { getCategories } from "../controllers/categories.controller.js";

export const categoriesRouter = Router();

categoriesRouter.get("/", getCategories);
