from flask import render_template, request, session, redirect, url_for, jsonify, flash, current_app
from . import admin_bp
from models.users_model import get_user_by_email
from utils.category_mapper import CategoryMapper
from utils.db import get_db
import json
import re
import uuid
import requests
from datetime import datetime, timezone, timedelta

try:
    from deep_translator import GoogleTranslator
except Exception:  # pragma: no cover - optional dependency in some environments
    GoogleTranslator = None

# Helper constants and utilities
_TRANSLATION_CACHE = {}

def prettify_slug(t):
    if not t: return t
    t = str(t).replace("cat_", "").replace("brand_", "").replace("-", " ").replace("_", " ")
    return " ".join([w.capitalize() for w in t.split()])

def _to_bool(value, default=False):
    if value is None: return default
    if isinstance(value, bool): return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

def _now_utc(): return datetime.now(timezone.utc)

def _to_aware_utc(value):
    if not isinstance(value, datetime): return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

def _id(prefix): return f"{prefix}_{uuid.uuid4().hex[:12]}"

def _parse_positive_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except: return default

def _parse_int(value, default=0):
    try: return int(value)
    except: return default

def _slugify(value):
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

def _translate_text(text, source_lang="en", target_lang="de"):
    val = (text or "").strip()
    if not val or source_lang == target_lang: return val
    key = (val, source_lang, target_lang)
    if key in _TRANSLATION_CACHE: return _TRANSLATION_CACHE[key]
    api_url = current_app.config.get("ADMIN_TRANSLATE_API_URL") or "https://libretranslate.com/translate"
    try:
        resp = requests.post(api_url, json={"q": val, "source": source_lang, "target": target_lang, "format": "text"}, timeout=2.0)
        if resp.ok:
            translated = (resp.json().get("translatedText") or "").strip() or None
            _TRANSLATION_CACHE[key] = translated or val
        else:
            _TRANSLATION_CACHE[key] = val
    except: _TRANSLATION_CACHE[key] = val

    if _TRANSLATION_CACHE.get(key) == val and GoogleTranslator is not None:
        try:
            translated = (GoogleTranslator(source=source_lang, target=target_lang).translate(val) or "").strip()
            if translated:
                _TRANSLATION_CACHE[key] = translated
        except Exception:
            pass

    return _TRANSLATION_CACHE.get(key, val)

def _localized_pair(name_en, name_de):
    en = (name_en or "").strip(); de = (name_de or "").strip()
    if not en and not de: return "", ""
    if not en and de: en = _translate_text(de, "de", "en") or de
    if not de and en: de = _translate_text(en, "en", "de") or en
    return en, de

def _localized_optional_pair(text_en, text_de):
    en, de = _localized_pair(text_en, text_de)
    return en or None, de or None

def _format_admin_dt(value):
    if isinstance(value, datetime):
        dt = _to_aware_utc(value)
        return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"
    if isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            dt = _to_aware_utc(dt)
            return dt.strftime("%Y-%m-%d %H:%M") if dt else value.strip()
        except: return value.strip()
    return "-"

def _admin_emails():
    return {i.strip().lower() for i in str(current_app.config.get("ADMIN_EMAILS", "")).split(",") if i.strip()}

def _is_admin_user(email):
    if not email: return False
    if email.lower() in _admin_emails(): return True
    user = get_user_by_email(email) or {}
    return bool(user.get("is_admin"))

def _require_admin():
    email = session.get('user')
    if not email: return False, redirect(url_for('auth.login'))
    if not _is_admin_user(email): return False, (jsonify({"status": "error", "detail": "admin required"}), 403)
    return True, email

def _effective_price(offer):
    if not isinstance(offer, dict): return None
    return offer.get("promoPrice") if offer.get("promoPrice") is not None else offer.get("basePrice")

def _build_category_tree(rows):
    nodes = {}; children_map = {}
    for row in rows:
        cid = row.get("categoryId")
        if not cid: continue
        node = {"categoryId": cid, "name_en": row.get("name_en") or "Unnamed", "name_de": row.get("name_de") or "", "slug": row.get("slug") or "", "parentId": row.get("parentId"), "image_url": row.get("image_url"), "children": []}
        nodes[cid] = node; children_map.setdefault(node["parentId"], []).append(node)
    roots = []
    for cid, node in nodes.items():
        pid = str(node.get("parentId")) if node.get("parentId") else None
        if pid and pid in nodes: nodes[pid]["children"].append(node)
        else: roots.append(node)
    def _sort(n):
        n["children"].sort(key=lambda c: (c.get("name_en") or "").lower())
        for c in n["children"]: _sort(c)
    roots.sort(key=lambda i: (i.get("name_en") or "").lower())
    for r in roots: _sort(r)
    return roots

