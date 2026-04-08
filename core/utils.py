from datetime import datetime, timezone
import uuid
import re

def to_bool(value, default=False):
    if value is None: return default
    if isinstance(value, bool): return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

def now_utc():
    return datetime.now(timezone.utc)

def generate_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def slugify(value):
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

def format_dt(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value) if value else "-"

def prettify_slug(t):
    if not t: return t
    t = str(t).replace("cat_", "").replace("brand_", "")
    t = t.replace("-", " ").replace("_", " ")
    return " ".join([w.capitalize() for w in t.split()])
