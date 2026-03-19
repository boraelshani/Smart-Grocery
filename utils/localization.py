"""Localization helpers for multilingual Mongo documents."""


def normalize_language(lang, default="en"):
    if not lang:
        return default
    value = str(lang).strip().lower()
    return value if value in {"en", "de"} else default


def get_localized_field(obj, field, lang="en"):
    if not isinstance(obj, dict):
        return None
    safe_lang = normalize_language(lang)
    key = f"{field}_{safe_lang}"
    if obj.get(key) not in (None, ""):
        return obj.get(key)

    fallback = f"{field}_en"
    if obj.get(fallback) not in (None, ""):
        return obj.get(fallback)

    return obj.get(field)
