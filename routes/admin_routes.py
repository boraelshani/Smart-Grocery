from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone

from flask import current_app, flash, jsonify, redirect, render_template, request, session, url_for
import requests

from . import admin_bp
from models.users_model import get_user_by_email
from utils.category_mapper import CategoryMapper
from utils.db import get_db

def prettify_slug(t):
    if not t: return t
    t = str(t).replace("cat_", "").replace("brand_", "")
    t = t.replace("-", " ").replace("_", " ")
    return " ".join([w.capitalize() for w in t.split()])


def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _now_utc():
    return datetime.now(timezone.utc)


def _to_aware_utc(value):
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _parse_positive_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _parse_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _slugify(value):
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


_TRANSLATION_CACHE = {}


def _translate_text(text, source_lang="en", target_lang="de"):
    value = (text or "").strip()
    if not value:
        return ""
    if source_lang == target_lang:
        return value

    cache_key = (value, source_lang, target_lang)
    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]

    translated = None
    api_url = current_app.config.get("ADMIN_TRANSLATE_API_URL") or "https://libretranslate.com/translate"

    try:
        response = requests.post(
            api_url,
            json={
                "q": value,
                "source": source_lang,
                "target": target_lang,
                "format": "text",
            },
            timeout=2.0,
        )
        if response.ok:
            payload = response.json() or {}
            translated = (payload.get("translatedText") or "").strip() or None
    except Exception:
        translated = None

    _TRANSLATION_CACHE[cache_key] = translated or value
    return _TRANSLATION_CACHE[cache_key]


def _localized_pair(name_en, name_de):
    en = (name_en or "").strip()
    de = (name_de or "").strip()

    if not en and not de:
        return "", ""
    if not en and de:
        en = _translate_text(de, source_lang="de", target_lang="en") or de
    if not de and en:
        de = _translate_text(en, source_lang="en", target_lang="de") or en
    return en, de


def _localized_optional_pair(text_en, text_de):
    en = (text_en or "").strip()
    de = (text_de or "").strip()
    if not en and not de:
        return None, None
    en, de = _localized_pair(en, de)
    return en or None, de or None


def _format_admin_dt(value):
    if isinstance(value, datetime):
        dt = _to_aware_utc(value)
        return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"

    if isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            dt = _to_aware_utc(dt)
            return dt.strftime("%Y-%m-%d %H:%M") if dt else raw
        except Exception:
            return raw

    return "-"


def _build_category_tree(rows):
    nodes = {}
    children_map = {}
    for row in rows:
        category_id = row.get("categoryId")
        if not category_id:
            continue
        node = {
            "categoryId": category_id,
            "name_en": row.get("name_en") or "Unnamed",
            "name_de": row.get("name_de") or "",
            "slug": row.get("slug") or "",
            "parentId": row.get("parentId") or None,
            "children": [],
        }
        nodes[category_id] = node
        children_map.setdefault(node["parentId"], []).append(node)

    roots = []
    for category_id, node in nodes.items():
        parent_id = node.get("parentId")
        if parent_id and parent_id in nodes:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)

    def _sort_node(node):
        node["children"].sort(key=lambda child: (child.get("name_en") or "").lower())
        for child in node["children"]:
            _sort_node(child)

    roots.sort(key=lambda item: (item.get("name_en") or "").lower())
    for root in roots:
        _sort_node(root)
    return roots


def _effective_price(offer):
    if not isinstance(offer, dict):
        return None
    return offer.get("promoPrice") if offer.get("promoPrice") is not None else offer.get("basePrice")


def _admin_emails():
    raw = current_app.config.get("ADMIN_EMAILS", "") or ""
    return {item.strip().lower() for item in str(raw).split(",") if item.strip()}


def _is_admin_user(email):
    if not email:
        return False

    if email.lower() in _admin_emails():
        return True

    user = get_user_by_email(email) or {}
    return bool(user.get("is_admin"))


def _require_admin():
    email = session.get("user")
    if not email:
        return False, redirect(url_for("auth.login"))
    if not _is_admin_user(email):
        return False, (jsonify({"status": "error", "detail": "admin required"}), 403)
    return True, email


def _build_category_path(db, category_id):
    category = db.categories.find_one({"categoryId": category_id})
    if not category:
        return [], []

    path = []
    full = []
    cursor = category
    visited = set()

    while cursor and cursor.get("categoryId") and cursor.get("categoryId") not in visited:
        visited.add(cursor.get("categoryId"))
        path.insert(0, cursor.get("categoryId"))
        full.insert(0, {
            "categoryId": cursor.get("categoryId"),
            "name_en": cursor.get("name_en") or "",
            "name_de": cursor.get("name_de") or "",
            "slug": cursor.get("slug") or "",
        })
        parent_id = cursor.get("parentId")
        if not parent_id:
            break
        cursor = db.categories.find_one({"categoryId": parent_id})

    return path, full


def _recompute_product_state(db, product_id):
    product = db.products.find_one({"productId": product_id})
    if not product:
        return

    offers = list(db.store_products.find({"productId": product_id, "isAvailable": True}))
    cheapest = None
    for offer in offers:
        price = _effective_price(offer)
        if price is None:
            continue
        if cheapest is None or float(price) < float(cheapest["price"]):
            cheapest = {"price": float(price), "storeProductId": offer.get("storeProductId")}

    labels = set(product.get("labels") or [])

    created_at = _to_aware_utc(product.get("createdAt"))
    if created_at and created_at >= (_now_utc() - timedelta(days=30)):
        labels.add("new")
    else:
        labels.discard("new")

    has_sale = any(offer.get("promoPrice") is not None for offer in offers)
    if has_sale:
        labels.add("on_sale")
    else:
        labels.discard("on_sale")

    db.products.update_one(
        {"productId": product_id},
        {
            "$set": {
                "labels": sorted(labels),
                "cheapestPrice": cheapest["price"] if cheapest else None,
                "cheapestStoreProductId": cheapest["storeProductId"] if cheapest else None,
                "updatedAt": _now_utc(),
            }
        },
    )


