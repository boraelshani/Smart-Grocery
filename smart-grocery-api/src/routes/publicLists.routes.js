import { Router } from "express";
import { getPublicLists } from "../controllers/publicLists.controller.js";

export const publicListsRouter = Router();

publicListsRouter.get("/", getPublicLists);
