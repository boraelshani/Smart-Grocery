import Joi from "joi";
import { validateBody } from "../middleware/validate.js";
import {
  addItemToList,
  createList,
  publishAsPublicTemplate,
  shareList,
  toggleListItemChecked
} from "../services/list.service.js";
import { recalculateListTotal } from "../services/pricing.service.js";

const createListSchema = Joi.object({
  userId: Joi.string().required(),
  name: Joi.string().min(2).max(100).required()
});

const addItemSchema = Joi.object({
  productId: Joi.string().required(),
  storeId: Joi.string().allow(null).optional(),
  quantity: Joi.number().positive().default(1)
});

const toggleSchema = Joi.object({
  productId: Joi.string().required(),
  storeId: Joi.string().allow(null).optional(),
  checked: Joi.boolean().required()
});

const publishSchema = Joi.object({
  type: Joi.string().valid("template", "user").required(),
  creatorUserId: Joi.string().allow(null).optional(),
  name_en: Joi.string().required(),
  name_de: Joi.string().required(),
  description_en: Joi.string().allow(null).optional(),
  description_de: Joi.string().allow(null).optional()
});

export const validateCreateList = validateBody(createListSchema);
export const validateAddItem = validateBody(addItemSchema);
export const validateToggleItem = validateBody(toggleSchema);
export const validatePublishList = validateBody(publishSchema);

export const createListHandler = async (req, res, next) => {
  try {
    const row = await createList(req.body);
    res.status(201).json(row);
  } catch (err) {
    next(err);
  }
};

export const addItemHandler = async (req, res, next) => {
  try {
    const list = await addItemToList({ listId: req.params.listId, item: req.body });
    res.json(list);
  } catch (err) {
    next(err);
  }
};

export const toggleItemHandler = async (req, res, next) => {
  try {
    const list = await toggleListItemChecked({ listId: req.params.listId, ...req.body });
    res.json(list);
  } catch (err) {
    next(err);
  }
};

export const recalcListHandler = async (req, res, next) => {
  try {
    const list = await recalculateListTotal(req.params.listId);
    res.json(list);
  } catch (err) {
    next(err);
  }
};

export const shareListHandler = async (req, res, next) => {
  try {
    const list = await shareList(req.params.listId);
    res.json(list);
  } catch (err) {
    next(err);
  }
};

export const publishListHandler = async (req, res, next) => {
  try {
    const result = await publishAsPublicTemplate({ listId: req.params.listId, ...req.body });
    res.status(201).json(result);
  } catch (err) {
    next(err);
  }
};