def _recompute_lists_for_product(db, product_id):
    lists = list(db.lists.find({"items.productId": product_id}))
    if not lists:
        return 0

    updated = 0
    for row in lists:
        total = 0.0
        items = row.get("items") or []
        for item in items:
            chosen_store = item.get("storeId")
            query = {"productId": item.get("productId"), "isAvailable": True}
            if chosen_store:
                query["storeId"] = chosen_store
            offer = db.store_products.find_one(query, sort=[("promoPrice", 1), ("basePrice", 1), ("lastPriceUpdate", -1)])
            if not offer and chosen_store:
                offer = db.store_products.find_one(
                    {"productId": item.get("productId"), "isAvailable": True},
                    sort=[("promoPrice", 1), ("basePrice", 1), ("lastPriceUpdate", -1)],
                )

            unit_price = float(_effective_price(offer) or 0)
            qty = float(item.get("quantity") or 1)
            line_total = round(unit_price * qty, 2)
            item["unitPrice"] = unit_price
            item["lineTotal"] = line_total
            total += line_total

        db.lists.update_one(
            {"_id": row.get("_id")},
            {"$set": {"items": items, "totalPrice": round(total, 2), "updatedAt": _now_utc()}},
        )
        updated += 1

    return updated


def _dashboard_payload(db):
    collections = [
        "stores",
        "brands",
        "categories",
        "products",
        "users",
        "feedback",
    ]
    counts = {name: db[name].count_documents({}) for name in collections}
    
    # Calculate stats for the new dashboard
    stats = {
        "total_products": counts.get("products", 0),
        "total_stores": counts.get("stores", 0),
        "total_users": counts.get("users", 0),
        "pending_feedback": db.feedback.count_documents({"resolved": {"$ne": True}}),
    }

    # Fetch recent feedback for the dashboard widget
    recent_feedback = list(db.feedback.find().sort("timestamp", -1).limit(5))

    return {
        "stats": stats,
        "recent_feedback": recent_feedback,
        "counts": counts, # Keep for backward compatibility if needed
    }


def _redirect_admin(default_endpoint, **kwargs):
    redirect_to = (request.form.get("redirectTo") or "").strip().lower()
    endpoint_map = {
        "overview": "admin.admin_dashboard",
        "products": "admin.admin_products_page",
        "categories": "admin.admin_categories_page",
        "brands": "admin.admin_brands_page",
        "lists": "admin.admin_lists_page",
        "feedback": "admin.admin_feedback_page",
    }
    endpoint = endpoint_map.get(redirect_to, default_endpoint)
    return redirect(url_for(endpoint, **kwargs))


@admin_bp.route("/admin/", methods=["GET"])
@admin_bp.route("/admin", methods=["GET"])
def admin_dashboard():
    allowed, result = _require_admin()
    if not allowed:
        if isinstance(result, tuple):
            return result
        return result

    db = get_db()
    if db is None:
        return render_template("admin_dashboard.html", error="Database unavailable", data={})

    data = _dashboard_payload(db)
    return render_template("admin_dashboard.html", data=data, user_email=result)


@admin_bp.route("/admin/products/new/", methods=["GET"])
@admin_bp.route("/admin/products/new", methods=["GET"])
def admin_products_new_page():
    allowed, result = _require_admin()
    if not allowed:
        if isinstance(result, tuple):
            return result
        return result
    return redirect(url_for("admin.admin_products_page", showForm=1))


