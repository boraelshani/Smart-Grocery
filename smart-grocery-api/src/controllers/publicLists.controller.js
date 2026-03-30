import { PublicList } from "../models/index.js";

export const getPublicLists = async (req, res, next) => {
  try {
    const query = {};
    if (req.query.type) {
      query.type = req.query.type;
    }

    const rows = await PublicList.find(query).sort({ popularityScore: -1, createdAt: -1 }).lean();
    res.json(rows);
  } catch (err) {
    next(err);
  }
};
