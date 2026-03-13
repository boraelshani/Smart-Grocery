from flask import jsonify, request

from . import compare_engine_bp
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.products_model import products_model
from models.quantity_discounts_model import quantity_discounts_model
from models.stores_model import stores_model
from utils import helpers
from comparison.comparison_engine import build_best_price_summary, build_compare_product_payload
from comparison.store_matcher import build_store_meta_map


def _fetch_product_or_deal_by_id(product_id):
    if not product_id:
        return None

    doc = products_model.get_product_by_id(str(product_id))
    if not doc:
        doc = featured_deals_model.get_deal_by_id(str(product_id))
    if not doc:
        doc = multibuy_offers_model.get_offer_by_id(str(product_id))
    if not doc:
        try:
            doc = quantity_discounts_model.get_discount_by_id(str(product_id))
        except Exception:
            doc = None
    return doc


@compare_engine_bp.route('/product/<product_id>')
def compare_product(product_id):
    """Normalized compare payload for a single product."""
    try:
        product = _fetch_product_or_deal_by_id(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404

        store_meta = build_store_meta_map(stores_model.list_stores())
        payload = build_compare_product_payload(helpers.sanitize_mongo_doc(product), store_meta_map=store_meta)
        best_price_value, best_price_stores = build_best_price_summary(payload)
        payload['best_price_value'] = best_price_value
        payload['best_price_stores'] = best_price_stores
        return jsonify({'product': payload})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@compare_engine_bp.route('/list')
def compare_list():
    """Comparison list endpoint for compare page and quick compare widgets."""
    try:
        per_page = max(1, min(int(request.args.get('per_page', 30)), 100))
    except Exception:
        per_page = 30
    try:
        page = max(1, int(request.args.get('page', 1)))
    except Exception:
        page = 1

    category_filter = (request.args.get('category') or '').strip()
    search_query = (request.args.get('search') or '').strip()

    query = {}
    if category_filter:
        query['category'] = {'$regex': f"^{category_filter}$", '$options': 'i'}

    product_query = dict(query)
    if search_query:
        search_regex = {'$regex': search_query, '$options': 'i'}
        product_query['$or'] = [
            {'name': search_regex},
            {'title': search_regex},
            {'category': search_regex},
            {'stores.store': search_regex},
            {'stores.name': search_regex},
        ]

    total_products = products_model.count_products(product_query)
    total_pages = (total_products + per_page - 1) // per_page if total_products else 1
    page = min(page, total_pages) if total_products else 1
    skip_amount = (page - 1) * per_page

    raw_products = products_model.list_products(query=product_query, skip=skip_amount, limit=per_page)
    store_meta = build_store_meta_map(stores_model.list_stores())
    products = [
        build_compare_product_payload(helpers.sanitize_mongo_doc(p), store_meta_map=store_meta)
        for p in raw_products
    ]

    return jsonify({
        'products': products,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_products': total_products,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'showing_start': ((page - 1) * per_page) + 1 if total_products else 0,
            'showing_end': min(page * per_page, total_products),
        },
    })


@compare_engine_bp.route('/store-differences')
def compare_store_differences():
    """Aggregate per-store totals over selected products for ranking differences."""
    product_ids = request.args.getlist('product_id')
    if not product_ids:
        return jsonify({'store_totals': [], 'products_count': 0})

    try:
        store_meta = build_store_meta_map(stores_model.list_stores())
        products = []
        for pid in product_ids[:50]:
            doc = _fetch_product_or_deal_by_id(str(pid))
            if not doc:
                continue
            products.append(build_compare_product_payload(helpers.sanitize_mongo_doc(doc), store_meta_map=store_meta))

        totals = {}
        for prod in products:
            for s in (prod.get('stores') or []):
                if s.get('price') is None or not s.get('store'):
                    continue
                name = s.get('store')
                if name not in totals:
                    totals[name] = {'store': name, 'total': 0.0, 'coverage': 0}
                totals[name]['total'] += float(s.get('price'))
                totals[name]['coverage'] += 1

        rows = list(totals.values())
        rows.sort(key=lambda x: (x['coverage'] != len(products), x['total']))

        return jsonify({'store_totals': rows, 'products_count': len(products)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@compare_engine_bp.route('/best-basket', methods=['POST'])
def compare_best_basket():
    """Compute mixed-store optimum and single-store options for selected products."""
    try:
        payload = request.get_json() or {}
        product_ids = payload.get('product_ids') or []
        if not isinstance(product_ids, list) or not product_ids:
            return jsonify({'error': 'product_ids list is required'}), 400

        store_meta = build_store_meta_map(stores_model.list_stores())
        products = []
        for pid in product_ids[:30]:
            doc = _fetch_product_or_deal_by_id(str(pid))
            if not doc:
                continue
            products.append(build_compare_product_payload(helpers.sanitize_mongo_doc(doc), store_meta_map=store_meta))

        mixed_total = 0.0
        mixed_breakdown = []
        single_store_totals = {}

        for prod in products:
            stores = [s for s in (prod.get('stores') or []) if s.get('price') is not None and s.get('store')]
            if not stores:
                continue
            best = min(stores, key=lambda s: s.get('price'))
            mixed_total += float(best.get('price'))
            mixed_breakdown.append({
                'product_id': prod.get('id'),
                'product_name': prod.get('name'),
                'store': best.get('store'),
                'price': best.get('price'),
            })

            for s in stores:
                name = s.get('store')
                if name not in single_store_totals:
                    single_store_totals[name] = {'total': 0.0, 'coverage': 0}
                single_store_totals[name]['total'] += float(s.get('price'))
                single_store_totals[name]['coverage'] += 1

        full_coverage = [
            {'store': name, 'total': val['total']}
            for name, val in single_store_totals.items()
            if val['coverage'] == len(products)
        ]
        full_coverage.sort(key=lambda x: x['total'])

        return jsonify({
            'products_count': len(products),
            'mixed': {
                'total': round(mixed_total, 2),
                'breakdown': mixed_breakdown,
            },
            'single_store_options': full_coverage,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Compatibility aliases used by existing frontend code.
@compare_engine_bp.route('/search')
def compare_search_compat():
    return compare_list()


@compare_engine_bp.route('/basket', methods=['POST'])
def compare_basket_compat():
    return compare_best_basket()