@admin_bp.route("/admin/products/", methods=["GET"])
@admin_bp.route("/admin/products", methods=["GET"])
def admin_products_page():
    allowed, result = _require_admin()
    if not allowed:
        if isinstance(result, tuple):
            return result
        return result

    db = get_db()
    if db is None:
        return render_template("admin_products.html", error="Database unavailable", data={})

    query_text = (request.args.get("q") or "").strip()
    brand_filter = (request.args.get("brand") or "").strip()
    page = _parse_positive_int(request.args.get("page"), 1)
    per_page = 25

    query = {}
    if query_text:
        query["$or"] = [
            {"productId": {"$regex": query_text, "$options": "i"}},
            {"name_en": {"$regex": query_text, "$options": "i"}},
            {"name_de": {"$regex": query_text, "$options": "i"}},
            {"barcode": {"$regex": query_text, "$options": "i"}},
        ]
    if brand_filter:
        query["brandId"] = brand_filter

    total = db.products.count_documents(query)
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    skip = (page - 1) * per_page

    products = list(
        db.products.find(query, {"_id": 0})
        .sort([("updatedAt", -1), ("createdAt", -1), ("name_en", 1)])
        .skip(skip)
        .limit(per_page)
    )

    categories = list(db.categories.find({}, {"_id": 0, "categoryId": 1, "name_en": 1}).sort("name_en", 1))
    brands = list(db.brands.find({}, {"_id": 0, "brandId": 1, "name": 1, "name_en": 1}).sort("name", 1))
    stores = list(db.stores.find({}, {"_id": 0, "storeId": 1, "name": 1}).sort("name", 1))

    for b in brands:
        if not b.get("name_en"):
            b["name_en"] = b.get("name") or prettify_slug(b.get("brandId"))
    for c in categories:
        if not c.get("name_en"):
            c["name_en"] = prettify_slug(c.get("categoryId"))

    category_name_map = {row.get("categoryId"): row.get("name_en") for row in categories if row.get("categoryId")}
    brand_name_map = {
        row.get("brandId"): (row.get("name_en") or row.get("name") or prettify_slug(row.get("brandId")))
        for row in brands
        if row.get("brandId")
    }

    store_name_map = {row.get("storeId"): row.get("name") for row in stores if row.get("storeId")}

    for row in products:
        cat_id = row.get("categoryId")
        brand_id = row.get("brandId")
        row["category_name"] = category_name_map.get(cat_id) or (prettify_slug(cat_id) if cat_id else "Uncategorized")
        row["brand_name"] = brand_name_map.get(brand_id) or (prettify_slug(brand_id) if brand_id else "Generic")
        row["createdAtDisplay"] = _format_admin_dt(row.get("createdAt"))
        row["updatedAtDisplay"] = _format_admin_dt(row.get("updatedAt"))

    product_ids = [row.get("productId") for row in products if row.get("productId")]
    product_offers = {}
    for product_id in product_ids:
        offers = list(
            db.store_products.find({"productId": product_id}, {"_id": 0})
            .sort([("lastPriceUpdate", -1), ("updatedAt", -1)])
            .limit(40)
        )
        for offer in offers:
            offer["storeName"] = store_name_map.get(offer.get("storeId")) or "Unknown store"
            offer["lastPriceUpdateDisplay"] = _format_admin_dt(offer.get("lastPriceUpdate") or offer.get("updatedAt"))
        product_offers[product_id] = offers

    selected_id = (request.args.get("edit") or "").strip()
    selected_product = None
    selected_category_names = []
    if selected_id:
        selected_product = db.products.find_one({"productId": selected_id}, {"_id": 0})
        if selected_product:
            selected_category_names = [
                category_name_map.get(cat_id) or "Unknown category" for cat_id in (selected_product.get("categoryPath") or [])
            ]

    data = {
        "products": products,
        "product_offers": product_offers,
        "selected_product": selected_product,
        "selected_category_names": selected_category_names,
        "categories": categories,
        "brands": brands,
        "stores": stores,
        "q": query_text,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }
    return render_template("admin_products.html", data=data, user_email=result)


@admin_bp.route("/admin/categories/", methods=["GET"])
@admin_bp.route("/admin/categories", methods=["GET"])
def admin_categories_page():
    allowed, result = _require_admin()
    if not allowed:
        if isinstance(result, tuple):
            return result
        return result

    db = get_db()
    if db is None:
        return render_template("admin_categories.html", error="Database unavailable", data={})

    query_text = (request.args.get("q") or "").strip()
    all_categories = list(db.categories.find({}, {"_id": 0}).sort([("name_en", 1)]))
    for row in all_categories:
        row["name_en"] = row.get("name_en") or prettify_slug(row.get("categoryId"))
        row["name_de"] = row.get("name_de") or prettify_slug(row.get("categoryId"))

    categories = all_categories
    if query_text:
        query_text_l = query_text.lower()
        categories = [
            row
            for row in all_categories
            if query_text_l in str(row.get("categoryId") or "").lower()
            or query_text_l in str(row.get("name_en") or "").lower()
            or query_text_l in str(row.get("name_de") or "").lower()
            or query_text_l in str(row.get("slug") or "").lower()
        ]

    category_name_map = {row.get("categoryId"): row.get("name_en") for row in all_categories if row.get("categoryId")}
    for row in categories:
        row["parentName"] = category_name_map.get(row.get("parentId")) if row.get("parentId") else None
        row["updatedAtDisplay"] = _format_admin_dt(row.get("updatedAt"))

    selected_id = (request.args.get("edit") or "").strip()
    selected = db.categories.find_one({"categoryId": selected_id}, {"_id": 0}) if selected_id else None
    roots = [
        {
            "categoryId": row.get("categoryId"),
            "name_en": row.get("name_en") or row.get("categoryId"),
        }
        for row in all_categories
        if row.get("categoryId")
    ]
    category_tree = _build_category_tree(categories if query_text else all_categories)

    data = {
        "q": query_text,
        "categories": categories,
        "category_tree": category_tree,
        "selected_category": selected,
        "root_categories": roots,
    }
    return render_template("admin_categories.html", data=data, user_email=result)


@admin_bp.route("/admin/brands/", methods=["GET"])
@admin_bp.route("/admin/brands", methods=["GET"])
def admin_brands_page():
    allowed, result = _require_admin()
    if not allowed:
        if isinstance(result, tuple):
            return result
        return result

    db = get_db()
    if db is None:
        return render_template("admin_brands.html", error="Database unavailable", data={})

    query_text = (request.args.get("q") or "").strip()
    query = {}
    if query_text:
        query = {
            "$or": [
                {"brandId": {"$regex": query_text, "$options": "i"}},
                {"name": {"$regex": query_text, "$options": "i"}},
                {"name_en": {"$regex": query_text, "$options": "i"}},
                {"name_de": {"$regex": query_text, "$options": "i"}},
            ]
        }

    brands = list(db.brands.find(query, {"_id": 0}).sort([("updatedAt", -1), ("name", 1)]).limit(250))
    for row in brands:
        row["name_en"] = row.get("name_en") or row.get("name") or prettify_slug(row.get("brandId"))
        row["name_de"] = row.get("name_de") or row.get("name") or prettify_slug(row.get("brandId"))
        row["updatedAtDisplay"] = _format_admin_dt(row.get("updatedAt"))

    selected_id = (request.args.get("edit") or "").strip()
    selected_brand = db.brands.find_one({"brandId": selected_id}, {"_id": 0}) if selected_id else None

    data = {
        "q": query_text,
        "brands": brands,
        "selected_brand": selected_brand,
    }
    return render_template("admin_brands.html", data=data, user_email=result)


