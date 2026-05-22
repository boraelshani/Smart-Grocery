import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import requests
from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from models.users_model import get_user_by_email
from utils.category_mapper import CategoryMapper
from utils.mongo_mock import MockDb

from . import admin_bp

try:
    from deep_translator import GoogleTranslator
except Exception:  # pragma: no cover - optional dependency in some environments
    GoogleTranslator = None

# Helper constants and utilities
_TRANSLATION_CACHE = {}


def prettify_slug(t):
    if not t:
        return t
    t = (
        str(t)
        .replace("cat_", "")
        .replace("brand_", "")
        .replace("-", " ")
        .replace("_", " ")
    )
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
    except:
        return default


def _parse_int(value, default=0):
    try:
        return int(value)
    except:
        return default


def _slugify(value):
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _unique_category_slug(base_slug, exclude_category_id=None):
    from models.postgres_models import Category

    root_slug = _slugify(base_slug) or "category"
    slug = root_slug
    suffix = 2

    while True:
        q = Category.query.filter(Category.slug == slug)
        if exclude_category_id is not None:
            q = q.filter(Category.id != exclude_category_id)
        if not q.first():
            return slug
        slug = f"{root_slug}-{suffix}"
        suffix += 1


def _translate_text(text, source_lang="en", target_lang="de"):
    val = (text or "").strip()
    if not val or source_lang == target_lang:
        return val
    key = (val, source_lang, target_lang)
    if key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[key]
    api_url = (
        current_app.config.get("ADMIN_TRANSLATE_API_URL")
        or "https://libretranslate.com/translate"
    )
    try:
        resp = requests.post(
            api_url,
            json={
                "q": val,
                "source": source_lang,
                "target": target_lang,
                "format": "text",
            },
            timeout=2.0,
        )
        if resp.ok:
            translated = (resp.json().get("translatedText") or "").strip() or None
            _TRANSLATION_CACHE[key] = translated or val
        else:
            _TRANSLATION_CACHE[key] = val
    except:
        _TRANSLATION_CACHE[key] = val

    if _TRANSLATION_CACHE.get(key) == val and GoogleTranslator is not None:
        try:
            translated = (
                GoogleTranslator(source=source_lang, target=target_lang).translate(val)
                or ""
            ).strip()
            if translated:
                _TRANSLATION_CACHE[key] = translated
        except Exception:
            pass

    return _TRANSLATION_CACHE.get(key, val)


def _localized_pair(name_en, name_de):
    en = (name_en or "").strip()
    de = (name_de or "").strip()
    if not en and not de:
        return "", ""
    if not en and de:
        en = _translate_text(de, "de", "en") or de
    if not de and en:
        de = _translate_text(en, "en", "de") or en
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
        except:
            return value.strip()
    return "-"


def _admin_emails():
    return {
        i.strip().lower()
        for i in str(current_app.config.get("ADMIN_EMAILS", "")).split(",")
        if i.strip()
    }


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


def _effective_price(offer):
    if not isinstance(offer, dict):
        return None
    return (
        offer.get("promoPrice")
        if offer.get("promoPrice") is not None
        else offer.get("basePrice")
    )


def _build_category_tree(rows):
    nodes = {}
    children_map = {}
    for row in rows:
        cid = row.get("categoryId")
        if not cid:
            continue
        node = {
            "categoryId": cid,
            "name_en": row.get("name_en") or "Unnamed",
            "name_de": row.get("name_de") or "",
            "slug": row.get("slug") or "",
            "parentId": row.get("parentId"),
            "image_url": row.get("image_url"),
            "children": [],
        }
        nodes[cid] = node
        children_map.setdefault(node["parentId"], []).append(node)
    roots = []
    for cid, node in nodes.items():
        pid = str(node.get("parentId")) if node.get("parentId") else None
        if pid and pid in nodes:
            nodes[pid]["children"].append(node)
        else:
            roots.append(node)

    def _sort(n):
        n["children"].sort(key=lambda c: (c.get("name_en") or "").lower())
        for c in n["children"]:
            _sort(c)

    roots.sort(key=lambda i: (i.get("name_en") or "").lower())
    for r in roots:
        _sort(r)
    return roots


def _build_category_path(cid):
    from models.postgres_models import Category

    category = None
    try:
        category = Category.query.get(_parse_int(cid, 0))
    except Exception:
        category = None
    if not category:
        return [], []

    path = []
    full = []
    cursor = category
    visited = set()
    while cursor and cursor.id and cursor.id not in visited:
        visited.add(cursor.id)
        category_id = str(cursor.id)
        path.insert(0, category_id)
        full.insert(
            0,
            {
                "categoryId": category_id,
                "name_en": cursor.name_en or "",
                "name_de": cursor.name_de or "",
                "slug": cursor.slug or "",
            },
        )
        if not cursor.parent_id:
            break
        cursor = Category.query.get(cursor.parent_id)
    return path, full


def _recompute_product_state(db, pid):
    prod = db.products.find_one({"productId": pid})
    if not prod:
        return
    offers = list(db.store_products.find({"productId": pid, "isAvailable": True}))
    cheapest = None
    for o in offers:
        p = _effective_price(o)
        if p is None:
            continue
        if cheapest is None or float(p) < float(cheapest["price"]):
            cheapest = {"price": float(p), "storeProductId": o.get("storeProductId")}
    labels = set(prod.get("labels") or [])
    ca = _to_aware_utc(prod.get("createdAt"))
    if ca and ca >= (_now_utc() - timedelta(days=30)):
        labels.add("new")
    else:
        labels.discard("new")
    if any(o.get("promoPrice") is not None for o in offers):
        labels.add("on_sale")
    else:
        labels.discard("on_sale")
    db.products.update_one(
        {"productId": pid},
        {
            "$set": {
                "labels": sorted(labels),
                "cheapestPrice": cheapest["price"] if cheapest else None,
                "cheapestStoreProductId": cheapest["storeProductId"]
                if cheapest
                else None,
                "updatedAt": _now_utc(),
            }
        },
    )


