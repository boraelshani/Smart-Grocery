from flask import render_template, jsonify, session, request, current_app, url_for
from . import main_bp
from models import models as m
from bson.decimal128 import Decimal128
import json
import os
try:
    from utils.db import mongo
    HAS_DB = True
except Exception:
    mongo = None
    HAS_DB = False
import re

# Cached fallback client to avoid creating a new MongoClient on every request
_FALLBACK_CLIENT = None


def load_featured_deals_fallback():
    """Load featured deals from the static JSON fallback file."""
    try:
        path = os.path.join(current_app.root_path, 'data', 'featured_deals.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'WARNING: Failed to load featured deals fallback: {e}')
        return []


def _get_user_email():
    """Get user email from session or fallback to mock user for development."""
    email = session.get('user')
    if not email and getattr(m, 'users', None):
        email = 'user1@example.com' if 'user1@example.com' in m.users else next(iter(m.users.keys()), None)
    return email


def _has_db():
    """Check if MongoDB is available."""
    return HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None


def get_db():
    """Return a working pymongo Database instance."""
    if _has_db():
        return mongo.db
    
    # Fallback: create direct MongoClient
    try:
        from pymongo import MongoClient
        import certifi
        
        global _FALLBACK_CLIENT
        if _FALLBACK_CLIENT is None:
            uri = current_app.config.get('MONGO_URI') or os.environ.get('MONGO_URI')
            if uri and uri.startswith('mongodb+srv://'):
                _FALLBACK_CLIENT = MongoClient(uri, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=2000)
            else:
                _FALLBACK_CLIENT = MongoClient(uri, serverSelectionTimeoutMS=2000)
        
        dbname = current_app.config.get('MONGO_DBNAME') or 'smart_grocery'
        return _FALLBACK_CLIENT[dbname]
    except Exception as e:
        print(f'ERROR: get_db() failed: {e}')
        return None


@main_bp.route('/')
def home():
    # If the user is not signed in, show the entry page prompting Log In / Sign Up
    user_email = session.get('user')
    if not user_email:
        return render_template('entry.html')

    # Load stores/products/deals from MongoDB when available, otherwise use in-memory mocks
    using_fallback = False
    db = get_db()
    if db is not None:
        try:
            stores = list(db.stores.find({}))
            products = list(db.products.find({}))
            featured_deals = list(db.featured_deals.find({}))
            # If no featured deals in DB, use JSON fallback
            if not featured_deals:
                using_fallback = True
                featured_deals = load_featured_deals_fallback()
        except Exception:
            stores = products = []
            using_fallback = True
            featured_deals = load_featured_deals_fallback()
        # convert ObjectId to string id for templates
        for doc_list in (stores, products, featured_deals):
            for d in doc_list:
                if '_id' in d:
                    d['id'] = str(d['_id'])
    else:
        using_fallback = True
        print('WARNING: Using in-memory fallback data for home page (DB unavailable)')
        stores = getattr(m, 'stores', [])
        products = getattr(m, 'products', [])
        featured_deals = load_featured_deals_fallback()

    # Calculate total product count: count each store entry in products + featured deals
    total_product_count = 0
    for product in products:
        stores_list = product.get('stores', [])
        total_product_count += len(stores_list) if stores_list else 1
    total_product_count += len(featured_deals)

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

    # Load user favorites to power the liked products section
    favorites = []
    if db is not None:
        try:
            user = db.users.find_one({'email': user_email})
            if user:
                favorites = user.get('favorites', []) or []
                # Normalize id to string for template usage
                for fav in favorites:
                    if isinstance(fav, dict) and fav.get('id'):
                        fav['id'] = str(fav['id'])
        except Exception as e:
            print(f'WARNING: Failed to load favorites: {e}')

    return render_template('home.html', 
                         stores=stores, 
                         products=products, 
                         featured_deals=featured_deals, 
                         favorites=favorites,
                         using_fallback=using_fallback, 
                         total_product_count=total_product_count, 
                         max_savings=max_savings)

@main_bp.route('/stores')
def stores_page():
    using_fallback = False
    db = get_db()
    if db is not None:
        try:
            stores = list(db.stores.find({}))
            for s in stores:
                if '_id' in s:
                    s['id'] = str(s['_id'])
        except Exception:
            using_fallback = True
            print('WARNING: Using in-memory fallback data for stores page (DB query failed)')
            stores = getattr(m, 'stores', [])
    else:
        using_fallback = True
        print('WARNING: Using in-memory fallback data for stores page (DB unavailable)')
        stores = getattr(m, 'stores', [])
    return render_template('stores.html', stores=stores, using_fallback=using_fallback)

@main_bp.route('/stores/<store_name>')
def store_products_page(store_name):
    """Display all products for a specific store."""
    db = get_db()
    products = []
    store_info = None
    
    if db is not None:
        try:
            # Get store info
            store_info = db.stores.find_one({'name': {'$regex': f'^{re.escape(store_name)}$', '$options': 'i'}})
            if store_info and '_id' in store_info:
                store_info['id'] = str(store_info['_id'])
            
            # Get products for this store
            regex = {'$regex': re.escape(store_name), '$options': 'i'}
            prod_cursor = db.products.find({
                '$or': [
                    {'stores': {'$elemMatch': {'$or': [{'store': regex}, {'name': regex}]}}},
                    {'store': regex}
                ]
            })
            
            for prod in prod_cursor:
                if '_id' in prod:
                    prod['id'] = str(prod['_id'])
                # Extract matched store data
                matched_stores = [s for s in (prod.get('stores') or []) 
                                if (s.get('store') or '').lower() == store_name.lower()]
                if matched_stores:
                    prod['store_price'] = matched_stores[0].get('price')
                    prod['store_image'] = matched_stores[0].get('image') or prod.get('image')
                else:
                    prod['store_price'] = prod.get('price')
                    prod['store_image'] = prod.get('image')
                products.append(prod)
            
            # Also get featured deals for this store
            deals_cursor = db.featured_deals.find({
                '$or': [
                    {'store': regex},
                    {'source': regex}
                ]
            })
            
            for deal in deals_cursor:
                if '_id' in deal:
                    deal['id'] = str(deal['_id'])
                # Use deal's name field as 'name' for consistency
                if 'title' in deal and 'name' not in deal:
                    deal['name'] = deal['title']
                # Set store-specific price and image
                deal['store_price'] = deal.get('price')
                deal['store_image'] = deal.get('image')
                products.append(deal)
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
    
    return render_template('store_products.html', 
                         store_name=store_name, 
                         store=store_info,
                         products=products,
                         product_count=len(products))

@main_bp.route('/featured-deals')
def featured_deals_page():
    using_fallback = False
    db = get_db()
    if db is not None:
        try:
            deals = list(db.featured_deals.find({}))
            for d in deals:
                if '_id' in d:
                    d['id'] = str(d['_id'])
            # If no featured deals in MongoDB, use JSON fallback
            if not deals:
                using_fallback = True
                deals = load_featured_deals_fallback()
        except Exception:
            using_fallback = True
            print('WARNING: MongoDB query failed for featured deals, using JSON fallback')
            deals = load_featured_deals_fallback()
    else:
        using_fallback = True
        print('WARNING: DB unavailable for featured deals, using JSON fallback')
        deals = load_featured_deals_fallback()
    return render_template('featured_deals.html', deals=deals, using_fallback=using_fallback)

@main_bp.route('/compare-prices')
def compare_prices():
    """Render compare page with server-side pagination (30 per page) and category filter."""
    using_fallback = False
    per_page = 30
    try:
        page = int(request.args.get('page', 1))
    except Exception:
        page = 1
    page = max(page, 1)

    category_filter = (request.args.get('category') or '').strip()

    total_products = 0
    total_pages = 1
    products = []
    db = get_db()
    category_options = []

    if db is not None:
        try:
            query = {}
            if category_filter:
                import re as _re
                query['category'] = {'$regex': f"^{_re.escape(category_filter)}$", '$options': 'i'}

            total_products = int(db.products.count_documents(query))
            total_pages = (total_products + per_page - 1) // per_page if total_products else 1
            page = min(page, total_pages) if total_products else 1
            skip_amount = (page - 1) * per_page
            cursor = db.products.find(query).skip(skip_amount).limit(per_page)
            products = list(cursor)
            for p in products:
                if '_id' in p:
                    p['id'] = str(p['_id'])
            try:
                from collections import Counter
                all_prods = list(db.products.find({}, {'category': 1}))
                cat_counts = Counter(p.get('category') for p in all_prods if p.get('category'))
                category_options = sorted(cat_counts.keys(), key=lambda c: (-cat_counts[c], c.lower()))
            except Exception:
                category_options = []
        except Exception:
            using_fallback = True
            products = getattr(m, 'products', [])
            total_products = len(products)
            total_pages = (total_products + per_page - 1) // per_page if total_products else 1
    else:
        using_fallback = True
        products = getattr(m, 'products', [])
        total_products = len(products)
        total_pages = (total_products + per_page - 1) // per_page if total_products else 1

    has_prev = page > 1
    has_next = page < total_pages
    showing_start = ((page - 1) * per_page) + 1 if total_products else 0
    showing_end = min(page * per_page, total_products)

    return render_template(
        'compare_prices.html',
        products=products,
        using_fallback=using_fallback,
        page=page,
        per_page=per_page,
        total_products=total_products,
        total_pages=total_pages,
        has_prev=has_prev,
        has_next=has_next,
        showing_start=showing_start,
        showing_end=showing_end,
        category_filter=category_filter,
        category_options=category_options,
    )

@main_bp.route('/product/<product_id>')
def product_detail(product_id):
    db = get_db()
    product = None
    
    # Check database first (MongoDB)
    if db is not None:
        try:
            from bson import ObjectId
            # Try to find by ObjectId first
            try:
                product = db.products.find_one({'_id': ObjectId(product_id)})
            except:
                # If not a valid ObjectId, try as string id
                product = db.products.find_one({'id': product_id})
            
            # Also check featured_deals collection in MongoDB
            if not product:
                try:
                    product = db.featured_deals.find_one({'_id': ObjectId(product_id)})
                except:
                    product = db.featured_deals.find_one({'id': product_id})
            
            if product and '_id' in product:
                product['id'] = str(product['_id'])
        except Exception as e:
            print(f'Error fetching product from MongoDB: {e}')
    
    # If not found in database, fall back to JSON featured deals
    if not product:
        featured_deals = load_featured_deals_fallback()
        for deal in featured_deals:
            if deal.get('id') == product_id:
                product = deal
                break
    
    if not product:
        return render_template('404.html'), 404

    # Ensure a minimal stores array exists for featured deals or products without stores
    if not product.get('stores'):
        store_name = product.get('store') or product.get('source') or 'Store'
        price_val = product.get('price') or product.get('best_price') or product.get('original_price') or 'N/A'
        product['stores'] = [{
            'store': store_name,
            'price': price_val,
            'image': product.get('image')
        }]
    
    return render_template('product_detail.html', product=product)


@main_bp.route('/featured-deal/<deal_id>')
def featured_deal_detail(deal_id):
    """Display a single featured deal with store link."""
    db = get_db()
    deal = None

    if db is not None:
        try:
            from bson import ObjectId
            try:
                deal = db.featured_deals.find_one({'_id': ObjectId(deal_id)})
            except Exception:
                deal = db.featured_deals.find_one({'id': deal_id})
            if deal and '_id' in deal:
                deal['id'] = str(deal['_id'])
        except Exception as e:
            print(f'ERROR loading featured deal {deal_id}: {e}')

    if deal is None:
        all_deals = load_featured_deals_fallback()
        for d in all_deals:
            if str(d.get('id')) == str(deal_id) or str(d.get('_id', '')) == str(deal_id):
                deal = d
                break

    if deal is None:
        return render_template('404.html'), 404

    return render_template('featured_deal_detail.html', deal=deal)


@main_bp.route('/product-info/<product_id>')
def product_info(product_id):
    """Simple product info page showing just description and unit"""
    db = get_db()
    product = None
    
    # Get store-specific information from query parameters
    store_name = request.args.get('store_name', '')
    store_price = request.args.get('store_price', '')
    
    # Check database for product
    if db is not None:
        try:
            from bson import ObjectId
            # Try to find by ObjectId first
            try:
                product = db.products.find_one({'_id': ObjectId(product_id)})
            except:
                # If not a valid ObjectId, try as string id
                product = db.products.find_one({'id': product_id})
            
            if product and '_id' in product:
                product['id'] = str(product['_id'])
        except Exception as e:
            print(f'Error fetching product from MongoDB: {e}')

    # Also allow featured deals when hitting /product-info directly
    if db is not None and not product:
        try:
            from bson import ObjectId
            try:
                product = db.featured_deals.find_one({'_id': ObjectId(product_id)})
            except Exception:
                product = db.featured_deals.find_one({'id': product_id})
            if product and '_id' in product:
                product['id'] = str(product['_id'])
        except Exception as e:
            print(f'Error fetching featured deal for product-info: {e}')
    
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
    
    return render_template('product_info.html', product=product, store_name=store_name, store_price=store_price)

@main_bp.route('/shopping-list')
def shopping_list():
    user_email = session.get('user')
    db = get_db()
    
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
    
    # Get user data
    if db is not None and user_email:
        try:
            user = db.users.find_one({'email': user_email})
            if user and '_id' in user:
                user['id'] = str(user['_id'])
            user_data = user or {}
        except Exception:
            user_data = getattr(m, 'users', {}).get('user1@example.com', {})
    else:
        user_data = getattr(m, 'users', {}).get('user1@example.com', {})
    
    # Get all lists for this user using new multi-list structure
    from models.users_model import get_user_lists
    lists_data = get_user_lists(user_email) if user_email else {'lists': [], 'active_list_id': None}
    all_lists = lists_data.get('lists', [])
    # Rename 'items' key to 'list_items' to avoid conflict with Jinja2 dict.items() method
    for lst in all_lists:
        if 'items' in lst:
            lst['list_items'] = lst.pop('items')
        # Calculate estimated total for each list
        total = 0.0
        items = lst.get('list_items', [])
        # Calculate completed count
        completed_count = 0
        for item in items:
            if isinstance(item, dict):
                # Count completed items
                if item.get('purchased') or item.get('completed'):
                    completed_count += 1
                # Calculate total price
                price = item.get('price', 0)
                qty = item.get('qty', 1)
                # Convert price string to float if needed
                if isinstance(price, str):
                    price = float(price.replace('$', '').replace('€', '').replace(',', '').strip() or 0)
                total += float(price) * int(qty)
        lst['estimated_total'] = f'€{total:.2f}'
        lst['completed'] = [item for item in items if isinstance(item, dict) and (item.get('purchased') or item.get('completed'))]
    active_list_id = lists_data.get('active_list_id')
    
    # Get the active list or create a default one if none exist
    active_list = None
    if all_lists:
        if active_list_id:
            active_list = next((lst for lst in all_lists if lst.get('id') == active_list_id), all_lists[0])
        else:
            active_list = all_lists[0]
    else:
        # Create default list if user has none
        from models.users_model import create_shopping_list, set_active_list
        if user_email:
            new_id = create_shopping_list(user_email, 'My List')
            if new_id:
                set_active_list(user_email, new_id)
                lists_data = get_user_lists(user_email)
                all_lists = lists_data.get('lists', [])
                active_list = all_lists[0] if all_lists else None
    
    # Build items list with price/store information for the template
    shopping_entries = active_list.get('items', []) if active_list else []

    # load products to try to find prices
    db = get_db()
    if db is not None:
        try:
            products = list(db.products.find({}))
            for p in products:
                if '_id' in p:
                    p['id'] = str(p['_id'])
        except Exception:
            products = getattr(m, 'products', [])
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
    # Aggregate duplicates by name + store so multiple additions stack into a single line with qty
    agg = {}
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
        
        # PRIORITY 1: Use price from the entry if it exists (sent from add-to-list)
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
        
        # PRIORITY 2: If no price in entry, try to get from product catalog
        if (not price_val or price_val == 0) and product:
            # try common fields for price on product
            cheapest = product.get('cheapest') or {}
            price_field = cheapest.get('price') if isinstance(cheapest, dict) else product.get('price')
            if price_field is None:
                # fallback to first 'stores' entry
                try:
                    stores_list = product.get('stores', [])
                    if stores_list and isinstance(stores_list, list):
                        price_field = stores_list[0].get('price')
                        if not store_name:
                            store_name = stores_list[0].get('store') or stores_list[0].get('name')
                except Exception:
                    price_field = None
            if price_field is not None:
                # normalize to float, handle Decimal128 specially
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

        # Prefer to aggregate by product id + store when possible (more reliable), otherwise use normalized name + store
        # This ensures same product from different stores appear as separate items
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
        # try to get image from product or entry
        try:
            if isinstance(entry, dict):
                image_val = entry.get('image') or (entry.get('images')[0] if entry.get('images') else '')
            if not image_val and product:
                image_val = product.get('image') or (product.get('images')[0] if product.get('images') else '')
        except Exception:
            image_val = ''

        if existing:
            # increment quantity and update purchased flag
            existing['qty'] += qty
            existing['purchased'] = existing['purchased'] or purchased
            # if price_val differs and existing is zero, set; otherwise keep existing unit price
            if existing.get('price_val', 0) == 0 and price_val:
                existing['price_val'] = price_val
            # prefer to set image if missing
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
                'image': image_val or ''
            }

    # build final items list from aggregated values, set formatted price as total (unit * qty)
    for k, v in agg.items():
        unit = float(v.get('price_val') or 0.0)
        qty = int(v.get('qty') or 1)
        total = unit * qty
        v['price'] = f"€{total:.2f}"
        items.append(v)

    return render_template('shopping_list.html', 
                         user_data=user_data, 
                         items=items,
                         all_lists=all_lists,
                         active_list=active_list)