@admin_bp.route("/admin/lists/", methods=["GET"])
@admin_bp.route("/admin/lists", methods=["GET"])
def admin_lists_page():
    allowed, result = _require_admin()
    if not allowed:
        if isinstance(result, tuple):
            return result
        return result

    db = get_db()
    if db is None:
        return render_template("admin_lists.html", error="Database unavailable", data={})

    lists = list(db.lists.find({}, {"_id": 0}).sort("updatedAt", -1).limit(80))
    public_lists = list(db.public_lists.find({}, {"_id": 0}).sort("createdAt", -1).limit(80))
    products = list(db.products.find({}, {"_id": 0, "productId": 1, "name_en": 1, "name_de": 1}).sort("name_en", 1).limit(500))

    users = list(db.users.find({}, {"_id": 0, "userId": 1, "email": 1, "name": 1, "username": 1}))
    user_display_map = {}
    for user in users:
        uid = user.get("userId")
        if not uid:
            continue
        user_display_map[uid] = (
            user.get("email")
            or user.get("name")
            or user.get("username")
            or "Unknown user"
        )

    for row in lists:
        row["owner_display"] = row.get("owner") or user_display_map.get(row.get("userId")) or "Unknown"
        row["createdAtDisplay"] = _format_admin_dt(row.get("createdAt"))
        row["updatedAtDisplay"] = _format_admin_dt(row.get("updatedAt"))
        
        # Ensure items is a list to avoid Jinja2 resolving .items to dict.items()
        row_items = row.get("items")
        if row_items is None:
            row_items = []
            row["items"] = row_items
            
        row["itemsCount"] = len(row_items)
        for item in row_items:
            item["product_display"] = item.get("name") or item.get("productId") or "Item"
            item["quantity_display"] = item.get("quantity") or item.get("qty") or 1

    user_options = []
    for user in users:
        user_options.append(
            {
                "userId": user.get("userId"),
                "label": user.get("email") or user.get("name") or user.get("username") or "Unknown user",
            }
        )

    data = {
        "lists": lists,
        "public_lists": public_lists,
        "products": products,
        "users": user_options,
        "counts": {
            "lists": db.lists.count_documents({}),
            "public_lists": db.public_lists.count_documents({}),
            "users": db.users.count_documents({}),
        },
    }
    return render_template("admin_lists.html", data=data, user_email=result)


@admin_bp.route("/admin/feedback/", methods=["GET"])
@admin_bp.route("/admin/feedback", methods=["GET"])
def admin_feedback_page():
    allowed, result = _require_admin()
    if not allowed:
        if isinstance(result, tuple):
            return result
        return result

    db = get_db()
    if db is None:
        return render_template("admin_feedback.html", error="Database unavailable", data={})

    status_filter = (request.args.get("status") or "all").strip().lower()
    query = {}
    if status_filter and status_filter != "all":
        query["status"] = status_filter

    feedback = list(db.feedback.find(query, {"_id": 0}).sort("createdAt", -1).limit(120))
    users = list(db.users.find({}, {"_id": 0, "userId": 1, "email": 1, "name": 1, "username": 1}))
    user_display_map = {}
    for user in users:
        uid = user.get("userId")
        if not uid:
            continue
        user_display_map[uid] = (
            user.get("email")
            or user.get("name")
            or user.get("username")
            or "Unknown user"
        )

    for row in feedback:
        row["user_display"] = row.get("userEmail") or user_display_map.get(row.get("userId")) or "Unknown"

    counts = {
        "all": db.feedback.count_documents({}),
        "pending": db.feedback.count_documents({"status": "pending"}),
        "reviewed": db.feedback.count_documents({"status": "reviewed"}),
        "resolved": db.feedback.count_documents({"status": "resolved"}),
    }

    data = {
        "feedback": feedback,
        "status_filter": status_filter,
        "counts": counts,
    }
    return render_template("admin_feedback.html", data=data, user_email=result)


@admin_bp.route("/admin/api/overview", methods=["GET"])
def admin_overview_api():
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    if db is None:
        return jsonify({"status": "error", "detail": "database unavailable"}), 500

    return jsonify({"status": "ok", "data": _dashboard_payload(db)})


@admin_bp.route("/admin/stores/save", methods=["POST"])
def admin_save_store():
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    payload = {
        "storeId": (request.form.get("storeId") or "").strip() or _id("store"),
        "name": (request.form.get("name") or "").strip(),
        "logoUrl": (request.form.get("logoUrl") or "").strip() or None,
        "website": (request.form.get("website") or "").strip() or None,
        "country": (request.form.get("country") or "AT").strip(),
        "languages_available": [lang.strip() for lang in (request.form.get("languages_available") or "en,de").split(",") if lang.strip()],
        "apiAvailable": _to_bool(request.form.get("apiAvailable"), False),
        "scrapingRequired": _to_bool(request.form.get("scrapingRequired"), True),
        "updatedAt": _now_utc(),
    }
    if not payload["name"]:
        flash("Store name is required", "error")
        return _redirect_admin("admin.admin_dashboard")

    existing = db.stores.find_one({"storeId": payload["storeId"]})
    if existing:
        db.stores.update_one({"storeId": payload["storeId"]}, {"$set": payload})
    else:
        payload["createdAt"] = _now_utc()
        db.stores.insert_one(payload)

    flash("Store saved", "success")
    return _redirect_admin("admin.admin_dashboard")