def _recompute_lists_for_product(db, pid):
    lists = list(db.lists.find({"items.productId": pid}))
    if not lists:
        return 0
    u = 0
    for row in lists:
        total = 0.0
        items = row.get("items") or []
        for item in items:
            cs = item.get("storeId")
            q = {"productId": item.get("productId"), "isAvailable": True}
            if cs:
                q["storeId"] = cs
            offer = db.store_products.find_one(
                q, sort=[("promoPrice", 1), ("basePrice", 1), ("lastPriceUpdate", -1)]
            )
            if not offer and cs:
                offer = db.store_products.find_one(
                    {"productId": item.get("productId"), "isAvailable": True},
                    sort=[("promoPrice", 1), ("basePrice", 1), ("lastPriceUpdate", -1)],
                )
            up = float(_effective_price(offer) or 0)
            qty = float(item.get("quantity") or 1)
            lt = round(up * qty, 2)
            item["unitPrice"] = up
            item["lineTotal"] = lt
            total += lt
        db.lists.update_one(
            {"_id": row.get("_id")},
            {
                "$set": {
                    "items": items,
                    "totalPrice": round(total, 2),
                    "updatedAt": _now_utc(),
                }
            },
        )
        u += 1
    return u


def _dashboard_payload(db=None):
    """Build dashboard stats using PostgreSQL / SQLAlchemy models."""
    try:
        from models.postgres_models import (
            Brand,
            Category,
            Feedback,
            Product,
            Store,
            User,
        )

        counts = {
            "stores": Store.query.count(),
            "brands": Brand.query.count(),
            "categories": Category.query.count(),
            "products": Product.query.count(),
            "users": User.query.count(),
            "feedback": Feedback.query.count(),
        }
        stats = {
            "total_products": counts["products"],
            "total_stores": counts["stores"],
            "total_users": counts["users"],
            "pending_feedback": Feedback.query.filter_by(status="pending").count(),
        }
        rf_rows = Feedback.query.order_by(Feedback.created_at.desc()).limit(5).all()
        rf = [
            {
                "feedback_id": r.feedback_id,
                "user_email": r.user_email,
                "type": r.type,
                "subject": r.subject,
                "message": r.message,
                "status": r.status,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rf_rows
        ]
    except Exception as e:
        print(f"WARNING: _dashboard_payload error: {e}")
        counts = {
            n: 0
            for n in ["stores", "brands", "categories", "products", "users", "feedback"]
        }
        stats = {
            "total_products": 0,
            "total_stores": 0,
            "total_users": 0,
            "pending_feedback": 0,
        }
        rf = []
    return {"stats": stats, "recent_feedback": rf, "counts": counts}


def _redirect_admin(default, **kwargs):
    rt = (request.form.get("redirectTo") or "").strip().lower()
    m = {
        "overview": "admin.admin_dashboard",
        "products": "admin.admin_products_page",
        "categories": "admin.admin_categories_page",
        "brands": "admin.admin_brands_page",
        "lists": "admin.admin_lists_page",
        "feedback": "admin.admin_feedback_page",
    }
    return redirect(url_for(m.get(rt, default), **kwargs))


@admin_bp.route("/")
def admin_dashboard():
    ok, res = _require_admin()
    if not ok:
        return res
    return render_template(
        "admin_dashboard.html", data=_dashboard_payload(), user_email=res
    )


@admin_bp.route("/products")
def admin_products_page():
    ok, res = _require_admin()
    if not ok:
        return res
    from sqlalchemy import String, cast, or_

    from models.postgres_models import Brand, Category, Offer, Product, ProductStore, Store, User

    try:
        qt = (request.args.get("q") or "").strip()
        bf = (request.args.get("brand") or "").strip()
        page = _parse_positive_int(request.args.get("page"), 1)
        per = 25

        pq = Product.query
        if qt:
            pq = pq.filter(
                or_(
                    Product.name_de.ilike(f"%{qt}%"),
                    Product.barcode.ilike(f"%{qt}%"),
                    Product.brand.ilike(f"%{qt}%"),
                )
            )
        if bf:
            pq = pq.filter(Product.brand == bf)
        pq = pq.order_by(Product.updated_at.desc(), Product.name_de.asc())

        total = pq.count()
        tp = max((total + per - 1) // per, 1)
        page = min(page, tp)
        product_rows = pq.offset((page - 1) * per).limit(per).all()
        products = [r.to_dict() for r in product_rows]

        # categories / brands / stores for dropdowns
        cat_rows = Category.query.order_by(Category.name_en.asc()).all()
        brand_rows = Brand.query.order_by(Brand.name.asc()).all()
        store_rows = Store.query.filter_by(active=True).order_by(Store.name.asc()).all()

        categories = [
            {"categoryId": str(r.id), "name_en": r.name_en or prettify_slug(r.slug)}
            for r in cat_rows
        ]
        brands = [
            {
                "brandId": r.brand_id or str(r.id),
                "name": r.name,
                "name_en": r.name_en or r.name,
            }
            for r in brand_rows
        ]
        stores = [{"storeId": r.store_id, "name": r.name} for r in store_rows]

        cat_map = {str(r.id): r.name_en or prettify_slug(r.slug) for r in cat_rows}
        store_map = {r.store_id: r.name for r in store_rows}
        # brand map keyed by both brand_id and brand name (Products store the name, not the id)
        brand_map = {}
        for r in brand_rows:
            display = r.name_en or r.name or ""
            if r.brand_id:
                brand_map[r.brand_id] = display
            if r.name:
                brand_map[r.name] = display

        for row in products:
            row["category_name"] = (
                cat_map.get(row.get("categoryId") or "") or "Uncategorized"
            )
            row["brand_name"] = (
                brand_map.get(row.get("brand") or row.get("brandId") or "")
                or row.get("brand")
                or "Generic"
            )
            row["createdAtDisplay"] = _format_admin_dt(row.get("createdAt"))
            row["updatedAtDisplay"] = _format_admin_dt(row.get("updatedAt"))

        p_offers = {}
        for prod in products:
            pid_int = _parse_int(prod.get("id") or prod.get("productId"), 0)
            if pid_int:
                offer_rows = (
                    ProductStore.query.filter_by(product_id=pid_int, is_available=True)
                    .order_by(ProductStore.last_seen.desc())
                    .limit(40)
                    .all()
                )
                offs = []
                for o in offer_rows:
                    offs.append(
                        {
                            "storeProductId": f"{o.product_id}_{o.store_id}",
                            "productId": str(o.product_id),
                            "storeId": o.store_id,
                            "storeName": store_map.get(o.store_id) or o.store_id or "Unknown",
                            "basePrice": float(o.base_price) if o.base_price is not None else None,
                            "isAvailable": bool(o.is_available),
                            "productPageUrl": o.product_url,
                            "lastSeen": o.last_seen,
                            "lastPriceUpdateDisplay": _format_admin_dt(o.last_seen),
                        }
                    )
                p_offers[prod.get("productId")] = offs

        sel_id = (request.args.get("edit") or "").strip()
        sel_p = None
        if sel_id:
            r = Product.query.filter_by(id=_parse_int(sel_id, 0)).first()
            sel_p = r.to_dict() if r else None

        data = {
            "products": products,
            "product_offers": p_offers,
            "selected_product": sel_p,
            "selected_category_names": [],
            "categories": categories,
            "brands": brands,
            "stores": stores,
            "q": qt,
            "page": page,
            "per_page": per,
            "total": total,
            "total_pages": tp,
            "has_prev": page > 1,
            "has_next": page < tp,
        }
    except Exception as e:
        print(f"admin_products_page error: {e}")
        data = {
            "products": [],
            "product_offers": {},
            "selected_product": None,
            "selected_category_names": [],
            "categories": [],
            "brands": [],
            "stores": [],
            "q": "",
            "page": 1,
            "per_page": 25,
            "total": 0,
            "total_pages": 1,
            "has_prev": False,
            "has_next": False,
            "error": str(e),
        }
    return render_template("admin_products.html", data=data, user_email=res)


@admin_bp.route("/categories")
def admin_categories_page():
    ok, res = _require_admin()
    if not ok:
        return res
    from models.postgres_models import Category

    try:
        qt = (request.args.get("q") or "").strip()
        cat_rows = Category.query.order_by(Category.name_en.asc()).all()

        def _cat_to_dict(r):
            return {
                "categoryId": str(r.id),
                "name_en": r.name_en or prettify_slug(r.slug),
                "name_de": r.name_de or prettify_slug(r.slug),
                "slug": r.slug or "",
                "parentId": str(r.parent_id) if r.parent_id else None,
                "image_url": r.image_url,
                "level": r.level,
                "updatedAt": None,
            }

        all_cats = [_cat_to_dict(r) for r in cat_rows]
        cats = all_cats
        if qt:
            ql = qt.lower()
            cats = [
                r
                for r in all_cats
                if ql in r["categoryId"].lower() or ql in r["name_en"].lower()
            ]

        cat_map = {r["categoryId"]: r["name_en"] for r in all_cats}
        for r in all_cats:
            r["parentName"] = cat_map.get(r["parentId"] or "")
            r["updatedAtDisplay"] = "-"

        sel_id = (request.args.get("edit") or "").strip()
        sel = None
        if sel_id:
            sr = Category.query.filter_by(id=_parse_int(sel_id, 0)).first()
            sel = _cat_to_dict(sr) if sr else None

        roots = [
            {"categoryId": r["categoryId"], "name_en": r["name_en"]} for r in all_cats
        ]
        tree = _build_category_tree(cats if qt else all_cats)
        data = {
            "q": qt,
            "categories": cats,
            "category_tree": tree,
            "selected_category": sel,
            "root_categories": roots,
        }
    except Exception as e:
        print(f"admin_categories_page error: {e}")
        data = {
            "q": "",
            "categories": [],
            "category_tree": [],
            "selected_category": None,
            "root_categories": [],
            "error": str(e),
        }
    return render_template("admin_categories.html", data=data, user_email=res)


@admin_bp.route("/brands")
def admin_brands_page():
    ok, res = _require_admin()
    if not ok:
        return res
    from sqlalchemy import String, cast, or_

    from models.postgres_models import Brand

    try:
        qt = (request.args.get("q") or "").strip()
        bq = Brand.query
        if qt:
            bq = bq.filter(
                or_(
                    Brand.name.ilike(f"%{qt}%"),
                    Brand.name_en.ilike(f"%{qt}%"),
                    Brand.brand_id.ilike(f"%{qt}%"),
                )
            )
        bq = bq.order_by(Brand.updated_at.desc(), Brand.name.asc()).limit(250)
        brand_rows = bq.all()

        def _brand_to_dict(r):
            return {
                "brandId": r.brand_id or str(r.id),
                "name": r.name or "",
                "name_en": r.name_en or r.name or prettify_slug(r.brand_id or ""),
                "name_de": r.name_de or "",
                "image_url": r.image_url or "",
                "website": r.website or "",
                "updatedAt": r.updated_at,
                "updatedAtDisplay": _format_admin_dt(r.updated_at),
            }

        brands = [_brand_to_dict(r) for r in brand_rows]
        sel_id = (request.args.get("edit") or "").strip()
        sel = None
        if sel_id:
            sr = (
                Brand.query.filter(
                    (Brand.brand_id == sel_id) | (cast(Brand.id, String) == sel_id)
                ).first()
                if sel_id
                else None
            )
            sel = _brand_to_dict(sr) if sr else None
        data = {"q": qt, "brands": brands, "selected_brand": sel}
    except Exception as e:
        print(f"admin_brands_page error: {e}")
        data = {"q": "", "brands": [], "selected_brand": None, "error": str(e)}
    return render_template("admin_brands.html", data=data, user_email=res)


@admin_bp.route("/lists")
def admin_lists_page():
    ok, res = _require_admin()
    if not ok:
        return res
    from models.postgres_models import Product, PublicList, ShoppingList, User

    try:
        # Shopping lists
        sl_rows = (
            ShoppingList.query.order_by(ShoppingList.updated_at.desc()).limit(80).all()
        )
        user_cache = {}

        def _get_user(uid):
            if uid not in user_cache:
                u = User.query.get(uid)
                user_cache[uid] = u.email if u else "Unknown"
            return user_cache[uid]

        lists = []
        for sl in sl_rows:
            d = sl.to_dict()
            d["owner_display"] = _get_user(sl.user_id)
            d["createdAtDisplay"] = _format_admin_dt(sl.created_at)
            d["updatedAtDisplay"] = _format_admin_dt(sl.updated_at)
            items = d.get("items") or []
            d["itemsCount"] = len(items)
            for i in items:
                i["product_display"] = i.get("name") or i.get("productId") or "Item"
                i["quantity_display"] = i.get("quantity") or i.get("qty") or 1
            lists.append(d)

        # Public lists
        pl_rows = (
            PublicList.query.order_by(PublicList.created_at.desc()).limit(80).all()
        )
        pub_lists = [
            {
                "list_id": r.list_id,
                "name": r.name,
                "items": r.items or [],
                "createdAt": r.created_at,
                "createdAtDisplay": _format_admin_dt(r.created_at),
            }
            for r in pl_rows
        ]

        # Products dropdown
        prod_rows = Product.query.order_by(Product.name_de.asc()).limit(500).all()
        prods = [
            {"productId": str(r.id), "name_en": r.name_de or str(r.id)}
            for r in prod_rows
        ]

        # Users dropdown
        user_rows = User.query.order_by(User.email.asc()).all()
        u_opts = [
            {"userId": r.user_id or str(r.id), "label": r.email or r.name or "Unknown"}
            for r in user_rows
        ]

        data = {
            "lists": lists,
            "public_lists": pub_lists,
            "products": prods,
            "users": u_opts,
        }
    except Exception as e:
        print(f"admin_lists_page error: {e}")
        data = {
            "lists": [],
            "public_lists": [],
            "products": [],
            "users": [],
            "error": str(e),
        }
    return render_template("admin_lists.html", data=data, user_email=res)


@admin_bp.route("/feedback")
def admin_feedback_page():
    ok, res = _require_admin()
    if not ok:
        return res
    from models.postgres_models import Feedback

    try:
        sf = (request.args.get("status") or "all").strip().lower()
        fq = Feedback.query
        if sf != "all":
            fq = fq.filter_by(status=sf)
        fb_rows = fq.order_by(Feedback.created_at.desc()).limit(120).all()
        fb = [
            {
                "feedback_id": r.feedback_id or str(r.id),
                "user_email": r.user_email or "",
                "type": r.type or "",
                "subject": r.subject or "",
                "message": r.message or "",
                "status": r.status or "pending",
                "createdAt": r.created_at,
                "createdAtDisplay": _format_admin_dt(r.created_at),
            }
            for r in fb_rows
        ]
        data = {"feedback": fb, "status_filter": sf}
    except Exception as e:
        print(f"admin_feedback_page error: {e}")
        data = {"feedback": [], "status_filter": "all", "error": str(e)}
    return render_template("admin_feedback.html", data=data, user_email=res)


@admin_bp.route("/api/overview")
def admin_overview_api():
    ok, res = _require_admin()
    if not ok:
        return res
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass
    if db is None:
        return jsonify({"status": "error"}), 500
    return jsonify({"status": "ok", "data": _dashboard_payload()})


@admin_bp.route("/stores/save", methods=["POST"])
def admin_save_store():
    ok, res = _require_admin()
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass
    sid = (request.form.get("storeId") or "").strip() or _id("store")
    payload = {
        "storeId": sid,
        "name": (request.form.get("name") or "").strip(),
        "logoUrl": (request.form.get("logoUrl") or "").strip(),
        "website": (request.form.get("website") or "").strip(),
        "country": (request.form.get("country") or "AT").strip(),
        "apiAvailable": _to_bool(request.form.get("apiAvailable")),
        "scrapingRequired": _to_bool(request.form.get("scrapingRequired"), True),
        "updatedAt": _now_utc(),
    }
    if not payload["name"]:
        flash("Name required", "error")
        return _redirect_admin("admin.admin_dashboard")
    db.stores.update_one(
        {"storeId": sid},
        {"$set": payload, "$setOnInsert": {"createdAt": _now_utc()}},
        upsert=True,
    )
    flash("Store saved", "success")
    return _redirect_admin("admin.admin_dashboard")


@admin_bp.route("/brands/save", methods=["POST"])
def admin_save_brand():
    ok, res = _require_admin()
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass
    en, de = _localized_pair(
        request.form.get("name_en") or request.form.get("name"),
        request.form.get("name_de"),
    )
    bid = (request.form.get("brandId") or "").strip() or _id("brand")
    payload = {
        "brandId": bid,
        "name": en,
        "name_en": en,
        "name_de": de,
        "image_url": (request.form.get("image_url") or "").strip(),
        "website": (request.form.get("website") or "").strip(),
        "updatedAt": _now_utc(),
    }
    if not payload["name_en"]:
        flash("Name required", "error")
        return _redirect_admin("admin.admin_brands_page")

    brand = Brand.query.filter_by(brand_id=bid).first()
    if brand is None:
        brand = Brand(
            brand_id=bid,
            name=payload["name"],
            name_en=payload["name_en"],
            name_de=payload["name_de"],
            image_url=payload["image_url"],
            website=payload["website"],
            created_at=_now_utc(),
            updated_at=payload["updatedAt"],
        )
        db.session.add(brand)
    else:
        brand.name = payload["name"]
        brand.name_en = payload["name_en"]
        brand.name_de = payload["name_de"]
        brand.image_url = payload["image_url"]
        brand.website = payload["website"]
        brand.updated_at = payload["updatedAt"]

    db.session.commit()
    flash("Brand saved", "success")
    return _redirect_admin("admin.admin_brands_page", edit=bid)


@admin_bp.route("/categories/save", methods=["POST"])
def admin_save_category():
    ok, res = _require_admin()
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass
    cid = (request.form.get("categoryId") or "").strip() or _id("cat")
    en, de = _localized_pair(request.form.get("name_en"), request.form.get("name_de"))
    parent_id_raw = (request.form.get("parentId") or "").strip()
    parent_id = _parse_int(parent_id_raw, 0) if parent_id_raw else None
    parent = Category.query.get(parent_id) if parent_id else None
    payload = {
        "name_en": en,
        "name_de": de,
        "slug": (request.form.get("slug") or "").strip(),
        "image_url": (request.form.get("image_url") or "").strip(),
        "updatedAt": _now_utc(),
    }
    if not payload["slug"]:
        payload["slug"] = _slugify(en or de) or cid
    if not payload["name_en"]:
        flash("Name required", "error")
        return _redirect_admin("admin.admin_categories_page")

    category = Category.query.get(_parse_int(cid, 0)) if cid.isdigit() else None
    if category is None:
        payload["slug"] = _unique_category_slug(payload["slug"])
        category = Category(
            slug=payload["slug"],
            name_en=payload["name_en"],
            name_de=payload["name_de"],
            image_url=payload["image_url"],
            parent_id=parent.id if parent else None,
            level=(parent.level + 1) if parent and parent.level is not None else (1 if parent else 0),
        )
        db.session.add(category)
        db.session.flush()
    else:
        payload["slug"] = _unique_category_slug(payload["slug"], exclude_category_id=category.id)
        category.slug = payload["slug"]
        category.name_en = payload["name_en"]
        category.name_de = payload["name_de"]
        category.image_url = payload["image_url"]
        category.parent_id = parent.id if parent else None
        category.level = (parent.level + 1) if parent and parent.level is not None else (1 if parent else 0)

    db.session.commit()

    cid = str(category.id)
    path, full = _build_category_path(cid)
    flash("Category saved", "success")
    return _redirect_admin("admin.admin_categories_page", edit=cid)


@admin_bp.route("/products/save-ai", methods=["POST"])
def admin_save_ai_product():
    ok, res = _require_admin()
    if not ok:
        return res
    
    from models.postgres_models import Brand, Category, Offer, Product, Store, db
    
    if db is None:
        flash("Database connection error", "error")
        return redirect(url_for("admin.admin_smart_import_page"))
    
    try:
        # Get form data
        name_en = (request.form.get("name_en") or "").strip()
        name_de = (request.form.get("name_de") or "").strip()
        
        if not name_de:
            flash("German name is required", "error")
            return redirect(url_for("admin.admin_smart_import_page"))
        
        # Get category
        category_id = request.form.get("categoryId")
        category = None
        if category_id:
            category = Category.query.get(_parse_int(category_id, 0))
        
        # Get or create brand
        brand_name = (request.form.get("brandId") or "").strip()
        brand_obj = None
        if brand_name:
            brand_obj = Brand.query.filter_by(name=brand_name).first()
            if not brand_obj:
                brand_obj = Brand(
                    brand_id=f"brand_{uuid.uuid4().hex[:12]}",
                    name=brand_name,
                    name_en=brand_name,
                    name_de=brand_name
                )
                db.session.add(brand_obj)
                db.session.flush()
        
        # Create product
        product = Product(
            product_id=f"prod_{uuid.uuid4().hex[:12]}",
            name_de=name_de,
            name_en=name_en or name_de,
            brand=brand_name,
            category_id=category.id if category else None,
            unit_size=(request.form.get("size") or "").strip() or None,
            image_url=(request.form.get("image_url") or "").strip() or None,
            description_en=(request.form.get("description_en") or "").strip() or None,
            description_de=(request.form.get("description_de") or "").strip() or None,
        )
        db.session.add(product)
        db.session.flush()  # Get the product ID
        
        # Get store and price data
        store_id = (request.form.get("store_id") or "").strip()
        price_str = (request.form.get("price") or "").strip()
        promo_price_str = (request.form.get("promo_price") or "").strip()
        store_url = (request.form.get("store_url") or "").strip()
        offer_details = (request.form.get("offer_details") or "").strip() or None
        unit_price = (request.form.get("unit_price") or "").strip() or None
        
        # Create offer if we have store and price
        if store_id and price_str:
            try:
                base_price = float(price_str)
                promo_price = None
                if promo_price_str:
                    try:
                        promo_price = float(promo_price_str)
                    except:
                        pass
                
                # Verify store exists
                store = Store.query.filter_by(store_id=store_id).first()
                if not store:
                    # Create store if it doesn't exist
                    store = Store(
                        store_id=store_id,
                        name=store_id.capitalize(),
                        active=True
                    )
                    db.session.add(store)
                    db.session.flush()
                
                # Create offer
                min_quantity_str = (request.form.get("min_quantity") or "").strip()
                min_quantity = None
                if min_quantity_str:
                    try:
                        min_quantity = int(min_quantity_str)
                    except:
                        pass
                
                offer = Offer(
                    product_id=product.id,
                    store_id=store_id,
                    base_price=base_price,
                    promo_price=promo_price,
                    unit_price=unit_price,
                    offer_details=offer_details,
                    min_quantity=min_quantity,
                    product_url=store_url or None,
                    is_available=True
                )
                db.session.add(offer)
            except ValueError as e:
                flash(f"Invalid price format: {e}", "error")
                db.session.rollback()
                return redirect(url_for("admin.admin_smart_import_page"))
        
        db.session.commit()
        flash(f"Product '{name_de}' imported successfully!", "success")
        return redirect(url_for("admin.admin_products_page", edit=product.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"Error saving AI product: {e}")
        flash(f"Error saving product: {str(e)}", "error")
        return redirect(url_for("admin.admin_smart_import_page"))


@admin_bp.route("/api/products/search", methods=["GET"])
def admin_api_products_search():
    ok, res = _require_admin()
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass
    if not ok or db is None:
        return jsonify([])
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])
    from sqlalchemy import or_

    from models.postgres_models import Product

    rows = (
        Product.query.filter(
            or_(Product.name_de.ilike(f"%{q}%"), Product.brand.ilike(f"%{q}%"))
        )
        .order_by(Product.name_de.asc())
        .limit(20)
        .all()
    )
    return jsonify([{"id": str(r.id), "text": r.name_de or str(r.id)} for r in rows])


@admin_bp.route("/products/merge", methods=["POST"])
def admin_merge_products():
    ok, res = _require_admin()
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass
    if not ok or db is None:
        return _redirect_admin("admin.admin_dashboard")

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
        {"$set": {"productId": target_id, "updatedAt": _now_utc()}},
    )

    # Update user shopping lists
    db.lists.update_many(
        {"items.productId": source_id},
        {"$set": {"items.$[elem].productId": target_id}},
        array_filters=[{"elem.productId": source_id}],
    )

    # Delete the source product
    db.products.delete_one({"productId": source_id})

    # Recompute state for target
    _recompute_product_state(db, target_id)
    _recompute_lists_for_product(db, target_id)

    flash(
        f"Successfully merged {source_prod.get('name_en')} into {target_prod.get('name_en')}.",
        "success",
    )
    return _redirect_admin("admin.admin_products_page")


