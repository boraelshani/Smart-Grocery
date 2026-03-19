import { Router } from "express";
import {
  addItemHandler,
  createListHandler,
  publishListHandler,
  recalcListHandler,
  shareListHandler,
  toggleItemHandler,
  validateAddItem,
  validateCreateList,
  validatePublishList,
  validateToggleItem
} from "../controllers/lists.controller.js";
import { requireAuth } from "../middleware/auth.js";

export const listsRouter = Router();

listsRouter.post("/", requireAuth, validateCreateList, createListHandler);
listsRouter.post("/:listId/items", requireAuth, validateAddItem, addItemHandler);
listsRouter.patch("/:listId/items/check", requireAuth, validateToggleItem, toggleItemHandler);
listsRouter.post("/:listId/recalculate", requireAuth, recalcListHandler);
listsRouter.post("/:listId/share", requireAuth, shareListHandler);
listsRouter.post("/:listId/publish", requireAuth, validatePublishList, publishListHandler);
