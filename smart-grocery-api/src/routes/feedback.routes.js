import { Router } from "express";
import {
  createFeedback,
  listFeedback,
  resolveFeedback,
  validateCreateFeedback,
  validateUpdateFeedback
} from "../controllers/feedback.controller.js";
import { requireAdmin } from "../middleware/auth.js";

export const feedbackRouter = Router();

feedbackRouter.post("/", validateCreateFeedback, createFeedback);
feedbackRouter.get("/admin", requireAdmin, listFeedback);
feedbackRouter.patch("/admin/:feedbackId/status", requireAdmin, validateUpdateFeedback, resolveFeedback);
