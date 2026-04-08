import re
from flask import render_template, session, request, current_app
from .. import main_bp
from models.products_model import products_model
from models.stores_model import stores_model
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.quantity_discounts_model import quantity_discounts_model
from models.favorites_model import favorites_model
from utils import helpers

# Standard category list
STANDARD_CATEGORIES = [
    "Produce", "Pantry", "Dairy", "Meat", "Frozen",
    "Bakery", "Baby food", "Snacks", "Fast Food & To Go",
    "Household", "Beverages"
]

def _mark_list_metadata(items, fav_ids=None):
    if not items:
        return items
    multibuy_offers_model.attach_offers_to_products(items)
    quantity_discounts_model.attach_discounts_to_products(items)
    if fav_ids is not None:
        for item in items:
            if isinstance(item, dict):
                item_id = str(item.get('id') or item.get('_id', ''))
                item['is_favorited'] = item_id in fav_ids
    return items

@main_bp.route('/stores')
def stores_page():
    """Stores Directory Page."""
    try:
        stores = stores_model.list_stores()
        for s in stores:
            store_name = s.get('name', '')
            product_count = products_model.count_by_store(store_name)
            deals_count = featured_deals_model.count_by_store(store_name)
            s['product_count'] = product_count + deals_count
    except Exception as e:
        print(f"Error fetching stores: {e}")
        stores = []
    
    category_options = [{"name": cat} for cat in STANDARD_CATEGORIES]
    stores = helpers.sanitize_mongo_doc(stores)
    return render_template('stores.html', stores=stores, category_options=category_options)

@main_bp.route('/stores/<store_name>')
def store_products_page(store_name):
    """Display all products for a specific store."""
    products = []
    store_info = None
    try:
        store_info = stores_model.get_store_by_name(store_name)
        prod_docs = products_model.find_by_store(store_name)
        for prod in prod_docs:
            matched_stores = [s for s in (prod.get('stores') or []) 
                            if (s.get('store') or '').lower() == store_name.lower()]
            if matched_stores:
                prod['store_price'] = matched_stores[0].get('price')
                prod['store_image'] = matched_stores[0].get('image') or prod.get('image')
                if matched_stores[0].get('url'):
                    prod['url'] = matched_stores[0].get('url')
            else:
                prod['store_price'] = prod.get('price')
                prod['store_image'] = prod.get('image')
            products.append(prod)
        
        deals_docs = featured_deals_model.find_by_store(store_name)
        for deal in deals_docs:
            if 'title' in deal and 'name' not in deal:
                deal['name'] = deal['title']
            deal['store_price'] = deal.get('price')
            deal['store_image'] = deal.get('image')
            products.append(deal)

        # Apply favorites
        user_email = session.get('user')
        fav_ids = set()
        if user_email:
            try:
                user_favs = favorites_model.get_user_favorites(user_email)
                fav_ids = {str(f.get('product_id')) for f in user_favs}
            except: pass
        
        _mark_list_metadata(products, fav_ids)
    except Exception as e:
        print(f'ERROR loading store products: {e}')

    category_options = [{"name": cat} for cat in STANDARD_CATEGORIES]
    products = helpers.sanitize_mongo_doc(products)
    store_info = helpers.sanitize_mongo_doc(store_info)
    
    return render_template('store_products.html', 
                         store_name=store_name, 
                         store=store_info, 
                         products=products, 
                         product_count=len(products), 
                         category_options=category_options)
