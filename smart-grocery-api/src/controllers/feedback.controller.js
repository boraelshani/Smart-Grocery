import Joi from "joi";
import { randomUUID } from "crypto";
import { Feedback } from "../models/index.js";
import { validateBody } from "../middleware/validate.js";

const createFeedbackSchema = Joi.object({
  userId: Joi.string().allow(null).optional(),
  productId: Joi.string().allow(null).optional(),
  storeProductId: Joi.string().allow(null).optional(),
  type: Joi.string()
    .valid("wrong_price", "missing_product", "wrong_store", "image_issue", "feature_request", "other")
    .required(),
  message: Joi.string().min(3).max(2000).required()
});

const updateFeedbackSchema = Joi.object({
  status: Joi.string().valid("pending", "reviewed", "resolved").required()
});

export const validateCreateFeedback = validateBody(createFeedbackSchema);
export const validateUpdateFeedback = validateBody(updateFeedbackSchema);

export const createFeedback = async (req, res, next) => {
  try {
    const row = await Feedback.create({
      feedbackId: `feedback_${randomUUID()}`,
      ...req.body,
      createdAt: new Date()
    });

    res.status(201).json(row.toObject());
  } catch (err) {
    next(err);
  }
};

export const listFeedback = async (req, res, next) => {
  try {
    const query = {};
    if (req.query.type) {
      query.type = req.query.type;
    }
    if (req.query.status) {
      query.status = req.query.status;
    }

    const rows = await Feedback.find(query).sort({ createdAt: -1 }).lean();
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

export const resolveFeedback = async (req, res, next) => {
  try {
    const row = await Feedback.findOneAndUpdate(
      { feedbackId: req.params.feedbackId },
      { $set: { status: req.body.status } },
      { new: true }
    ).lean();

    if (!row) {
      return next({ status: 404, message: "Feedback not found" });
    }

    return res.json({
      ...row,
      notification: row.userId ? "User notification should be queued here." : null
    });
  } catch (err) {
    return next(err);
  }
};
