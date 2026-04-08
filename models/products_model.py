"""
Schema-aware product model.

This model supports both:
1) Legacy product documents in `products` with embedded stores.
2) Production catalog split across `products`, `store_products`, `stores`, `categories`.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import List, Optional

from bson import ObjectId


class ProductsModel:
    def __init__(self):
        from utils.db import get_db

        self.db = get_db()

    def _refresh_db(self):
        from utils.db import get_db

        self.db = get_db()
        return self.db

    def _is_new_schema_enabled(self) -> bool:
        db = self.db if self.db is not None else self._refresh_db()
        if db is None:
            return False
        try:
            if "store_products" not in db.list_collection_names():
                return False
            return db.products.count_documents({"productId": {"$exists": True}}) > 0
        except Exception:
            return False

    @staticmethod
    def _effective_price(offer: dict):
        if not isinstance(offer, dict):
            return None
        return offer.get("promoPrice") if offer.get("promoPrice") is not None else offer.get("basePrice")

    def _category_name_map(self, category_ids):
        if not category_ids:
            return {}
        rows = self.db.categories.find(
            {"categoryId": {"$in": list(category_ids)}},
            {"_id": 0, "categoryId": 1, "name_en": 1},
        )
        return {row.get("categoryId"): row.get("name_en") for row in rows}

    def _store_name_map(self, store_ids):
        if not store_ids:
            return {}
        rows = self.db.stores.find(
            {"storeId": {"$in": list(store_ids)}},
            {"_id": 0, "storeId": 1, "name": 1, "logoUrl": 1, "image": 1},
        )
        out = {}
        for row in rows:
            out[row.get("storeId")] = {
                "name": row.get("name") or row.get("storeId"),
                "image": row.get("logoUrl") or row.get("image"),
            }
        return out

    def _offers_by_product_id(self, product_ids):
        if not product_ids:
            return {}
        rows = list(
            self.db.store_products.find(
                {"productId": {"$in": list(product_ids)}},
                {
                    "_id": 0,
                    "storeProductId": 1,
                    "productId": 1,
                    "storeId": 1,
                    "productPageUrl": 1,
                    "basePrice": 1,
                    "promoPrice": 1,
                    "isAvailable": 1,
                    "stockStatus": 1,
                    "multiBuy": 1,
                    "extractedImageUrl": 1,
                },
            )
        )
        grouped = defaultdict(list)
        for row in rows:
            grouped[row.get("productId")].append(row)
        return grouped

    def _hydrate_new_product(self, doc: dict, offers=None, store_map=None, category_map=None):
        offers = offers or []
        store_map = store_map or {}
        category_map = category_map or {}

        stores = []
        cheapest = None

        for offer in offers:
            price = self._effective_price(offer)
            store_id = offer.get("storeId")
            sm = store_map.get(store_id, {})
            if price is not None and (cheapest is None or float(price) < float(cheapest)):
                cheapest = float(price)

            stores.append(
                {
                    "store": sm.get("name") or store_id,
                    "store_id": store_id,
                    "store_product_id": offer.get("storeProductId"),
                    "price": price,
                    "base_price": offer.get("basePrice"),
                    "promo_price": offer.get("promoPrice"),
                    "url": offer.get("productPageUrl"),
                    "image": offer.get("extractedImageUrl") or doc.get("defaultImageUrl"),
                    "stock_status": offer.get("stockStatus"),
                    "is_available": offer.get("isAvailable"),
                    "offer": offer.get("multiBuy") or {},
                }
            )

        stores.sort(key=lambda row: (row.get("price") is None, row.get("price") or 0))

        return {
            **doc,
            "id": str(doc.get("_id")) if doc.get("_id") is not None else str(doc.get("productId") or ""),
            "name": doc.get("name_en") or doc.get("name_de") or doc.get("name"),
            "category": category_map.get(doc.get("categoryId")) or doc.get("categoryId") or doc.get("category"),
            "image": doc.get("defaultImageUrl") or doc.get("image"),
            "price": cheapest if cheapest is not None else doc.get("price"),
            "price_val": cheapest if cheapest is not None else doc.get("price_val"),
            "stores": stores if stores else doc.get("stores", []),
        }

    def _translate_legacy_query_for_new(self, query: dict):
        query = query or {}
        out = {}

        if "productId" in query:
            out["productId"] = query.get("productId")
        if "barcode" in query:
            out["barcode"] = query.get("barcode")
        if "categoryId" in query:
            out["categoryId"] = query.get("categoryId")
        if "labels" in query:
            out["labels"] = query.get("labels")

        if query.get("category"):
            cat = query.get("category")
            cat_rows = list(self.db.categories.find({"name_en": {"$regex": re.escape(str(cat)), "$options": "i"}}, {"_id": 0, "categoryId": 1}))
            out["categoryId"] = {"$in": [r.get("categoryId") for r in cat_rows]} if cat_rows else "__none__"

        if query.get("name") and isinstance(query.get("name"), dict) and "$regex" in query.get("name"):
            out["$or"] = [
                {"name_en": {"$regex": query["name"]["$regex"], "$options": query["name"].get("$options", "i")}},
                {"name_de": {"$regex": query["name"]["$regex"], "$options": query["name"].get("$options", "i")}},
            ]
            
        if "$or" in query:
            new_or = out.get("$or", [])
            for cond in query["$or"]:
                if "name" in cond:
                    new_or.append({"name_en": cond["name"]})
                    new_or.append({"name_de": cond["name"]})
                elif "title" in cond:
                    new_or.append({"name_en": cond["title"]})
                    new_or.append({"name_de": cond["title"]})
                elif "barcode" in cond:
                    new_or.append({"barcode": cond["barcode"]})
                elif "gtin" in cond or "ean" in cond or "upc" in cond:
                    new_or.append({"barcode": cond.get("gtin") or cond.get("ean") or cond.get("upc")})
                elif "_id" in cond:
                    new_or.append({"_id": cond["_id"]})
            if new_or:
                out["$or"] = new_or
            else:
                out["_id"] = "__none__"

        return out

    def list_products(self, query: Optional[dict] = None, skip: int = 0, limit: int = 0) -> List[dict]:
        db = self.db if self.db is not None else self._refresh_db()
        if db is None:
            return []

        if self._is_new_schema_enabled():
            new_query = self._translate_legacy_query_for_new(query or {})
            cursor = db.products.find(new_query).sort("updatedAt", -1)
            if skip:
                cursor = cursor.skip(skip)
            if limit:
                cursor = cursor.limit(limit)

            docs = list(cursor)
            product_ids = [row.get("productId") for row in docs if row.get("productId")]
            offers_map = self._offers_by_product_id(product_ids)

            store_ids = set()
            for pid in product_ids:
                for offer in offers_map.get(pid, []):
                    if offer.get("storeId"):
                        store_ids.add(offer.get("storeId"))
            store_map = self._store_name_map(store_ids)

            category_ids = {row.get("categoryId") for row in docs if row.get("categoryId")}
            category_map = self._category_name_map(category_ids)

            return [
                self._hydrate_new_product(row, offers_map.get(row.get("productId"), []), store_map, category_map)
                for row in docs
            ]

        cursor = db.products.find(query or {})
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        docs = list(cursor)
        for d in docs:
            if "_id" in d:
                d["id"] = str(d["_id"])
        return docs

    def get_latest_products(self, limit: int = 10) -> List[dict]:
        if self._is_new_schema_enabled():
            return self.list_products(skip=0, limit=limit)
        try:
            docs = list(self.db.products.find({}).sort("_id", -1).limit(limit))
            for d in docs:
                if "_id" in d:
                    d["id"] = str(d["_id"])
            return docs
        except Exception:
            return []

    def count_products(self, query: Optional[dict] = None) -> int:
        if self._is_new_schema_enabled():
            return self.db.products.count_documents(self._translate_legacy_query_for_new(query or {}))
        return self.db.products.count_documents(query or {})

    def get_popular_products(self, limit: int = 12) -> List[dict]:
        if self._is_new_schema_enabled():
            docs = list(self.db.products.find({}).sort([("updatedAt", -1)]).limit(limit * 2))
            hydrated = self.list_products(query={"productId": {"$in": [d.get("productId") for d in docs if d.get("productId")]}})
            hydrated.sort(key=lambda d: ("popular" not in (d.get("labels") or []), d.get("price") or 0))
            return hydrated[:limit]

        docs = list(self.db.products.find({}).sort([("view_count", -1), ("add_to_list_count", -1)]).limit(limit))
        for d in docs:
            if "_id" in d:
                d["id"] = str(d["_id"])
        return docs

    def get_category_counts(self) -> dict:
        if self._is_new_schema_enabled():
            pipeline = [
                {"$match": {"categoryId": {"$exists": True, "$ne": None}}},
                {"$group": {"_id": "$categoryId", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
            counts = {row["_id"]: row["count"] for row in self.db.products.aggregate(pipeline)}
            cat_map = self._category_name_map(counts.keys())
            return {cat_map.get(k) or k: v for k, v in counts.items()}

        pipeline = [
            {"$match": {"category": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        results = list(self.db.products.aggregate(pipeline))
        return {r["_id"]: r["count"] for r in results}

    def get_category_options(self) -> List[str]:
        if self._is_new_schema_enabled():
            rows = list(self.db.categories.find({}, {"_id": 0, "name_en": 1}))
            return sorted({r.get("name_en") for r in rows if r.get("name_en")})

        all_prods = list(self.db.products.find({}, {"category": 1}))
        cat_counts = Counter(p.get("category") for p in all_prods if p.get("category"))
        return sorted(cat_counts.keys(), key=lambda c: (-cat_counts[c], c.lower()))

    def get_categories(self) -> List[str]:
        if self._is_new_schema_enabled():
            return [row.get("name_en") for row in self.db.categories.find({}, {"_id": 0, "name_en": 1}) if row.get("name_en")]
        return self.db.products.distinct("category")

    def upsert_product(self, key: dict, set_doc: dict) -> dict:
        if self._is_new_schema_enabled():
            mapped = dict(set_doc or {})
            if mapped.get("name") and not mapped.get("name_en"):
                mapped["name_en"] = mapped.get("name")
            if mapped.get("name") and not mapped.get("name_de"):
                mapped["name_de"] = mapped.get("name")
            if mapped.get("category") and not mapped.get("categoryId"):
                cat = self.db.categories.find_one({"name_en": {"$regex": re.escape(str(mapped.get("category"))), "$options": "i"}})
                if cat:
                    mapped["categoryId"] = cat.get("categoryId")
            mapped.setdefault("productId", key.get("productId") or set_doc.get("productId") if set_doc else None)
            if not mapped.get("productId"):
                mapped["productId"] = f"prod_{ObjectId()}"

            mapped["updatedAt"] = mapped.get("updatedAt") or __import__("datetime").datetime.utcnow()
            if "createdAt" not in mapped:
                mapped["createdAt"] = mapped["updatedAt"]

            res = self.db.products.update_one({"productId": mapped["productId"]}, {"$set": mapped}, upsert=True)
            return {
                "upserted_id": res.upserted_id,
                "modified_count": res.modified_count,
                "matched_count": res.matched_count,
            }

        res = self.db.products.update_one(key, {"$set": set_doc}, upsert=True)
        return {
            "upserted_id": res.upserted_id,
            "modified_count": res.modified_count,
            "matched_count": res.matched_count,
        }

    def search_by_name(self, query: str, limit: int = 50) -> List[dict]:
        if self._is_new_schema_enabled():
            rgx = {"$regex": re.escape(query), "$options": "i"}
            docs = list(self.db.products.find({"$or": [{"name_en": rgx}, {"name_de": rgx}]}).limit(limit))
            product_ids = [d.get("productId") for d in docs if d.get("productId")]
            offers_map = self._offers_by_product_id(product_ids)

            store_ids = set()
            for pid in product_ids:
                for offer in offers_map.get(pid, []):
                    if offer.get("storeId"):
                        store_ids.add(offer.get("storeId"))
            store_map = self._store_name_map(store_ids)

            category_map = self._category_name_map({d.get("categoryId") for d in docs if d.get("categoryId")})
            return [self._hydrate_new_product(d, offers_map.get(d.get("productId"), []), store_map, category_map) for d in docs]

        rgx = {"$regex": re.escape(query), "$options": "i"}
        docs = list(self.db.products.find({"name": rgx}).limit(limit))
        for d in docs:
            if "_id" in d:
                d["id"] = str(d["_id"])
        return docs

    def get_product_by_name(self, name: str) -> Optional[dict]:
        if self._is_new_schema_enabled():
            rgx_exact = {"$regex": "^" + re.escape(name) + "$", "$options": "i"}
            doc = self.db.products.find_one({"$or": [{"name_en": rgx_exact}, {"name_de": rgx_exact}]})
            if not doc:
                rgx = {"$regex": re.escape(name), "$options": "i"}
                doc = self.db.products.find_one({"$or": [{"name_en": rgx}, {"name_de": rgx}]})
            if not doc:
                return None
            return self.search_by_name(doc.get("name_en") or doc.get("name_de"), limit=1)[0]

        doc = self.db.products.find_one({"name": {"$regex": "^" + re.escape(name) + "$", "$options": "i"}})
        if not doc:
            doc = self.db.products.find_one({"name": {"$regex": re.escape(name), "$options": "i"}})
        if doc and "_id" in doc:
            doc["id"] = str(doc["_id"])
        return doc

    def get_product_by_id(self, product_id: str) -> Optional[dict]:
        if self._is_new_schema_enabled():
            doc = None
            try:
                doc = self.db.products.find_one({"_id": ObjectId(product_id)})
            except Exception:
                pass
            if not doc:
                doc = self.db.products.find_one({"productId": str(product_id)})
            if not doc:
                doc = self.db.products.find_one({"id": str(product_id)})
            if not doc:
                return None
                
            pid = doc.get("productId")
            if pid:
                hydrated = self.list_products(query={"productId": pid}, limit=1)
                return hydrated[0] if hydrated else None
            else:
                return self._hydrate_new_product(doc)

        try:
            doc = self.db.products.find_one({"_id": ObjectId(product_id)})
            if not doc:
                doc = self.db.products.find_one({"id": product_id})
            if doc and "_id" in doc:
                doc["id"] = str(doc["_id"])
            return doc
        except Exception:
            doc = self.db.products.find_one({"id": product_id})
            if doc and "_id" in doc:
                doc["id"] = str(doc["_id"])
            return doc

    def count_by_store(self, store_name: str) -> int:
        if self._is_new_schema_enabled():
            rgx = {"$regex": re.escape(store_name), "$options": "i"}
            store_ids = [row.get("storeId") for row in self.db.stores.find({"name": rgx}, {"_id": 0, "storeId": 1}) if row.get("storeId")]
            if not store_ids:
                return 0
            return len(self.db.store_products.distinct("productId", {"storeId": {"$in": store_ids}}))

        rgx = {"$regex": re.escape(store_name), "$options": "i"}
        return self.db.products.count_documents(
            {
                "$or": [
                    {"stores": {"$elemMatch": {"$or": [{"store": rgx}, {"name": rgx}]}}},
                    {"store": rgx},
                ]
            }
        )

    def find_by_store(self, store_name: str) -> List[dict]:
        if self._is_new_schema_enabled():
            rgx = {"$regex": re.escape(store_name), "$options": "i"}
            store_ids = [row.get("storeId") for row in self.db.stores.find({"name": rgx}, {"_id": 0, "storeId": 1}) if row.get("storeId")]
            if not store_ids:
                return []
            pids = self.db.store_products.distinct("productId", {"storeId": {"$in": store_ids}})
            docs = list(self.db.products.find({"productId": {"$in": pids}}))

            offers_map = self._offers_by_product_id([d.get("productId") for d in docs if d.get("productId")])
            store_map = self._store_name_map(store_ids)
            category_map = self._category_name_map({d.get("categoryId") for d in docs if d.get("categoryId")})

            out = []
            for doc in docs:
                offers = [o for o in offers_map.get(doc.get("productId"), []) if o.get("storeId") in set(store_ids)]
                out.append(self._hydrate_new_product(doc, offers, store_map, category_map))
            return out

        rgx = {"$regex": re.escape(store_name), "$options": "i"}
        docs = list(
            self.db.products.find(
                {
                    "$or": [
                        {"stores": {"$elemMatch": {"$or": [{"store": rgx}, {"name": rgx}]}}},
                        {"store": rgx},
                    ]
                }
            )
        )
        for d in docs:
            if "_id" in d:
                d["id"] = str(d["_id"])
        return docs

    def get_recommendations(self, shops: List[str], categories: List[str], target_total: int = 12) -> List[dict]:
        if self._is_new_schema_enabled():
            chosen = []
            seen = set()

            for shop in shops or []:
                for row in self.find_by_store(shop)[:4]:
                    pid = row.get("productId") or row.get("id")
                    if pid and pid not in seen:
                        chosen.append(row)
                        seen.add(pid)
                        if len(chosen) >= target_total:
                            return chosen

            if categories:
                cat_ids = [
                    row.get("categoryId")
                    for row in self.db.categories.find(
                        {"name_en": {"$in": categories}},
                        {"_id": 0, "categoryId": 1},
                    )
                    if row.get("categoryId")
                ]
                if cat_ids:
                    rows = self.list_products(query={"categoryId": {"$in": cat_ids}}, limit=target_total * 2)
                    for row in rows:
                        pid = row.get("productId") or row.get("id")
                        if pid and pid not in seen:
                            chosen.append(row)
                            seen.add(pid)
                            if len(chosen) >= target_total:
                                return chosen

            for row in self.get_popular_products(limit=target_total * 2):
                pid = row.get("productId") or row.get("id")
                if pid and pid not in seen:
                    chosen.append(row)
                    seen.add(pid)
                    if len(chosen) >= target_total:
                        break
            return chosen

        recommended_products = []
        seen_ids = set()
        for shop in shops:
            if len(recommended_products) >= target_total:
                break
            try:
                rgx = {"$regex": re.escape(shop), "$options": "i"}
                shop_products = list(
                    self.db.products.find({"$or": [{"store": rgx}, {"stores": {"$elemMatch": {"store": rgx}}}]}).limit(3)
                )
                for p in shop_products:
                    pid = str(p.get("_id"))
                    if pid not in seen_ids:
                        p["id"] = pid
                        recommended_products.append(p)
                        seen_ids.add(pid)
                        if len(recommended_products) >= target_total:
                            break
            except Exception:
                pass

        for cat in categories:
            if len(recommended_products) >= target_total:
                break
            try:
                cat_products = list(self.db.products.find({"category": cat}).limit(3))
                for p in cat_products:
                    pid = str(p.get("_id"))
                    if pid not in seen_ids:
                        p["id"] = pid
                        recommended_products.append(p)
                        seen_ids.add(pid)
                        if len(recommended_products) >= target_total:
                            break
            except Exception:
                pass

        if len(recommended_products) < target_total:
            remaining = target_total - len(recommended_products)
            popular = self.get_popular_products(limit=remaining + 10)
            for p in popular:
                pid = str(p.get("_id"))
                if pid not in seen_ids:
                    p["id"] = pid
                    recommended_products.append(p)
                    seen_ids.add(pid)
                    if len(recommended_products) >= target_total:
                        break

        return recommended_products


products_model = ProductsModel()
