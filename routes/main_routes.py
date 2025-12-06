from flask import render_template, jsonify, session, request, current_app
from . import main_bp
from models import models as m
from bson.decimal128 import Decimal128
try:
    from utils.db import mongo
    HAS_DB = True
except Exception:
    mongo = None
    HAS_DB = False
import re

# Cached fallback client to avoid creating a new MongoClient on every request
_FALLBACK_CLIENT = None

def _db_available():
    return HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None


def get_db():
    """Return a working pymongo Database instance. Prefer the Flask-PyMongo `mongo.db` when available;
    otherwise open a fresh MongoClient using the configured URI in the app config or environment.
    """
    try:
        if _db_available():
            return mongo.db
    except Exception:
        pass
    # fallback: try direct MongoClient using configured URI
    try:
        from pymongo import MongoClient
        import os
        # ensure .env is loaded here too (override any process env) so we consistently prefer it
        try:
            from dotenv import load_dotenv, find_dotenv
            dotenv_path = find_dotenv('.env', usecwd=True)
            if dotenv_path:
                load_dotenv(dotenv_path, override=True)
        except Exception:
            pass
        # prefer the Flask app config, otherwise read from .env (now loaded) or process env
        uri = current_app.config.get('MONGO_URI') or os.environ.get('MONGO_URI')
        # If this is an Atlas SRV URI, ensure TLS and CA file are provided to avoid SSL issues
        try:
            import certifi
            # Reuse a cached fallback client when possible to avoid repeated server-selection handshakes
            global _FALLBACK_CLIENT
            if _FALLBACK_CLIENT is None:
                if isinstance(uri, str) and uri.startswith('mongodb+srv://'):
                    _FALLBACK_CLIENT = MongoClient(uri, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=2000)
                else:
                    _FALLBACK_CLIENT = MongoClient(uri, serverSelectionTimeoutMS=2000)
            client = _FALLBACK_CLIENT
        except Exception:
            # last-resort: create a simple client with a small timeout
            client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        dbname = current_app.config.get('MONGO_DBNAME')
        if not dbname:
            try:
                default = client.get_default_database()
                dbname = getattr(default, 'name', None) or 'smart_grocery'
            except Exception:
                dbname = 'smart_grocery'
        return client[dbname]
    except Exception as e:
        print('ERROR: get_db() failed to create MongoClient:', e)
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
        except Exception:
            stores = products = featured_deals = []
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
        featured_deals = getattr(m, 'featured_deals', [])

    return render_template('home.html', stores=stores, products=products, featured_deals=featured_deals, using_fallback=using_fallback)

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
        except Exception:
            using_fallback = True
            print('WARNING: Using in-memory fallback data for featured deals (DB query failed)')
            deals = getattr(m, 'featured_deals', [])
    else:
        using_fallback = True
        print('WARNING: Using in-memory fallback data for featured deals (DB unavailable)')
        deals = getattr(m, 'featured_deals', [])
    return render_template('featured_deals.html', deals=deals, using_fallback=using_fallback)

@main_bp.route('/compare-prices')
def compare_prices():
    using_fallback = False
    db = get_db()
    if db is not None:
        try:
            products = list(db.products.find({}))
            for p in products:
                if '_id' in p:
                    p['id'] = str(p['_id'])
        except Exception:
            using_fallback = True
            print('WARNING: Using in-memory fallback data for compare prices (DB query failed)')
            products = getattr(m, 'products', [])
    else:
        using_fallback = True
        print('WARNING: Using in-memory fallback data for compare prices (DB unavailable)')
        products = getattr(m, 'products', [])
    return render_template('compare_prices.html', products=products, using_fallback=using_fallback)

@main_bp.route('/product/<product_id>')
def product_detail(product_id):
    db = get_db()
    product = None
    
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
            print(f'Error fetching product: {e}')
    
    if not product:
        return render_template('404.html'), 404
    
    return render_template('product_detail.html', product=product)

