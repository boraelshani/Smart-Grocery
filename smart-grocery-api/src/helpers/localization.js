import { env } from "../config/env.js";

const allowedLangs = new Set(["en", "de"]);

export const normalizeLanguage = (lang) => {
  if (!lang) {
    return env.defaultLanguage;
  }
  return allowedLangs.has(lang) ? lang : env.defaultLanguage;
};

export const getLocalizedField = (object, field, lang = env.defaultLanguage) => {
  const safeLang = normalizeLanguage(lang);
  if (!object || typeof object !== "object") {
    return null;
  }

  const localizedKey = `${field}_${safeLang}`;
  if (object[localizedKey] !== undefined && object[localizedKey] !== null) {
    return object[localizedKey];
  }

  const fallbackKey = `${field}_${env.defaultLanguage}`;
  if (object[fallbackKey] !== undefined && object[fallbackKey] !== null) {
    return object[fallbackKey];
  }

  return object[field] ?? null;
};