@main_bp.route('/profile')
def profile():
    user_email = session.get('user')
    stores_options = []
    category_options = []

    if _has_db() and user_email:
        user = mongo.db.users.find_one({'email': user_email})
        if user and '_id' in user:
            user['id'] = str(user['_id'])

        # Initialize favorites and recent_views if not present
        if user and 'favorites' not in user:
            user['favorites'] = []
        if user and 'recent_views' not in user:
            user['recent_views'] = []

        user_data = user or {}
        try:
            stores_cursor = mongo.db.stores.find({}, {'name': 1}).limit(200)
            stores_options = sorted({s.get('name') for s in stores_cursor if s.get('name')})
        except Exception:
            stores_options = []
        try:
            from collections import Counter
            all_prods = list(mongo.db.products.find({}, {'category': 1}))
            cat_counts = Counter(p.get('category') for p in all_prods if p.get('category'))
            category_options = sorted(cat_counts.keys(), key=lambda c: (-cat_counts[c], c.lower()))
        except Exception:
            category_options = []
    else:
        user_data = getattr(m, 'users', {}).get('user1@example.com', {})
        stores_options = [s.get('name') for s in getattr(m, 'stores', []) if s.get('name')]
        from collections import Counter
        cat_counts = Counter(p.get('category') for p in getattr(m, 'products', []) if p.get('category'))
        category_options = sorted(cat_counts.keys(), key=lambda c: (-cat_counts[c], c.lower()))

    return render_template('profile.html', user_data=user_data, stores_options=stores_options, category_options=category_options)


