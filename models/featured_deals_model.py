"""Featured deals helpers — uses MongoDB when available, otherwise falls back to in-memory mocks.
"""
from typing import List, Optional
try:
    from utils.db import mongo
    HAS_DB = True
except Exception:
    mongo = None
    HAS_DB = False

from models.models import featured_deals as MOCK_DEALS


def list_featured_deals() -> List[dict]:
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        docs = list(mongo.db.featured_deals.find({}))
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs
    return MOCK_DEALS


def get_deal_by_title(title: str) -> Optional[dict]:
    if not title:
        return None
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        doc = mongo.db.featured_deals.find_one({'title': title})
        if not doc:
            return None
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc
    for d in MOCK_DEALS:
        if d.get('title') == title:
            return d
    return None


def insert_deal(doc: dict):
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        res = mongo.db.featured_deals.insert_one(doc)
        return str(res.inserted_id)
    MOCK_DEALS.append(doc)
    return doc