@admin_bp.route("/products/save", methods=["POST"])
def admin_save_product():
    ok, res = _require_admin()
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass
    pid = (request.form.get("productId") or "").strip() or _id("prod")
    cid = (request.form.get("categoryId") or "").strip()
    path, _ = _build_category_path(cid)
    roots = {
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
    if (not cid) or (cid in roots):
        mapper = CategoryMapper()
        signal = " ".join(
            [
                request.form.get("name_en") or "",
                request.form.get("name_de") or "",
                request.form.get("categoryId") or "",
            ]
        )
        inf = mapper.map_category_with_path(signal)
        inf_leaf = inf.get("categoryId")
        if inf_leaf:
            cid = inf_leaf
            path, _ = _build_category_path(cid)
    en, de = _localized_pair(request.form.get("name_en"), request.form.get("name_de"))
    den, dde = _localized_optional_pair(
        request.form.get("description_en"), request.form.get("description_de")
    )
    # Fallback to image_url if defaultImageUrl is empty
    img_url = (
        request.form.get("defaultImageUrl") or request.form.get("image_url") or ""
    ).strip()

    # Handle inline store offer addition
    new_store_ids = request.form.getlist("newStoreId[]")
    new_store_urls = request.form.getlist("newStoreUrl[]")
    new_store_prices = request.form.getlist("newStorePrice[]")

    if not img_url and new_store_urls and new_store_urls[0].strip():
        from scripts.ai_product_fetcher import fetch_product_from_url

        auto_dt = fetch_product_from_url(new_store_urls[0].strip())
        if auto_dt and auto_dt.get("success") and auto_dt.get("data"):
            img_url = auto_dt["data"].get("image_url", img_url)

    payload = {
        "productId": pid,
        "name_en": en,
        "name_de": de,
        "name": en,
        "brandId": (request.form.get("brandId") or "").strip() or None,
        "categoryId": cid or None,
        "categoryPath": path,
        "unitSize": (request.form.get("unitSize") or "").strip(),
        "barcode": (request.form.get("barcode") or "").strip(),
        "defaultImageUrl": img_url,
        "labels": [
            i.strip()
            for i in (request.form.get("labels") or "").split(",")
            if i.strip()
        ],
        "description_en": den,
        "description_de": dde,
        "updatedAt": _now_utc(),
    }
    if not payload["name_en"]:
        flash("Name required", "error")
        return _redirect_admin("admin.admin_dashboard")
    db.products.update_one(
        {"productId": pid},
        {"$set": payload, "$setOnInsert": {"createdAt": _now_utc()}},
        upsert=True,
    )

    for i in range(len(new_store_ids)):
        store_id = (new_store_ids[i] or "").strip()
        if not store_id:
            continue

        url = (new_store_urls[i] or "").strip()
        try:
            base_price = float(new_store_prices[i] or 0.0)
        except ValueError:
            base_price = 0.0

        if url and base_price > 0:
            spid = _id("sp")
            store_payload = {
                "storeProductId": spid,
                "productId": pid,
                "storeId": store_id,
                "productPageUrl": url,
                "basePrice": base_price,
                "promoPrice": None,
                "isAvailable": True,
                "lastPriceUpdate": _now_utc(),
                "updatedAt": _now_utc(),
            }
            db.store_products.insert_one(store_payload)
            db.price_history.insert_one(
                {
                    "historyId": _id("hist"),
                    "storeProductId": spid,
                    "oldPrice": None,
                    "newPrice": base_price,
                    "timestamp": _now_utc(),
                }
            )

    _recompute_product_state(db, pid)
    flash("Product saved", "success")
    return _redirect_admin("admin.admin_dashboard")


@admin_bp.route("/store-products/save", methods=["POST"])
def admin_save_store_product():
    ok, res = _require_admin()
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass
    spid = (request.form.get("storeProductId") or "").strip() or _id("sp")
    pid = (request.form.get("productId") or "").strip()

    def _tf(n):
        try:
            return float(request.form.get(n))
        except:
            return None

    payload = {
        "storeProductId": spid,
        "productId": pid,
        "storeId": (request.form.get("storeId") or "").strip(),
        "productPageUrl": (request.form.get("productPageUrl") or "").strip(),
        "basePrice": _tf("basePrice") or 0.0,
        "promoPrice": _tf("promoPrice"),
        "isAvailable": _to_bool(request.form.get("isAvailable"), True),
        "lastPriceUpdate": _now_utc(),
        "updatedAt": _now_utc(),
    }
    if not payload["productId"] or not payload["storeId"]:
        flash("IDs required", "error")
        return _redirect_admin("admin.admin_dashboard")
    exist = db.store_products.find_one({"storeProductId": spid})
    old_p = _effective_price(exist) if exist else None
    db.store_products.update_one(
        {"storeProductId": spid},
        {"$set": payload, "$setOnInsert": {"createdAt": _now_utc()}},
        upsert=True,
    )
    new_p = _effective_price(payload)
    if old_p != new_p:
        db.price_history.insert_one(
            {
                "historyId": _id("hist"),
                "storeProductId": spid,
                "oldPrice": old_p,
                "newPrice": new_p,
                "timestamp": _now_utc(),
            }
        )
    _recompute_product_state(db, pid)
    _recompute_lists_for_product(db, pid)
    flash("Store product saved", "success")
    return _redirect_admin("admin.admin_dashboard")


@admin_bp.route("/products/delete/<pid>", methods=["POST"])
def admin_delete_product(pid):
    ok, res = _require_admin()
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass
    db.products.delete_one({"productId": pid})
    db.store_products.delete_many({"productId": pid})
    db.lists.update_many(
        {"items.productId": pid}, {"$pull": {"items": {"productId": pid}}}
    )
    flash(f"Deleted {pid}", "success")
    return redirect(url_for("admin.admin_products_page"))


@admin_bp.route("/categories/delete/<cid>", methods=["POST"])
def admin_delete_category(cid):
    ok, res = _require_admin()
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass

    category = Category.query.get(_parse_int(cid, 0))
    if not category:
        flash("Category not found", "error")
        return redirect(url_for("admin.admin_categories_page"))

    if Category.query.filter_by(parent_id=category.id).first() or Product.query.filter_by(category_id=category.id).first():
        flash("In use", "error")
        return redirect(url_for("admin.admin_categories_page"))

    db.session.delete(category)
    db.session.commit()
    flash(f"Deleted {cid}", "success")
    return redirect(url_for("admin.admin_categories_page"))


@admin_bp.route("/brands/delete/<bid>", methods=["POST"])
def admin_delete_brand(bid):
    ok, res = _require_admin()
    from sqlalchemy import String, cast

    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass
    brand = Brand.query.filter((Brand.brand_id == bid) | (cast(Brand.id, String) == bid)).first()
    brand_keys = {bid}
    if brand:
        brand_keys.update(filter(None, {brand.brand_id, brand.name, brand.name_en}))

    if Product.query.filter(Product.brand.in_(brand_keys)).first():
        flash("In use", "error")
        return redirect(url_for("admin.admin_brands_page"))

    if brand:
        db.session.delete(brand)
        db.session.commit()
    flash(f"Deleted {bid}", "success")
    return redirect(url_for("admin.admin_brands_page"))


@admin_bp.route("/api/store-products/delete/<spid>", methods=["POST"])
def admin_delete_store_product(spid):
    from flask import jsonify

    ok, res = _require_admin()
    if not ok:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass
    offer = db.store_products.find_one({"storeProductId": spid})
    if not offer:
        return jsonify({"success": False, "error": "Not found"}), 404
    db.store_products.delete_one({"storeProductId": spid})
    db.price_history.delete_many({"storeProductId": spid})
    _recompute_product_state(db, offer["productId"])
    _recompute_lists_for_product(db, offer["productId"])
    return jsonify({"success": True})


@admin_bp.route("/scraper/run")
def run_scraper_manual():
    ok, res = _require_admin()
    import subprocess

    subprocess.Popen(["python3", "scripts/cron_pipeline.py"])
    flash("Price updates started", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/cache/clear")
def clear_cache():
    ok, res = _require_admin()
    flash("Cache cleared", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/products/smart-import", methods=["GET"])
def admin_smart_import_page():
    ok, res = _require_admin()
    if not ok:
        return res
    from models.postgres_models import (
        Brand,
        Category,
        FeaturedDeal,
        ListItem,
        Offer,
        Product,
        ShoppingList,
        Store,
        User,
        db,
    )

    pass

    categories = []
    try:
        from models.postgres_models import Category as CatModel

        rows = CatModel.query.order_by(CatModel.name_en.asc()).all()
        categories = [
            {
                "categoryId": str(r.id),
                "name_en": r.name_en or prettify_slug(r.slug),
                "slug": r.slug,
            }
            for r in rows
        ]
    except Exception as e:
        print("DB error fetching categories:", e)
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
                data["description_en"] = (
                    f"A carefully selected, high-quality {data['name_en']} essential for your pantry. It pairs nicely with fresh meals."
                )

        return jsonify(result)
    except Exception as e:
        return jsonify(
            {"success": False, "error": f"Internal Server Error: {str(e)}"}
        ), 500


@admin_bp.route("/scans", methods=["GET"])
def pending_scans():
    ok, res = _require_admin()
    if not ok:
        return res
    from models.postgres_models import PendingProduct

    try:
        pending = PendingProduct.query.filter_by(status="pending").order_by(PendingProduct.created_at.desc()).all()
        pending_list = [
            {
                "barcode": p.barcode,
                "name": p.name,
                "image": p.image,
                "status": p.status,
                "submitted_by": p.submitted_by,
                "created_at": p.created_at,
            }
            for p in pending
        ]
        return render_template(
            "admin_pending_scans.html", scancount=len(pending_list), pending_scans=pending_list, user_email=res
        )
    except Exception as e:
        print(f"pending_scans error: {e}")
        return render_template(
            "admin_pending_scans.html", scancount=0, pending_scans=[], user_email=res, error=str(e)
        )


@admin_bp.route("/api/scans/<barcode>/approve", methods=["POST"])
def approve_scan(barcode):
    ok, res = _require_admin()
    if not ok:
        return jsonify({"success": False, "error": "Unauthorized"})
    
    from models.postgres_models import PendingProduct, Product, Offer, Category, db
    import uuid

    try:
        data = request.get_json() or {}
        name = data.get("name")
        category = data.get("category")
        price = data.get("price")
        store = data.get("store")

        # Update pending product status
        pending = PendingProduct.query.filter_by(barcode=barcode).first()
        if not pending:
            return jsonify({"success": False, "error": "Pending product not found"})
        
        pending.status = "approved"
        
        # Create product
        name_en = _translate_text(name, "de", "en") or name
        
        # Find category by slug or name
        cat = None
        if category:
            cat = Category.query.filter(
                (Category.slug == category.lower()) | 
                (Category.name_en.ilike(category)) |
                (Category.name_de.ilike(category))
            ).first()
        
        new_product = Product(
            fingerprint=str(uuid.uuid4()),
            name_de=name,
            barcode=barcode,
            category_id=cat.id if cat else None,
            store_id=store.lower() if store else None,
            created_at=_now_utc(),
            updated_at=_now_utc()
        )
        db.session.add(new_product)
        db.session.flush()  # Get the product ID
        
        # Create offer if price and store provided
        if price and store:
            new_offer = Offer(
                product_id=new_product.id,
                store_id=store.lower(),
                price=float(price),
                is_available=True,
                last_seen=_now_utc(),
                created_at=_now_utc(),
                updated_at=_now_utc()
            )
            db.session.add(new_offer)
        
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        print(f"approve_scan error: {e}")
        return jsonify({"success": False, "error": str(e)})


@admin_bp.route("/api/scans/<barcode>/reject", methods=["POST"])
def reject_scan(barcode):
    ok, res = _require_admin()
    if not ok:
        return jsonify({"success": False, "error": "Unauthorized"})
    
    from models.postgres_models import PendingProduct, db

    try:
        pending = PendingProduct.query.filter_by(barcode=barcode).first()
        if not pending:
            return jsonify({"success": False, "error": "Pending product not found"})
        
        pending.status = "rejected"
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        print(f"reject_scan error: {e}")
        return jsonify({"success": False, "error": str(e)})


@admin_bp.route("/api/products/bulk-delete", methods=["POST"])
def bulk_delete_products():
    from bson import ObjectId
    from flask import jsonify, request

    from utils.mongo_mock import MockDb

    try:
        data = request.get_json()
        if not data or "ids" not in data:
            return jsonify({"error": "Missing product IDs"}), 400

        ids = data["ids"]
        if not isinstance(ids, list):
            return jsonify({"error": "IDs must be a list"}), 400

        from models.postgres_models import (
            Brand,
            Category,
            FeaturedDeal,
            ListItem,
            Offer,
            Product,
            ShoppingList,
            Store,
            User,
            db,
        )

        object_ids = []
        for id_str in ids:
            try:
                object_ids.append(ObjectId(id_str))
            except Exception:
                object_ids.append(id_str)

        if not object_ids:
            return jsonify({"error": "No valid IDs provided"}), 400

        query = {
            "$or": [{"_id": {"$in": object_ids}}, {"productId": {"$in": object_ids}}]
        }
        result = db.products.delete_many(query)
        db.store_products.delete_many({"productId": {"$in": object_ids}})

        return jsonify(
            {
                "message": f"Successfully deleted {result.deleted_count} products.",
                "deleted_count": result.deleted_count,
            }
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
