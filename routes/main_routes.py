from flask import render_template
from . import main_bp
from models.models import stores, products, featured_deals, users

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