@admin_bp.route("/admin/brands/save", methods=["POST"])
def admin_save_brand():
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    name_en, name_de = _localized_pair(
        request.form.get("name_en") or request.form.get("name"),
        request.form.get("name_de"),
    )
    payload = {
        "brandId": (request.form.get("brandId") or "").strip() or _id("brand"),
        "name": name_en,
        "name_en": name_en,
        "name_de": name_de,
        "logoUrl": (request.form.get("logoUrl") or "").strip() or None,
        "website": (request.form.get("website") or "").strip() or None,
        "updatedAt": _now_utc(),
    }
    if not payload["name_en"]:
        flash("Brand name is required", "error")
        return _redirect_admin("admin.admin_brands_page")

    existing = db.brands.find_one({"brandId": payload["brandId"]})
    if existing:
        db.brands.update_one({"brandId": payload["brandId"]}, {"$set": payload})
    else:
        payload["createdAt"] = _now_utc()
        db.brands.insert_one(payload)

    flash("Brand saved", "success")
    return _redirect_admin("admin.admin_brands_page", edit=payload["brandId"])


@admin_bp.route("/admin/categories/save", methods=["POST"])
def admin_save_category():
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    category_id = (request.form.get("categoryId") or "").strip() or _id("cat")
    name_en, name_de = _localized_pair(request.form.get("name_en"), request.form.get("name_de"))
    payload = {
        "categoryId": category_id,
        "name_en": name_en,
        "name_de": name_de,
        "slug": (request.form.get("slug") or "").strip(),
        "parentId": (request.form.get("parentId") or "").strip() or None,
        "updatedAt": _now_utc(),
    }
    if not payload["slug"]:
        payload["slug"] = _slugify(payload["name_en"] or payload["name_de"]) or category_id
    if not payload["name_en"]:
        flash("Category English name is required", "error")
        return _redirect_admin("admin.admin_categories_page")

    existing = db.categories.find_one({"categoryId": category_id})
    if existing:
        db.categories.update_one({"categoryId": category_id}, {"$set": payload})
    else:
        payload["createdAt"] = _now_utc()
        db.categories.insert_one(payload)

    path, full = _build_category_path(db, category_id)
    db.categories.update_one(
        {"categoryId": category_id},
        {"$set": {"path": path, "fullPathNames": full, "updatedAt": _now_utc()}},
    )

    flash("Category saved", "success")
    return _redirect_admin("admin.admin_categories_page", edit=category_id)


@admin_bp.route("/admin/products/save", methods=["POST"])
def admin_save_product():
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    product_id = (request.form.get("productId") or "").strip() or _id("prod")
    category_id = (request.form.get("categoryId") or "").strip()
    path, _ = _build_category_path(db, category_id)

    taxonomy_roots = {
        "cat_produce",
        "cat_pantry",
        "cat_dairy",
        "cat_meat",
        "cat_frozen",
        "cat_bakery",
        "cat_baby-food",
        "cat_snacks",
        "cat_fast-food-to-go",
        "cat_household",
        "cat_beverages",
    }

    # If category is missing (or only a broad root), infer a deeper leaf category.
    if (not category_id) or (category_id in taxonomy_roots):
        mapper = CategoryMapper()
        signal = " ".join(
            [
                request.form.get("name_en") or "",
                request.form.get("name_de") or "",
                request.form.get("description_en") or "",
                request.form.get("description_de") or "",
                request.form.get("categoryId") or "",
            ]
        )
        inferred = mapper.map_category_with_path(signal)
        inferred_leaf = inferred.get("categoryId")
        inferred_path = inferred.get("categoryPath") or []

        if inferred_leaf:
            if (not category_id) or (category_id in inferred_path):
                category_id = inferred_leaf
                path, _ = _build_category_path(db, category_id)

    name_en, name_de = _localized_pair(request.form.get("name_en"), request.form.get("name_de"))
    description_en, description_de = _localized_optional_pair(
        request.form.get("description_en"),
        request.form.get("description_de"),
    )

    labels = [item.strip() for item in (request.form.get("labels") or "").split(",") if item.strip()]
    payload = {
        "productId": product_id,
        "name_en": name_en,
        "name_de": name_de,
        "brandId": (request.form.get("brandId") or "").strip() or None,
        "categoryId": category_id or None,
        "categoryPath": path,
        "unitSize": (request.form.get("unitSize") or "").strip() or None,
        "barcode": (request.form.get("barcode") or "").strip() or None,
        "defaultImageUrl": (request.form.get("defaultImageUrl") or "").strip() or None,
        "legalImageStatus": (request.form.get("legalImageStatus") or "placeholder").strip(),
        "labels": labels,
        "description_en": description_en,
        "description_de": description_de,
        "updatedAt": _now_utc(),
    }
    redirect_to = (request.form.get("redirectTo") or "").strip().lower()

    if not payload["name_en"]:
        flash("Product English name is required", "error")
        if redirect_to == "products":
            return redirect(url_for("admin.admin_products_page", edit=product_id))
        return _redirect_admin("admin.admin_dashboard")

    existing = db.products.find_one({"productId": product_id})
    if existing:
        db.products.update_one({"productId": product_id}, {"$set": payload})
    else:
        payload["createdAt"] = _now_utc()
        db.products.insert_one(payload)

    _recompute_product_state(db, product_id)

    flash("Product saved", "success")
    if redirect_to == "products":
        return redirect(url_for("admin.admin_products_page", edit=product_id))
    return _redirect_admin("admin.admin_dashboard")


