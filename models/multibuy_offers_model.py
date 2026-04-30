"""
MULTI-BUY OFFERS MODEL - Canonical promotions-backed view.

This model preserves the existing API while reading multi-buy promotions from the
normalized `promotions` collection when available.
"""

from __future__ import annotations

from bson import ObjectId
from datetime import datetime
from typing import List, Optional


class MultibuyOffersModel:
    def __init__(self):
        from utils.db import get_db

        self.db = get_db()
        self._client = None

    def _collection(self):
        if self.db is not None:
            try:
                if 'promotions' in self.db.list_collection_names():
                    return self.db.promotions
            except Exception:
                pass
        return self.db.multibuy_offers

    @staticmethod
    def _normalize_offer(doc: dict) -> dict:
        if not isinstance(doc, dict):
            return doc

        out = dict(doc)
        if '_id' in out:
            out['id'] = str(out['_id'])

        out['promotionType'] = out.get('promotionType') or 'multibuy'
        out['active'] = bool(out.get('active', out.get('status') == 'active'))
        out['title'] = out.get('title') or out.get('product_name') or out.get('productName') or out.get('name')
        out['product_name'] = out.get('product_name') or out['title']
        out['product_id'] = out.get('product_id') or out.get('productId')
        out['store'] = out.get('store') or out.get('storeName')
        out['x'] = out.get('x') or out.get('buy_quantity') or out.get('buyQuantity')
        out['y'] = out.get('y') or out.get('free_quantity') or out.get('freeQuantity')
        out['buy_quantity'] = out.get('buy_quantity') or out['x']
        out['free_quantity'] = out.get('free_quantity') or out['y']
        out['type'] = out.get('type') or out.get('offer_type') or 'buyXgetY'
        out['offer_type'] = out.get('offer_type') or out['type']
        out['original_price'] = out.get('original_price') or out.get('originalPrice') or out.get('price') or out.get('priceText')
        out['valid_until'] = out.get('valid_until') or out.get('validUntil')
        if not out.get('discount_label') and out.get('buy_quantity') and out.get('free_quantity'):
            out['discount_label'] = f"{out.get('buy_quantity')}+{out.get('free_quantity')} FREE"
        return out

    def list_active_offers(self) -> List[dict]:
        now = datetime.utcnow()
        query = {
            '$and': [
                {
                    '$or': [
                        {'promotionType': 'multibuy', 'status': 'active'},
                        {'promotionType': 'multibuy', 'active': True},
                    ]
                },
                {
                    '$or': [
                        {'valid_until': {'$exists': False}},
                        {'valid_until': None},
                        {'valid_until': {'$gte': now}},
                        {'validUntil': {'$gte': now}},
                    ]
                },
            ]
        }
        return [self._normalize_offer(doc) for doc in self._collection().find(query)]

    def get_offers_count(self) -> int:
        collection = self._collection()
        return collection.count_documents({
            '$and': [
                {'$or': [
                    {'promotionType': 'multibuy', 'status': 'active'},
                    {'promotionType': 'multibuy', 'active': True},
                ]},
            ]
        })

    def get_latest_offers(self, limit: int = 5) -> List[dict]:
        collection = self._collection()
        cursor = collection.find({
            '$and': [
                {'$or': [
                    {'promotionType': 'multibuy', 'status': 'active'},
                    {'promotionType': 'multibuy', 'active': True},
                ]},
            ]
        }).sort('_id', -1).limit(limit)
        return [self._normalize_offer(doc) for doc in cursor]

    def get_offer_by_id(self, offer_id: str) -> Optional[dict]:
        try:
            doc = self._collection().find_one({'_id': ObjectId(offer_id)})
            return self._normalize_offer(doc) if doc else None
        except Exception:
            return None

    def get_offers_by_product(self, product_id: str) -> List[dict]:
        now = datetime.utcnow()
        product_filters = [{'productId': str(product_id)}]
        try:
            product_filters.append({'product_id': ObjectId(product_id)})
        except Exception:
            pass

        query = {
            '$and': [
                {'$or': product_filters},
                {'$or': [
                    {'promotionType': 'multibuy', 'status': 'active'},
                    {'promotionType': 'multibuy', 'active': True},
                ]},
                {'$or': [
                    {'valid_until': {'$exists': False}},
                    {'valid_until': None},
                    {'valid_until': {'$gte': now}},
                    {'validUntil': {'$gte': now}},
                ]},
            ]
        }
        return [self._normalize_offer(doc) for doc in self._collection().find(query)]

    def attach_offers_to_products(self, products: List[dict]) -> List[dict]:
        if not products:
            return products

        try:
            mb_offers = self.list_active_offers()
            from models.quantity_discounts_model import quantity_discounts_model

            q_discounts = quantity_discounts_model.list_active_discounts()

            mb_map_id = {}
            mb_map_name = {}
            for offer in mb_offers:
                pid = str(offer.get('product_id') or offer.get('productId') or '')
                if pid:
                    mb_map_id[pid] = offer
                pname = offer.get('product_name') or offer.get('title')
                if pname:
                    mb_map_name[pname.lower().strip()] = offer

            qd_map = {}
            for discount in q_discounts:
                pid = str(discount.get('product_id') or discount.get('productId') or '')
                if pid:
                    qd_map[pid] = discount

            for product in products:
                pid = str(product.get('id') or product.get('_id') or '')
                pname = str(product.get('name') or '').lower().strip()

                offer_x = product.get('buy_quantity') or product.get('multibuy_buy') or ''
                offer_y = product.get('free_quantity') or product.get('multibuy_free') or ''

                if isinstance(product.get('offer'), dict):
                    offer_obj = product.get('offer')
                    product['offer_type'] = offer_obj.get('type') or product.get('offer_type', '')
                    product['offer_x'] = offer_obj.get('x') or offer_x
                    product['offer_y'] = offer_obj.get('y') or offer_y

                if not product.get('offer_x'):
                    product['offer_x'] = offer_x
                if not product.get('offer_y'):
                    product['offer_y'] = offer_y
                if not product.get('offer_type') and product.get('offer_x') and product.get('offer_y'):
                    product['offer_type'] = 'buyXgetY'

                offer = None
                if not product.get('offer_x'):
                    offer = mb_map_id.get(pid) or mb_map_name.get(pname)

                if offer:
                    product['offer'] = offer
                    product['offer_type'] = offer.get('type')
                    ox = offer.get('x') or offer.get('buy_quantity') or 0
                    oy = offer.get('y') or offer.get('free_quantity') or 0
                    product['offer_x'] = ox
                    product['offer_y'] = oy
                    product['buy_quantity'] = ox
                    product['free_quantity'] = oy
                    if offer.get('original_price'):
                        product['original_price'] = offer.get('original_price')
                    elif offer.get('price'):
                        product['original_price'] = offer.get('price')

                if product.get('offer_x') and product.get('offer_y') and not product.get('discount_label'):
                    product['discount_label'] = f"{product['offer_x']}+{product['offer_y']} FREE"

                if not product.get('offer_type') and pid in qd_map:
                    discount = qd_map[pid]
                    product['offer'] = discount
                    product['offer_type'] = 'quantity_discount'
                    if not product.get('discount_label'):
                        product['discount_label'] = 'VOLUME DEAL'
                    if discount.get('original_price'):
                        product['original_price'] = discount.get('original_price')

            return products
        except Exception as exc:
            print(f'Error attaching offers: {exc}')
            return products


multibuy_offers_model = MultibuyOffersModel()
