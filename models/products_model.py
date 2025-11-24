"""Products model helpers — uses MongoDB when available, otherwise falls back to in-memory mocks.
"""
from typing import List, Optional
try:
    from utils.db import mongo
    HAS_DB = True
except Exception:
    mongo = None
    HAS_DB = False

from models.models import products as MOCK_PRODUCTS


def list_products() -> List[dict]:
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        docs = list(mongo.db.products.find({}))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs
    return MOCK_PRODUCTS


def get_product_by_name(name: str) -> Optional[dict]:
    if not name:
        return None
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        doc = mongo.db.products.find_one({'name': name})
        if not doc:
            return None
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc
    for p in MOCK_PRODUCTS:
        if p.get('name') == name:
            return p
    return None


def insert_product(doc: dict):
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        res = mongo.db.products.insert_one(doc)
        return str(res.inserted_id)
    # For mocks, just append
    MOCK_PRODUCTS.append(doc)
    return doc