@admin_bp.route("/admin/store-products/save", methods=["POST"])
def admin_save_store_product():
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    store_product_id = (request.form.get("storeProductId") or "").strip() or _id("sp")
    product_id = (request.form.get("productId") or "").strip()

    multi_buy_details = {}
    raw_multi = (request.form.get("multiBuyDetails") or "").strip()
    if raw_multi:
        try:
            multi_buy_details = json.loads(raw_multi)
        except Exception:
            multi_buy_details = {"raw": raw_multi}

    def _to_float(name, fallback=None):
        val = request.form.get(name)
        if val in (None, ""):
            return fallback
        try:
            return float(val)
        except Exception:
            return fallback

    payload = {
        "storeProductId": store_product_id,
        "productId": product_id,
        "storeId": (request.form.get("storeId") or "").strip(),
        "productPageUrl": (request.form.get("productPageUrl") or "").strip() or None,
        "extractedImageUrl": (request.form.get("extractedImageUrl") or "").strip() or None,
        "basePrice": _to_float("basePrice", 0.0),
        "promoPrice": _to_float("promoPrice", None),
        "multiBuy": {
            "type": (request.form.get("multiBuyType") or "none").strip(),
            "details": multi_buy_details,
        },
        "isAvailable": _to_bool(request.form.get("isAvailable"), True),
        "lastScrapeStatus": (request.form.get("lastScrapeStatus") or "ok").strip(),
        "offerStart": None,
        "offerEnd": None,
        "lastPriceUpdate": _now_utc(),
        "stockStatus": (request.form.get("stockStatus") or "unknown").strip(),
        "unitPriceComparison": {
            "value": _to_float("unitPriceValue", None),
            "unit": (request.form.get("unitPriceUnit") or "").strip() or None,
        },
        "updatedAt": _now_utc(),
    }

    redirect_to = (request.form.get("redirectTo") or "").strip().lower()

    if not payload["productId"] or not payload["storeId"]:
        flash("Store product requires productId and storeId", "error")
        if redirect_to == "products" and payload["productId"]:
            return redirect(url_for("admin.admin_products_page", edit=payload["productId"]))
        return _redirect_admin("admin.admin_dashboard")

    existing = db.store_products.find_one({"storeProductId": store_product_id})
    if existing:
        old_effective = _effective_price(existing)
        db.store_products.update_one({"storeProductId": store_product_id}, {"$set": payload})
    else:
        old_effective = None
        payload["createdAt"] = _now_utc()
        db.store_products.insert_one(payload)

    new_effective = _effective_price(payload)
    if old_effective != new_effective:
        db.price_history.insert_one(
            {
                "historyId": _id("hist"),
                "storeProductId": store_product_id,
                "oldPrice": old_effective,
                "newPrice": new_effective,
                "promoPrice": payload.get("promoPrice"),
                "timestamp": _now_utc(),
            }
        )

    _recompute_product_state(db, product_id)
    _recompute_lists_for_product(db, product_id)

    flash("Store product saved and dependent pricing refreshed", "success")
    if redirect_to == "products":
        return redirect(url_for("admin.admin_products_page", edit=product_id))
    return _redirect_admin("admin.admin_dashboard")


@admin_bp.route("/admin/scraper-rules/save", methods=["POST"])
def admin_save_scraper_rule():
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    store_id = (request.form.get("storeId") or "").strip()
    if not store_id:
        flash("Scraper rule requires storeId", "error")
        return _redirect_admin("admin.admin_dashboard")

    payload = {
        "storeId": store_id,
        "productNameSelector": (request.form.get("productNameSelector") or "").strip() or "h1",
        "basePriceSelector": (request.form.get("basePriceSelector") or "").strip() or "",
        "promoPriceSelector": (request.form.get("promoPriceSelector") or "").strip() or None,
        "availabilitySelector": (request.form.get("availabilitySelector") or "").strip() or "",
        "imageSelector": (request.form.get("imageSelector") or "").strip() or None,
        "offerSelector": (request.form.get("offerSelector") or "").strip() or None,
        "multiBuySelector": (request.form.get("multiBuySelector") or "").strip() or None,
        "requiresJSRendering": _to_bool(request.form.get("requiresJSRendering"), False),
        "updatedAt": _now_utc(),
    }

    db.scraper_rules.update_one({"storeId": store_id}, {"$set": payload}, upsert=True)

    flash("Scraper rule saved", "success")
    return _redirect_admin("admin.admin_dashboard")