@main_bp.route('/shopping-list')
def shopping_list():
    user_email = session.get('user')
    db = get_db()
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
    # Build items list with price/store information for the template
    shopping_entries = user_data.get('shopping_list', []) if isinstance(user_data, dict) else []

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
    # Aggregate duplicates by name so multiple additions stack into a single line with qty
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
        # If we found a product in the catalog, prefer that product's price.
        if product:
            # try common fields for price on product
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
        # If product price is missing or zero, but the stored entry contains a price, use it.
        if (not price_val or price_val == 0) and isinstance(entry, dict):
            entry_price = entry.get('price') or entry.get('price_val')
            if entry_price is not None:
                try:
                    if isinstance(entry_price, (int, float)):
                        price_val = float(entry_price)
                    else:
                        cleaned = re.sub(r"[^0-9.]", "", str(entry_price))
                        price_val = float(cleaned) if cleaned else price_val
                except Exception:
                    pass

        # Prefer to aggregate by product id when possible (more reliable), otherwise use normalized name
        if product and product.get('id'):
            item_key = str(product.get('id'))
        else:
            item_key = (name or f'item-{idx}').strip().lower()
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
                'store': store_name,
                'qty': qty,
                'purchased': purchased,
                'image': image_val or ''
            }

    # build final items list from aggregated values, set formatted price as total (unit * qty)
    for k, v in agg.items():
        unit = float(v.get('price_val') or 0.0)
        qty = int(v.get('qty') or 1)
        total = unit * qty
        v['price'] = f"${total:.2f}"
        items.append(v)

    return render_template('shopping_list.html', user_data=user_data, items=items)

@main_bp.route('/profile')
def profile():
    user_email = session.get('user')
    if _db_available() and user_email:
        user = mongo.db.users.find_one({'email': user_email})
        if user and '_id' in user:
            user['id'] = str(user['_id'])
        
        # Initialize favorites and recent_views if not present
        if user and 'favorites' not in user:
            user['favorites'] = []
        if user and 'recent_views' not in user:
            user['recent_views'] = []
        
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
        if _db_available():
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


@main_bp.route('/api/claim-deal', methods=['POST'])
def api_claim_deal():
    """Endpoint to claim a featured deal and add it to the user's shopping list.
    Expects JSON { deal_id: '<id>' } or { title: '<title>' }. Returns JSON { success: bool }.
    """
    data = request.get_json() or {}
    deal_id = data.get('deal_id') or data.get('id') or data.get('title')
    if not deal_id:
        return jsonify({'error': 'no_deal_id_provided'}), 400

    # determine user (fallback to in-memory default)
    fallback = 'user1@example.com' if getattr(m, 'users', None) and 'user1@example.com' in m.users else (next(iter(m.users.keys())) if getattr(m, 'users', None) else None)
    email = session.get('user') or fallback

    try:
        # attempt to find deal document (DB or fallback)
        deal_doc = None
        if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
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

        # add to user's shopping list if we have an email
        added = False
        if email:
            # prefer storing a deal representation if available
            added = m.add_deal_to_user_shopping_list(email, deal_doc or str(deal_id))

        return jsonify({'success': bool(claimed or added), 'claimed': bool(claimed), 'added': bool(added)})
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
            # Get product details
            try:
                from bson import ObjectId
                try:
                    product = db.products.find_one({'_id': ObjectId(product_id)})
                except:
                    product = db.products.find_one({'id': product_id})
            except Exception as e:
                return jsonify({'error': f'Product not found: {str(e)}'}), 404
            
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            
            # Create favorite entry
            favorite_entry = {
                'id': str(product.get('_id', product_id)),
                'name': product.get('name', ''),
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

@main_bp.route('/api/check-favorite/<product_id>', methods=['GET'])
def check_favorite(product_id):
    """Check if a product is in user's favorites"""
    try:
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
        
        data = request.get_json()
        
        db = get_db()
        if db is None:
            return jsonify({'error': 'Database not available'}), 500
        
        db.users.update_one(
            {'email': user_email},
            {'$set': {'preferences': data}}
        )
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
