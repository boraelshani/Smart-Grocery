#!/usr/bin/env python3
import os
import sys
import uuid

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app
from utils.db import get_db


def main():
    db = get_db()
    email = (db.users.find_one({}, {"_id": 0, "email": 1}) or {}).get("email")
    print("test_email", email)

    suffix = uuid.uuid4().hex[:8]
    cat_id = f"cat_test_{suffix}"
    prod_id = f"prod_test_{suffix}"
    sp_id = f"sp_test_{suffix}"

    with app.test_client() as c:
        app.config["ADMIN_EMAILS"] = email or ""
        with c.session_transaction() as sess:
            sess["user"] = email

        r_dash = c.get("/admin")
        print("admin_dashboard_status", r_dash.status_code)

        r_cat = c.post(
            "/admin/categories/save",
            data={
                "categoryId": cat_id,
                "name_en": "Test Category",
                "name_de": "Test Kategorie",
                "slug": f"test-category-{suffix}",
            },
            follow_redirects=False,
        )
        print("admin_save_category_status", r_cat.status_code)

        r_prod = c.post(
            "/admin/products/save",
            data={
                "productId": prod_id,
                "name_en": "Test Product",
                "name_de": "Test Produkt",
                "categoryId": cat_id,
                "brandId": "brand_generic",
                "legalImageStatus": "placeholder",
            },
            follow_redirects=False,
        )
        print("admin_save_product_status", r_prod.status_code)

        r_sp = c.post(
            "/admin/store-products/save",
            data={
                "storeProductId": sp_id,
                "productId": prod_id,
                "storeId": "store_billa",
                "basePrice": "1.99",
                "promoPrice": "1.49",
                "isAvailable": "on",
                "lastScrapeStatus": "ok",
                "stockStatus": "in_stock",
            },
            follow_redirects=False,
        )
        print("admin_save_store_product_status", r_sp.status_code)

    print("created_category", bool(db.categories.find_one({"categoryId": cat_id})))
    print("created_product", bool(db.products.find_one({"productId": prod_id})))
    print("created_store_product", bool(db.store_products.find_one({"storeProductId": sp_id})))

    # cleanup test docs
    db.store_products.delete_many({"storeProductId": sp_id})
    db.products.delete_many({"productId": prod_id})
    db.categories.delete_many({"categoryId": cat_id})
    print("cleanup_done", True)


if __name__ == "__main__":
    main()
