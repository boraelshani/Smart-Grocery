from flask import jsonify, request
from . import compare_bp
from models.deals_compat import list_active_promotions, get_promotion_by_id
from models.multibuy_offers_model import multibuy_offers_model
from models.products_model import products_model
from models.quantity_discounts_model import quantity_discounts_model
from models.stores_model import stores_model
from utils import helpers
from comparison.comparison_engine import build_best_price_summary, build_compare_product_payload
from comparison.store_matcher import build_store_meta_map

def _fetch_product_or_deal_by_id(product_id):
    if not product_id: return None
    doc = products_model.get_product_by_id(str(product_id))
    if not doc: doc = get_promotion_by_id(str(product_id))
    if not doc: doc = multibuy_offers_model.get_offer_by_id(str(product_id))
    if not doc:
        try: doc = quantity_discounts_model.get_discount_by_id(str(product_id))
        except: doc = None
    return doc

@compare_bp.route('/product/<product_id>')
def compare_product(product_id):
    try:
        product = _fetch_product_or_deal_by_id(product_id)
        if not product: return jsonify({'error': 'Product not found'}), 404
        store_meta = build_store_meta_map(stores_model.list_stores())
        payload = build_compare_product_payload(helpers.sanitize_mongo_doc(product), store_meta_map=store_meta)
        best_price_value, best_price_stores = build_best_price_summary(payload)
        payload['best_price_value'] = best_price_value
        payload['best_price_stores'] = best_price_stores
        return jsonify({'product': payload})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@compare_bp.route('/list')
def compare_list():
    try: per_page = max(1, min(int(request.args.get('per_page', 30)), 100))
    except: per_page = 30
    try: page = max(1, int(request.args.get('page', 1)))
    except: page = 1
    category_filter = (request.args.get('category') or '').strip()
    search_query = (request.args.get('search') or '').strip()
    query = {}
    if category_filter:
        import re
        query['$or'] = [
            {'category': {'$regex': f"^{re.escape(category_filter)}$", '$options': 'i'}},
            {'category_path': {'$regex': f"^{re.escape(category_filter)}$", '$options': 'i'}}
        ]
    product_query = dict(query)
    if search_query:
        import requests
        search_regex = {'': search_query, '': 'i'}
        or_list = [
            {'name': search_regex}, {'title': search_regex}, {'category': search_regex},
            {'stores.store': search_regex}, {'stores.name': search_regex}, {'barcode': search_query},
            {'gtin': search_query}, {'ean': search_query}, {'upc': search_query}
        ]
        import bson
        try:
            if bson.ObjectId.is_valid(search_query):
                or_list.append({'_id': bson.ObjectId(search_query)})
        except: pass
        product_query[''] = or_list

        from utils.db import mongo
        try:
            # Atlas search not available with PostgreSQL - fallback to regex search
            raise Exception('Fallback to regex')
        except Exception:
            total_products = products_model.count_products(product_query)
            total_pages = (total_products + per_page - 1) // per_page if total_products else 1
            page = min(page, total_pages) if total_products else 1
            skip_amount = (page - 1) * per_page
            raw_products = products_model.list_products(query=product_query, skip=skip_amount, limit=per_page)
    else:
        total_products = products_model.count_products(product_query)
        total_pages = (total_products + per_page - 1) // per_page if total_products else 1
        page = min(page, total_pages) if total_products else 1
        skip_amount = (page - 1) * per_page
        raw_products = products_model.list_products(query=product_query, skip=skip_amount, limit=per_page)
    store_meta = build_store_meta_map(stores_model.list_stores())
    products = [build_compare_product_payload(helpers.sanitize_mongo_doc(p), store_meta_map=store_meta) for p in raw_products]
    
    sort_param = request.args.get('sort')
    if sort_param == 'unit_price':
        # Strict Unit-Price Normalization Post-Filter sorting
        for p in products:
            p['normalized_unit_price'] = p.get('normalized_unit_price') or float('inf')
        products.sort(key=lambda x: x['normalized_unit_price'])

    return jsonify({
        'products': products,
        'pagination': {'page': page, 'per_page': per_page, 'total_products': total_products, 'total_pages': total_pages, 'has_prev': page > 1, 'has_next': page < total_pages, 'showing_start': ((page-1)*per_page)+1 if total_products else 0, 'showing_end': min(page*per_page, total_products)}
    })

