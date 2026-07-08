"""
PRODUCTS MODEL — PostgreSQL / SQLAlchemy (updated for normalized schema)
"""
from __future__ import annotations
import math
from datetime import date as _date, datetime as _datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import or_, func, desc, asc
from models.postgres_models import db, Product, ProductStore, Store, Category, PriceHistory, Promotion, PromotionTarget, Offer


def _format_last_seen(dt) -> str:
    if not dt:
        return '—'
    if isinstance(dt, str):
        try:
            dt = _datetime.fromisoformat(dt)
        except ValueError:
            return dt[:10]
    if hasattr(dt, 'date'):
        if dt.date() == _date.today():
            return 'Today'
        return f"{dt.day} {dt.strftime('%b')}"
    return '—'


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

    @staticmethod
    def _category_ids_for_filter(value: str) -> list:
        """Return category id + all descendant ids matching slug or name."""
        # Strip regex anchors if passed from the route
        clean = value.strip().lstrip('^').rstrip('$')
        root = Category.query.filter(
            or_(Category.slug == clean,
                Category.name_en.ilike(clean),
                Category.name_de.ilike(clean))
        ).first()
        if not root:
            return []
        # Collect all descendants via BFS
        ids = [root.id]
        queue = [root.id]
        while queue:
            children = Category.query.filter(Category.parent_id.in_(queue)).all()
            child_ids = [c.id for c in children]
            ids.extend(child_ids)
            queue = child_ids
        return ids

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
                                cat_ids = self._category_ids_for_filter(cond['$regex'])
                                if cat_ids:
                                    sa_ors.append(Product.category_id.in_(cat_ids))
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
                                cat_ids = self._category_ids_for_filter(cond['$regex'])
                                if cat_ids:
                                    sa_ors.append(Product.category_id.in_(cat_ids))
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

    def get_price_history(self, product_id, limit=60):
        if not product_id:
            return []
        try:
            pid = int(product_id)
        except (ValueError, TypeError):
            return []

        # Get all distinct store_ids for this product
        store_ids_q = db.session.query(PriceHistory.store_id).filter(
            PriceHistory.product_id == pid
        ).distinct().all()
        all_store_ids = [r[0] for r in store_ids_q if r[0]]

        store_names = {}
        if all_store_ids:
            stores = Store.query.filter(Store.store_id.in_(all_store_ids)).all()
            store_names = {s.store_id: s.name for s in stores}

        # Fetch recent history per store so all stores are represented
        per_store = max(6, limit // max(len(all_store_ids), 1))
        all_history = []
        for sid in all_store_ids:
            rows = PriceHistory.query.filter(
                PriceHistory.product_id == pid,
                PriceHistory.store_id == sid,
            ).order_by(desc(PriceHistory.recorded_at)).limit(per_store).all()
            all_history.extend(rows)

        from datetime import datetime as _dt
        def _row_date(h):
            return h.recorded_at or h.changed_at or _dt.min

        all_history.sort(key=_row_date)

        return [
            {
                'store': store_names.get(h.store_id, h.store_id),
                'old_price': float(h.old_price) if h.old_price else None,
                'new_price': float(h.new_price) if h.new_price else None,
                'price': float(h.price) if h.price else (float(h.new_price) if h.new_price else None),
                'timestamp': _row_date(h).isoformat(),
                'date': _row_date(h).strftime('%b %-d'),
            }
            for h in all_history
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
                    'unit_price': float(ps.unit_price) if ps.unit_price else None,
                    'unit_price_unit': ps.unit_price_unit or None,
                    'url': ps.product_url,
                    'image': row.default_image_url,
                    'storeProductId': f'{ps.product_id}_{ps.store_id}',
                    'has_deal': promo is not None,
                    'store_product_name': ps.store_product_name or None,
                    'store_size': f"{ps.store_size_normalized.normalize():f}".rstrip('0').rstrip('.') + (f" {ps.store_unit_normalized}" if ps.store_unit_normalized else '') if ps.store_size_normalized else None,
                    'last_seen': ps.last_seen,
                    'last_seen_label': _format_last_seen(ps.last_seen),
                }

                # If the scraper stored the original (pre-sale) price explicitly, use it directly
                if ps.was_price and price:
                    store_entry['original_price'] = float(ps.was_price)
                    store_entry['has_deal'] = True
                    # compute approximate discount percent from the two prices
                    was = float(ps.was_price)
                    if was > price:
                        store_entry['discount_percent'] = int(round((was - price) / was * 100))

                if promo and price:
                    dt = promo['discount_type']
                    dv = promo['discount_value']
                    if dt == 'percentage' and dv > 0:
                        if not ps.was_price:
                            # No explicit was_price — compute from the percentage
                            # base_price is the regular (pre-discount) price; compute actual sale price
                            sale_price = round(price * (1 - dv / 100), 2)
                            store_entry['original_price'] = price
                            store_entry['price'] = sale_price
                            price = sale_price
                        store_entry['discount_percent'] = int(dv)
                    elif dt == 'fixed' and dv > 0:
                        if not ps.was_price:
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