def _build_category_path(db, cid):
    cat = db.categories.find_one({"categoryId": cid})
    if not cat: return [], []
    path = []; full = []; cursor = cat; visited = set()
    while cursor and cursor.get("categoryId") and cursor.get("categoryId") not in visited:
        visited.add(cursor.get("categoryId"))
        path.insert(0, cursor.get("categoryId"))
        full.insert(0, {"categoryId": cursor.get("categoryId"), "name_en": cursor.get("name_en") or "", "name_de": cursor.get("name_de") or "", "slug": cursor.get("slug") or ""})
        pid = cursor.get("parentId")
        if not pid: break
        cursor = db.categories.find_one({"categoryId": pid})
    return path, full

def _recompute_product_state(db, pid):
    prod = db.products.find_one({"productId": pid})
    if not prod: return
    offers = list(db.store_products.find({"productId": pid, "isAvailable": True}))
    cheapest = None
    for o in offers:
        p = _effective_price(o)
        if p is None: continue
        if cheapest is None or float(p) < float(cheapest["price"]): cheapest = {"price": float(p), "storeProductId": o.get("storeProductId")}
    labels = set(prod.get("labels") or [])
    ca = _to_aware_utc(prod.get("createdAt"))
    if ca and ca >= (_now_utc() - timedelta(days=30)): labels.add("new")
    else: labels.discard("new")
    if any(o.get("promoPrice") is not None for o in offers): labels.add("on_sale")
    else: labels.discard("on_sale")
    db.products.update_one({"productId": pid}, {"$set": {"labels": sorted(labels), "cheapestPrice": cheapest["price"] if cheapest else None, "cheapestStoreProductId": cheapest["storeProductId"] if cheapest else None, "updatedAt": _now_utc()}})

def _recompute_lists_for_product(db, pid):
    lists = list(db.lists.find({"items.productId": pid}))
    if not lists: return 0
    u = 0
    for row in lists:
        total = 0.0; items = row.get("items") or []
        for item in items:
            cs = item.get("storeId"); q = {"productId": item.get("productId"), "isAvailable": True}
            if cs: q["storeId"] = cs
            offer = db.store_products.find_one(q, sort=[("promoPrice", 1), ("basePrice", 1), ("lastPriceUpdate", -1)])
            if not offer and cs: offer = db.store_products.find_one({"productId": item.get("productId"), "isAvailable": True}, sort=[("promoPrice", 1), ("basePrice", 1), ("lastPriceUpdate", -1)])
            up = float(_effective_price(offer) or 0); qty = float(item.get("quantity") or 1); lt = round(up * qty, 2)
            item["unitPrice"] = up; item["lineTotal"] = lt; total += lt
        db.lists.update_one({"_id": row.get("_id")}, {"$set": {"items": items, "totalPrice": round(total, 2), "updatedAt": _now_utc()}})
        u += 1
    return u

def _dashboard_payload(db):
    cols = ["stores", "brands", "categories", "products", "users", "feedback"]
    counts = {n: db[n].count_documents({}) for n in cols}
    stats = {"total_products": counts.get("products", 0), "total_stores": counts.get("stores", 0), "total_users": counts.get("users", 0), "pending_feedback": db.feedback.count_documents({"status": "pending"})}
    rf = list(db.feedback.find().sort("createdAt", -1).limit(5))
    return {"stats": stats, "recent_feedback": rf, "counts": counts}

def _redirect_admin(default, **kwargs):
    rt = (request.form.get("redirectTo") or "").strip().lower()
    m = {"overview": "admin.admin_dashboard", "products": "admin.admin_products_page", "categories": "admin.admin_categories_page", "brands": "admin.admin_brands_page", "lists": "admin.admin_lists_page", "feedback": "admin.admin_feedback_page"}
    return redirect(url_for(m.get(rt, default), **kwargs))

@admin_bp.route("/")
def admin_dashboard():
    ok, res = _require_admin()
    if not ok: return res
    db = get_db()
    if db is None: return render_template("admin_dashboard.html", error="DB offline", data={})
    return render_template("admin_dashboard.html", data=_dashboard_payload(db), user_email=res)

