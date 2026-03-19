"""Store model with support for both legacy and production schema fields."""

from __future__ import annotations

import re
from typing import List, Optional

from bson import ObjectId


class StoresModel:
    def __init__(self):
        from utils.db import get_db

        self.db = get_db()

    def _refresh_db(self):
        from utils.db import get_db

        self.db = get_db()
        return self.db

    @staticmethod
    def _shape_store(doc: dict):
        if not isinstance(doc, dict):
            return {}
        shaped = dict(doc)
        if "_id" in shaped:
            shaped["id"] = str(shaped["_id"])

        if shaped.get("storeId") and not shaped.get("id"):
            shaped["id"] = shaped.get("storeId")

        if shaped.get("logoUrl") and not shaped.get("image"):
            shaped["image"] = shaped.get("logoUrl")

        if shaped.get("website") and not shaped.get("url"):
            shaped["url"] = shaped.get("website")

        return shaped

    def list_stores(self) -> List[dict]:
        db = self.db if self.db is not None else self._refresh_db()
        if db is None:
            return []
        docs = list(db.stores.find({}))
        return [self._shape_store(d) for d in docs]

    def get_store_count(self) -> int:
        db = self.db if self.db is not None else self._refresh_db()
        if db is None:
            return 0
        return db.stores.count_documents({})

    def get_store_by_name(self, name: str) -> Optional[dict]:
        if not name:
            return None
        db = self.db if self.db is not None else self._refresh_db()
        if db is None:
            return None

        doc = db.stores.find_one({"name": name})
        if not doc:
            doc = db.stores.find_one({"name": {"$regex": "^" + re.escape(name) + "$", "$options": "i"}})

        return self._shape_store(doc) if doc else None

    def get_store_by_id(self, id_str: str) -> Optional[dict]:
        db = self.db if self.db is not None else self._refresh_db()
        if db is None:
            return None

        doc = None
        try:
            doc = db.stores.find_one({"_id": ObjectId(id_str)})
        except Exception:
            doc = None

        if not doc:
            doc = db.stores.find_one({"storeId": id_str})

        return self._shape_store(doc) if doc else None

    def insert_store(self, doc: dict) -> str:
        db = self.db if self.db is not None else self._refresh_db()
        payload = dict(doc or {})

        if payload.get("website") and not payload.get("url"):
            payload["url"] = payload.get("website")
        if payload.get("logoUrl") and not payload.get("image"):
            payload["image"] = payload.get("logoUrl")

        res = db.stores.insert_one(payload)
        return str(res.inserted_id)

    def update_store(self, id_str: str, update_doc: dict) -> bool:
        db = self.db if self.db is not None else self._refresh_db()
        payload = dict(update_doc or {})
        payload.pop("_id", None)

        if payload.get("website") and not payload.get("url"):
            payload["url"] = payload.get("website")
        if payload.get("logoUrl") and not payload.get("image"):
            payload["image"] = payload.get("logoUrl")

        try:
            res = db.stores.update_one({"_id": ObjectId(id_str)}, {"$set": payload})
            if getattr(res, "modified_count", 0) > 0:
                return True
        except Exception:
            pass

        res = db.stores.update_one({"storeId": id_str}, {"$set": payload})
        return getattr(res, "modified_count", 0) > 0

    def delete_store(self, id_str: str) -> bool:
        db = self.db if self.db is not None else self._refresh_db()
        try:
            res = db.stores.delete_one({"_id": ObjectId(id_str)})
            if getattr(res, "deleted_count", 0) > 0:
                return True
        except Exception:
            pass

        res = db.stores.delete_one({"storeId": id_str})
        return getattr(res, "deleted_count", 0) > 0


stores_model = StoresModel()


def list_stores() -> List[dict]:
    return stores_model.list_stores()


def get_store_by_name(name: str) -> Optional[dict]:
    return stores_model.get_store_by_name(name)


def get_store_count() -> int:
    return stores_model.get_store_count()


def insert_store(doc: dict):
    return stores_model.insert_store(doc)
