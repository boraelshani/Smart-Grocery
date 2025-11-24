from flask import render_template, jsonify, session
from . import main_bp
from models import models as m
try:
    from utils.db import mongo
    HAS_DB = True
except Exception:
    mongo = None
    HAS_DB = False

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
    return render_template('shopping_list.html', user_data=user_data)

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