@admin_bp.route("/products")
def admin_products_page():
    ok, res = _require_admin()
    if not ok: return res
    db = get_db()
    if db is None: return render_template("admin_products.html", error="DB offline", data={})
    qt = (request.args.get("q") or "").strip(); bf = (request.args.get("brand") or "").strip()
    page = _parse_positive_int(request.args.get("page"), 1); per = 25; q = {}
    if qt: q["$or"] = [{"productId": {"$regex": qt, "$options": "i"}}, {"name_en": {"$regex": qt, "$options": "i"}}, {"name_de": {"$regex": qt, "$options": "i"}}, {"barcode": {"$regex": qt, "$options": "i"}}]
    if bf: q["brandId"] = bf
    total = db.products.count_documents(q); tp = max((total + per - 1) // per, 1); page = min(page, tp)
    products = list(db.products.find(q, {"_id": 0}).sort([("updatedAt", -1), ("createdAt", -1), ("name_en", 1)]).skip((page-1)*per).limit(per))
    categories = list(db.categories.find({}, {"_id": 0, "categoryId": 1, "name_en": 1}).sort("name_en", 1))
    brands = list(db.brands.find({}, {"_id": 0, "brandId": 1, "name": 1, "name_en": 1}).sort("name", 1))
    stores = list(db.stores.find({}, {"_id": 0, "storeId": 1, "name": 1}).sort("name", 1))
    cat_map = {c.get("categoryId"): c.get("name_en") or prettify_slug(c.get("categoryId")) for c in categories}
    brand_map = {b.get("brandId"): b.get("name_en") or b.get("name") or prettify_slug(b.get("brandId")) for b in brands}
    store_map = {s.get("storeId"): s.get("name") for s in stores}
    for row in products:
        row["category_name"] = cat_map.get(row.get("categoryId")) or "Uncategorized"
        row["brand_name"] = brand_map.get(row.get("brandId")) or "Generic"
        row["createdAtDisplay"] = _format_admin_dt(row.get("createdAt")); row["updatedAtDisplay"] = _format_admin_dt(row.get("updatedAt"))
    p_offers = {}
    for pid in [p.get("productId") for p in products]:
        offs = list(db.store_products.find({"productId": pid}, {"_id": 0}).sort([("lastPriceUpdate", -1)]).limit(40))
        for o in offs: o["storeName"] = store_map.get(o.get("storeId")) or "Unknown"; o["lastPriceUpdateDisplay"] = _format_admin_dt(o.get("lastPriceUpdate") or o.get("updatedAt"))
        p_offers[pid] = offs
    sel_id = (request.args.get("edit") or "").strip()
    sel_p = db.products.find_one({"productId": sel_id}, {"_id": 0}) if sel_id else None
    sel_cat_names = [cat_map.get(cid) or "Unknown" for cid in (sel_p.get("categoryPath") or [])] if sel_p else []
    data = {"products": products, "product_offers": p_offers, "selected_product": sel_p, "selected_category_names": sel_cat_names, "categories": categories, "brands": brands, "stores": stores, "q": qt, "page": page, "per_page": per, "total": total, "total_pages": tp, "has_prev": page > 1, "has_next": page < tp}
    return render_template("admin_products.html", data=data, user_email=res)

@admin_bp.route("/categories")
def admin_categories_page():
    ok, res = _require_admin()
    if not ok: return res
    db = get_db()
    if db is None: return render_template("admin_categories.html", error="DB offline", data={})
    qt = (request.args.get("q") or "").strip()
    all_cats = list(db.categories.find({}, {"_id": 0}).sort([("name_en", 1)]))
    for r in all_cats:
        r["name_en"] = r.get("name_en") or prettify_slug(r.get("categoryId"))
        r["name_de"] = r.get("name_de") or prettify_slug(r.get("categoryId"))
    cats = all_cats
    if qt:
        ql = qt.lower()
        cats = [r for r in all_cats if ql in str(r.get("categoryId")).lower() or ql in str(r.get("name_en")).lower()]
    cat_map = {r.get("categoryId"): r.get("name_en") for r in all_cats}
    for r in cats: r["parentName"] = cat_map.get(r.get("parentId")); r["updatedAtDisplay"] = _format_admin_dt(r.get("updatedAt"))
    sel_id = (request.args.get("edit") or "").strip()
    sel = db.categories.find_one({"categoryId": sel_id}, {"_id": 0}) if sel_id else None
    roots = [{"categoryId": r.get("categoryId"), "name_en": r.get("name_en")} for r in all_cats if r.get("categoryId")]
    tree = _build_category_tree(cats if qt else all_cats)
    data = {"q": qt, "categories": cats, "category_tree": tree, "selected_category": sel, "root_categories": roots}
    return render_template("admin_categories.html", data=data, user_email=res)

@admin_bp.route("/brands")
def admin_brands_page():
    ok, res = _require_admin()
    if not ok: return res
    db = get_db()
    if db is None: return render_template("admin_brands.html", error="DB offline", data={})
    qt = (request.args.get("q") or "").strip(); q = {}
    if qt: q = {"$or": [{"brandId": {"$regex": qt, "$options": "i"}}, {"name": {"$regex": qt, "$options": "i"}}]}
    brands = list(db.brands.find(q, {"_id": 0}).sort([("updatedAt", -1), ("name", 1)]).limit(250))
    for r in brands: r["name_en"] = r.get("name_en") or r.get("name") or prettify_slug(r.get("brandId")); r["updatedAtDisplay"] = _format_admin_dt(r.get("updatedAt"))
    sid = (request.args.get("edit") or "").strip()
    sel = db.brands.find_one({"brandId": sid}, {"_id": 0}) if sid else None
    data = {"q": qt, "brands": brands, "selected_brand": sel}
    return render_template("admin_brands.html", data=data, user_email=res)

@admin_bp.route("/lists")
def admin_lists_page():
    ok, res = _require_admin()
    if not ok: return res
    db = get_db()
    if db is None: return render_template("admin_lists.html", error="DB offline", data={})
    lists = list(db.lists.find({}, {"_id": 0}).sort("updatedAt", -1).limit(80))
    pub_lists = list(db.public_lists.find({}, {"_id": 0}).sort("createdAt", -1).limit(80))
    prods = list(db.products.find({}, {"_id": 0, "productId": 1, "name_en": 1}).sort("name_en", 1).limit(500))
    users = list(db.users.find({}, {"_id": 0, "userId": 1, "email": 1, "name": 1}))
    u_map = {u.get("userId"): u.get("email") or u.get("name") or "Unknown" for u in users}
    for r in lists:
        r["owner_display"] = r.get("owner") or u_map.get(r.get("userId")) or "Unknown"
        r["createdAtDisplay"] = _format_admin_dt(r.get("createdAt")); r["updatedAtDisplay"] = _format_admin_dt(r.get("updatedAt"))
        items = r.get("items") or []; r["items"] = items; r["itemsCount"] = len(items)
        for i in items: i["product_display"] = i.get("name") or i.get("productId") or "Item"; i["quantity_display"] = i.get("quantity") or i.get("qty") or 1
    u_opts = [{"userId": u.get("userId"), "label": u.get("email") or u.get("name") or "Unknown"} for u in users]
    data = {"lists": lists, "public_lists": pub_lists, "products": prods, "users": u_opts}
    return render_template("admin_lists.html", data=data, user_email=res)

@admin_bp.route("/feedback")
def admin_feedback_page():
    ok, res = _require_admin()
    if not ok: return res
    db = get_db()
    if db is None: return render_template("admin_feedback.html", error="DB offline", data={})
    sf = (request.args.get("status") or "all").strip().lower(); q = {}
    if sf != "all": q["status"] = sf
    fb = list(db.feedback.find(q, {"_id": 0}).sort("createdAt", -1).limit(120))
    data = {"feedback": fb, "status_filter": sf}
    return render_template("admin_feedback.html", data=data, user_email=res)

@admin_bp.route("/api/overview")
def admin_overview_api():
    ok, res = _require_admin()
    if not ok: return res
    db = get_db()
    if db is None: return jsonify({"status": "error"}), 500
    return jsonify({"status": "ok", "data": _dashboard_payload(db)})

@admin_bp.route("/stores/save", methods=["POST"])
def admin_save_store():
    ok, res = _require_admin(); db = get_db()
    sid = (request.form.get("storeId") or "").strip() or _id("store")
    payload = {"storeId": sid, "name": (request.form.get("name") or "").strip(), "logoUrl": (request.form.get("logoUrl") or "").strip(), "website": (request.form.get("website") or "").strip(), "country": (request.form.get("country") or "AT").strip(), "apiAvailable": _to_bool(request.form.get("apiAvailable")), "scrapingRequired": _to_bool(request.form.get("scrapingRequired"), True), "updatedAt": _now_utc()}
    if not payload["name"]: flash("Name required", "error"); return _redirect_admin("admin.admin_dashboard")
    db.stores.update_one({"storeId": sid}, {"$set": payload, "$setOnInsert": {"createdAt": _now_utc()}}, upsert=True)
    flash("Store saved", "success"); return _redirect_admin("admin.admin_dashboard")

@admin_bp.route("/brands/save", methods=["POST"])
def admin_save_brand():
    ok, res = _require_admin(); db = get_db()
    en, de = _localized_pair(request.form.get("name_en") or request.form.get("name"), request.form.get("name_de"))
    bid = (request.form.get("brandId") or "").strip() or _id("brand")
    payload = {"brandId": bid, "name": en, "name_en": en, "name_de": de, "image_url": (request.form.get("image_url") or "").strip(), "website": (request.form.get("website") or "").strip(), "updatedAt": _now_utc()}
    if not payload["name_en"]: flash("Name required", "error"); return _redirect_admin("admin.admin_brands_page")
    db.brands.update_one({"brandId": bid}, {"$set": payload, "$setOnInsert": {"createdAt": _now_utc()}}, upsert=True)
    flash("Brand saved", "success"); return _redirect_admin("admin.admin_brands_page", edit=bid)

@admin_bp.route("/categories/save", methods=["POST"])
def admin_save_category():
    ok, res = _require_admin(); db = get_db()
    cid = (request.form.get("categoryId") or "").strip() or _id("cat")
    en, de = _localized_pair(request.form.get("name_en"), request.form.get("name_de"))
    payload = {"categoryId": cid, "name_en": en, "name_de": de, "slug": (request.form.get("slug") or "").strip(), "image_url": (request.form.get("image_url") or "").strip(), "parentId": (request.form.get("parentId") or "").strip() or None, "updatedAt": _now_utc()}
    if not payload["slug"]: payload["slug"] = _slugify(en or de) or cid
    if not payload["name_en"]: flash("Name required", "error"); return _redirect_admin("admin.admin_categories_page")
    db.categories.update_one({"categoryId": cid}, {"$set": payload, "$setOnInsert": {"createdAt": _now_utc()}}, upsert=True)
    path, full = _build_category_path(db, cid)
    db.categories.update_one({"categoryId": cid}, {"$set": {"path": path, "fullPathNames": full, "updatedAt": _now_utc()}})
    flash("Category saved", "success"); return _redirect_admin("admin.admin_categories_page", edit=cid)


@admin_bp.route("/products/save-ai", methods=["POST"])
def admin_save_ai_product():
    ok, res = _require_admin(); db = get_db()
    if not ok: return res
    if db is None: return res
    pid = _id("prod")
    cid = (request.form.get("categoryId") or "").strip()
    path, _ = _build_category_path(db, cid)
    
    en = request.form.get("name_en")
    de = request.form.get("name_de")
    if not en:
        flash("Name required", "error")
        return redirect(url_for("admin.admin_smart_import_page"))
        
    payload = {
        "productId": pid, 
        "name_en": en, 
        "name_de": de, 
        "name": en,
        "brandId": (request.form.get("brandId") or "").strip() or None, 
        "categoryId": cid or None, 
        "categoryPath": path, 
        "unitSize": (request.form.get("size") or "").strip(), 
        "defaultImageUrl": (request.form.get("image_url") or "").strip(), 
        "description_en": request.form.get("description_en"), 
        "description_de": request.form.get("description_de"), 
        "updatedAt": _now_utc()
    }
    
    db.products.update_one({"productId": pid}, {"$set": payload, "$setOnInsert": {"createdAt": _now_utc()}}, upsert=True)
    
    # Array of stores
    store_urls = request.form.getlist("store_url")
    prices = request.form.getlist("price")
    store_ids = request.form.getlist("store_id")
    
    for i in range(min(len(store_urls), len(prices))):
        s_url = store_urls[i].strip()
        p_val = prices[i].strip()
        s_id = store_ids[i].strip() if i < len(store_ids) else None
        
        if not s_url or not p_val or not s_id:
            continue
            
        try:
            p_val = float(p_val)
        except:
            continue
            
        spid = _id("sp")
        promo_prices = request.form.getlist("promo_price")
        offer_details = request.form.getlist("offer_details")
        
        pr_val = None
        od_val = None
        if i < len(promo_prices):
            try:
                if promo_prices[i].strip():
                    pr_val = float(promo_prices[i].strip())
            except:
                pass
        
        if i < len(offer_details):
            od_val = offer_details[i].strip() or None

        db.store_products.update_one({"storeProductId": spid}, {"$set": {
            "storeProductId": spid,
            "productId": pid,
            "storeId": s_id,
            "productPageUrl": s_url,
            "basePrice": p_val,
            "promoPrice": pr_val,
            "offerDetails": od_val,
            "isAvailable": True,
            "lastPriceUpdate": _now_utc(),
            "updatedAt": _now_utc()
        }, "$setOnInsert": {"createdAt": _now_utc()}}, upsert=True)
        
        db.price_history.insert_one({
            "historyId": _id("hist"), 
            "storeProductId": spid, 
            "oldPrice": None, 
            "newPrice": p_val, 
            "timestamp": _now_utc()
        })

    _recompute_product_state(db, pid)
    flash("AI Product imported successfully!", "success")
    return redirect(url_for("admin.admin_products_page"))


@admin_bp.route("/api/products/search", methods=["GET"])
def admin_api_products_search():
    ok, res = _require_admin(); db = get_db()
    if not ok or db is None: return jsonify([])
    q = (request.args.get("q") or "").strip()
    if not q: return jsonify([])
    query = {"$or": [
        {"name_en": {"$regex": q, "$options": "i"}}, {"name": {"$regex": q, "$options": "i"}},
        {"name_de": {"$regex": q, "$options": "i"}},
        {"productId": {"$regex": q, "$options": "i"}}
    ]}
    docs = list(db.products.find(query, {"_id": 0, "productId": 1, "name_en": 1, "name": 1}).sort("name_en", 1).limit(20))
    return jsonify([{"id": d.get("productId"), "text": d.get("name_en") or d.get("name") or d.get("productId")} for d in docs])

@admin_bp.route("/products/merge", methods=["POST"])
def admin_merge_products():
    ok, res = _require_admin(); db = get_db()
    if not ok or db is None: return _redirect_admin("admin.admin_dashboard")
    
    target_id = (request.form.get("targetProductId") or "").strip()
    source_id = (request.form.get("sourceProductId") or "").strip()
    
    if not target_id or not source_id or target_id == source_id:
        flash("Invalid merge parameters.", "error")
        return _redirect_admin("admin.admin_products_page")
        
    target_prod = db.products.find_one({"productId": target_id})
    source_prod = db.products.find_one({"productId": source_id})
    
    if not target_prod or not source_prod:
        flash("One or both products not found.", "error")
        return _redirect_admin("admin.admin_products_page")
        
    # Move all store_products from source to target
    db.store_products.update_many(
        {"productId": source_id},
        {"$set": {"productId": target_id, "updatedAt": _now_utc()}}
    )
    
    # Update user shopping lists
    db.lists.update_many(
        {"items.productId": source_id},
        {"$set": {"items.$[elem].productId": target_id}},
        array_filters=[{"elem.productId": source_id}]
    )
    
    # Delete the source product
    db.products.delete_one({"productId": source_id})
    
    # Recompute state for target
    _recompute_product_state(db, target_id)
    _recompute_lists_for_product(db, target_id)
    
    flash(f"Successfully merged {source_prod.get('name_en')} into {target_prod.get('name_en')}.", "success")
    return _redirect_admin("admin.admin_products_page")

@admin_bp.route("/products/save", methods=["POST"])
def admin_save_product():
    ok, res = _require_admin(); db = get_db()
    pid = (request.form.get("productId") or "").strip() or _id("prod")
    cid = (request.form.get("categoryId") or "").strip()
    path, _ = _build_category_path(db, cid)
    roots = {"cat_produce", "cat_pantry", "cat_dairy", "cat_meat", "cat_frozen", "cat_bakery", "cat_baby-food", "cat_snacks", "cat_fast-food-to-go", "cat_household", "cat_beverages"}
    if (not cid) or (cid in roots):
        mapper = CategoryMapper(); signal = " ".join([request.form.get("name_en") or "", request.form.get("name_de") or "", request.form.get("categoryId") or ""])
        inf = mapper.map_category_with_path(signal); inf_leaf = inf.get("categoryId")
        if inf_leaf: cid = inf_leaf; path, _ = _build_category_path(db, cid)
    en, de = _localized_pair(request.form.get("name_en"), request.form.get("name_de"))
    den, dde = _localized_optional_pair(request.form.get("description_en"), request.form.get("description_de"))
    # Fallback to image_url if defaultImageUrl is empty
    img_url = (request.form.get("defaultImageUrl") or request.form.get("image_url") or "").strip()
    
    # Handle inline store offer addition
    new_store_ids = request.form.getlist("newStoreId[]")
    new_store_urls = request.form.getlist("newStoreUrl[]")
    new_store_prices = request.form.getlist("newStorePrice[]")

    if not img_url and new_store_urls and new_store_urls[0].strip():
        from scripts.ai_product_fetcher import fetch_product_from_url
        auto_dt = fetch_product_from_url(new_store_urls[0].strip())
        if auto_dt and auto_dt.get("success") and auto_dt.get("data"):
            img_url = auto_dt["data"].get("image_url", img_url)

    payload = {"productId": pid, "name_en": en, "name_de": de, "name": en, "brandId": (request.form.get("brandId") or "").strip() or None, "categoryId": cid or None, "categoryPath": path, "unitSize": (request.form.get("unitSize") or "").strip(), "barcode": (request.form.get("barcode") or "").strip(), "defaultImageUrl": img_url, "labels": [i.strip() for i in (request.form.get("labels") or "").split(",") if i.strip()], "description_en": den, "description_de": dde, "updatedAt": _now_utc()}
    if not payload["name_en"]: flash("Name required", "error"); return _redirect_admin("admin.admin_dashboard")
    db.products.update_one({"productId": pid}, {"$set": payload, "$setOnInsert": {"createdAt": _now_utc()}}, upsert=True)
    
    for i in range(len(new_store_ids)):
        store_id = (new_store_ids[i] or "").strip()
        if not store_id: continue
        
        url = (new_store_urls[i] or "").strip()
        try:
            base_price = float(new_store_prices[i] or 0.0)
        except ValueError:
            base_price = 0.0
            
        if url and base_price > 0:
            spid = _id("sp")
            store_payload = {
                "storeProductId": spid, "productId": pid, "storeId": store_id,
                "productPageUrl": url,
                "basePrice": base_price,
                "promoPrice": None,
                "isAvailable": True, "lastPriceUpdate": _now_utc(), "updatedAt": _now_utc()
            }
            db.store_products.insert_one(store_payload)
            db.price_history.insert_one({
                "historyId": _id("hist"), "storeProductId": spid,
                "oldPrice": None, "newPrice": base_price, "timestamp": _now_utc()
            })

    _recompute_product_state(db, pid); flash("Product saved", "success"); return _redirect_admin("admin.admin_dashboard")

@admin_bp.route("/store-products/save", methods=["POST"])
def admin_save_store_product():
    ok, res = _require_admin(); db = get_db()
    spid = (request.form.get("storeProductId") or "").strip() or _id("sp"); pid = (request.form.get("productId") or "").strip()
    def _tf(n):
        try: return float(request.form.get(n))
        except: return None
    payload = {"storeProductId": spid, "productId": pid, "storeId": (request.form.get("storeId") or "").strip(), "productPageUrl": (request.form.get("productPageUrl") or "").strip(), "basePrice": _tf("basePrice") or 0.0, "promoPrice": _tf("promoPrice"), "isAvailable": _to_bool(request.form.get("isAvailable"), True), "lastPriceUpdate": _now_utc(), "updatedAt": _now_utc()}
    if not payload["productId"] or not payload["storeId"]: flash("IDs required", "error"); return _redirect_admin("admin.admin_dashboard")
    exist = db.store_products.find_one({"storeProductId": spid})
    old_p = _effective_price(exist) if exist else None
    db.store_products.update_one({"storeProductId": spid}, {"$set": payload, "$setOnInsert": {"createdAt": _now_utc()}}, upsert=True)
    new_p = _effective_price(payload)
    if old_p != new_p: db.price_history.insert_one({"historyId": _id("hist"), "storeProductId": spid, "oldPrice": old_p, "newPrice": new_p, "timestamp": _now_utc()})
    _recompute_product_state(db, pid); _recompute_lists_for_product(db, pid); flash("Store product saved", "success")
    return _redirect_admin("admin.admin_dashboard")

@admin_bp.route("/products/delete/<pid>", methods=["POST"])
def admin_delete_product(pid):
    ok, res = _require_admin(); db = get_db()
    db.products.delete_one({"productId": pid}); db.store_products.delete_many({"productId": pid})
    db.lists.update_many({"items.productId": pid}, {"$pull": {"items": {"productId": pid}}})
    flash(f"Deleted {pid}", "success"); return redirect(url_for("admin.admin_products_page"))

@admin_bp.route("/categories/delete/<cid>", methods=["POST"])
def admin_delete_category(cid):
    ok, res = _require_admin(); db = get_db()
    if db.categories.find_one({"parentId": cid}) or db.products.find_one({"categoryId": cid}): flash("In use", "error"); return redirect(url_for("admin.admin_categories_page"))
    db.categories.delete_one({"categoryId": cid}); flash(f"Deleted {cid}", "success"); return redirect(url_for("admin.admin_categories_page"))

@admin_bp.route("/brands/delete/<bid>", methods=["POST"])
def admin_delete_brand(bid):
    ok, res = _require_admin(); db = get_db()
    if db.products.find_one({"brandId": bid}): flash("In use", "error"); return redirect(url_for("admin.admin_brands_page"))
    db.brands.delete_one({"brandId": bid}); flash(f"Deleted {bid}", "success"); return redirect(url_for("admin.admin_brands_page"))

@admin_bp.route("/api/store-products/delete/<spid>", methods=["POST"])
def admin_delete_store_product(spid):
    from flask import jsonify
    ok, res = _require_admin()
    if not ok: return jsonify({"success": False, "error": "Unauthorized"}), 401
    db = get_db()
    offer = db.store_products.find_one({"storeProductId": spid})
    if not offer: return jsonify({"success": False, "error": "Not found"}), 404
    db.store_products.delete_one({"storeProductId": spid})
    db.price_history.delete_many({"storeProductId": spid})
    _recompute_product_state(db, offer["productId"])
    _recompute_lists_for_product(db, offer["productId"])
    return jsonify({"success": True})

@admin_bp.route("/scraper/run")
def run_scraper_manual():
    ok, res = _require_admin()
    import subprocess; subprocess.Popen(["python3", "scripts/cron_pipeline.py"])
    flash("Price updates started", "success"); return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/cache/clear")
def clear_cache():
    ok, res = _require_admin(); flash("Cache cleared", "success"); return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/products/smart-import", methods=["GET"])
def admin_smart_import_page():
    ok, res = _require_admin()
    if not ok: return res
    db = get_db()
    
    categories = []
    if db is not None:
        try:
            # Fallback to local dev JSON if DB breaks/is empty
            categories = list(db.categories.find().sort("name_en", 1))
        except Exception as e:
            print("DB error fetching categories:", e)
            
    if not categories:
        import json
        import os
        try:
            with open(os.path.join(os.path.dirname(__file__), '../../data/products.json')) as f:
                product_data = json.load(f)
                # Infer categories from products in worst case, or better yet, read categories.json if exists
        except:
            pass
            
    return render_template("admin_smart_import.html", categories=categories)

@admin_bp.route("/api/products/smart-extract", methods=["POST"])
def admin_smart_extract():
    try:
        ok, res = _require_admin()
        if not ok:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        
        url = (request.json or {}).get("url")
        if not url: 
            return jsonify({"success": False, "error": "No URL provided"}), 400
        
        from scripts.ai_product_fetcher import fetch_product_from_url
        result = fetch_product_from_url(url)
            
        if result and result.get("success") and result.get("data"):
            data = result["data"]
            name_de = data.get("name_de", "")
            if name_de:
                # Translating the German name extracted from the store page to English
                data["name_en"] = _translate_text(name_de, "de", "en")
                # Update the description with the new translated English name
                data["description_en"] = f"A carefully selected, high-quality {data['name_en']} essential for your pantry. It pairs nicely with fresh meals."
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": f"Internal Server Error: {str(e)}"}), 500

@admin_bp.route("/scans", methods=["GET"])
def pending_scans():
    db = get_db()
    if db is None:
        return "No DB", 500
    pending = list(db.pending_products.find({"status": "pending"}).sort("created_at", -1))
    return render_template("admin_pending_scans.html", scancount=len(pending), pending_scans=pending)

@admin_bp.route("/api/scans/<barcode>/approve", methods=["POST"])
def approve_scan(barcode):
    db = get_db()
    if db is None: return jsonify({"success": False})
    
    data = request.get_json() or {}
    name = data.get("name")
    category = data.get("category")
    price = data.get("price")
    store = data.get("store")
    
    db.pending_products.update_one({"barcode": barcode}, {"$set": {"status": "approved"}})
    
    # insert into products directly
    import uuid
    pid = str(uuid.uuid4())
    name_en = _translate_text(name, "de", "en") or name
    db.products.insert_one({
        "id": pid,
        "name": name_en,
        "name_en": name_en,
        "name_de": name,
        "barcode": barcode,
        "category": category,
        "categoryId": category.lower(),
        "created_at": datetime.now(timezone.utc)
    })
    if price and store:
         db.store_products.insert_one({
             "productId": pid,
             "storeId": store.lower(),
             "price": float(price),
             "currency": "EUR"
         })
         
    return jsonify({"success": True})

@admin_bp.route("/api/scans/<barcode>/reject", methods=["POST"])
def reject_scan(barcode):
    db = get_db()
    if db is None: return jsonify({"success": False})
    db.pending_products.update_one({"barcode": barcode}, {"$set": {"status": "rejected"}})
    return jsonify({"success": True})



@admin_bp.route('/api/products/bulk-delete', methods=['POST'])
def bulk_delete_products():
    from flask import request, jsonify
    from bson import ObjectId
    from utils.db import get_db
    
    try:
        data = request.get_json()
        if not data or 'ids' not in data:
            return jsonify({'error': 'Missing product IDs'}), 400
            
        ids = data['ids']
        if not isinstance(ids, list):
            return jsonify({'error': 'IDs must be a list'}), 400
            
        db = get_db()
        object_ids = []
        for id_str in ids:
            try:
                object_ids.append(ObjectId(id_str))
            except Exception:
                object_ids.append(id_str)
                
        if not object_ids:
            return jsonify({'error': 'No valid IDs provided'}), 400
            
        query = {'$or': [{'_id': {'$in': object_ids}}, {'productId': {'$in': object_ids}}]}
        result = db.products.delete_many(query)
        db.store_products.delete_many({'productId': {'$in': object_ids}})
        
        return jsonify({
            'message': f'Successfully deleted {result.deleted_count} products.', 
            'deleted_count': result.deleted_count
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