@main_bp.route('/admin/status')
def admin_status():
    """Return JSON with collection counts so you can verify DB connectivity."""
    collections = ['products', 'stores', 'featured_deals', 'users']
    counts = {}
    # Prefer directly opening a MongoClient with the app-configured URI so we reliably
    # query the intended Atlas cluster (avoids any Flask-PyMongo initialization quirks).
    try:
        from pymongo import MongoClient
        import certifi
        uri = current_app.config.get('MONGO_URI')
        dbname = current_app.config.get('MONGO_DBNAME') or 'smart_grocery'
        if isinstance(uri, str) and uri.startswith('mongodb+srv://'):
            client = MongoClient(uri, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
        else:
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[dbname]
        for c in collections:
            counts[c] = int(db[c].count_documents({}))
    except Exception as e:
        # fallback to in-memory mock data
        print('WARNING: admin_status could not query MongoDB directly:', e)
        counts['products'] = len(getattr(m, 'products', []))
        counts['stores'] = len(getattr(m, 'stores', []))
        counts['featured_deals'] = len(getattr(m, 'featured_deals', []))
        counts['users'] = len(getattr(m, 'users', {}))

    return jsonify({'db': counts})


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
        if _has_db():
            # case-insensitive regex search on 'name' field
            regex = {'$regex': q, '$options': 'i'}
            cursor = mongo.db.products.find({'name': regex}).limit(50)
            for d in cursor:
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
                if '_id' in d:
                    d['id'] = str(d['_id'])
                results.append(d)
        else:
            # fallback to in-memory search (log this so it's visible)
            print('WARNING: api_search_products used fallback in-memory products (DB unavailable)')
            for p in getattr(m, 'products', []):
                name = p.get('name', '')
                if q.lower() in str(name).lower():
                    # filter out in-memory legacy items without price
                    if p.get('price') not in (None, '') or (p.get('cheapest') and p['cheapest'].get('price')) or (p.get('stores') and len(p.get('stores')) and p.get('stores')[0].get('price')):
                        results.append(p)
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
        if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
            query = None
            if pid:
                try:
                    from bson import ObjectId
                    query = {'_id': ObjectId(str(pid))}
                except Exception:
                    # treat as plain id string match on 'id' or 'sku'
                    query = {'id': str(pid)}
            else:
                # case-insensitive name match
                query = {'name': {'$regex': name, '$options': 'i'}}
            doc = mongo.db.products.find_one(query)
            if not doc:
                return jsonify({'item': None}), 404
            if '_id' in doc:
                doc['id'] = str(doc['_id'])
            return jsonify({'item': doc})
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
    """Return all unique categories from products, sorted by frequency."""
    try:
        db = get_db()
        if db is not None:
            try:
                from collections import Counter
                all_prods = list(db.products.find({}, {'category': 1}))
                cat_counts = Counter(p.get('category') for p in all_prods if p.get('category'))
                categories = sorted(cat_counts.keys(), key=lambda c: (-cat_counts[c], c.lower()))
                return jsonify({'categories': categories}), 200
            except Exception as e:
                print(f'WARNING: Failed to fetch categories from DB: {e}')
        # Fallback to in-memory data
        from collections import Counter
        cat_counts = Counter(p.get('category') for p in getattr(m, 'products', []) if p.get('category'))
        categories = sorted(cat_counts.keys(), key=lambda c: (-cat_counts[c], c.lower()))
        return jsonify({'categories': categories}), 200
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
        if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
            cursor = mongo.db.stores.find({}).limit(500)
            for s in cursor:
                if '_id' in s:
                    s['id'] = str(s['_id'])
                out.append(shape_store(s))
        else:
            for s in getattr(m, 'stores', []):
                out.append(shape_store(s))
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
    db = get_db()
    try:
        if db is not None:
            # match contains (not anchored) to be tolerant of casing/spacing
            regex = {'$regex': re.escape(store_query), '$options': 'i'}
            prod_cursor = db.products.find({
                '$or': [
                    {'stores': {'$elemMatch': {'$or': [{'store': regex}, {'name': regex}]}}},
                    {'store': regex}
                ]
            })
            products = [_shape_product(p) for p in prod_cursor]
            # if DB query returns nothing, allow fallback to in-memory products as a safety net
            if not products:
                products = [_shape_product(p) for p in getattr(m, 'products', []) if any(_match_store_entry(s) for s in (p.get('stores') or [])) or (isinstance(p.get('store'), str) and p.get('store', '').lower() == store_lc)]
        else:
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
    email = _get_user_email()

    try:
        # attempt to find deal document (DB or fallback)
        deal_doc = None
        if _has_db():
            from bson import ObjectId
            query = None
            try:
                query = {'_id': ObjectId(str(deal_id))}
            except Exception:
                query = {'title': str(deal_id)}
            deal_doc = mongo.db.featured_deals.find_one(query)
            if deal_doc and '_id' in deal_doc:
                deal_doc['id'] = str(deal_doc['_id'])
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
                    mb_buy = (deal_doc or {}).get('multibuy_buy') or data.get('multibuy_buy')
                    mb_free = (deal_doc or {}).get('multibuy_free') or data.get('multibuy_free')
                    if mb_buy and mb_free:
                        offer_obj = {'type': 'buyXgetY', 'x': mb_buy, 'y': mb_free}

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
                    'image': (deal_doc or {}).get('image') or ((deal_doc or {}).get('images') or [None])[0],
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
        
        db = get_db()
        if db is None:
            return jsonify({'error': 'Database not available'}), 500
        
        # Get user
        user = db.users.find_one({'email': user_email})
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get favorites list
        favorites = user.get('favorites', [])
        
        # Check if product is already in favorites
        is_favorited = any(str(fav.get('id')) == str(product_id) for fav in favorites if isinstance(fav, dict))
        
        if is_favorited:
            # Remove from favorites
            favorites = [fav for fav in favorites if str(fav.get('id')) != str(product_id)]
            db.users.update_one(
                {'email': user_email},
                {'$set': {'favorites': favorites}}
            )
            return jsonify({'success': True, 'action': 'removed', 'is_favorite': False})
        else:
            # Add to favorites
            # Get product details from products or featured_deals
            product = None
            try:
                from bson import ObjectId
                try:
                    product = db.products.find_one({'_id': ObjectId(product_id)})
                except:
                    product = db.products.find_one({'id': product_id})
                
                # If not found in products, check featured_deals
                if not product:
                    try:
                        product = db.featured_deals.find_one({'_id': ObjectId(product_id)})
                    except:
                        product = db.featured_deals.find_one({'id': product_id})
            except Exception as e:
                return jsonify({'error': f'Product not found: {str(e)}'}), 404
            
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            
            # Create favorite entry
            favorite_entry = {
                'id': str(product.get('_id', product_id)),
                'name': product.get('name') or product.get('title', ''),
                'image': product.get('image', ''),
                'category': product.get('category', ''),
                'best_price': (product.get('cheapest') and product.get('cheapest').get('price')) or product.get('price', 'N/A')
            }
            
            favorites.append(favorite_entry)
            db.users.update_one(
                {'email': user_email},
                {'$set': {'favorites': favorites}}
            )
            return jsonify({'success': True, 'action': 'added', 'is_favorite': True})
    
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
        
        db = get_db()
        if db is None:
            return jsonify({'is_favorite': False})
        
        user = db.users.find_one({'email': user_email})
        if not user:
            return jsonify({'is_favorite': False})
        
        favorites = user.get('favorites', [])
        is_favorited = any(str(fav.get('id')) == str(product_id) for fav in favorites if isinstance(fav, dict))
        
        return jsonify({'is_favorite': is_favorited})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/save-preferences', methods=['POST'])
def save_preferences():
    """Save user preferences"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.get_json() or {}
        preferred_stores = [s for s in data.get('preferred_stores', []) if s]
        favorite_categories = [c for c in data.get('favorite_categories', []) if c]
        prefs = {
            'preferred_stores': preferred_stores,
            'favorite_categories': favorite_categories
        }
        
        db = get_db()
        if db is None:
            return jsonify({'error': 'Database not available'}), 500
        
        db.users.update_one(
            {'email': user_email},
            {'$set': {
                'preferences': prefs,
                'preferred_stores': preferred_stores,
                'favorite_categories': favorite_categories
            }}
        )
        
        return jsonify({'success': True, 'preferences': prefs})
    
    except Exception as e:
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
        return jsonify({'success': success, 'count': _unpurchased_total(updated_lists)})
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
        
        # Return lists with basic info (id, name, item count)
        lists = []
        for lst in lists_data.get('lists', []):
            lists.append({
                'id': lst.get('id'),
                'name': lst.get('name'),
                'items': lst.get('items', [])
            })
        
        return jsonify({'success': True, 'lists': lists})
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
        
        # Enrich items with product images (and fallback placeholder)
        raw_items = target_list.get('items', [])

        db = get_db()
        products = []
        if db is not None:
            try:
                products = list(db.products.find({}))
                for p in products:
                    if '_id' in p:
                        p['id'] = str(p['_id'])
            except Exception:
                products = []

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


