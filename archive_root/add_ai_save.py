import re

with open('routes/admin/common.py', 'r') as f:
    content = f.read()

injection = """
@admin_bp.route("/products/save-ai", methods=["POST"])
def admin_save_ai_product():
    ok, res = _require_admin(); db = get_db()
    if not ok: return res
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
    
    # Try to map to store
    store_url = request.form.get("store_url") or ""
    price_val = request.form.get("price")
    try:
        price_val = float(price_val)
    except:
        price_val = None
        
    if store_url and price_val is not None:
        # naive store detect
        store_id = None
        if "billa" in store_url.lower(): store_id = "billa"
        elif "spar" in store_url.lower(): store_id = "spar"
        elif "hofer" in store_url.lower(): store_id = "hofer"
        
        if store_id:
            spid = _id("sp")
            sp_payload = {
                "storeProductId": spid,
                "productId": pid,
                "storeId": store_id,
                "productPageUrl": store_url,
                "basePrice": price_val,
                "promoPrice": None,
                "isAvailable": True,
                "lastPriceUpdate": _now_utc(),
                "updatedAt": _now_utc()
            }
            db.store_products.update_one({"storeProductId": spid}, {"$set": sp_payload, "$setOnInsert": {"createdAt": _now_utc()}}, upsert=True)
            db.price_history.insert_one({
                "historyId": _id("hist"), 
                "storeProductId": spid, 
                "oldPrice": None, 
                "newPrice": price_val, 
                "timestamp": _now_utc()
            })

    _recompute_product_state(db, pid)
    flash("AI Product imported successfully!", "success")
    return redirect(url_for("admin.admin_products_page"))
"""

if "/products/save-ai" not in content:
    idx = content.find('def admin_save_product():')
    if idx != -1:
        # find the full decorator above it
        dec_idx = content.rfind('@admin_bp.route', 0, idx)
        content = content[:dec_idx] + injection + "\n" + content[dec_idx:]
        with open('routes/admin/common.py', 'w') as f:
            f.write(content)
        print("Injected AI save route.")
    else:
        print("Could not find admin_save_product")
else:
    print("Already there")