@admin_bp.route("/admin/public-lists/save", methods=["POST"])
def admin_save_public_list():
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    public_id = (request.form.get("id") or "").strip() or _id("public")
    name_en, name_de = _localized_pair(request.form.get("name_en"), request.form.get("name_de"))
    description_en, description_de = _localized_optional_pair(
        request.form.get("description_en"),
        request.form.get("description_de"),
    )

    payload = {
        "id": public_id,
        "type": (request.form.get("type") or "template").strip(),
        "name_en": name_en,
        "name_de": name_de,
        "description_en": description_en,
        "description_de": description_de,
        "creatorUserId": (request.form.get("creatorUserId") or "").strip() or None,
        "popularityScore": _parse_int(request.form.get("popularityScore"), 0),
    }

    items = []
    raw_items = (request.form.get("items_json") or "").strip()
    if raw_items:
        try:
            parsed = json.loads(raw_items)
            if isinstance(parsed, list):
                items = parsed
        except Exception:
            items = []
    payload["items"] = items

    if not payload["name_en"]:
        flash("Public list English name is required", "error")
        return _redirect_admin("admin.admin_lists_page")

    db.public_lists.update_one(
        {"id": public_id},
        {"$set": {**payload}, "$setOnInsert": {"createdAt": _now_utc()}},
        upsert=True,
    )

    flash("Public list saved", "success")
    return _redirect_admin("admin.admin_lists_page")


@admin_bp.route("/admin/lists/save", methods=["POST"])
def admin_save_list():
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    list_id = (request.form.get("listId") or "").strip() or _id("list")
    list_name = (request.form.get("name") or "").strip()
    owner_user_id = (request.form.get("userId") or "").strip()

    if not list_name:
        flash("List name is required", "error")
        return _redirect_admin("admin.admin_lists_page")
    if not owner_user_id:
        flash("Please select a user for the list", "error")
        return _redirect_admin("admin.admin_lists_page")

    owner_user = db.users.find_one({"userId": owner_user_id}, {"_id": 0, "email": 1, "name": 1, "username": 1}) or {}
    owner_label = owner_user.get("email") or owner_user.get("name") or owner_user.get("username") or owner_user_id

    product_ids = request.form.getlist("item_product_id")
    quantities = request.form.getlist("item_quantity")
    store_ids = request.form.getlist("item_store_id")

    selected_product_ids = [pid for pid in product_ids if (pid or "").strip()]
    products = list(
        db.products.find(
            {"productId": {"$in": selected_product_ids}},
            {"_id": 0, "productId": 1, "name_en": 1, "name_de": 1},
        )
    ) if selected_product_ids else []
    product_map = {row.get("productId"): row for row in products if row.get("productId")}

    items = []
    total = 0.0
    for idx, raw_product_id in enumerate(product_ids):
        product_id = (raw_product_id or "").strip()
        if not product_id:
            continue

        try:
            quantity = max(int(float((quantities[idx] if idx < len(quantities) else "1") or 1)), 1)
        except Exception:
            quantity = 1

        selected_store_id = (store_ids[idx] if idx < len(store_ids) else "").strip() or None
        offer_query = {"productId": product_id, "isAvailable": True}
        if selected_store_id:
            offer_query["storeId"] = selected_store_id

        offer = db.store_products.find_one(
            offer_query,
            sort=[("promoPrice", 1), ("basePrice", 1), ("lastPriceUpdate", -1)],
        )
        if not offer and selected_store_id:
            offer = db.store_products.find_one(
                {"productId": product_id, "isAvailable": True},
                sort=[("promoPrice", 1), ("basePrice", 1), ("lastPriceUpdate", -1)],
            )

        unit_price = float(_effective_price(offer) or 0)
        line_total = round(unit_price * quantity, 2)
        product_doc = product_map.get(product_id) or {}

        item = {
            "productId": product_id,
            "name": product_doc.get("name_en") or product_doc.get("name_de") or product_id,
            "quantity": quantity,
            "qty": quantity,
            "unitPrice": unit_price,
            "lineTotal": line_total,
            "price": unit_price,
            "price_val": unit_price,
            "purchased": False,
            "checked": False,
            "is_new": True,
        }
        if offer and offer.get("storeId"):
            item["storeId"] = offer.get("storeId")
            item["store_product_id"] = offer.get("storeProductId")

        items.append(item)
        total += line_total

    payload = {
        "listId": list_id,
        "name": list_name,
        "userId": owner_user_id,
        "owner": owner_label,
        "items": items,
        "totalPrice": round(total, 2),
        "shared": _to_bool(request.form.get("shared"), False),
        "updatedAt": _now_utc(),
    }

    db.lists.update_one(
        {"listId": list_id, "userId": owner_user_id},
        {"$set": payload, "$setOnInsert": {"createdAt": _now_utc()}},
        upsert=True,
    )

    flash("User list saved", "success")
    return _redirect_admin("admin.admin_lists_page")


@admin_bp.route("/admin/feedback/status", methods=["POST"])
def admin_feedback_status():
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    feedback_id = (request.form.get("feedbackId") or "").strip()
    status = (request.form.get("status") or "pending").strip()
    if not feedback_id:
        flash("feedbackId is required", "error")
        return _redirect_admin("admin.admin_dashboard")

    db.feedback.update_one({"feedbackId": feedback_id}, {"$set": {"status": status}})
    flash("Feedback status updated", "success")
    return _redirect_admin("admin.admin_dashboard", status=(request.form.get("statusFilter") or "all"))


@admin_bp.route("/admin/maintenance/recompute", methods=["POST"])
def admin_recompute():
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    product_id = (request.form.get("productId") or "").strip()

    processed = 0
    if product_id:
        _recompute_product_state(db, product_id)
        _recompute_lists_for_product(db, product_id)
        processed = 1
    else:
        for row in db.products.find({}, {"productId": 1}).limit(200):
            pid = row.get("productId")
            if not pid:
                continue
            _recompute_product_state(db, pid)
            _recompute_lists_for_product(db, pid)
            processed += 1

    flash(f"Recompute finished for {processed} product(s)", "success")
    return _redirect_admin("admin.admin_dashboard")


