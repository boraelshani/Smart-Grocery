export const notFoundHandler = (_req, res) => {
  res.status(404).json({ error: "Not found" });
};

export const errorHandler = (err, _req, res, _next) => {
  const status = err.status || 500;
  const message = err.message || "Internal server error";
  res.status(status).json({ error: message });
};
