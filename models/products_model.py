"""
PRODUCTS MODEL — PostgreSQL / SQLAlchemy (updated for normalized schema)
"""
from __future__ import annotations
import math
from typing import List, Optional, Dict, Any
from sqlalchemy import or_, func, desc, asc
from models.postgres_models import db, Product, ProductStore, Store, Category, PriceHistory, Promotion, PromotionTarget, Offer


class ProductsModel:

    def get_max_product_price_ceiling(self):
        """Return the rounded-up ceiling for the highest cheapest product price."""
        cheapest_prices = db.session.query(
            ProductStore.product_id.label('product_id'),
            func.min(ProductStore.base_price).label('cheapest_price')
        ).filter(
            ProductStore.is_available == True
        ).group_by(ProductStore.product_id).subquery()

        max_price = db.session.query(func.max(cheapest_prices.c.cheapest_price)).scalar()
        if max_price is None:
            return 0
        return int(math.ceil(float(max_price)))

    def list_products(self, query=None, skip=0, limit=20, sort=None):
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
                                sa_ors.append(Product.name.ilike(pat))
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
                    q = q.order_by(asc(Product.name) if direction == 1 else desc(Product.name))
        else:
            q = q.order_by(desc(Product.updated_at))
        rows = q.offset(skip).limit(limit).all()
        return self._hydrate_products_bulk(rows)

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
                                sa_ors.append(Product.name.ilike(pat))
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
        rows = Product.query.filter(
            or_(Product.name.ilike(pat), Product.name_de.ilike(pat))
        ).order_by(Product.name).limit(limit).all()
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
        row = Product.query.filter(
            or_(
                func.lower(Product.name) == name.lower().strip(),
                func.lower(Product.name_de) == name.lower().strip()
            )
        ).first()
        return self._hydrate_product(row) if row else None

    def get_price_history(self, product_id, limit=8):
        if not product_id:
            return []
        try:
            pid = int(product_id)
        except (ValueError, TypeError):
            return []
        
        # Get price history for this product across all stores
        history = PriceHistory.query.filter(
            PriceHistory.product_id == pid
        ).order_by(desc(PriceHistory.changed_at)).limit(limit).all()
        
        # Get store names
        store_ids = list(set(h.store_id for h in history if h.store_id))
        store_names = {}
        if store_ids:
            stores = Store.query.filter(Store.store_id.in_(store_ids)).all()
            store_names = {s.store_id: s.name for s in stores}
        
        return [
            {
                'store': store_names.get(h.store_id, h.store_id),
                'old_price': float(h.old_price) if h.old_price else None,
                'new_price': float(h.new_price) if h.new_price else None,
                'price': float(h.new_price) if h.new_price else None,
                'timestamp': h.changed_at.isoformat() if h.changed_at else None,
                'date': h.changed_at.strftime('%Y-%m-%d') if h.changed_at else None
            }
            for h in history
        ]

    def _hydrate_products_bulk(self, rows: list) -> list:
        if not rows:
            return []
        
        product_ids = [r.id for r in rows]
        product_map = {r.id: r for r in rows}
        
        # Get product-store pricing data
        product_stores = ProductStore.query.filter(
            ProductStore.product_id.in_(product_ids),
            ProductStore.is_available == True
        ).all()
        
        # Get store names
        store_ids = list(set(ps.store_id for ps in product_stores))
        store_name_map = {}
        if store_ids:
            stores = Store.query.filter(Store.store_id.in_(store_ids)).all()
            store_name_map = {s.store_id: s.name for s in stores}
        
        # Get categories
        cat_ids = list(set(r.category_id for r in rows if r.category_id))
        cat_map = {}
        if cat_ids:
            cats = Category.query.filter(Category.id.in_(cat_ids)).all()
            cat_map = {c.id: c for c in cats}
        
        # Group product_stores by product_id
        product_pricing = {}
        for ps in product_stores:
            product_pricing.setdefault(ps.product_id, []).append(ps)

        # Load active promotions for these products (one query, not per-product)
        from datetime import date as _date
        today = _date.today()
        promo_map: dict = {}  # (product_id, store_id) -> {discount_percent, original_price, promo_text}
        if product_ids:
            pt_rows = db.session.query(
                PromotionTarget.product_id,
                PromotionTarget.store_id,
                Promotion.description,
                Offer.discount_type,
                Offer.discount_value,
            ).join(Promotion, Promotion.id == PromotionTarget.promotion_id
            ).outerjoin(Offer, Offer.id == Promotion.offer_id
            ).filter(
                PromotionTarget.product_id.in_(product_ids),
                Promotion.is_active == True,
                Promotion.start_date <= today,
                db.or_(Promotion.end_date == None, Promotion.end_date >= today),
            ).all()
            for pt in pt_rows:
                promo_map[(pt.product_id, pt.store_id)] = {
                    'discount_type': pt.discount_type,
                    'discount_value': float(pt.discount_value) if pt.discount_value else 0,
                    'promo_text': pt.description,
                }

        results = []
        for row in rows:
            doc = row.to_dict()
            row_pricing = product_pricing.get(row.id, [])

            stores_list = []
            cheapest_price = None
            cheapest_store = None

            for ps in row_pricing:
                price = float(ps.base_price) if ps.base_price else None
                store_name = store_name_map.get(ps.store_id, ps.store_id)
                promo = promo_map.get((ps.product_id, ps.store_id))

                store_entry = {
                    'store': store_name,
                    'name': store_name,
                    'price': price,
                    'url': ps.product_url,
                    'image': row.default_image_url,
                    'storeProductId': f'{ps.product_id}_{ps.store_id}',
                    'has_deal': promo is not None,
                }

                if promo and price:
                    dt = promo['discount_type']
                    dv = promo['discount_value']
                    if dt == 'percentage' and dv > 0:
                        original = price / (1 - dv / 100) if dv < 100 else price
                        store_entry['original_price'] = round(original, 2)
                        store_entry['discount_percent'] = int(dv)
                    elif dt == 'fixed' and dv > 0:
                        store_entry['original_price'] = round(price + dv, 2)
                        store_entry['discount_percent'] = int(dv / (price + dv) * 100) if price + dv else 0
                    elif dt == 'bogo':
                        store_entry['discount_percent'] = int(dv)
                    store_entry['promo_text'] = promo.get('promo_text') or ''

                stores_list.append(store_entry)

                if price is not None and (cheapest_price is None or price < cheapest_price):
                    cheapest_price = price
                    cheapest_store = store_name

            doc['stores'] = stores_list
            doc['price'] = cheapest_price
            doc['store'] = cheapest_store
            doc['has_deal'] = any(s.get('has_deal') for s in stores_list)

            # Bubble up promo info from the cheapest store to the top-level doc
            # so product card templates can show badges without extra lookups
            for s in stores_list:
                if s.get('has_deal') and s.get('store') == cheapest_store:
                    if s.get('discount_percent'):
                        doc['discount_percent'] = s['discount_percent']
                    if s.get('original_price'):
                        doc['original_price'] = s['original_price']
                    if s.get('promo_text'):
                        doc['promo_text'] = s['promo_text']
                    break

            if cheapest_price is not None and cheapest_store:
                doc['cheapest'] = {'price': cheapest_price, 'store': cheapest_store}

            if row.category_id and row.category_id in cat_map:
                cat = cat_map[row.category_id]
                doc['category'] = cat.name_en or cat.name_de

            results.append(doc)
        
        return results

    def _hydrate_product(self, row: Product) -> dict:
        if row is None:
            return {}
        docs = self._hydrate_products_bulk([row])
        return docs[0] if docs else {}


products_model = ProductsModel()