@compare_bp.route('/store-differences')
def compare_store_differences():
    product_ids = request.args.getlist('product_id')
    if not product_ids: return jsonify({'store_totals': [], 'products_count': 0})
    try:
        store_meta = build_store_meta_map(stores_model.list_stores())
        products = []
        for pid in product_ids[:50]:
            doc = _fetch_product_or_deal_by_id(str(pid))
            if doc: products.append(build_compare_product_payload(helpers.sanitize_mongo_doc(doc), store_meta_map=store_meta))
        totals = {}
        for prod in products:
            for s in (prod.get('stores') or []):
                if s.get('price') is None or not s.get('store'): continue
                name = s.get('store')
                if name not in totals: totals[name] = {'store': name, 'total': 0.0, 'coverage': 0}
                totals[name]['total'] += float(s.get('price'))
                totals[name]['coverage'] += 1
        rows = list(totals.values())
        rows.sort(key=lambda x: (x['coverage'] != len(products), x['total']))
        return jsonify({'store_totals': rows, 'products_count': len(products)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@compare_bp.route('/best-basket', methods=['POST'])
def compare_best_basket():
    try:
        payload = request.get_json() or {}
        product_ids = payload.get('product_ids') or []
        items_req = payload.get('items') or []
        
        # Build parsed request dictionary of product_id -> qty
        req_qtys = {}
        for pid in product_ids:
            req_qtys[str(pid)] = 1
        for it in items_req:
            req_qtys[str(it.get('id') or it.get('productId') or it.get('product_id'))] = float(it.get('qty') or it.get('quantity') or 1)
            
        if not req_qtys: return jsonify({'error': 'products required'}), 400
        
        store_meta = build_store_meta_map(stores_model.list_stores())
        products = []
        for pid, qty in list(req_qtys.items())[:50]:
            doc = _fetch_product_or_deal_by_id(str(pid))
            if doc: 
                doc = helpers.sanitize_mongo_doc(doc)
                # Enrich with multibuy logic if any
                enriched = multibuy_offers_model.attach_offers_to_products([doc])
                if enriched:
                    doc = enriched[0]
                
                # Estimate missing prices to cover the basket
                doc = PricePredictorModel.estimate_missing_prices(doc)
                
                doc['requested_qty'] = float(qty)
                payload = build_compare_product_payload(doc, store_meta_map=store_meta)
                # Override payload to store raw doc elements for calculations
                payload['raw_offer_type'] = doc.get('offer_type')
                payload['raw_offer_x'] = float(doc.get('offer_x') or 0)
                payload['raw_offer_y'] = float(doc.get('offer_y') or 0)
                payload['requested_qty'] = float(qty)
                products.append(payload)
                
        def calculate_effective_price(p, store_price):
            qty = p.get('requested_qty', 1)
            raw_cost = float(store_price) * qty
            
            # Multibuy: Buy X get Y Free
            if p.get('raw_offer_type') in ['buyXgetY', 'multibuy'] and p.get('raw_offer_x') and p.get('raw_offer_y'):
                bx = p['raw_offer_x']
                fy = p['raw_offer_y']
                group_size = bx + fy
                groups = int(qty // group_size)
                remainder = qty % group_size
                paid_items = (groups * bx) + min(remainder, bx)
                return float(store_price) * paid_items
                
            return raw_cost
        import itertools
        
        all_stores = set()
        for prod in products:
            for s in prod.get('stores', []):
                if s.get('price') is not None and s.get('store'):
                    all_stores.add(s.get('store'))
                    s['effective_cost'] = calculate_effective_price(prod, float(s.get('price')))

        # Single store calculation
        single_stores = []
        for name in all_stores:
            total = 0.0
            coverage = 0
            for prod in products:
                match = next((s for s in (prod.get('stores') or []) if s.get('store') == name), None)
                if match:
                    total += match['effective_cost']
                    coverage += 1
            if coverage == len(products):
                single_stores.append({'store': name, 'total': round(total, 2)})
        
        single_stores.sort(key=lambda x: x['total'])

        # Two-Stop Shop calculation
        two_stop_options = []
        for s1, s2 in itertools.combinations(all_stores, 2):
            total = 0.0
            coverage = 0
            breakdown = []
            for prod in products:
                matches = [s for s in (prod.get('stores') or []) if s.get('store') in (s1, s2)]
                if not matches:
                    break
                best = min(matches, key=lambda s: s['effective_cost'])
                total += best['effective_cost']
                coverage += 1
                breakdown.append({
                    'product_id': prod.get('id'),
                    'product_name': prod.get('name'),
                    'store': best.get('store'),
                    'price': best.get('price'),
                    'effective_cost': best.get('effective_cost'),
                    'qty': prod.get('requested_qty')
                })
            
            if coverage == len(products):
                two_stop_options.append({
                    'store': f"{s1} + {s2}",
                    'total': round(total, 2),
                    'breakdown': breakdown
                })
        
        two_stop_options.sort(key=lambda x: x['total'])

        # Multi-store (Absolute lowest possible picking from any store)
        mixed_total = 0.0
        mixed_breakdown = []
        for prod in products:
            stores = [s for s in (prod.get('stores') or []) if s.get('price') is not None and s.get('store')]
            if not stores: continue
            best = min(stores, key=lambda s: s.get('effective_cost', float('inf')))
            mixed_total += best.get('effective_cost')
            mixed_breakdown.append({
                'product_id': prod.get('id'),
                'product_name': prod.get('name'),
                'store': best.get('store'),
                'price': best.get('price'),
                'effective_cost': best.get('effective_cost'),
                'qty': prod.get('requested_qty')
            })

        return jsonify({
            'products_count': len(products),
            'mixed': {'total': round(mixed_total, 2), 'breakdown': mixed_breakdown},
            'two_stop_options': two_stop_options[:3],
            'single_store_options': single_stores
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@compare_bp.route('/search')
def compare_search_compat(): return compare_list()

@compare_bp.route('/basket', methods=['POST'])
def compare_basket_compat(): return compare_best_basket()
