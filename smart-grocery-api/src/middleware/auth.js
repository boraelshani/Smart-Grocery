import jwt from "jsonwebtoken";
import { env } from "../config/env.js";

const unauthorized = { status: 401, message: "Unauthorized" };

export const requireAuth = (req, _res, next) => {
  const header = req.headers.authorization;
  if (!header || !header.startsWith("Bearer ")) {
    return next(unauthorized);
  }

  const token = header.replace("Bearer ", "").trim();
  try {
    req.user = jwt.verify(token, env.jwtSecret);
    return next();
  } catch (_err) {
    return next(unauthorized);
  }
};

export const requireAdmin = (req, _res, next) => {
  const header = req.headers.authorization;
  if (!header || !header.startsWith("Bearer ")) {
    return next(unauthorized);
  }

  const token = header.replace("Bearer ", "").trim();
  try {
    req.user = jwt.verify(token, env.adminJwtSecret);
    if (!req.user?.isAdmin) {
      return next({ status: 403, message: "Admin access required" });
    }
    return next();
  } catch (_err) {
    return next(unauthorized);
  }
};
