export const sanitizePaging = (query) => {
  const page = Math.max(1, Number(query.page || 1));
  const limit = Math.min(100, Math.max(1, Number(query.limit || 20)));
  const skip = (page - 1) * limit;
  return { page, limit, skip };
};

export const safeObjectIdString = (value) => {
  if (!value || typeof value !== "string") {
    return null;
  }
  return value.trim();
};
