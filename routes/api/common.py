from flask import jsonify, session, request, current_app, url_for, redirect
from . import api_bp
from models import models as m
from models.products_model import products_model
from models.stores_model import stores_model
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.favorites_model import favorites_model
from models.quantity_discounts_model import quantity_discounts_model
from utils import helpers
import json
import os
import random
import re
import uuid
from datetime import datetime, timezone, timedelta
from utils.db import get_db
from comparison.cheapest_finder import get_cheapest_from_product

STANDARD_CATEGORIES = ["Produce", "Pantry", "Dairy", "Meat", "Frozen", "Bakery", "Baby food", "Snacks", "Fast Food & To Go", "Household", "Beverages"]

def load_featured_deals_fallback():
    try:
        path = os.path.join(current_app.root_path, 'data', 'featured_deals.json')
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

@api_bp.route('/search-products')
def api_search_products():
    q = request.args.get('q', '').strip()
    if not q: return jsonify({'items': []})
    results = []
    try:
        if m.HAS_DB:
            prods = products_model.search_by_name(q, limit=50)
            try:
                qd = quantity_discounts_model.list_active_discounts()
                for d in qd:
                    if q.lower() in (d.get('name') or d.get('product_name') or '').lower(): prods.append(d)
            except: pass
            for d in prods:
                c = get_cheapest_from_product(d)
                if d.get('price') or (isinstance(c, dict) and c.get('price')) or (d.get('stores') and d['stores'][0].get('price')):
                    p_doc = dict(d); p_doc['url'] = f"/product/{p_doc.get('_id') or p_doc.get('id')}"
                    results.append(helpers.sanitize_mongo_doc(p_doc))
    except: pass
    return jsonify({'items': results})

@api_bp.route('/product')
def api_get_product():
    pid = request.args.get('id') or request.args.get('product_id')
    name = request.args.get('name') or request.args.get('title') or request.args.get('q')
    if not pid and not name: return jsonify({'item': None}), 400
    doc = products_model.get_product_by_id(str(pid)) if pid else products_model.get_product_by_name(str(name))
    return jsonify({'item': helpers.sanitize_mongo_doc(doc)}) if doc else (jsonify({'item': None}), 404)

@api_bp.route('/categories')
def api_get_categories():
    return jsonify({'categories': STANDARD_CATEGORIES})

@api_bp.route('/stores')
def api_get_stores():
    try:
        stores = stores_model.list_stores()[:500]
        out = []
        for s in stores:
            img = s.get('image') or (s.get('images')[0] if s.get('images') else None)
            loc = s.get('location') or ', '.join(filter(None, [s.get('address'), s.get('city')]))
            out.append({'id': str(s.get('_id') or s.get('id')), 'name': s.get('name'), 'location': loc, 'image': img, 'url': s.get('url') or s.get('website'), 'hours': s.get('hours') or s.get('opening_hours'), 'deals': len(s.get('active_deals', [])) if isinstance(s.get('active_deals'), list) else 0})
        return jsonify({'stores': out})
    except Exception as e: return jsonify({'error': str(e)}), 500

@api_bp.route('/claim-deal', methods=['POST'])
def api_claim_deal():
    data = request.get_json() or {}
    deal_id = data.get('deal_id') or data.get('id') or data.get('title')
    if not deal_id: return jsonify({'error': 'no_id'}), 400
    email = helpers.get_user_email()
    deal_doc = featured_deals_model.get_deal_by_id(str(deal_id)) or multibuy_offers_model.get_offer_by_id(str(deal_id))
    claimed = m.claim_featured_deal_by_id(deal_id, email=email) if deal_doc else False
    added = False
    if email:
        from models.users_model import get_user_lists, add_item_to_list, create_shopping_list, set_active_list
        try:
            raw_p = data.get('price') or (deal_doc or {}).get('price')
            payload = {'name': (deal_doc or {}).get('title') or str(deal_id), 'price': raw_p, 'qty': 1}
            l_data = get_user_lists(email); aid = l_data.get('active_list_id')
            if not aid: aid = create_shopping_list(email, 'My List'); set_active_list(email, aid)
            added = add_item_to_list(email, aid, payload)
        except: pass
    return jsonify({'success': bool(claimed or added)})

@api_bp.route('/toggle-favorite', methods=['POST'])
def toggle_favorite():
    email = session.get('user')
    if not email: return jsonify({'error': 'unauthorized'}), 401
    pid = request.get_json().get('product_id')
    if not pid: return jsonify({'error': 'missing_id'}), 400
    if favorites_model.is_favorited(email, pid):
        favorites_model.remove_favorite(email, pid)
        return jsonify({'success': True, 'action': 'removed', 'is_favorite': False})
    p = products_model.get_product_by_id(pid) or featured_deals_model.get_deal_by_id(pid)
    if not p: return jsonify({'error': 'not_found'}), 404
    c = get_cheapest_from_product(p)
    success = favorites_model.add_favorite(email, pid, {'name': p.get('name') or p.get('title'), 'image': p.get('image'), 'best_price': c.get('price'), 'store': c.get('store')})
    return jsonify({'success': bool(success), 'is_favorite': True})

@api_bp.route('/community-price-report', methods=['POST'])
def api_community_price_report_create():
    try:
        p = request.get_json() or {}
        doc = {'product_id': p.get('product_id'), 'store_name': p.get('store_name'), 'observed_price': p.get('observed_price'), 'created_at': datetime.now(timezone.utc)}
        res = get_db().community_price_reports.insert_one(doc)
        return jsonify({'success': True, 'id': str(res.inserted_id)})
    except Exception as e: return jsonify({'error': str(e)}), 500
