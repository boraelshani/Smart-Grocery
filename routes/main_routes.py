from flask import render_template, jsonify, session
from . import main_bp
from models import models as m
try:
    from utils.db import mongo
    HAS_DB = True
except Exception:
    mongo = None
    HAS_DB = False
import re

@main_bp.route('/')
def home():
    # Load stores/products/deals from MongoDB when available, otherwise use in-memory mocks
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        stores = list(mongo.db.stores.find({}))
        products = list(mongo.db.products.find({}))
        featured_deals = list(mongo.db.featured_deals.find({}))
        # convert ObjectId to string id for templates
        for doc_list in (stores, products, featured_deals):
            for d in doc_list:
                if '_id' in d:
                    d['id'] = str(d['_id'])
    else:
        stores = getattr(m, 'stores', [])
        products = getattr(m, 'products', [])
        featured_deals = getattr(m, 'featured_deals', [])

    return render_template('home.html', stores=stores, products=products, featured_deals=featured_deals)

@main_bp.route('/stores')
def stores_page():
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        stores = list(mongo.db.stores.find({}))
        for s in stores:
            if '_id' in s:
                s['id'] = str(s['_id'])
    else:
        stores = getattr(m, 'stores', [])
    return render_template('stores.html', stores=stores)

@main_bp.route('/featured-deals')
def featured_deals_page():
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        deals = list(mongo.db.featured_deals.find({}))
        for d in deals:
            if '_id' in d:
                d['id'] = str(d['_id'])
    else:
        deals = getattr(m, 'featured_deals', [])
    return render_template('featured_deals.html', deals=deals)

@main_bp.route('/compare-prices')
def compare_prices():
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        products = list(mongo.db.products.find({}))
        for p in products:
            if '_id' in p:
                p['id'] = str(p['_id'])
    else:
        products = getattr(m, 'products', [])
    return render_template('compare_prices.html', products=products)

@main_bp.route('/shopping-list')
def shopping_list():
    user_email = session.get('user')
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None and user_email:
        user = mongo.db.users.find_one({'email': user_email})
        if user and '_id' in user:
            user['id'] = str(user['_id'])
        user_data = user or {}
    else:
        user_data = getattr(m, 'users', {}).get('user1@example.com', {})
    # Build items list with price/store information for the template
    shopping_entries = user_data.get('shopping_list', []) if isinstance(user_data, dict) else []

    # load products to try to find prices
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        products = list(mongo.db.products.find({}))
        for p in products:
            if '_id' in p:
                p['id'] = str(p['_id'])
    else:
        products = getattr(m, 'products', [])

    def find_product_by_name(name):
        if not name:
            return None
        name_l = name.lower()
        for p in products:
            if isinstance(p.get('name'), str) and p.get('name').lower() == name_l:
                return p
        for p in products:
            if isinstance(p.get('name'), str) and name_l in p.get('name').lower():
                return p
        return None

    items = []
    for idx, entry in enumerate(shopping_entries):
        # entry might be a plain string or dict
        if isinstance(entry, dict):
            name = entry.get('name')
            qty = int(entry.get('qty', entry.get('quantity', 1))) if entry.get('qty') or entry.get('quantity') else 1
            purchased = bool(entry.get('purchased', False))
        else:
            name = str(entry)
            qty = 1
            purchased = False

        product = find_product_by_name(name)
        price_val = 0.0
        store_name = ''
        if product:
            # try common fields for price
            cheapest = product.get('cheapest') or {}
            price_field = cheapest.get('price') if isinstance(cheapest, dict) else product.get('price')
            if price_field is None:
                # fallback to first 'stores' entry
                try:
                    stores_list = product.get('stores', [])
                    if stores_list and isinstance(stores_list, list):
                        price_field = stores_list[0].get('price')
                        store_name = stores_list[0].get('store') or stores_list[0].get('name')
                except Exception:
                    price_field = None
            if price_field is not None:
                # normalize to float
                try:
                    if isinstance(price_field, (int, float)):
                        price_val = float(price_field)
                    else:
                        # strip anything except digits and dot
                        cleaned = re.sub(r"[^0-9.]", "", str(price_field))
                        price_val = float(cleaned) if cleaned else 0.0
                except Exception:
                    price_val = 0.0
            if not store_name:
                # try cheapest.store
                try:
                    store_name = (product.get('cheapest') or {}).get('store', '')
                except Exception:
                    store_name = ''

        item = {
            'id': product.get('id') if product and product.get('id') else f'item-{idx}',
            'name': name,
            'price': f"${price_val:.2f}",
            'price_val': price_val,
            'store': store_name,
            'qty': qty,
            'purchased': purchased,
        }
        items.append(item)

    return render_template('shopping_list.html', user_data=user_data, items=items)

@main_bp.route('/profile')
def profile():
    user_email = session.get('user')
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None and user_email:
        user = mongo.db.users.find_one({'email': user_email})
        if user and '_id' in user:
            user['id'] = str(user['_id'])
        user_data = user or {}
    else:
        user_data = getattr(m, 'users', {}).get('user1@example.com', {})
    return render_template('profile.html', user_data=user_data)

@main_bp.route('/about')
def about():
    return render_template('about.html')


@main_bp.route('/admin/status')
def admin_status():
    """Return JSON with collection counts so you can verify DB connectivity."""
    collections = ['products', 'stores', 'featured_deals', 'users']
    counts = {}
    if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
        try:
            for c in collections:
                counts[c] = int(mongo.db[c].count_documents({}))
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        # fallback to in-memory mock data
        counts['products'] = len(getattr(m, 'products', []))
        counts['stores'] = len(getattr(m, 'stores', []))
        counts['featured_deals'] = len(getattr(m, 'featured_deals', []))
        counts['users'] = len(getattr(m, 'users', {}))

    return jsonify({'db': counts})
