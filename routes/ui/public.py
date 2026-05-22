import time
import random
import re
from datetime import datetime
from flask import render_template, session, request, url_for, current_app, redirect
from .. import main_bp
from models import models as m
from models.products_model import products_model
from models.stores_model import stores_model
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.quantity_discounts_model import quantity_discounts_model
from models.favorites_model import favorites_model
from utils import helpers

_PAGE_CACHE_TTL_SEC = 120
_page_cache = {}


def invalidate_home_cache(user_email=None):
    if user_email:
        _page_cache.pop(f"home:{user_email}", None)
    else:
        _page_cache.clear()

def load_featured_deals_fallback():
    import os
    import json
    try:
        path = os.path.join(current_app.root_path, 'data', 'featured_deals.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'WARNING: Failed to load featured deals fallback: {e}')
        return []

@main_bp.route('/')
def home():
    """Main dashboard route."""
    user_email = session.get('user')
    if not user_email:
        return render_template('entry.html')

    # Cache handling
    cache_bust = request.args.get('refresh') == '1'
    cache_key = f"home:{user_email}"
    now_ts = time.time()
    cached = _page_cache.get(cache_key)
    if not cache_bust and cached and cached.get('expires_at', 0) > now_ts:
        return render_template('home.html', **cached.get('context', {}))

    # Initialization
    stores = []
    products = []
    featured_deals = []
    popular_products = []
    store_products = []
    categories = []
    total_deals_count = 0
    total_product_count = 0
    chosen_store_name = None
    max_savings = 25
    using_fallback = False
    user_join_date = None

    # Load shared data
    try:
        stores = stores_model.list_stores()
        products = products_model.list_products(limit=20)
        
        # Fetch root categories from PostgreSQL (parent_id is NULL)
        try:
            from models.postgres_models import Category
            cat_rows = Category.query.filter(
                Category.parent_id.is_(None),
                Category.image_url.isnot(None),
                Category.image_url != ''
            ).limit(12).all()
            categories = [
                {
                    'id': cat.slug,
                    'name': cat.name_en or 'Category',
                    'image': cat.image_url or ''
                }
                for cat in cat_rows if cat.image_url
            ]
        except Exception as e:
            print(f'WARNING: Failed to load categories: {e}')
            categories = []
        
        total_deals_count = (featured_deals_model.get_deals_count() + 
                           multibuy_offers_model.get_offers_count() + 
                           len(quantity_discounts_model.list_active_discounts()))
        try:
            total_product_count = products_model.count_products()
        except:
            total_product_count = len(products)
        
        featured_deals_list = featured_deals_model.list_featured_deals()
        multibuy_offers_list = multibuy_offers_model.list_active_offers()
        quantity_discounts_list = quantity_discounts_model.list_active_discounts()
        
        multibuy_deals = []
        regular_deals = []
        
        for deal in featured_deals_list:
            offer_str = str(deal.get('offer') or '').lower()
            is_multibuy = 'buy' in offer_str and ('get' in offer_str or 'free' in offer_str or '+' in offer_str)
            if is_multibuy:
                multibuy_deals.append(deal)
            else:
                regular_deals.append(deal)
        
        multibuy_deals.extend(multibuy_offers_list)
        multibuy_deals.extend(quantity_discounts_list)
        
        selected_multibuy = multibuy_deals[:5]
        selected_regular = regular_deals[:5]
        featured_deals = selected_multibuy + selected_regular
        
        remaining = [d for d in (multibuy_deals + regular_deals) if d not in featured_deals]
        featured_deals.extend(remaining[:max(0, 20 - len(featured_deals))])
        
        if not featured_deals:
            using_fallback = True
            featured_deals = load_featured_deals_fallback()
            total_deals_count = len(featured_deals)
            
    except Exception as e:
        print(f'ERROR in home route: {e}')
        using_fallback = True
        featured_deals = load_featured_deals_fallback()
        total_deals_count = len(featured_deals)

    # Favorites
    fav_ids = set()
    if user_email:
        try:
            user_favs = favorites_model.get_user_favorites(user_email)
            fav_ids = {str(f.get('product_id')) for f in user_favs}
        except: pass
    
    for p in products:
        p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids
    for d in featured_deals:
        d['is_favorited'] = str(d.get('id') or d.get('_id', '')) in fav_ids

    # Popular - Get products from database
    try:
        from models.postgres_models import Product
        pop_rows = Product.query.filter(
            Product.default_image_url.isnot(None),
            Product.default_image_url != '',
        ).order_by(Product.updated_at.desc()).limit(12).all()
        popular_products = [products_model._hydrate_product(p) for p in pop_rows]

        if not popular_products:
            popular_products = products[:12]

        # Mark favorites
        for p in popular_products:
            p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids
    except Exception as e:
        print(f'ERROR fetching popular products: {e}')
        popular_products = products[:12]

    # Store stats & Featured store
    from collections import defaultdict
    store_counts = defaultdict(int)
    
    def _norm(n): return str(n or '').strip().lower()
    
    for p in products:
        s_list = p.get('stores', [])
        if s_list:
            for s in s_list:
                name = s.get('store') or s.get('name')
                if name: store_counts[_norm(name)] += 1
        else:
            name = p.get('store')
            if name: store_counts[_norm(name)] += 1
            
    for d in featured_deals:
        name = d.get('store') or d.get('source')
        if name: store_counts[_norm(name)] += 1

    for s in stores:
        s['product_count'] = store_counts.get(_norm(s.get('name')), 0)

    # Pick Featured Store
    store_lookup = {_norm(s.get('name')): s.get('name') for s in stores if s.get('name')}
    if store_lookup:
        chosen_norm = random.choice(list(store_lookup.keys()))
        chosen_store_name = store_lookup[chosen_norm]
        
        # Build store products
        compact_chosen = re.sub(r'[^a-z0-9]', '', chosen_norm)
        for p in products:
            match = None
            for s in p.get('stores', []) or []:
                sn = _norm(s.get('store') or s.get('name'))
                if sn == chosen_norm or (compact_chosen and compact_chosen in re.sub(r'[^a-z0-9]', '', sn)):
                    match = s
                    break
            if not match and _norm(p.get('store')) == chosen_norm:
                match = {'store': p.get('store'), 'price': p.get('price')}
            
            if match:
                store_products.append({
                    'id': str(p.get('_id') or p.get('id')),
                    'name': p.get('name') or p.get('title'),
                    'image': match.get('image') or p.get('image'),
                    'store': chosen_store_name,
                    'price': match.get('price') or p.get('price'),
                    'category': p.get('category'),
                    'url': p.get('url') or p.get('link') or ''
                })
        store_products = store_products[:20]

    # Render Context
    context = {
        'stores': stores,
        'products': products[:15],
        'featured_deals': featured_deals[:10],
        'popular_products': popular_products,
        'store_products': store_products,
        'categories': categories,
        'total_deals_count': total_deals_count,
        'total_product_count': total_product_count,
        'chosen_store_name': chosen_store_name,
        'max_savings': max_savings,
        'using_fallback': using_fallback
    }

    # Internal cache update
    _page_cache[cache_key] = {
        'expires_at': now_ts + _PAGE_CACHE_TTL_SEC,
        'context': context
    }

    return render_template('home.html', **context)

@main_bp.route('/scanner')
def barcode_scanner():
    """Barcode Scanner Tool UI."""
    return render_template('barcode_scanner.html')
