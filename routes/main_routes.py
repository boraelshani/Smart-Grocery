from flask import render_template, jsonify, session, request, current_app, url_for, redirect
from . import main_bp
from models import models as m
from models.products_model import products_model
from models.stores_model import stores_model
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.favorites_model import favorites_model
from models.notifications_model import notifications_model
from models.quantity_discounts_model import quantity_discounts_model
from utils import helpers
from bson.decimal128 import Decimal128
import json
import os
import random
import re

# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

# Standard category list provided by user for consistent filtering across pages
STANDARD_CATEGORIES = [
    "Produce", "Pantry", "Dairy", "Meat", "Frozen", 
    "Bakery", "Baby food", "Snacks", "Fast Food & To Go", 
    "Household", "Beverages"
]

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def load_featured_deals_fallback():
    """
    Load featured deals from the static JSON fallback file.
    Used when MongoDB is unavailable during development/testing.
    Returns: List of featured deal dictionaries
    """
    try:
        path = os.path.join(current_app.root_path, 'data', 'featured_deals.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'WARNING: Failed to load featured deals fallback: {e}')
        return []








def _mark_list_metadata(items, fav_ids=None):
    """
    Universal marker function to attach offers and favorites to a list of product items.
    """
    if not items:
        return items
        
    # 1. Attach offer metadata using Model-based helper
    multibuy_offers_model.attach_offers_to_products(items)
    
    # 2. Attach quantity discount metadata
    quantity_discounts_model.attach_discounts_to_products(items)

    # 3. Mark favorites if fav_ids provided
    if fav_ids is not None:
        for item in items:
            if isinstance(item, dict):
                item_id = str(item.get('id') or item.get('_id', ''))
                item['is_favorited'] = item_id in fav_ids
    
    return items


@main_bp.route('/')
def home():
    """
    The Main Dashboard (Home) Route.
    
    Logic Flow:
    1. Authentication Check: Redirects to Entry page if not logged in.
    2. Data Aggregation: Fetches Stores, Products, and Featured Deals from DB.
    3. User Personalization: 
       - Fetches user favorites to mark items with hearts.
       - Generates recommendations based on past behavior.
    4. Fallback Handling: Uses local JSON data if MongoDB fails.
    5. Statistics: Calculates total savings and counts for badges.
    """
    # If the user is not signed in, show the entry page prompting Log In / Sign Up
    user_email = session.get('user')
    if not user_email:
        return render_template('entry.html')

    # Initialize all potential template variables to empty defaults
    stores = []
    products = []
    featured_deals = []
    popular_products = []
    store_products = []
    recommended_products = []
    favorites = []
    total_deals_count = 0
    total_product_count = 0
    chosen_store_name = None
    max_savings = 25
    using_fallback = False
    user_join_date = None

    # Get user join date for "NEW" badge logic
    if user_email:
        try:
            from models.users_model import get_user_by_email
            user_data = get_user_by_email(user_email)
            if user_data:
                user_join_date = user_data.get('created_at')
        except:
            pass

    # Load stores/products/deals from Models
    try:
        stores = stores_model.list_stores()
        products = products_model.list_products()
        
        # Count total deals from all collections using Models
        total_deals_count = (featured_deals_model.get_deals_count() + 
                           multibuy_offers_model.get_offers_count() + 
                           len(quantity_discounts_model.list_active_discounts()))
        
        # Fetch featured deals, multibuy offers, and quantity discounts
        featured_deals_list = featured_deals_model.list_featured_deals()
        multibuy_offers_list = multibuy_offers_model.list_active_offers()
        quantity_discounts_list = quantity_discounts_model.list_active_discounts()
        
        # Separate multi-buy deals from regular discount deals
        multibuy_deals = []
        regular_deals = []
        
        # Check featured_deals_list for multi-buy vs regular
        for deal in featured_deals_list:
            offer_obj = deal.get('offer') if isinstance(deal.get('offer'), dict) else None
            offer_str = deal.get('offer', '') if isinstance(deal.get('offer'), str) else ''
            offer_x = offer_obj.get('x') if offer_obj else (deal.get('buy_quantity') or deal.get('multibuy_buy') or '')
            offer_y = offer_obj.get('y') if offer_obj else (deal.get('free_quantity') or deal.get('multibuy_free') or '')
            offer_type = offer_obj.get('type') if offer_obj else ('buyXgetY' if offer_x and offer_y else '')
            is_multibuy = (offer_type == 'buyXgetY') or (offer_str and ('buy' in offer_str.lower() and ('get' in offer_str.lower() or 'free' in offer_str.lower() or '+' in offer_str)))
            
            if is_multibuy:
                multibuy_deals.append(deal)
            else:
                regular_deals.append(deal)
        
        # Add all multibuy_offers and quantity_discounts to multibuy_deals
        multibuy_deals.extend(multibuy_offers_list)
        multibuy_deals.extend(quantity_discounts_list)
        
        # Ensure at least 5 multibuy and 5 regular deals
        import random
        selected_multibuy = multibuy_deals[:5] if len(multibuy_deals) >= 5 else multibuy_deals
        selected_regular = regular_deals[:5] if len(regular_deals) >= 5 else regular_deals
        
        # Combine and fill remaining with any other deals
        featured_deals = selected_multibuy + selected_regular
        
        # Add more deals to reach 20 total
        remaining_deals = [d for d in (multibuy_deals + regular_deals) if d not in featured_deals]
        if remaining_deals:
            featured_deals.extend(remaining_deals[:max(0, 20 - len(featured_deals))])
        
        # If no deals found, use JSON fallback
        if not featured_deals:
            using_fallback = True
            featured_deals = load_featured_deals_fallback()
            total_deals_count = len(featured_deals)
            
    except Exception as e:
        print(f'ERROR in home route: {e}')
        using_fallback = True
        featured_deals = load_featured_deals_fallback()
        total_deals_count = len(featured_deals)
    
    # Filter featured deals based on user join date if requested
    if user_join_date:
        from datetime import datetime
        # Helper to parse dates from Mongo/JSON strings if needed
        def get_date(d):
            dt = d.get('created_at')
            if isinstance(dt, str):
                try: return datetime.fromisoformat(dt)
                except: return None
            return dt
        
        # Filter notification-like "posts" (featured deals)
        featured_deals = [d for d in featured_deals if not get_date(d) or get_date(d) >= user_join_date]

    # Check favorites for user using Model
    fav_ids = set()
    if user_email:
        try:
            user_favs = favorites_model.get_user_favorites(user_email)
            fav_ids = {str(f.get('product_id')) for f in user_favs}
        except Exception as e:
            print(f"Error loading favorites for home page: {e}")
    
    # Mark favorited items
    for p in products:
        p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids
    for d in featured_deals:
        d['is_favorited'] = str(d.get('id') or d.get('_id', '')) in fav_ids

    # Fetch popular products using Model
    try:
        popular_products = products_model.get_popular_products(limit=12)
        for p in popular_products:
            p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids
    except Exception as e:
        print(f"Error fetching popular products: {e}")
        popular_products = products[:12] if products else []

    # Pull user preferences (preferred stores)
    preferred_stores = []
    if user_email:
        try:
            from models.users_model import get_user_by_email
            user_doc = get_user_by_email(user_email)
            if user_doc:
                prefs_obj = user_doc.get('preferences') or {}
                preferred_stores = prefs_obj.get('preferred_stores') or user_doc.get('preferred_stores') or []
        except Exception:
            preferred_stores = []

    # Calculate per-store product counts and total product count
    from collections import defaultdict

    def _norm_store(name):
        return (str(name or '').strip().lower())

    def _norm_compact(name):
        # normalize and remove non-alphanumeric for flexible matching
        import re as _re
        n = _norm_store(name)
        return _re.sub(r"[^a-z0-9]", "", n)

    store_counts = defaultdict(int)
    total_product_count = 0

    # Count products by store (only count products, not deals, for accuracy)
    for product in products:
        stores_list = product.get('stores', [])
        if stores_list:
            total_product_count += len(stores_list)
            for s in stores_list:
                store_name = s.get('store') or s.get('store_name') or s.get('name') or ''
                norm = _norm_store(store_name)
                if norm:
                    store_counts[norm] += 1
        else:
            total_product_count += 1
            store_name = product.get('store') or product.get('store_name') or ''
            norm = _norm_store(store_name)
            if norm:
                store_counts[norm] += 1

    # Count featured deals separately by store and add to product count
    for deal in featured_deals:
        deal_store = deal.get('store') or deal.get('source') or ''
        norm = _norm_store(deal_store)
        if norm:
            store_counts[norm] += 1
    total_product_count += len(featured_deals)

    # Attach counts to store documents shown on the home page
    # Use the same counting logic as store_products_page for consistency
    for store in stores:
        name = store.get('name') or store.get('store') or ''
        norm = _norm_store(name)
        
        # Count actual products for this store using Models
        store_product_count = 0
        try:
            # Count products and deals using Models instead of direct DB calls
            product_count = products_model.count_by_store(name)
            deal_count = featured_deals_model.count_by_store(name)
            store_product_count = product_count + deal_count
        except Exception as e:
            print(f'WARNING: Error counting products for {name}: {e}')
            store_product_count = store_counts.get(norm, 0)
        
        store['product_count'] = store_product_count

    # Choose a single store to feature on the home page based on preferences
    store_lookup = {(_norm_store(s.get('name') or s.get('store') or '')): (s.get('name') or s.get('store') or '') for s in stores if (s.get('name') or s.get('store'))}
    candidate_norms = [_norm_store(s) for s in preferred_stores if _norm_store(s) in store_lookup]
    chosen_norm = None
    if candidate_norms:
        chosen_norm = candidate_norms[0] if len(candidate_norms) == 1 else random.choice(candidate_norms)
    elif store_lookup:
        chosen_norm = random.choice(list(store_lookup.keys()))
    chosen_store_name = store_lookup.get(chosen_norm) if chosen_norm else None

    # Build list of products and deals for the chosen store
    if chosen_norm:
        chosen_compact = _norm_compact(chosen_store_name or chosen_norm)
        for product in products:
            match_entry = None
            for s in product.get('stores', []) or []:
                store_name = s.get('store') or s.get('store_name') or s.get('name') or ''
                store_norm = _norm_store(store_name)
                store_compact = _norm_compact(store_name)
                # Accept exact or compact contains matching to handle variants like "lidl österreich"
                if store_norm == chosen_norm or (store_compact and chosen_compact and (store_compact in chosen_compact or chosen_compact in store_compact)):
                    match_entry = s
                    break
            if not match_entry:
                single_store = product.get('store') or product.get('store_name')
                if single_store:
                    single_norm = _norm_store(single_store)
                    single_compact = _norm_compact(single_store)
                    if single_norm == chosen_norm or (single_compact and chosen_compact and (single_compact in chosen_compact or chosen_compact in single_compact)):
                        match_entry = {'store': single_store, 'price': product.get('price')}

            if match_entry:
                pid = product.get('id') or product.get('_id') or product.get('product_id') or match_entry.get('product_id') or match_entry.get('id') or None
                image = match_entry.get('image') or product.get('image') or ((product.get('images') or [None])[0]) or url_for('static', filename='placeholder.svg')
                price_val = match_entry.get('price') or match_entry.get('price_val') or product.get('price') or 0
                store_products.append({
                    'id': str(pid) if pid is not None else None,
                    'name': product.get('name') or product.get('title') or 'Product',
                    'image': image,
                    'store': match_entry.get('store') or match_entry.get('store_name') or chosen_store_name,
                    'price': price_val,
                    'category': product.get('category'),
                    'unit': product.get('unit'),
                    'url': product.get('url') or match_entry.get('url') or product.get('link') or product.get('product_url') or '',
                })

        # Also include featured deals for the chosen store
        try:
            for deal in featured_deals:
                deal_store = deal.get('store') or deal.get('source') or ''
                deal_norm = _norm_store(deal_store)
                deal_compact = _norm_compact(deal_store)
                if deal_norm == chosen_norm or (deal_compact and chosen_compact and (deal_compact in chosen_compact or chosen_compact in deal_compact)):
                    did = str(deal.get('id') or deal.get('_id') or '')
                    dname = deal.get('name') or deal.get('title') or 'Deal'
                    dimg = deal.get('image') or url_for('static', filename='placeholder.svg')
                    dprice = deal.get('price') or deal.get('best_price') or 0
                    store_products.append({
                        'id': did if did else None,
                        'name': dname,
                        'image': dimg,
                        'store': deal_store or chosen_store_name,
                        'price': dprice,
                        'category': deal.get('category'),
                        'unit': deal.get('unit'),
                        'url': deal.get('url') or deal.get('deal_url') or deal.get('link') or '',
                    })
        except Exception:
            pass

    # Limit to a manageable number for Home section (use View All for the rest)
    store_products = store_products[:20]

    # Calculate max savings percentage from featured deals
    max_savings = 0
    for deal in featured_deals:
        # Check for discount_percent field
        discount = deal.get('discount_percent')
        if discount:
            try:
                discount_value = float(discount)
                max_savings = max(max_savings, discount_value)
            except:
                pass
        
        # Calculate from original_price and price if available
        original = deal.get('original_price')
        current = deal.get('price')
        if original and current:
            try:
                original_val = float(original)
                current_val = float(current)
                if original_val > 0:
                    discount_pct = ((original_val - current_val) / original_val) * 100
                    max_savings = max(max_savings, discount_pct)
            except:
                pass
    
    # Round to nearest integer
    max_savings = int(round(max_savings)) if max_savings > 0 else 25

    # Load user favorites and recommendations using Models
    try:
        favorites = favorites_model.get_user_favorites(user_email)
        # Normalize id to string for template usage
        for fav in favorites:
            if isinstance(fav, dict):
                if not fav.get('id') and fav.get('product_id'):
                    fav['id'] = str(fav['product_id'])
                if not fav.get('name') and fav.get('product_name'):
                    fav['name'] = fav.get('product_name')
                if not fav.get('image') and fav.get('product_image'):
                    fav['image'] = fav.get('product_image')
        
        # Compute recommendations using Model method
        try:
            from models.users_model import get_user_lists
            
            # Collect shops and categories from favorites and shopping lists
            favorite_shops = [fav.get('store') for fav in favorites if fav.get('store')]
            favorite_categories = [fav.get('category') for fav in favorites if fav.get('category')]
            
            list_shops = []
            list_categories = []
            lists_data = get_user_lists(user_email) or {}
            for lst in (lists_data.get('lists', []) or []):
                for item in (lst.get('items', []) or []):
                    if isinstance(item, dict):
                        if item.get('store'): list_shops.append(item.get('store'))
                        if item.get('category'): list_categories.append(item.get('category'))
            
            all_shops = favorite_shops + list_shops
            all_categories = favorite_categories + list_categories
            
            # Use ProductsModel to get recommendations
            recommended_products = products_model.get_recommendations(all_shops, all_categories)
                
        except Exception as e:
            print(f'WARNING: Failed to compute recommendations: {e}')
            recommended_products = products[:12]
    except Exception as e:
        print(f'WARNING: Failed to load favorites: {e}')

    # Ensure all product lists are marked with is_favorited status
    if user_email:
        try:
            fav_ids = {str(f.get('product_id')) for f in favorites}
            
            _mark_list_metadata(products, fav_ids)
            _mark_list_metadata(featured_deals, fav_ids)
            _mark_list_metadata(store_products, fav_ids)
            _mark_list_metadata(recommended_products, fav_ids)
            _mark_list_metadata(popular_products, fav_ids)
        except Exception as e:
            print(f"Error marking metadata in home route: {e}")
            print(f"Error marking favorites on home page: {e}")

    # Sanitize all data for template rendering to prevent ObjectId errors
    stores = helpers.sanitize_mongo_doc(stores)
    products = helpers.sanitize_mongo_doc(products)
    featured_deals = helpers.sanitize_mongo_doc(featured_deals)
    popular_products = helpers.sanitize_mongo_doc(popular_products)
    recommended_products = helpers.sanitize_mongo_doc(recommended_products)
    store_products = helpers.sanitize_mongo_doc(store_products)
    favorites = helpers.sanitize_mongo_doc(favorites)

    return render_template('home.html', 
                         stores=stores, 
                         products=products, 
                         featured_deals=featured_deals,
                         popular_products=popular_products,
                         total_deals_count=total_deals_count,
                         favorites=favorites,
                         recommended_products=recommended_products,
                         store_products=store_products,
                         chosen_store_name=chosen_store_name,
                         using_fallback=using_fallback, 
                         total_product_count=total_product_count, 
                         max_savings=max_savings,
                         user_join_date=user_join_date)

@main_bp.route('/stores')
def stores_page():
    using_fallback = False
    try:
        stores = stores_model.list_stores()
        for s in stores:
            # Count products for this store using Models
            store_name = s.get('name', '')
            
            # Count in products and featured_deals collections
            product_count = products_model.count_by_store(store_name)
            deals_count = featured_deals_model.count_by_store(store_name)
            
            s['product_count'] = product_count + deals_count
    except Exception as e:
        print(f"Error fetching stores with counts: {e}")
    # Get standard category options for chips/filters
    category_options = [{"name": cat} for cat in STANDARD_CATEGORIES]
    
    # Sanitize stores data
    stores = helpers.sanitize_mongo_doc(stores)

    return render_template('stores.html', stores=stores, using_fallback=using_fallback, category_options=category_options)

@main_bp.route('/stores/<store_name>')
def store_products_page(store_name):
    """Display all products for a specific store."""
    products = []
    store_info = None
    
    try:
        # Get store info using Model
        store_info = stores_model.get_store_by_name(store_name)
        
        # Get products for this store using Model
        prod_docs = products_model.find_by_store(store_name)
        
        for prod in prod_docs:
            # Extract matched store data
            matched_stores = [s for s in (prod.get('stores') or []) 
                            if (s.get('store') or '').lower() == store_name.lower()]
            if matched_stores:
                prod['store_price'] = matched_stores[0].get('price')
                prod['store_image'] = matched_stores[0].get('image') or prod.get('image')
                # Extract URL from store entry if available
                if matched_stores[0].get('url'):
                    prod['url'] = matched_stores[0].get('url')
            else:
                prod['store_price'] = prod.get('price')
                prod['store_image'] = prod.get('image')
            products.append(prod)
        
        # Also get featured deals for this store using Model
        deals_docs = featured_deals_model.find_by_store(store_name)
        
        for deal in deals_docs:
            # Use deal's name field as 'name' for consistency
            if 'title' in deal and 'name' not in deal:
                deal['name'] = deal['title']
            # Set store-specific price and image
            deal['store_price'] = deal.get('price')
            deal['store_image'] = deal.get('image')
            products.append(deal)

        # Get Quantity Discounts for this store
        try:
            qd_all = quantity_discounts_model.list_active_discounts()
            for qd in qd_all:
                if (qd.get('store') or '').lower() == store_name.lower():
                     if 'title' in qd and 'name' not in qd:
                         qd['name'] = qd['title']
                     qd['store_price'] = qd.get('price')
                     qd['store_image'] = qd.get('image')
                     products.append(qd)
        except Exception as e:
            print(f"Error merging quantity discounts: {e}")

        # Check favorites for user using Model
        user_email = session.get('user')
        fav_ids = set()
        if user_email:
            try:
                user_favs = favorites_model.get_user_favorites(user_email)
                fav_ids = {str(f.get('product_id')) for f in user_favs}
            except Exception as e:
                print(f"Error loading favorites for store products: {e}")
        
        for p in products:
            p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids
        
        # Attach offers and additional metadata using Models
        _mark_list_metadata(products, fav_ids)

    except Exception as e:
        print(f'ERROR loading products for {store_name}: {e}')

    # Fallback to in-memory data and JSON deals when DB is unavailable or returned nothing
    try:
        if not products:
            store_lc = store_name.lower()

            # In-memory products
            for prod in getattr(m, 'products', []):
                matched_stores = [s for s in (prod.get('stores') or [])
                                  if (s.get('store') or s.get('name') or '').lower() == store_lc]
                top_level_match = isinstance(prod.get('store'), str) and prod.get('store', '').lower() == store_lc
                if matched_stores or top_level_match:
                    shaped = dict(prod)
                    if '_id' in shaped:
                        shaped['id'] = str(shaped['_id'])
                    shaped['store_price'] = matched_stores[0].get('price') if matched_stores else prod.get('price')
                    shaped['store_image'] = matched_stores[0].get('image') if matched_stores else prod.get('image')
                    if matched_stores and matched_stores[0].get('url'):
                        shaped['url'] = matched_stores[0].get('url')
                    products.append(shaped)

            # Featured deals fallback JSON
            for deal in load_featured_deals_fallback():
                deal_store = (deal.get('store') or deal.get('source') or '').lower()
                if deal_store == store_lc:
                    shaped = dict(deal)
                    if '_id' in shaped:
                        shaped['id'] = str(shaped['_id'])
                    products.append(shaped)
    except Exception as e:
        print(f'ERROR loading fallback products for {store_name}: {e}')
    
    # Enrich fallback products with is_favorited status
    user_email = session.get('user')
    fav_ids = set()
    if user_email:
        try:
            from models.favorites_model import get_user_favorites
            user_favs = get_user_favorites(user_email)
            fav_ids = {str(f.get('product_id')) for f in user_favs}
        except Exception:
            pass
            
    for p in products:
        if 'is_favorited' not in p:
            p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids
    
    # Get standard category options for filters
    category_options = [{"name": cat} for cat in STANDARD_CATEGORIES]
    
    # Sanitize data for template
    products = helpers.sanitize_mongo_doc(products)
    store_info = helpers.sanitize_mongo_doc(store_info)
    
    return render_template('store_products.html', 
                         store_name=store_name, 
                         store=store_info,
                         products=products,
                         product_count=len(products),
                         category_options=category_options)

@main_bp.route('/featured-deals')
def featured_deals_page():
    """
    Deals & Offers Page.
    
    Aggregates special offers from two sources:
    1. Featured Deals: Single item discounts (e.g., 20% off).
    2. Multibuy Offers: Quantity-based deals (e.g., Buy 1 Get 1 Free).
    
    Features:
    - Sorting: Automatically sorts by highest discount %.
    - Notification Logic: Tracks which deals the user has 'seen' to clear notification badges.
    """
    using_fallback = False
    per_page = 30
    try:
        page = int(request.args.get('page', 1))
    except Exception:
        page = 1
    page = max(page, 1)

    category_filter = (request.args.get('category') or '').strip()
    search_query = (request.args.get('search') or '').strip()
    user_email = session.get('user')
    
    deals = []
    category_options = []
    fav_ids = set()

    # 1. Fetch Deals
    try:
        featured_deals_list = featured_deals_model.list_featured_deals()
        multibuy_offers_list = multibuy_offers_model.list_active_offers()
        quantity_discounts_list = quantity_discounts_model.list_active_discounts()
        deals = featured_deals_list + multibuy_offers_list + quantity_discounts_list
    except Exception as e:
        print(f'WARNING: Model query failed for deals: {e}')
        using_fallback = True
        deals = load_featured_deals_fallback()

    # 2. Get category options (Sync with compare page - use specific standard categories)
    try:
        cat_counts = products_model.get_category_counts()
        category_options = [{"name": cat, "count": cat_counts.get(cat, 0)} for cat in STANDARD_CATEGORIES]
    except Exception as e:
        print(f"Error getting categories for deals: {e}")
        category_options = []

    # 3. Filter Deals
    if category_filter:
        deals = [d for d in deals if category_filter.lower() in (d.get('category') or '').lower()]
    
    if search_query:
        sq = search_query.lower()
        deals = [d for d in deals if sq in (d.get('title') or d.get('name') or '').lower() or 
                sq in (d.get('store') or '').lower() or 
                sq in (d.get('category') or '').lower() or
                sq in (d.get('description') or '').lower()]

    # 4. Load Favorites
    if user_email:
        try:
            user_favs = favorites_model.get_user_favorites(user_email)
            fav_ids = {str(f.get('product_id')) for f in user_favs}
        except Exception as e:
            print(f"Error loading favorites for deals page: {e}")
    
    # 5. Attach Metadata
    _mark_list_metadata(deals, fav_ids)
    
    # 6. Notifications logic
    if user_email and deals and not using_fallback:
        try:
            notifications_model.cleanup_old_notifications(7)
            from models.users_model import get_user_by_email, update_user
            user = get_user_by_email(user_email)
            if user:
                current_deal_ids = [str(d.get('id') or d.get('_id')) for d in deals]
                if 'seen_deals' not in user:
                    update_user(user_email, {'seen_deals': current_deal_ids})
                else:
                    seen_deals = set(user.get('seen_deals', []))
                    new_deal_ids = []
                    for deal in deals:
                        deal_id = str(deal.get('id') or deal.get('_id'))
                        if deal_id and deal_id not in seen_deals:
                            deal_title = deal.get('title') or deal.get('name', 'New Deal')
                            store_name = deal.get('store', '')
                            notifications_model.create_notification({
                                'user_email': user_email,
                                'type': 'new_deal',
                                'title': 'New Deal Available!',
                                'message': f'{deal_title}{" at " + store_name if store_name else ""}',
                                'deal_id': deal_id,
                                'store_name': store_name,
                                'action_url': f'/featured-deal/{deal_id}',
                                'priority': 'normal'
                            })
                            new_deal_ids.append(deal_id)
                    if new_deal_ids:
                        update_user(user_email, {'seen_deals': current_deal_ids})
        except Exception as e:
            print(f'WARNING: Failed notifications: {e}')
    
    # Sort deals by discount percentage (highest first)
    def get_sort_key(deal):
        discount = 0
        if deal.get('discount_percent'):
            try: discount = float(deal.get('discount_percent'))
            except: pass
        else:
            original = deal.get('original_price')
            current = deal.get('price')
            if original and current:
                try:
                    original_val = float(original)
                    current_val = float(current)
                    if original_val > 0:
                        discount = ((original_val - current_val) / original_val) * 100
                except: pass
        return -discount 
    
    deals.sort(key=get_sort_key)

    # Implement Pagination metadata
    total_products = len(deals)
    total_pages = (total_products + per_page - 1) // per_page if total_products else 1
    page = min(page, total_pages) if total_products else 1
    
    showing_start = (page - 1) * per_page + 1 if total_products else 0
    showing_end = min(page * per_page, total_products)
    
    # Slice deals for the current page
    paginated_deals = deals[(page - 1) * per_page: page * per_page]
    
    return render_template('featured_deals.html', 
                          deals=paginated_deals, 
                          total_products=total_products,
                          total_pages=total_pages,
                          current_page=page,
                          showing_start=showing_start,
                          showing_end=showing_end,
                          category_filter=category_filter,
                          category_options=category_options,
                          search_query=search_query,
                          using_fallback=using_fallback)

@main_bp.route('/compare-prices')
def compare_prices():
    """
    Core Feature: Price Comparison Engine.
    
    This route handles the complex logic of displaying products with:
    1. Filtering: By Category (e.g., 'Dairy', 'Meat').
    2. Searching: By name, store, or description (RegEx based).
    3. Pagination: Server-side pagination to handle large datasets efficiently.
       - Formula: skip = (page - 1) * per_page
    4. Data Enrichment: Adds real store logos and 'favorited' status to each item.
    """
    per_page = 30
    try:
        page = int(request.args.get('page', 1))
    except Exception:
        page = 1
    page = max(page, 1)

    category_filter = (request.args.get('category') or '').strip()
    search_query = (request.args.get('search') or '').strip()

    total_products = 0
    total_pages = 1
    products = []
    deals = []
    stores = []
    category_options = []

    try:
        query = {}
        if category_filter:
            query['category'] = {'$regex': f"^{re.escape(category_filter)}$", '$options': 'i'}
        
        product_query = dict(query)
        if search_query:
            search_regex = {'$regex': re.escape(search_query), '$options': 'i'}
            product_query['$or'] = [
                {'name': search_regex},
                {'title': search_regex},
                {'category': search_regex},
                {'store': search_regex}
            ]
        
        # New simplified logic using Models
        total_products = products_model.count_products(product_query)
        total_pages = (total_products + per_page - 1) // per_page if total_products else 1
        page = min(page, total_pages) if total_products else 1
        skip_amount = (page - 1) * per_page
        
        products = products_model.list_products(
            query=product_query,
            skip=skip_amount,
            limit=per_page
        )
        
        # Enrich products with real store images/logos from the stores model
        db_stores = stores_model.list_stores()
            
        def find_store_logo_and_image(store_name, db_stores):
            norm = lambda n: (n or '').strip().lower()
            for s in db_stores:
                if norm(s.get('name')) == norm(store_name) or norm(s.get('store')) == norm(store_name):
                    return s.get('logo'), s.get('image') or s.get('store_image')
            return None, None
            
        for p in products:
            product_img = p.get('image') or (p.get('images')[0] if p.get('images') else None)
            for s in (p.get('stores') or []):
                store_name = s.get('store') or s.get('store_name') or s.get('name')
                logo, img = find_store_logo_and_image(store_name, db_stores)
                
                # Attach real store logos/images
                if logo: s['logo'] = logo
                if img: s['store_image'] = img
                
                # If the store entry's 'image' is actually just the product image, clear it
                # to avoid it being used as a store logo in the frontend
                if s.get('image') and s.get('image') == product_img:
                    s['image'] = None

        # Mark favorites and attach offers using the marking helper
        user_email = session.get('user')
        fav_ids = set()
        if user_email:
            try:
                user_favs = favorites_model.get_user_favorites(user_email)
                fav_ids = {str(f.get('product_id')) for f in user_favs}
            except Exception as e:
                print(f"Error loading favorites for compare page: {e}")
        
        _mark_list_metadata(products, fav_ids)

        # Get category options for filter using specific standard categories
        cat_counts = products_model.get_category_counts()
        category_options = [{"name": cat, "count": cat_counts.get(cat, 0)} for cat in STANDARD_CATEGORIES]

        # Search result deals/stores if search query provided
        if search_query:
            try:
                all_deals = (featured_deals_model.list_featured_deals() + 
                           multibuy_offers_model.list_active_offers() + 
                           quantity_discounts_model.list_active_discounts())
                deals = [d for d in all_deals if search_query.lower() in (d.get('title') or d.get('name') or '').lower() or search_query.lower() in (d.get('store') or '').lower()]
                
                all_stores = stores_model.list_stores()
                stores = [s for s in all_stores if search_query.lower() in (s.get('name') or '').lower() or search_query.lower() in (s.get('description') or '').lower()]
            except:
                pass

    except Exception as e:
        print(f'ERROR in compare_prices route: {e}')
        # Minimal fallback
        products = getattr(m, 'products', [])[:30]
        total_products = len(products)
        total_pages = 1

    has_prev = page > 1
    has_next = page < total_pages
    showing_start = ((page - 1) * per_page) + 1 if total_products else 0
    showing_end = min(page * per_page, total_products)

    return render_template(
        'compare_prices.html',
        products=products,
        deals=deals,
        stores=stores,
        using_fallback=(len(products) == 0 or total_products == 0),
        page=page,
        per_page=per_page,
        total_products=total_products,
        total_pages=total_pages,
        has_prev=has_prev,
        has_next=has_next,
        showing_start=showing_start,
        showing_end=showing_end,
        category_filter=category_filter,
        search_query=search_query,
        category_options=category_options,
    )

@main_bp.route('/product/<product_id>')
def product_detail(product_id):
    product = None
    requested_store = request.args.get('store')
    
    # Check database first using Models
    try:
        # Try finding in products collection
        product = products_model.get_product_by_id(product_id)
        
        # If not found, try featured_deals collection
        if not product:
            product = featured_deals_model.get_deal_by_id(product_id)
            
    except Exception as e:
        print(f'Error fetching product using Models: {e}')
    

    # If not found in database, fall back to JSON featured deals
    if not product:
        featured_deals = load_featured_deals_fallback()
        for deal in featured_deals:
            if deal.get('id') == product_id:
                product = deal
                break

    # If still not found, check fallback products (used by compare page)
    if not product:
        from models import models as m
        for prod in getattr(m, 'products', []):
            if prod.get('id') == product_id:
                product = prod
                break

    if not product:
        return render_template('404.html'), 404

    # Attach any active multibuy/quantity offers to the single product
    multibuy_offers_model.attach_offers_to_products([product])
    quantity_discounts_model.attach_discounts_to_products([product])

    # Ensure a minimal stores array exists for featured deals or products without stores
    if not product.get('stores'):
        store_name = product.get('store') or product.get('source') or 'Store'
        price_val = product.get('price') or product.get('best_price') or product.get('original_price') or 'N/A'
        product['stores'] = [{
            'store': store_name,
            'price': price_val,
            'image': product.get('image')
        }]
    
    # Enrich product stores with real store images/logos from the stores collection
    stores_list = product.get('stores') or []
    db_stores = stores_model.list_stores()
    
    def find_store_logo_and_image(store_name, db_stores):
        norm = lambda n: (n or '').strip().lower()
        for s in db_stores:
            if norm(s.get('name')) == norm(store_name) or norm(s.get('store')) == norm(store_name):
                return s.get('logo'), s.get('image') or s.get('store_image')
        return None, None
    for s in stores_list:
        store_name = s.get('store') or s.get('store_name') or s.get('name')
        logo, image = find_store_logo_and_image(store_name, db_stores)
        if logo:
            s['logo'] = logo
        if image:
            # Don't overwrite product image with store image
            s['store_display_image'] = image

    # Always calculate the best price and its store(s)
    best_price_value = None
    best_price_stores = []
    try:
        min_price = float('inf')
        for s in stores_list:
            try:
                price = s.get('price')
                price_val = float(str(price).replace('€','').replace('$','').replace(',','.')) if price is not None else float('inf')
                if price_val < min_price:
                    min_price = price_val
                    best_price_stores = [s.get('store') or s.get('store_name') or s.get('name') or 'Store']
                elif price_val == min_price:
                    best_price_stores.append(s.get('store') or s.get('store_name') or s.get('name') or 'Store')
            except Exception:
                continue
        if min_price != float('inf'):
            best_price_value = f"{min_price:.2f}"
    except Exception:
        best_price_value = None
        best_price_stores = []

    # Do NOT filter stores by requested_store for detail page; always show all stores
    # Check if favorited
    is_favorited = False
    user_email = session.get('user')
    if user_email:
        try:
            from models.favorites_model import is_favorited as check_fav
            is_favorited = check_fav(user_email, str(product.get('id') or product.get('_id', '')))
        except Exception as e:
            print(f"Error checking favorites for product_detail: {e}")

    return render_template('product_detail.html', product=product, best_price_value=best_price_value, best_price_stores=best_price_stores, is_favorited=is_favorited)


@main_bp.route('/featured-deal/<deal_id>')
def featured_deal_detail(deal_id):
    """Display a single featured deal with store link."""
    deal = None

    try:
        # Try to find in featured_deals first using Model
        deal = featured_deals_model.get_deal_by_id(deal_id)
        
        # If not found, search in multibuy_offers using Model
        if not deal:
            deal = multibuy_offers_model.get_offer_by_id(deal_id)
            
        # If still not found, search in quantity_discounts using Model
        if not deal:
            deal = quantity_discounts_model.get_discount_by_id(deal_id)
            
        if deal:
            # ------------------------------------------------------------------
            # NORMALIZE DEAL OBJECT 
            # Ensure consistent fields (title, price, image) for the template
            # regardless of whether it came from featured_deals, multibuy, or quantity_discounts
            # ------------------------------------------------------------------
            
            # 1. Normalize Title/Name
            if not deal.get('title'):
                deal['title'] = deal.get('product_name') or deal.get('name') or "Special Offer"
            
            # 2. Normalize Price
            if deal.get('price') is None:
                deal['price'] = deal.get('base_price') or deal.get('new_price')
            
            # 3. Normalize Original Price (if applicable)
            if deal.get('original_price') is None:
                deal['original_price'] = deal.get('old_price')

            # 4. Normalize Image (Ensure it exists)
            # If image missing, try to fetch from linked product
            if not deal.get('image') and deal.get('product_id'):
                try:
                    p = products_model.get_product_by_id(str(deal['product_id']))
                    if p:
                        deal['image'] = p.get('image') or p.get('image_url')
                        # Also backfill other missing info from product if needed
                        if not deal.get('category'): deal['category'] = p.get('category')
                        if not deal.get('unit'): deal['unit'] = p.get('unit')
                except:
                    pass

            # 5. Construct Offer Label for Quantity Discounts if missing
            if not deal.get('offer') and not deal.get('discount_label'):
                if deal.get('discount_tiers'): # Quantity Discount
                    tiers = deal.get('discount_tiers')
                    if tiers and len(tiers) > 0:
                        first = tiers[0]
                        qty = first.get('quantity') or first.get('min_qty')
                        disc = first.get('discount') or first.get('discount_percentage') or first.get('discount_percent')
                        if qty and disc:
                            deal['offer'] = f"Buy {qty}+ Save {disc}%"
                            deal['discount_label'] = f"Save {disc}%"
                elif deal.get('buy_quantity') and deal.get('free_quantity'): # Multibuy
                     deal['discount_label'] = f"{deal['buy_quantity']}+{deal['free_quantity']}"
                     deal['offer'] = f"Buy {deal['buy_quantity']} Get {deal['free_quantity']} Free"

            # If deal is linked to a product but missing URL, try to fetch it from the product
            if (not deal.get('url') and not deal.get('link') and not deal.get('product_url') and not deal.get('store_url')):
                 product_id = deal.get('product_id')
                 if product_id:
                     try:
                         prod = products_model.get_product_by_id(str(product_id))
                         if prod:
                             # Try to find URL for the specific store
                             deal_store = deal.get('store') or deal.get('source')
                             found_url = None
                             
                             if deal_store and prod.get('stores'):
                                 for s in prod.get('stores', []):
                                     s_name = s.get('store') or s.get('name')
                                     if s_name and deal_store.lower() in s_name.lower():
                                         found_url = s.get('url') or s.get('link') or s.get('product_url')
                                         break
                             
                             # If not found for specific store, use any available URL
                             if not found_url and prod.get('stores'):
                                 first_store = prod.get('stores')[0]
                                 found_url = first_store.get('url') or first_store.get('link') or first_store.get('product_url')
                             
                             if found_url:
                                 deal['url'] = found_url
                     except Exception as e:
                         print(f"Error fetching product url for deal: {e}")

            # Attach any active multibuy/quantity offers using Model-based helper
            multibuy_offers_model.attach_offers_to_products([deal])
            
            # Check if favorited using Model
            is_favorited = False
            user_email = session.get('user')
            if user_email:
                try:
                    product_id = str(deal.get('_id') or deal.get('id'))
                    is_favorited = favorites_model.is_favorited(user_email, product_id)
                except Exception as e:
                    print(f"Error checking favorites for featured_deal_detail: {e}")
    except Exception as e:
        print(f'ERROR loading featured deal {deal_id}: {e}')

    if deal is None:
        all_deals = load_featured_deals_fallback()
        for d in all_deals:
            if str(d.get('id')) == str(deal_id) or str(d.get('_id', '')) == str(deal_id):
                deal = d
                break
        
        # Check favorite status for fallback data
        if deal:
            user_email = session.get('user')
            if user_email:
                try:
                    product_id = str(deal.get('_id') or deal.get('id'))
                    is_favorited = favorites_model.is_favorited(user_email, product_id) 
                except:
                    pass

    if deal is None:
        return render_template('404.html'), 404

    return render_template('featured_deal_detail.html', deal=deal, is_favorited=is_favorited)


@main_bp.route('/product-info/<product_id>')
def product_info(product_id):
    """Simple product info page showing just description and unit"""
    product = None
    
    # Get store-specific information from query parameters
    store_name = request.args.get('store_name', '')
    store_price = request.args.get('store_price', '')
    
    # Check database for product using Model
    try:
        product = products_model.get_product_by_id(product_id)
        
        # If not found, try featured_deals collection using Model
        if not product:
            product = featured_deals_model.get_deal_by_id(product_id)

        # If still not found, try multibuy_offers collection using Model
        if not product:
            product = multibuy_offers_model.get_offer_by_id(product_id)

        # If still not found, try quantity_discounts collection using Model
        if not product:
            try:
                product = quantity_discounts_model.get_discount_by_id(product_id)
            except Exception:
                pass
        
        # If found in specialized collections (multibuy/discount) but missing details, 
        # try to fetch parent product to fill in gaps (name, image, etc.)
        if product and (not product.get('name') or not product.get('image')):
            parent_id = product.get('product_id') or product.get('product_parent_id')
            if parent_id:
                try:
                    # Handle ObjectId if necessary
                    if not isinstance(parent_id, str):
                        parent_id = str(parent_id)
                        
                    parent_product = products_model.get_product_by_id(parent_id)
                    if parent_product:
                        # Merge parent data into the discount object
                        # We keep the discount object's id so the favorite context matches
                        for k, v in parent_product.items():
                            if k == 'id' or k == '_id':
                                continue # Don't overwrite the discount's ID
                            if k not in product or not product[k]:
                                 product[k] = v
                except Exception as e:
                    print(f"Error fetching parent product {parent_id} for {product_id}: {e}")

    except Exception as e:
        print(f'Error fetching product using Models for product-info: {e}')
    
    # Fallback to in-memory data and JSON deals
    if not product:
        try:
            for p in getattr(m, 'products', []):
                pid = str(p.get('id') or p.get('_id', ''))
                if pid and str(product_id) == pid:
                    product = p
                    break
        except Exception:
            pass
    if not product:
        try:
            for d in load_featured_deals_fallback():
                did = str(d.get('id') or d.get('_id', ''))
                if did and str(product_id) == did:
                    product = d
                    break
        except Exception:
            pass

    if not product:
        return render_template('404.html'), 404
    
    # Check if favorited using Model
    is_favorited = False
    user_email = session.get('user')
    if user_email:
        try:
            is_favorited = favorites_model.is_favorited(user_email, str(product.get('id')))
        except Exception as e:
            print(f"Error checking favorites for product_info: {e}")
    
    return render_template('product_info.html', product=product, store_name=store_name, store_price=store_price, is_favorited=is_favorited)

@main_bp.route('/shopping-list')
def shopping_list():
    user_email = session.get('user')

    # Auto-enrich existing items with missing images using models
    if user_email:
        try:
            from models.users_model import get_user_lists, update_user
            lists_data = get_user_lists(user_email) or {'lists': [], 'active_list_id': None}
            all_user_lists = lists_data.get('lists', [])
            needs_update = False

            for lst in all_user_lists:
                list_items = lst.get('items', [])
                for item in list_items:
                    if isinstance(item, dict) and not item.get('image'):
                        # Item is missing image, try to enrich it using models
                        item_name = item.get('name')
                        if item_name:
                            try:
                                prod = products_model.get_product_by_name(item_name)
                            except Exception:
                                prod = None

                            if prod:
                                if prod.get('image'):
                                    item['image'] = prod.get('image')
                                    needs_update = True
                                elif prod.get('images') and isinstance(prod.get('images'), list) and len(prod.get('images')) > 0:
                                    item['image'] = prod.get('images')[0]
                                    needs_update = True

            if needs_update:
                try:
                    update_user(user_email, {'shopping_lists': all_user_lists})
                except Exception as e:
                    print(f'Error updating lists with images: {e}')
        except Exception as e:
            print(f'Error enriching images: {e}')

    # Mark shopping list as viewed - store current count in session
    if user_email:
        from models.users_model import get_user_lists
        data = get_user_lists(user_email) or {}
        lists = data.get('lists', []) or []
        total = 0
        for lst in lists:
            items = lst.get('items', []) or []
            total += sum(1 for it in items if not (isinstance(it, dict) and it.get('purchased')))
        session['last_viewed_list_count'] = total
        session.modified = True

    # Get user data using model
    user_data = {}
    if user_email:
        try:
            from models.users_model import get_user_by_email
            user_data = get_user_by_email(user_email) or {}
        except Exception:
            user_data = getattr(m, 'users', {}).get('user1@example.com', {})
    else:
        user_data = getattr(m, 'users', {}).get('user1@example.com', {})

    # Get all lists for this user using new multi-list structure
    # Get all lists for this user using new multi-list structure
    try:
        from models.users_model import get_user_lists
        lists_data = get_user_lists(user_email) if user_email else {'lists': [], 'active_list_id': None}
        all_lists = lists_data.get('lists', [])

        # If no lists exist, create a default one
        if not all_lists and user_email:
            from models.users_model import create_shopping_list, set_active_list
            new_id = create_shopping_list(user_email, 'My List')
            if new_id:
                set_active_list(user_email, new_id)
                lists_data = get_user_lists(user_email)
                all_lists = lists_data.get('lists', [])

        # Now enrich all lists (including the potentially newly created one)
        # First, mark items in active list as seen
        requested_list_id = request.args.get('list_id') or lists_data.get('active_list_id')
        if user_email and requested_list_id:
            from models.users_model import mark_items_as_seen
            mark_items_as_seen(user_email, requested_list_id)
            # Refresh lists to reflect cleared 'is_new' status
            lists_data = get_user_lists(user_email)
            all_lists = lists_data.get('lists', [])

        for lst in all_lists:
            if 'items' in lst:
                lst['list_items'] = lst.pop('items')
            
            # Enrich items with fresh offer data
            items = lst.get('list_items') or []
            # Make sure items are dicts before processing
            valid_items = [i for i in items if isinstance(i, dict)]
            if valid_items:
                 multibuy_offers_model.attach_offers_to_products(valid_items)
                 quantity_discounts_model.attach_discounts_to_products(valid_items)

            total = 0.0
            completed_count = 0
            for item in items:
                if isinstance(item, dict):
                    if item.get('purchased') or item.get('completed'):
                        completed_count += 1
                    price = item.get('price', 0)
                    qty = item.get('qty', 1)
                    if isinstance(price, str):
                        price = float(price.replace('$', '').replace('€', '').replace(',', '').strip() or 0)
                    elif isinstance(price, Decimal128):
                        try:
                            price = float(price.to_decimal())
                        except Exception:
                            price = 0.0
                    else:
                         try:
                             price = float(price)
                         except Exception:
                             price = 0.0

                    # Apply effective price calculation for multibuy
                    offer = item.get('offer')
                    effective_price = price * int(qty) # Default to normal price

                    if offer and isinstance(offer, dict) and offer.get('type') == 'buyXgetY':
                        try:
                            ox = int(offer.get('x') or 0)
                            oy = int(offer.get('y') or 0)
                            quantity = int(qty)
                            
                            if ox and oy:
                                cycle = ox + oy
                                full_cycles = quantity // cycle
                                remainder = quantity % cycle
                                
                                # Pay for 'ox' items in each full cycle
                                # Pay for remainder items (capped at 'ox')
                                payable_qty = (full_cycles * ox) + min(remainder, ox)
                                effective_price = payable_qty * price
                        except Exception:
                            pass
                    
                    total += effective_price
            lst['estimated_total'] = f'€{total:.2f}'
            lst['completed'] = [item for item in items if isinstance(item, dict) and (item.get('purchased') or item.get('completed'))]
        
        active_list_id = lists_data.get('active_list_id')

        # Get the active list
        active_list = None
        if all_lists:
            if active_list_id:
                active_list = next((lst for lst in all_lists if lst.get('id') == active_list_id), all_lists[0])
            else:
                active_list = all_lists[0]

        # Sanitize lists for template to avoid ObjectId issues
        all_lists = helpers.sanitize_mongo_doc(all_lists)
        if active_list:
            active_list = helpers.sanitize_mongo_doc(active_list)

        # Build items list with price/store information for the template
        shopping_entries = active_list.get('list_items', active_list.get('items', [])) if active_list else []

        # load products to try to find prices using model
        products = products_model.list_products()

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
        agg = {}
        for idx, entry in enumerate(shopping_entries):
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

            if isinstance(entry, dict):
                entry_price = entry.get('price') or entry.get('price_val')
                store_name = entry.get('store', '')
                if entry_price is not None:
                    try:
                        if isinstance(entry_price, (int, float)):
                            price_val = float(entry_price)
                        elif isinstance(entry_price, Decimal128):
                            try:
                                price_val = float(entry_price.to_decimal())
                            except Exception:
                                price_val = 0.0
                        else:
                            cleaned = re.sub(r"[^0-9.]", "", str(entry_price))
                            price_val = float(cleaned) if cleaned else 0.0
                    except Exception:
                        price_val = 0.0

            if (not price_val or price_val == 0) and product:
                cheapest = product.get('cheapest') or {}
                price_field = cheapest.get('price') if isinstance(cheapest, dict) else product.get('price')
                if price_field is None:
                    try:
                        stores_list = product.get('stores', [])
                        if stores_list and isinstance(stores_list, list):
                            price_field = stores_list[0].get('price')
                            if not store_name:
                                store_name = stores_list[0].get('store') or stores_list[0].get('name')
                    except Exception:
                        price_field = None
                if price_field is not None:
                    try:
                        if isinstance(price_field, (int, float)):
                            price_val = float(price_field)
                        elif isinstance(price_field, Decimal128):
                            try:
                                price_val = float(price_field.to_decimal())
                            except Exception:
                                price_val = 0.0
                        else:
                            cleaned = re.sub(r"[^0-9.]", "", str(price_field))
                            price_val = float(cleaned) if cleaned else 0.0
                    except Exception:
                        price_val = 0.0
                if not store_name:
                    try:
                        store_name = (product.get('cheapest') or {}).get('store', '')
                    except Exception:
                        store_name = ''

            store_from_entry = ''
            if isinstance(entry, dict):
                store_from_entry = entry.get('store', '')
            if not store_from_entry:
                store_from_entry = store_name

            if product and product.get('id'):
                item_key = f"{str(product.get('id'))}#{store_from_entry}"
            else:
                item_key = f"{(name or f'item-{idx}').strip().lower()}#{store_from_entry}"
            existing = agg.get(item_key)
            image_val = ''
            try:
                if isinstance(entry, dict):
                    image_val = entry.get('image')
                    if not image_val and entry.get('images'):
                        if isinstance(entry.get('images'), list) and len(entry.get('images')) > 0:
                            image_val = entry.get('images')[0]
                        elif isinstance(entry.get('images'), str):
                            image_val = entry.get('images')

                if not image_val and product:
                    image_val = product.get('image')
                    if not image_val and product.get('images'):
                        if isinstance(product.get('images'), list) and len(product.get('images')) > 0:
                            image_val = product.get('images')[0]
                        elif isinstance(product.get('images'), str):
                            image_val = product.get('images')
            except Exception:
                image_val = ''

            if existing:
                existing['qty'] += qty
                existing['purchased'] = existing['purchased'] or purchased
                if existing.get('price_val', 0) == 0 and price_val:
                    existing['price_val'] = price_val
                if not existing.get('image') and image_val:
                    existing['image'] = image_val
            else:
                agg[item_key] = {
                    'id': product.get('id') if product and product.get('id') else f'item-{idx}',
                    'name': name,
                    'price_val': price_val,
                    'store': store_from_entry or store_name,
                    'qty': qty,
                    'purchased': purchased,
                    'image': image_val or '',
                    'offer': entry.get('offer') if isinstance(entry, dict) else None,
                    'discount_tiers': entry.get('discount_tiers') if isinstance(entry, dict) else None
                }

        for k, v in agg.items():
            unit = float(v.get('price_val') or 0.0)
            qty = int(v.get('qty') or 1)
            total = unit * qty

            # Apply effective price calculation for multibuy
            offer = v.get('offer')
            if offer and isinstance(offer, dict) and offer.get('type') == 'buyXgetY':
                try:
                    ox = int(offer.get('x') or 0)
                    oy = int(offer.get('y') or 0)
                    
                    if ox > 0 and oy > 0:
                        cycle = ox + oy
                        full_cycles = qty // cycle
                        remainder = qty % cycle
                        
                        # Pay for 'ox' items in each full cycle
                        # Pay for remainder items (capped at 'ox')
                        payable_qty = (full_cycles * ox) + min(remainder, ox)
                        total = payable_qty * unit
                except Exception:
                    pass

            v['price'] = f"€{total:.2f}"
            items.append(v)
            
        print("DEBUG: Rendering template")

        return render_template('shopping_list.html',
                            user_data=user_data,
                            items=items,
                            all_lists=all_lists,
                            active_list=active_list)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e

@main_bp.route('/notifications')
def notifications_page():
    """Display all notifications for the logged-in user"""
    user_email = session.get('user')
    if not user_email:
        return redirect(url_for('auth.login'))
    
    from models.notifications_model import get_user_notifications, get_unread_count, notifications_model
    from datetime import datetime
    
    # Clean up old notifications (older than 7 days) whenever page is visited
    try:
        notifications_model.cleanup_old_notifications(7)
    except Exception as e:
        print(f"Error cleaning up notifications: {e}")
    
    # Get all notifications (Limit persistent history to 20 to keep view clean)
    # Filter out persistent 'deal_alert', 'new_deal', 'price_drop' notifications to avoid duplicates 
    # and strictly enforce the limit of 10 deals.
    persistent_notifications = get_user_notifications(user_email, unread_only=False, limit=50)
    ignored_types = ['deal_alert', 'new_deal', 'price_drop']
    
    # Filter for display
    notifications = [n for n in persistent_notifications if n.get('type') not in ignored_types]
    
    # Calculate initial unread count just from the notifications WE ARE SHOWING from DB
    current_unread_count = len([n for n in notifications if not n.get('read')])

    # ------------------------------------------------------------------
    # DYNAMIC NOTIFICATIONS INJECTION (Requested Feature)
    # Inject latest items from db using Model methods
    # ------------------------------------------------------------------
    try:
        # Helper to normalize dates for sorting
        def get_naive_date(d):
            if d is None: return datetime.min
            if d.tzinfo is not None:
                return d.replace(tzinfo=None)
            return d

        # 1. Price Drops / New Deals: 10 Latest Featured Deals
        # Switched back to 'featured_deals' as user confirmed real data is present.
        latest_deals_drop = featured_deals_model.get_latest_deals(limit=10)
        
        for d in latest_deals_drop:
            d_id = str(d.get('id') or d.get('_id'))
            
            # Construct sensible offer text
            offer_text = d.get('discount_label') or d.get('offer') or d.get('offer_text')
            if not offer_text and d.get('discount_percent'):
                offer_text = f"{d.get('discount_percent')}% OFF"
            
            n = {
                'id': f"suggestion_fd_{d_id}",
                # CHANGED to 'price_drop' as requested to appear in Price Drops section
                'type': 'price_drop', 
                'title': f"Price Drop: {d.get('title') or d.get('product_name') or d.get('name')}",
                'message': d.get('description') or "Check out this amazing offer available now!",
                'created_at': get_naive_date(d.get('_id').generation_time),
                # CHANGED to unread (read=False) as requested
                'read': False,
                'deal_id': d_id,
                'product_name': d.get('title') or d.get('product_name') or d.get('name'),
                'product_image': d.get('image') or d.get('image_url'),
                'store_name': d.get('store'),
                'price': d.get('price') or d.get('new_price'),
                'old_price': d.get('original_price') or d.get('old_price'),
                'offer_name': offer_text,
                'action_url': '#' 
            }
            notifications.append(n)
            current_unread_count += 1

        # 2. Deals: 5 Latest Multibuy Offers (as requested)
        latest_multibuy = multibuy_offers_model.get_latest_offers(limit=5)
    
        for m_offer in latest_multibuy:
            m_id = str(m_offer.get('id') or m_offer.get('_id'))
            
            # Construct sensible offer name "Buy X Get Y"
            offer_text = m_offer.get('title')
            # If title is generic or just product name, construct from quantities
            if offer_text == "Special Offer" or not offer_text or m_offer.get('buy_quantity'):
                buy = m_offer.get('buy_quantity') or m_offer.get('min_quantity')
                get = m_offer.get('free_quantity')
                if buy and get:
                    offer_text = f"Buy {buy} Get {get} Free"
                elif buy:
                    offer_text = f"Buy {buy}+ Deal"
            
            n = {
                'id': f"suggestion_multi_{m_id}",
                # CHANGED to 'deal_alert' so it shows in Deals section
                'type': 'deal_alert',
                'title': f"Multibuy Offer",
                'message': "Buy more, save more with this special offer!",
                'created_at': get_naive_date(m_offer.get('_id').generation_time),
                # CHANGED to unread
                'read': False,
                'deal_id': m_id,
                'product_name': m_offer.get('title') or m_offer.get('product_name'),
                'product_image': m_offer.get('image'),
                'store_name': m_offer.get('store'),
                'price': m_offer.get('price'),
                'old_price': m_offer.get('original_price'),
                'offer_name': offer_text,
                'action_url': '#'
            }
            notifications.append(n)
            current_unread_count += 1

        # 3. Deals: 3 Latest Quantity Discounts (as requested)
        latest_qty = quantity_discounts_model.get_latest_discounts(limit=3)
        
        for q_disc in latest_qty:
            q_id = str(q_disc.get('id') or q_disc.get('_id'))
            
            # Construct offer text "Buy 3+ save 15%"
            offer_text = "Bulk Savings"
            tiers = q_disc.get('tiers') or q_disc.get('discount_tiers') or []
            if tiers and len(tiers) > 0:
                first = tiers[0]
                qty = first.get('quantity') or first.get('min_qty')
                disc = first.get('discount') or first.get('discount_percentage') or first.get('discount_percent')
                if qty and disc:
                    offer_text = f"Buy {qty}+ Save {disc}%"

            n = {
                'id': f"suggestion_qty_{q_id}",
                # CHANGED to 'deal_alert' so it shows in Deals section
                'type': 'deal_alert',
                'title': "Quantity Discount",
                'message': "Stock up and save with volume discounts!",
                'created_at': get_naive_date(q_disc.get('_id').generation_time),
                # CHANGED to unread
                'read': False,
                'deal_id': q_id,
                'product_name': q_disc.get('product_name'),
                'product_image': q_disc.get('image'),
                'store_name': q_disc.get('store'),
                'price': q_disc.get('base_price') or q_disc.get('price'),
                'offer_name': offer_text,
                'action_url': '#'
            }
            notifications.append(n)
            current_unread_count += 1

        # Sort combined list by date descending (Newest first)
        notifications.sort(key=lambda x: get_naive_date(x.get('created_at')), reverse=True)

    except Exception as e:
        print(f"Error injecting dynamic notifications: {e}")
        # Continue even if injections fail

    # ------------------------------------------------------------------
    # Apply Read Status from User Profile (Persistence for Dynamic Items)
    # ------------------------------------------------------------------
    try:
        from models.users_model import get_user_by_email
        user = get_user_by_email(user_email)
        read_dynamic_ids = set(user.get('read_dynamic_notifications', [])) if user else set()
        
        # Update read status for dynamic items
        for n in notifications:
            if n['id'].startswith('suggestion_') and n['id'] in read_dynamic_ids:
                n['read'] = True
    except Exception as e:
        print(f"Error applying read status persistence: {e}")

    # Use our calculated consistent unread count instead of DB global count
    # Re-calculate based on updated read statuses
    current_unread_count = len([n for n in notifications if not n.get('read')])
    unread_count = current_unread_count
    
    return render_template(
        'notifications.html',
        notifications=notifications,
        unread_count=unread_count
    )


@main_bp.route('/api/notifications/<notification_id>', methods=['DELETE'])
def delete_notification(notification_id):
    """Delete a specific notification"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'error': 'Not logged in'}), 401
        
        # Handle ephemeral/suggestion notifications
        if notification_id.startswith('suggestion_'):
            return jsonify({'success': True})
        
        from models.notifications_model import delete_notification as delete_notif
        
        success = delete_notif(notification_id, user_email)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to delete notification'}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    user_email = helpers.get_user_email()
    
    if request.method == 'POST' and user_email:
        name = request.form.get('name')
        phone = request.form.get('phone_number', '')
        address = request.form.get('address')
        avatar = request.form.get('avatar')
        
        print(f"DEBUG PROFILE UPDATE: User={user_email}, Avatar={avatar}")

        update_data = {
            'name': name,
            'phone': phone,
            'address': address
        }
        if avatar:
            update_data['avatar'] = avatar
            
        from models.users_model import update_user_profile
        update_user_profile(user_email, update_data)
        
        # Add system notification for profile update using Model
        try:
            notifications_model.create_system_notification(
                user_email, 
                "Profile Updated", 
                "Your profile details have been successfully updated.",
                priority="normal"
            )
        except:
            pass
        
        return redirect(url_for('main.profile'))

    user_data = {}
    stores_list = []

    if user_email:
        try:
            from models.users_model import get_user_by_email
            user = get_user_by_email(user_email)
            if user:
                user_data = user
            else:
                user_data = getattr(m, 'users', {}).get(user_email, {})

            # Load favorites using Model
            from models import favorites_model
            favorites = favorites_model.get_user_favorites(user_email)
            
            # Normalize favorites data
            for fav in favorites:
                if isinstance(fav, dict):
                    if not fav.get('id') and fav.get('product_id'):
                        fav['id'] = str(fav['product_id'])
                    if not fav.get('name') and fav.get('product_name'):
                        fav['name'] = fav.get('product_name')
                    if not fav.get('image') and fav.get('product_image'):
                        fav['image'] = fav.get('product_image')
            
            user_data['favorites'] = favorites
            
            if 'recent_views' not in user_data:
                user_data['recent_views'] = []

            # Load stores list using Model
            all_stores = stores_model.list_stores()
            seen_names = set()
            for s in all_stores:
                name = s.get('name')
                if name and name not in seen_names:
                    seen_names.add(name)
                    stores_list.append({
                        'name': name,
                        'id': s.get('id'),
                        'image': s.get('image') or s.get('logo'),
                        # Simplified count for profile view using Model
                        'count': products_model.count_by_store(name)
                    })
            stores_list.sort(key=lambda x: x['name'])
            
            # Load specific standard category options
            category_options = STANDARD_CATEGORIES
            
        except Exception as e:
            print(f"Error in profile route: {e}")
            user_data = getattr(m, 'users', {}).get(user_email, {})
            stores_list = []
            category_options = []

    return render_template('profile.html', user_data=user_data, stores=stores_list, category_options=category_options)


@main_bp.route('/update-stores', methods=['POST'])
def update_stores():
    """Handle preferred stores update from profile page"""
    user_email = helpers.get_user_email()
    if not user_email:
        return redirect(url_for('auth.login'))
        
    selected_stores = request.form.getlist('stores')
    from models.users_model import update_user
    update_user(user_email, {'preferred_stores': selected_stores})
    
    # Add system notification
    try:
        notifications_model.create_system_notification(
            user_email, 
            "Preferences Updated", 
            f"You have updated your preferred stores to: {', '.join(selected_stores) if selected_stores else 'None'}",
            priority="normal"
        )
    except:
        pass
        
    return redirect(url_for('main.profile'))


@main_bp.route('/update-categories', methods=['POST'])
def update_categories():
    """Handle preferred categories update from profile page"""
    user_email = helpers.get_user_email()
    if not user_email:
        return redirect(url_for('auth.login'))
        
    selected_categories = request.form.getlist('categories')
    from models.users_model import update_user
    update_user(user_email, {'preferred_categories': selected_categories})
    
    # Add system notification
    try:
        notifications_model.create_system_notification(
            user_email, 
            "Preferences Updated", 
            f"You have updated your preferred categories to include {len(selected_categories)} items.",
            priority="normal"
        )
    except:
        pass
        
    return redirect(url_for('main.profile'))


@main_bp.route('/admin/status')
def admin_status():
    """Return JSON with collection counts so you can verify DB connectivity."""
    try:
        from models.models import get_db_info
        info = get_db_info()
        return jsonify({'db': info.get('collections', {})})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/search-products')
def api_search_products():
    """Search products by query string `q` (case-insensitive substring match on name).
    Returns JSON list of product docs (id, name, price, stores, cheapest, image).
    """
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'items': []})

    results = []
    try:
        if m.HAS_DB:
            # Use model for search
            products = products_model.search_by_name(q, limit=50)
            
            # Also search quantity_discounts
            try:
                qd_list = quantity_discounts_model.list_active_discounts()
                for d in qd_list:
                    name = d.get('name') or d.get('product_name') or ''
                    if q.lower() in name.lower():
                         products.append(d)
            except Exception as e:
                print(f"Error searching quantity discounts: {e}")

            for d in products:
                # only include products that look like valid, usable product docs
                def _has_price(prod):
                    if prod is None: return False
                    if prod.get('price') not in (None, ''):
                        return True
                    c = prod.get('cheapest') or {}
                    if isinstance(c, dict) and c.get('price') not in (None, ''):
                        return True
                    stores_list = prod.get('stores') or []
                    try:
                        if isinstance(stores_list, list) and len(stores_list) and stores_list[0].get('price') not in (None, ''):
                            return True
                    except Exception:
                        pass
                    return False

                if not _has_price(d):
                    # skip legacy/broken entries that don't have usable price info
                    continue
                results.append(helpers.sanitize_mongo_doc(d))
        else:
            # fallback to in-memory search (log this so it's visible)
            print('WARNING: api_search_products used fallback in-memory products (DB unavailable)')
            for p in getattr(m, 'products', []):
                name = p.get('name', '')
                if q.lower() in str(name).lower():
                    # filter out in-memory legacy items without price
                    if p.get('price') not in (None, '') or (p.get('cheapest') and p['cheapest'].get('price')) or (p.get('stores') and len(p.get('stores')) and p.get('stores')[0].get('price')):
                        results.append(helpers.sanitize_mongo_doc(p))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'items': results})


@main_bp.route('/api/product')
def api_get_product():
    """Return a single product by id or name. Query params: ?id=<id> or ?name=<name>
    Response: { item: <product-doc> }
    """
    pid = request.args.get('id') or request.args.get('product_id')
    name = request.args.get('name') or request.args.get('title') or request.args.get('q')
    if not pid and not name:
        return jsonify({'item': None}), 400
    try:
        if m.HAS_DB:
            doc = None
            if pid:
                doc = products_model.get_product_by_id(str(pid))
            else:
                doc = products_model.get_product_by_name(str(name))
            
            if not doc:
                return jsonify({'item': None}), 404
            return jsonify({'item': helpers.sanitize_mongo_doc(doc)})
        else:
            # fallback: search in-memory products
            for p in getattr(m, 'products', []):
                if pid and (str(p.get('id')) == str(pid) or str(p.get('_id', '')) == str(pid)):
                    return jsonify({'item': p})
                if name and name.lower() in str(p.get('name', '')).lower():
                    return jsonify({'item': p})
            return jsonify({'item': None}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/categories')
def api_get_categories():
    """Return specific standard categories provided by user."""
    try:
        return jsonify({'categories': STANDARD_CATEGORIES}), 200
    except Exception as e:
        print(f'ERROR in api_get_categories: {e}')
        return jsonify({'categories': [], 'error': str(e)}), 500


@main_bp.route('/api/stores')
def api_get_stores():
    """Return a list of available stores (id, name, location).
    Uses MongoDB when available, otherwise falls back to in-memory `models.stores`.
    """
    try:
        out = []
        def shape_store(s):
            # prefer richer metadata so the UI can render cards from search results
            image = s.get('image') or (s.get('images')[0] if isinstance(s.get('images'), list) and s.get('images') else None)
            hours = s.get('hours') or s.get('opening_hours')
            deals_val = s.get('active_deals') or s.get('deals')
            if isinstance(deals_val, list):
                deals_count = len(deals_val)
            else:
                deals_count = deals_val
            location = s.get('location') or ', '.join(filter(None, [s.get('address'), s.get('city')]))
            return {
                'id': s.get('id') or s.get('_id'),
                'name': s.get('name'),
                'location': location,
                'image': image,
                'url': s.get('url') or s.get('website'),
                'hours': hours,
                'distance': s.get('distance'),
                'deals': deals_count
            }
        if m.HAS_DB:
            stores = stores_model.list_stores()[:500]
            for s in stores:
                out.append(shape_store(helpers.sanitize_mongo_doc(s)))
        else:
            for s in getattr(m, 'stores', []):
                out.append(shape_store(helpers.sanitize_mongo_doc(s)))
        return jsonify({'stores': out})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/store/<store_name>/products')
def api_get_store_products(store_name):
    """Return products for a given store name (no featured deals).

    Searches `products` for any entry where the `stores` array (or top-level `store`) matches
    the provided name case-insensitively. Only the matching store entries are returned in
    `matched_stores` so the UI can display per-store prices/images cleanly.
    """
    if not store_name:
        return jsonify({'error': 'missing_store'}), 400

    store_query = store_name.strip()
    if not store_query:
        return jsonify({'error': 'missing_store'}), 400

    store_lc = store_query.lower()

    def _normalize(doc):
        if not isinstance(doc, dict):
            return {}
        shaped = dict(doc)
        if '_id' in shaped:
            shaped['id'] = str(shaped['_id'])
            shaped.pop('_id', None)
        return shaped

    def _match_store_entry(entry):
        try:
            val = (entry.get('store') or entry.get('name') or '').strip()
        except Exception:
            val = ''
        return val and val.lower() == store_lc

    def _shape_product(prod):
        shaped = _normalize(prod)
        matched_stores = [s for s in (shaped.get('stores') or []) if _match_store_entry(s)]
        # Some legacy docs may store a single store field at top-level
        if not matched_stores and isinstance(shaped.get('store'), str) and shaped.get('store', '').lower() == store_lc:
            matched_stores.append({'store': shaped.get('store'), 'price': shaped.get('price'), 'image': shaped.get('image')})
        shaped['matched_stores'] = matched_stores
        # Prefer price from matching store entry, otherwise use cheapest/price
        price_val = None
        if matched_stores:
            price_val = matched_stores[0].get('price')
        if price_val in (None, ''):
            price_val = (shaped.get('cheapest') or {}).get('price') or shaped.get('price')
        # normalize Decimal128 or other to string/float-ish
        try:
            from bson.decimal128 import Decimal128
            if isinstance(price_val, Decimal128):
                price_val = float(price_val.to_decimal())
        except Exception:
            pass
        shaped['price'] = price_val
        shaped['source'] = 'product'
        return shaped

    def _shape_deal(deal):
        shaped = _normalize(deal)
        shaped['source'] = 'featured_deal'
        return shaped

    products = []
    try:
        # Using model to find products by store
        products = [_shape_product(p) for p in products_model.find_by_store(store_query)]
        
        # if Model returns nothing, allow fallback to in-memory products as a safety net
        if not products:
            products = [_shape_product(p) for p in getattr(m, 'products', []) if any(_match_store_entry(s) for s in (p.get('stores') or [])) or (isinstance(p.get('store'), str) and p.get('store', '').lower() == store_lc)]
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'store': store_query,
        'products': products,
        'count': len(products)
    })


@main_bp.route('/api/claim-deal', methods=['POST'])
def api_claim_deal():
    """Endpoint to claim a featured deal and add it to the user's shopping list.
    Expects JSON { deal_id: '<id>' } or { title: '<title>' }. Returns JSON { success: bool }.
    """
    data = request.get_json() or {}
    deal_id = data.get('deal_id') or data.get('id') or data.get('title')
    if not deal_id:
        return jsonify({'error': 'no_deal_id_provided'}), 400

    # Get user email
    email = helpers.get_user_email()

    try:
        # attempt to find deal document using models
        deal_doc = None
        if m.HAS_DB:
            # Search in featured_deals first
            deal_doc = featured_deals_model.get_deal_by_id(str(deal_id))
            
            # If not found in featured_deals, search in multibuy_offers
            if not deal_doc:
                deal_doc = multibuy_offers_model.get_offer_by_id(str(deal_id))
        else:
            # fallback to in-memory list
            for d in getattr(m, 'featured_deals', []):
                if str(d.get('title')) == str(deal_id) or str(d.get('id')) == str(deal_id):
                    deal_doc = d
                    break

        # mark claimed
        claimed = False
        if deal_doc:
            claimed = m.claim_featured_deal_by_id(deal_id, email=email)
        else:
            # still try to increment using helper (it will fail gracefully)
            claimed = m.claim_featured_deal_by_id(deal_id, email=email)

        # add to user's shopping list(s) if we have an email
        added = False
        active_added = False
        if email:
            # Prefer the multi-list structure: add to active list (create one if missing)
            try:
                from models.users_model import (
                    get_user_lists,
                    add_item_to_list,
                    create_shopping_list,
                    set_active_list,
                )

                # derive price/qty and offer (buy X get Y)
                raw_price = data.get('price') or (deal_doc or {}).get('price')
                raw_original = data.get('original_price') or (deal_doc or {}).get('original_price')
                raw_offer = data.get('offer') or (deal_doc or {}).get('offer') or ''
                raw_image = data.get('image') or (deal_doc or {}).get('image') or ((deal_doc or {}).get('images') or [None])[0]
                qty = int(data.get('qty') or 1)
                price_val = data.get('price_val') or raw_original or raw_price

                def _to_float(val):
                    try:
                        return float(str(val).replace('€', '').replace('$', '').replace(',', '').strip()) if val is not None else 0.0
                    except Exception:
                        return 0.0

                def _parse_offer(val):
                    # prefer object form {type:'buyXgetY', x, y}
                    if isinstance(val, dict) and val.get('type'):
                        return {
                            'type': val.get('type'),
                            'x': val.get('x'),
                            'y': val.get('y'),
                        }
                    if isinstance(val, str):
                        m = re.match(r"(\d+)\s*\+\s*(\d+)", val)
                        if m:
                            return {'type': 'buyXgetY', 'x': int(m.group(1)), 'y': int(m.group(2))}
                    return None

                offer_obj = _parse_offer(raw_offer)
                # fallback: if old multibuy fields exist, translate them
                if not offer_obj:
                    # Check for buy_quantity/free_quantity (from multibuy_offers collection)
                    mb_buy = (deal_doc or {}).get('buy_quantity') or (deal_doc or {}).get('multibuy_buy') or data.get('multibuy_buy')
                    mb_free = (deal_doc or {}).get('free_quantity') or (deal_doc or {}).get('multibuy_free') or data.get('multibuy_free')
                    if mb_buy and mb_free:
                        offer_obj = {'type': 'buyXgetY', 'x': int(mb_buy), 'y': int(mb_free)}

                price_val_num = _to_float(price_val)
                discounted_price_num = _to_float(raw_price)  # shown price (may be effective deal price)
                original_price_num = _to_float(raw_original)  # normal price per unit

                # For multibuy offers: use original_price as the unit price to charge
                # For regular deals: use the shown price or original price
                if offer_obj and offer_obj.get('type') == 'buyXgetY':
                    # For multibuy: original_price IS the unit price (what they pay per item)
                    # The discount is applied by the offer (2+1 means pay for 2, get 1 free)
                    charge_price = original_price_num if original_price_num > 0 else discounted_price_num
                else:
                    # Regular discount: use discounted price or original
                    charge_price = discounted_price_num or original_price_num or price_val_num

                # single payload: always add qty=1 (one unit) with the offer metadata
                payload = {
                    'name': (deal_doc or {}).get('title') or (deal_doc or {}).get('name') or str(deal_id),
                    'price': charge_price,
                    'price_val': charge_price,
                    'store': (deal_doc or {}).get('store') or (deal_doc or {}).get('source', ''),
                    'image': raw_image,
                    'qty': 1,  # always add 1 unit at a time
                    'offer': offer_obj or raw_offer,  # store offer object when available
                }

                lists_data = get_user_lists(email) or {}
                active_list_id = lists_data.get('active_list_id')

                if not active_list_id:
                    new_id = create_shopping_list(email, 'My List')
                    if new_id:
                        set_active_list(email, new_id)
                        active_list_id = new_id

                if active_list_id:
                    active_added = add_item_to_list(email, active_list_id, payload)
            except Exception:
                active_added = False

            # Legacy single-list storage for backwards compatibility
            added = m.add_deal_to_user_shopping_list(email, deal_doc or str(deal_id))

        return jsonify({'success': bool(claimed or added or active_added), 'claimed': bool(claimed), 'added': bool(added or active_added)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/toggle-favorite', methods=['POST'])
def toggle_favorite():
    """Add or remove a product from user's favorites"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.get_json()
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({'error': 'Product ID required'}), 400
        
        from models import favorites_model
        
        # Check if product is already in favorites
        is_favorited = favorites_model.is_favorited(user_email, product_id)
        
        if is_favorited:
            # Remove from favorites
            success = favorites_model.remove_favorite(user_email, product_id)
            if success:
                return jsonify({'success': True, 'action': 'removed', 'is_favorite': False})
            else:
                return jsonify({'error': 'Failed to remove favorite'}), 500
        else:
            # Add to favorites
            # Get product details using models
            product = products_model.get_product_by_id(product_id)
            if not product:
                product = featured_deals_model.get_deal_by_id(product_id)
            if not product:
                product = multibuy_offers_model.get_offer_by_id(product_id)
            if not product:
                # Try quantity discounts
                try: 
                    product = quantity_discounts_model.get_discount_by_id(product_id)
                except Exception: pass
            
            if not product:
                print(f'ERROR: Product not found with id {product_id}')
                return jsonify({'error': 'Product not found'}), 404
            
            # Get store information if available
            store_name = product.get('store') or product.get('source', '')
            if not store_name and product.get('stores') and len(product.get('stores', [])) > 0:
                # Get the cheapest store
                stores = product.get('stores', [])
                cheapest_store = min(stores, key=lambda s: float(s.get('price', float('inf'))))
                store_name = cheapest_store.get('store') or cheapest_store.get('name', '')
            
            # Create favorite entry data
            product_data = {
                'name': product.get('name') or product.get('title', ''),
                'image': product.get('image', ''),
                'category': product.get('category', ''),
                'best_price': (product.get('cheapest') and product.get('cheapest').get('price')) or product.get('price', 'N/A'),
                'store': store_name,
                'discount_tiers': product.get('discount_tiers'),
                'offer': product.get('offer')
            }
            
            success = favorites_model.add_favorite(user_email, product_id, product_data)
            if success:
                return jsonify({'success': True, 'action': 'added', 'is_favorite': True})
            else:
                return jsonify({'error': 'Failed to add favorite'}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/check-favorite', methods=['GET'])
@main_bp.route('/api/check-favorite/<product_id>', methods=['GET'])
def check_favorite(product_id=None):
    """Check if a product is in user's favorites"""
    try:
        # Support both URL parameter and query parameter
        if not product_id:
            product_id = request.args.get('product_id')
        
        if not product_id:
            return jsonify({'error': 'Product ID required'}), 400
        
        user_email = session.get('user')
        if not user_email:
            return jsonify({'is_favorite': False})
        
        from models import favorites_model
        is_favorited = favorites_model.is_favorited(user_email, product_id)
        
        return jsonify({'is_favorite': is_favorited})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/notifications/unshown', methods=['GET'])
def get_unshown_notifications():
    """Get notifications that haven't been shown as toasts yet"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'notifications': []})
        
        from models.notifications_model import get_user_notifications
        
        # Get unread notifications (we'll mark them as shown after displaying)
        all_notifications = get_user_notifications(user_email, unread_only=True, limit=10)
        
        # Filter to only new_deal type for Featured Deals page
        new_deal_notifications = [n for n in all_notifications if n.get('type') == 'new_deal']
        
        return jsonify({'notifications': new_deal_notifications})
    
    except Exception as e:
        print(f'ERROR fetching unshown notifications: {e}')
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/notifications/mark-read', methods=['POST'])
def mark_notifications_read():
    """Mark notifications as read"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.get_json()
        notification_ids = data.get('notification_ids', [])
        
        if not notification_ids or not isinstance(notification_ids, list):
            return jsonify({'error': 'Notification IDs required'}), 400
        
        from models.notifications_model import mark_as_read
        
        # Mark each notification as read
        success_count = 0
        ids_to_mark = []
        dynamic_ids = []
        
        # Filter out suggestion IDs (ephemeral)
        for nid in notification_ids:
            if str(nid).startswith('suggestion_'):
                dynamic_ids.append(str(nid))
            else:
                ids_to_mark.append(nid)

        # Handle Dynamic IDs: Persist to user profile
        if dynamic_ids:
            try:
                from models.users_model import users_model
                users_model.mark_dynamic_notifications_read(user_email, dynamic_ids)
                success_count += len(dynamic_ids)
            except Exception as e:
                print(f"Error saving dynamic read status: {e}")

        # Handle Persistent IDs: different model call
        if ids_to_mark:
            for nid in ids_to_mark:
                if mark_as_read(nid, user_email):
                    success_count += 1
        
        return jsonify({'success': True, 'marked_count': success_count})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_read():
    """Mark all notifications for the user as read"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'error': 'Not logged in'}), 401
        
        from models.notifications_model import notifications_model
        
        # 1. Mark DB notifications
        notifications_model.mark_all_as_read(user_email)
        
        # 2. Mark dynamic notifications
        # Since we don't know exactly which ones are generated without re-querying,
        # we will fetch the current "latest" IDs again and mark them all.
        try:
            # Re-fetch just IDs to mark them
            dynamic_ids = []
            
            # Featured
            fds = featured_deals_model.get_latest_deals(limit=10)
            dynamic_ids.extend([f"suggestion_fd_{str(d.get('_id'))}" for d in fds])
            
            # Multibuy
            mbs = multibuy_offers_model.get_latest_offers(limit=5)
            dynamic_ids.extend([f"suggestion_multi_{str(m.get('_id'))}" for m in mbs])
            
            # Quantity
            qds = quantity_discounts_model.get_latest_discounts(limit=3)
            dynamic_ids.extend([f"suggestion_qty_{str(q.get('_id'))}" for q in qds])
            
            if dynamic_ids:
                from models.users_model import users_model
                users_model.mark_dynamic_notifications_read(user_email, dynamic_ids)
        except Exception as e:
            print(f"Error marking all dynamic as read: {e}")
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/notifications/clear-all', methods=['DELETE'])
def clear_all_notifications():
    """Delete all notifications for the user"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'error': 'Not logged in'}), 401
        
        from models.notifications_model import notifications_model
        
        success = notifications_model.delete_all_notifications(user_email)
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/save-preferences', methods=['POST'])
def save_preferences():
    """Save user preferences without overwriting existing ones"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.get_json() or {}
        
        update_doc = {}
        
        # Build update document based on provided keys
        if 'preferred_stores' in data:
            preferred_stores = [s for s in data.get('preferred_stores', []) if s]
            update_doc['preferred_stores'] = preferred_stores
            update_doc['preferences.preferred_stores'] = preferred_stores
            
        if 'preferred_categories' in data:
            preferred_categories = [c for c in data.get('preferred_categories', []) if c]
            update_doc['preferred_categories'] = preferred_categories
            update_doc['preferences.preferred_categories'] = preferred_categories
            
        if not update_doc:
            return jsonify({'success': True, 'message': 'No changes provided'})
            
        from models.users_model import update_user
        update_user(user_email, update_doc)
        
        return jsonify({'success': True, 'updated_fields': list(update_doc.keys())})
    
    except Exception as e:
        print(f"Error saving preferences: {e}")
        return jsonify({'error': str(e)}), 500
        return jsonify({'error': str(e)}), 500


# Shopping List API Endpoints
@main_bp.route('/api/list/create', methods=['POST'])
def create_shopping_list_api():
    """Create a new shopping list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        list_name = data.get('name', '').strip()
        
        if not list_name:
            return jsonify({'success': False, 'error': 'List name is required'}), 400
        
        from models.users_model import create_shopping_list, set_active_list
        new_list_id = create_shopping_list(user_email, list_name)
        
        if new_list_id:
            set_active_list(user_email, new_list_id)
            return jsonify({'success': True, 'list_id': new_list_id})
        else:
            return jsonify({'success': False, 'error': 'Failed to create list'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/rename', methods=['POST'])
def rename_shopping_list_api():
    """Rename a shopping list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        list_id = data.get('list_id')
        new_name = data.get('name', '').strip()
        
        if not list_id or not new_name:
            return jsonify({'success': False, 'error': 'List ID and name are required'}), 400
        
        from models.users_model import rename_shopping_list
        success = rename_shopping_list(user_email, list_id, new_name)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/delete', methods=['POST'])
def delete_shopping_list_api():
    """Delete a shopping list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        list_id = data.get('list_id')
        
        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400
        
        from models.users_model import delete_shopping_list
        success = delete_shopping_list(user_email, list_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/set-active', methods=['POST'])
def set_active_list_api():
    """Set the active shopping list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        list_id = data.get('list_id')
        
        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400
        
        from models.users_model import set_active_list
        success = set_active_list(user_email, list_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/duplicate', methods=['POST'])
def duplicate_shopping_list_api():
    """Duplicate a shopping list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        list_id = data.get('list_id')
        
        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400
        
        from models.users_model import get_user_lists, create_shopping_list, update_list_items
        lists_data = get_user_lists(user_email)
        source_list = next((lst for lst in lists_data['lists'] if lst['id'] == list_id), None)
        
        if not source_list:
            return jsonify({'success': False, 'error': 'List not found'}), 404
        
        new_name = f"{source_list['name']} (Copy)"
        new_list_id = create_shopping_list(user_email, new_name)
        
        if new_list_id:
            items = source_list.get('items', [])
            update_list_items(user_email, new_list_id, items)
            return jsonify({'success': True, 'list_id': new_list_id})
        else:
            return jsonify({'success': False, 'error': 'Failed to duplicate list'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/update-items', methods=['POST'])
def update_list_items_api():
    """Update items in the active shopping list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        items = data.get('items', [])
        
        from models.users_model import get_user_lists, update_list_items
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        
        if not active_list_id:
            return jsonify({'success': False, 'error': 'No active list'}), 400
        
        success = update_list_items(user_email, active_list_id, items)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/mark-seen/<list_id>', methods=['POST'])
def mark_list_seen(list_id):
    """Clear the 'is_new' flag for all items in the specified list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        from models.users_model import mark_items_as_seen
        success = mark_items_as_seen(user_email, list_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/remove-item', methods=['POST'])
def remove_item_from_list_api():
    """Remove an item from the active shopping list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        item_name = data.get('item_name')
        
        if not item_name:
            return jsonify({'success': False, 'error': 'Item name is required'}), 400
        
        from models.users_model import get_user_lists, remove_item_from_list
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        
        if not active_list_id:
            return jsonify({'success': False, 'error': 'No active list'}), 400
        
        success = remove_item_from_list(user_email, active_list_id, item_name)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/clear-completed', methods=['POST'])
def clear_completed_items_api():
    """Clear completed items from the active shopping list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        from models.users_model import get_user_lists, update_list_items
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        
        if not active_list_id:
            return jsonify({'success': False, 'error': 'No active list'}), 400
        
        active_list = next((lst for lst in lists_data['lists'] if lst['id'] == active_list_id), None)
        if not active_list:
            return jsonify({'success': False, 'error': 'List not found'}), 404
        
        items = active_list.get('items', [])
        remaining_items = [item for item in items if not (isinstance(item, dict) and item.get('purchased'))]
        success = update_list_items(user_email, active_list_id, remaining_items)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/clear-all', methods=['POST'])
def clear_all_items_api():
    """Clear all items from the active shopping list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        from models.users_model import get_user_lists, update_list_items
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        
        if not active_list_id:
            return jsonify({'success': False, 'error': 'No active list'}), 400
        
        success = update_list_items(user_email, active_list_id, [])
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/move-item', methods=['POST'])
def move_item_to_list_api():
    """Move an item from active list to another list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        item_name = data.get('item_name')
        target_list_id = data.get('target_list_id')
        
        if not item_name or not target_list_id:
            return jsonify({'success': False, 'error': 'Item name and target list are required'}), 400
        
        from models.users_model import get_user_lists, remove_item_from_list, add_item_to_list
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        
        if not active_list_id:
            return jsonify({'success': False, 'error': 'No active list'}), 400
        
        active_list = next((lst for lst in lists_data['lists'] if lst['id'] == active_list_id), None)
        if not active_list:
            return jsonify({'success': False, 'error': 'List not found'}), 404
        
        item_to_move = None
        for item in active_list.get('items', []):
            if isinstance(item, dict) and item.get('name') == item_name:
                item_to_move = item
                break
            elif isinstance(item, str) and item == item_name:
                item_to_move = item
                break
        
        if not item_to_move:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        success = add_item_to_list(user_email, target_list_id, item_to_move)
        if success:
            success = remove_item_from_list(user_email, active_list_id, item_name)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/add-item', methods=['POST'])
def add_item_to_active_list_api():
    """Add an item to a shopping list (supports specifying which list)"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        item = data.get('item')
        target_list_id = data.get('list_id')
        
        if not item:
            return jsonify({'success': False, 'error': 'Item is required'}), 400
        
        from models.users_model import get_user_lists, add_item_to_list
        lists_data = get_user_lists(user_email)

        def _unpurchased_total(lists_payload):
            try:
                total = 0
                for lst in (lists_payload.get('lists', []) or []):
                    items = lst.get('items', []) or []
                    total += sum(1 for it in items if not (isinstance(it, dict) and it.get('purchased')))
                return total
            except Exception:
                return 0
        
        # If no list_id specified, use active list
        if not target_list_id:
            target_list_id = lists_data.get('active_list_id')
        
        if not target_list_id:
            return jsonify({'success': False, 'error': 'No list specified and no active list'}), 400
        
        success = add_item_to_list(user_email, target_list_id, item)
        updated_lists = get_user_lists(user_email) if success else lists_data
        # Sanitize lists data before returning
        sanitized_lists = helpers.sanitize_mongo_doc(updated_lists)
        return jsonify({'success': success, 'count': _unpurchased_total(sanitized_lists)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/get-lists', methods=['GET'])
def get_lists_api():
    """Get all shopping lists for the current user"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        from models.users_model import get_user_lists
        lists_data = get_user_lists(user_email)
        
        return jsonify({'success': True, 'lists': helpers.sanitize_mongo_doc(lists_data.get('lists', []))})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/<list_id>/items', methods=['GET'])
def get_list_items_api(list_id):
    """Get all items for a specific shopping list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        from models.users_model import get_user_lists
        lists_data = get_user_lists(user_email)
        
        # Find the specific list
        target_list = None
        for lst in lists_data.get('lists', []):
            if lst.get('id') == list_id:
                target_list = lst
                break
        
        if not target_list:
            return jsonify({'success': False, 'error': 'List not found'}), 404
        
        # Enrich items with product images (and fallback placeholder) using Model
        raw_items = target_list.get('items', [])
        products = products_model.list_products()

        def find_product_by_name(name):
            if not name:
                return None
            name_l = name.lower()
            for p in products:
                try:
                    if isinstance(p.get('name'), str) and p.get('name').lower() == name_l:
                        return p
                except Exception:
                    continue
            for p in products:
                try:
                    if isinstance(p.get('name'), str) and name_l in p.get('name').lower():
                        return p
                except Exception:
                    continue
            return None

        placeholder_url = url_for('static', filename='placeholder.svg')
        enriched_items = []
        for entry in raw_items:
            if isinstance(entry, dict):
                name = entry.get('name') or ''
                img_val = entry.get('image') or ''
            else:
                name = str(entry)
                img_val = ''

            product = find_product_by_name(name)
            if not img_val and product:
                try:
                    img_val = product.get('image') or (product.get('images') and product.get('images')[0]) or ''
                except Exception:
                    img_val = ''
            if not img_val:
                img_val = placeholder_url

            # preserve other fields
            if isinstance(entry, dict):
                enriched = dict(entry)
                enriched['image'] = img_val
            else:
                enriched = {'name': name, 'qty': 1, 'image': img_val}
            enriched_items.append(enriched)

        return jsonify({
            'success': True,
            'list_id': list_id,
            'name': target_list.get('name'),
            'items': enriched_items,
            'created_at': target_list.get('created_at')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


