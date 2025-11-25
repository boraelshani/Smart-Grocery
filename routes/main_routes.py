from flask import render_template, jsonify, session, request
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
    # If the user is not signed in, show the entry page prompting Log In / Sign Up
    user_email = session.get('user')
    if not user_email:
        return render_template('entry.html')

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
        if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
            # case-insensitive regex search on 'name' field
            regex = {'$regex': q, '$options': 'i'}
            cursor = mongo.db.products.find({'name': regex}).limit(50)
            for d in cursor:
                if '_id' in d:
                    d['id'] = str(d['_id'])
                results.append(d)
        else:
            # fallback to in-memory search
            for p in getattr(m, 'products', []):
                name = p.get('name', '')
                if q.lower() in str(name).lower():
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
        if HAS_DB and mongo is not None and getattr(mongo, 'db', None) is not None:
            cursor = mongo.db.stores.find({}).limit(500)
            for s in cursor:
                if '_id' in s:
                    s['id'] = str(s['_id'])
                out.append({'id': s.get('id') or s.get('_id'), 'name': s.get('name'), 'location': s.get('location')})
        else:
            for s in getattr(m, 'stores', []):
                out.append({'id': s.get('id') or s.get('name'), 'name': s.get('name'), 'location': s.get('location')})
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
