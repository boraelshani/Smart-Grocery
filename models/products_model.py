"""
PRODUCTS MODEL — PostgreSQL / SQLAlchemy (matches Neon schema)
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from sqlalchemy import or_, func, desc, asc
from models.postgres_models import db, Product, Offer, Store, Category, PriceHistory


class ProductsModel:

    def list_products(self, query=None, skip=0, limit=80, sort=None):
        q = Product.query
        if isinstance(query, dict):
            and_clauses = query.get('$and', [])
            for clause in and_clauses:
                or_clauses = clause.get('$or', [])
                sa_ors = []
                for oc in or_clauses:
                    for field, cond in oc.items():
                        if isinstance(cond, dict) and '$regex' in cond:
                            pat = f"%{cond['$regex']}%"
                            if field in ('name', 'title'):
                                sa_ors.append(Product.name_de.ilike(pat))
                            elif field == 'brand':
                                sa_ors.append(Product.brand.ilike(pat))
                            elif field == 'category':
                                cat = Category.query.filter(Category.name_en.ilike(pat)).first()
                                if cat:
                                    sa_ors.append(Product.category_id == cat.id)
                        elif field == 'category_path':
                            pass
                if sa_ors:
                    q = q.filter(or_(*sa_ors))
        if sort and isinstance(sort, list):
            for col, direction in sort:
                if col == 'price':
                    q = q.order_by(asc(Product.id) if direction == 1 else desc(Product.id))
                elif col == 'name':
                    q = q.order_by(asc(Product.name_de) if direction == 1 else desc(Product.name_de))
        else:
            q = q.order_by(desc(Product.updated_at))
        rows = q.offset(skip).limit(limit).all()
        return [self._hydrate_product(p) for p in rows]

    def count_products(self, query=None):
        q = Product.query
        if isinstance(query, dict):
            and_clauses = query.get('$and', [])
            for clause in and_clauses:
                or_clauses = clause.get('$or', [])
                sa_ors = []
                for oc in or_clauses:
                    for field, cond in oc.items():
                        if isinstance(cond, dict) and '$regex' in cond:
                            pat = f"%{cond['$regex']}%"
                            if field in ('name', 'title'):
                                sa_ors.append(Product.name_de.ilike(pat))
                            elif field == 'brand':
                                sa_ors.append(Product.brand.ilike(pat))
                            elif field == 'category':
                                cat = Category.query.filter(Category.name_en.ilike(pat)).first()
                                if cat:
                                    sa_ors.append(Product.category_id == cat.id)
                if sa_ors:
                    q = q.filter(or_(*sa_ors))
        return q.count()

    def search_by_name(self, name, limit=50):
        if not name:
            return []
        pat = f"%{name.strip()}%"
        rows = Product.query.filter(Product.name_de.ilike(pat)).order_by(Product.name_de).limit(limit).all()
        return [self._hydrate_product(p) for p in rows]

    def get_product_by_id(self, product_id):
        if not product_id:
            return None
        try:
            row = db.session.get(Product, int(product_id))
        except (ValueError, TypeError):
            row = Product.query.filter_by(fingerprint=str(product_id)).first()
        return self._hydrate_product(row) if row else None

    def get_product_by_name(self, name):
        if not name:
            return None
        row = Product.query.filter(func.lower(Product.name_de) == name.lower().strip()).first()
        return self._hydrate_product(row) if row else None

    def get_price_history(self, product_id, limit=8):
        if not product_id:
            return []
        try:
            pid = int(product_id)
        except (ValueError, TypeError):
            return []
        offers = Offer.query.filter_by(product_id=pid).all()
        if not offers:
            return []
        offer_ids = [o.id for o in offers]
        history = PriceHistory.query.filter(
            PriceHistory.offer_id.in_(offer_ids)
        ).order_by(desc(PriceHistory.changed_at)).limit(limit).all()
        store_map = {o.id: o.store_id for o in offers}
        store_names = {}
        store_ids = list(set(store_map.values()))
        if store_ids:
            stores = Store.query.filter(Store.store_id.in_(store_ids)).all()
            store_names = {s.store_id: s.name for s in stores}
        return [
            {'store': store_names.get(store_map.get(h.offer_id, ''), ''),
             'old_price': float(h.old_price) if h.old_price else None,
             'new_price': float(h.new_price) if h.new_price else None,
             'price': float(h.new_price) if h.new_price else None,
             'timestamp': h.changed_at.isoformat() if h.changed_at else None,
             'date': h.changed_at.strftime('%Y-%m-%d') if h.changed_at else None}
            for h in history
        ]

    def _hydrate_product(self, row: Product) -> dict:
        if row is None:
            return {}
        doc = row.to_dict()
        offers = Offer.query.filter_by(product_id=row.id, is_available=True).all()
        store_ids = list(set(o.store_id for o in offers))
        store_name_map = {}
        if store_ids:
            stores = Store.query.filter(Store.store_id.in_(store_ids)).all()
            store_name_map = {s.store_id: s.name for s in stores}
        stores_list = []
        cheapest_price = None
        cheapest_store = None
        for o in offers:
            price = o.effective_price()
            store_name = store_name_map.get(o.store_id, o.store_id)
            entry = {'store': store_name, 'name': store_name, 'price': price,
                     'url': o.product_url, 'image': row.default_image_url,
                     'storeProductId': str(o.id)}
            stores_list.append(entry)
            if price is not None and (cheapest_price is None or price < cheapest_price):
                cheapest_price = price
                cheapest_store = store_name
        doc['stores'] = stores_list
        doc['price'] = cheapest_price
        doc['store'] = cheapest_store
        if cheapest_price is not None and cheapest_store:
            doc['cheapest'] = {'price': cheapest_price, 'store': cheapest_store}
        if row.category_id:
            cat = db.session.get(Category, row.category_id)
            if cat:
                doc['category'] = cat.name_en or cat.name_de
        return doc


products_model = ProductsModel()