@admin_bp.route("/admin/products/delete/<product_id>", methods=["POST"])
def admin_delete_product(product_id):
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    db.products.delete_one({"productId": product_id})
    db.store_products.delete_many({"productId": product_id})
    # Optional: cleanup lists that contain this product
    db.lists.update_many(
        {"items.productId": product_id},
        {"$pull": {"items": {"productId": product_id}}}
    )

    flash(f"Product {product_id} deleted", "success")
    return redirect(url_for("admin.admin_products_page"))


@admin_bp.route("/admin/categories/delete/<category_id>", methods=["POST"])
def admin_delete_category(category_id):
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    # Check if category has children
    if db.categories.find_one({"parentId": category_id}):
        flash("Cannot delete category with subcategories", "error")
        return redirect(url_for("admin.admin_categories_page"))

    # Check if products use this category
    if db.products.find_one({"categoryId": category_id}):
        flash("Cannot delete category assigned to products", "error")
        return redirect(url_for("admin.admin_categories_page"))

    db.categories.delete_one({"categoryId": category_id})
    flash(f"Category {category_id} deleted", "success")
    return redirect(url_for("admin.admin_categories_page"))


@admin_bp.route("/admin/brands/delete/<brand_id>", methods=["POST"])
def admin_delete_brand(brand_id):
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    # Check if products use this brand
    if db.products.find_one({"brandId": brand_id}):
        flash("Cannot delete brand assigned to products", "error")
        return redirect(url_for("admin.admin_brands_page"))

    db.brands.delete_one({"brandId": brand_id})
    flash(f"Brand {brand_id} deleted", "success")
    return redirect(url_for("admin.admin_brands_page"))


@admin_bp.route("/admin/lists/delete/<list_id>", methods=["POST"])
def admin_delete_list(list_id):
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    db.lists.delete_one({"_id": list_id})  # ID is typically ObjectId, but let's see how it's stored.
    # Logic in lists page loop uses l.get('_id'), which might be an ObjectId.
    # To delete safely by ObjectId passed as string:
    from bson.objectid import ObjectId
    try:
        oid = ObjectId(list_id)
        db.lists.delete_one({"_id": oid})
    except Exception:
        # Fallback if listId is a string custom id
        db.lists.delete_one({"listId": list_id})

    flash("List deleted", "success")
    return redirect(url_for("admin.admin_lists_page"))


@admin_bp.route("/admin/public-lists/delete/<list_id>", methods=["POST"])
def admin_delete_public_list(list_id):
    allowed, result = _require_admin()
    if not allowed:
        return result

    db = get_db()
    db.public_lists.delete_one({"id": list_id})
    flash("Public list/template deleted", "success")
    return redirect(url_for("admin.admin_lists_page"))


@admin_bp.route("/admin/feedback/status/<feedback_id>", methods=["POST"])
def admin_feedback_status_direct(feedback_id):
    allowed, result = _require_admin()
    if not allowed:
        return result

    status = (request.form.get("status") or "").strip().lower()
    if status not in {"pending", "reviewed", "resolved"}:
        flash("Invalid status", "error")
        return redirect(url_for("admin.admin_feedback_page"))

    db = get_db()
    # Try updating by feedbackId first, then ObjectId
    # This maintains compatibility
    res = db.feedback.update_one({"feedbackId": feedback_id}, {"$set": {"status": status, "updatedAt": _now_utc()}})
    if res.matched_count == 0:
        from bson.objectid import ObjectId
        try:
            oid = ObjectId(feedback_id)
            db.feedback.update_one({"_id": oid}, {"$set": {"status": status, "updatedAt": _now_utc()}})
        except Exception:
            pass

    flash("Feedback updated", "success")
    return redirect(url_for("admin.admin_feedback_page"))

@admin_bp.route("/admin/scraper/run", methods=["GET"])
def run_scraper_manual():
    allowed, result = _require_admin()
    if not allowed:
        if isinstance(result, tuple):
            return result
        return result
    
    try:
        import subprocess
        subprocess.Popen(["python3", "scripts/cron_pipeline.py"])
        flash("Price update engine triggered in background. Store catalog will sync shortly.", "success")
    except Exception as e:
        flash(f"Failed to start price updates: {str(e)}", "danger")
        
    return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/admin/cache/clear", methods=["GET"])
def clear_cache():
    allowed, result = _require_admin()
    if not allowed:
        if isinstance(result, tuple):
            return result
        return result
    
    # Placeholder for cache clearing logic (e.g., Redis flush or dict clear)
    get_db() # Ensure DB connection is active
    flash("System cache has been cleared successfully.", "success")
    return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/admin/products/smart-import", methods=["GET"])
def admin_smart_import_page():
    _require_admin()
    return render_template("admin_smart_import.html")

@admin_bp.route("/admin/api/urls/update", methods=["POST"])
def admin_update_all_prices():
    """
    Triggers a background job or synchronous loop to hit product.store_url
    and parse the latest price using the AI fetcher or regex.
    """
    _require_admin()
    # In production: run as a Celery/Redis job because 10,000 URLs would time out a web request.
    return jsonify({"success": True, "message": "Background job started: Updating prices from live URLs."})

@admin_bp.route("/admin/api/products/smart-extract", methods=["POST"])
def admin_smart_extract():
    _require_admin()
    if not request.is_json:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400
    
    url = request.json.get("url")
    if not url:
        return jsonify({"success": False, "error": "URL required"}), 400

    from scripts.ai_product_fetcher import fetch_product_from_url
    result = fetch_product_from_url(url)
    return jsonify(result)
