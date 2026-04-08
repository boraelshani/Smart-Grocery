from flask import render_template, session, request, redirect, url_for
from .. import main_bp
from models.products_model import products_model
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.quantity_discounts_model import quantity_discounts_model
from models.favorites_model import favorites_model
from models.stores_model import stores_model
from comparison.comparison_engine import build_compare_product_payload, build_best_price_summary
from comparison.store_matcher import build_store_meta_map
from utils import helpers

@main_bp.route('/product-info/<product_id>')
@main_bp.route('/product/<product_id>')
def product_detail(product_id):
    """Detailed product comparison page."""
    product = products_model.get_product_by_id(product_id) or \
              featured_deals_model.get_deal_by_id(product_id) or \
              multibuy_offers_model.get_offer_by_id(product_id) or \
              quantity_discounts_model.get_discount_by_id(product_id)
    
    if not product:
        return render_template('404.html'), 404
    
    is_favorited = False
    user_email = session.get('user')
    if user_email:
        try:
            is_favorited = favorites_model.is_favorited(user_email, str(product.get('id') or product.get('_id', '')))
        except: pass
    
    # Build comparison payload
    store_meta = build_store_meta_map(stores_model.list_stores())
    payload = build_compare_product_payload(helpers.sanitize_mongo_doc(product), store_meta_map=store_meta)
    best_price_value, best_price_stores = build_best_price_summary(payload)
    
    return render_template('product_detail.html', 
                         product=payload, 
                         best_price_value=best_price_value,
                         best_price_stores=best_price_stores,
                         is_favorited=is_favorited)

@main_bp.route('/compare')
@main_bp.route('/compare-prices')
def compare_prices():
    """Price Comparison Engine - Search and Categories."""
    per_page = 30
    page = int(request.args.get('page', 1))
    category_filter = (request.args.get('category') or '').strip()
    search_query = (request.args.get('search') or '').strip()

    import re
    query = {}
    if category_filter:
        query['category'] = {'$regex': f"^{re.escape(category_filter)}$", '$options': 'i'}
    if search_query:
        search_regex = {'$regex': re.escape(search_query), '$options': 'i'}
        query['$or'] = [{'name': search_regex}, {'title': search_regex}, {'category': search_regex}]

    total_products = products_model.count_products(query)
    total_pages = (total_products + per_page - 1) // per_page if total_products else 1
    page = max(1, min(page, total_pages))
    
    products = products_model.list_products(query=query, skip=(page - 1) * per_page, limit=per_page)
    
    # Favorites mark
    user_email = session.get('user')
    fav_ids = set()
    if user_email:
        try:
            user_favs = favorites_model.get_user_favorites(user_email)
            fav_ids = {str(f.get('product_id')) for f in user_favs}
        except: pass
    
    for p in products:
        p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids

    category_options = [{"name": cat} for cat in ["Produce", "Pantry", "Dairy", "Meat", "Frozen", "Bakery", "Baby food", "Snacks", "Fast Food & To Go", "Household", "Beverages"]]
    
    return render_template('compare_prices.html',
                         products=helpers.sanitize_mongo_doc(products),
                         page=page,
                         total_pages=total_pages,
                         total_products=total_products,
                         category_filter=category_filter,
                         search_query=search_query,
                         category_options=category_options)
