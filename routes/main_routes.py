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
    return render_template('home.html', stores=stores, products=products, featured_deals=featured_deals)

@main_bp.route('/stores')
def stores_page():
    return render_template('stores.html', stores=stores)

@main_bp.route('/featured-deals')
def featured_deals_page():
    return render_template('featured_deals.html', deals=featured_deals)

@main_bp.route('/compare-prices')
def compare_prices():
    return render_template('compare_prices.html', products=products)

@main_bp.route('/shopping-list')
def shopping_list():
    return render_template('shopping_list.html', user_data=users.get("user1@example.com", {}))

@main_bp.route('/profile')
def profile():
    return render_template('profile.html', user_data=users.get("user1@example.com", {}))

@main_bp.route('/about')
def about():
    return render_template('about.html')


@main_bp.route('/admin/status')
def admin_status():
    """Return JSON with collection counts so you can verify DB connectivity."""
    collections = ['products', 'stores', 'featured_deals', 'users']
    counts = {}
    if HAS_DB and mongo and getattr(mongo, 'db', None):
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
