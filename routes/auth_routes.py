"""
═══════════════════════════════════════════════════════════════════════════
AUTHENTICATION ROUTES
═══════════════════════════════════════════════════════════════════════════
Handles user login, signup, logout, and session management.
Also includes shopping list API endpoints for adding/removing items.
"""

from flask import render_template, request, redirect, url_for, session, jsonify
from . import auth_bp
import re
from bson import Decimal128
from models import models as m
from models import users_model as users_model
from utils.db import mongo


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _get_user_email():
    """
    Get the current user's email from Flask session.
    Fallback to mock user data for development/testing.
    Returns: User email string or None
    """
    email = session.get('user')
    if not email and getattr(m, 'users', None):
        email = 'user1@example.com' if 'user1@example.com' in m.users else next(iter(m.users.keys()), None)
    return email


def _has_db():
    """
    Check if MongoDB is available and connected.
    Returns: Boolean indicating database availability
    """
    return mongo is not None and getattr(mongo, 'db', None) is not None


# ═══════════════════════════════════════════════════════════════════════════
# LOGIN & SIGNUP ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login with email and password.
    
    POST: Authenticate user credentials against stored hashed passwords
    GET: Display login form
    """
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        # Use users_model.authenticate which verifies hashed passwords
        print(f'[LOGIN] email={email}, password_entered={repr(password)}')
        ok = users_model.authenticate(email, password)
        print(f'[LOGIN] auth result={ok}')
        if ok:
            session['user'] = email  # Store user in session
            return redirect(url_for('main.home'))
        else:
            # Return email back so user doesn't need to retype it
            return render_template('login.html', error="Invalid credentials", email=email)
    return render_template('login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    Handle new user registration.
    
    Validates:
    - Email and password are provided
    - Email is in valid format
    - Account doesn't already exist
    - Password meets minimum requirements
    """
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        print(f'[SIGNUP] email={email}, password_entered={repr(password)}, name={name}')
        if not email or not password:
            return render_template('signup.html', error='Please provide email and password', name=name, email=email)

        # Check whether an account already exists
        existing = None
        try:
            existing = users_model.get_user_by_email(email)
        except Exception:
            existing = None
        if existing:
            return render_template('signup.html', error='Email already registered', name=name, email=email)

        # create user record
        user_doc = {
            'email': email,
            'password': password,
            'name': name or email,
            'shopping_list': [],
            'total_cost': 0.0,
            'seen_deals': []
        }
        try:
            users_model.create_user(user_doc)
        except Exception:
            # try once more, then fail gracefully
            try:
                users_model.create_user(user_doc)
            except Exception:
                return render_template('signup.html', error='Could not create user', name=name, email=email)

        session['user'] = email
        return redirect(url_for('main.home'))

    return render_template('signup.html')


@auth_bp.route('/profile', methods=['POST'])
def update_profile():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    email = session['user']
    new_list = request.form.getlist('shopping_list')
    # update shopping list in DB if available, otherwise the fallback in models will handle it
    try:
        if _has_db():
            mongo.db.users.update_one({'email': email}, {'$set': {'shopping_list': new_list}})
        else:
            # fallback: update via users_model helper
            users_model.update_shopping_list(email, new_list)
    except Exception:
        pass
    return redirect(url_for('main.profile'))



@auth_bp.route('/shopping-list/add', methods=['POST'])
def add_shopping_item():
    email = _get_user_email()
    if not email:
        return jsonify({'error': 'no_user_available'}), 400
    data = request.get_json() or request.form
    item = data.get('item')
    # coerce form-like objects to plain dicts to avoid type surprises
    try:
        if not isinstance(item, dict) and hasattr(item, 'to_dict'):
            item = item.to_dict()
        # also allow item to be a simple string (convert to dict)
        if not isinstance(item, dict) and item is not None:
            # if item looks like a JSON string, try to parse
            try:
                import json
                parsed = json.loads(item)
                if isinstance(parsed, dict):
                    item = parsed
            except Exception:
                item = {'name': str(item)}
    except Exception:
        pass
    if not item:
        return jsonify({'error': 'no_item_provided'}), 400
    def _unpurchased_count(seq):
        try:
            return sum(1 for it in (seq or []) if not (isinstance(it, dict) and it.get('purchased')))
        except Exception:
            return 0

    shopping_count = 0

    try:
        if mongo is not None and getattr(mongo, 'db', None) is not None:
            # If item is an object and missing a usable unit price or image, try to enrich it
            try:
                if isinstance(item, dict):
                    # prefer product id if provided
                    prod = None
                    prod_id = item.get('id') or item.get('product_id')
                    if prod_id:
                        try:
                            from bson import ObjectId
                            prod = mongo.db.products.find_one({'_id': ObjectId(str(prod_id))})
                        except Exception:
                            prod = mongo.db.products.find_one({'id': str(prod_id)})
                    # fallback: try matching by name
                    if prod is None and item.get('name'):
                        # try exact name (case-insensitive)
                        prod = mongo.db.products.find_one({'name': {'$regex': '^' + re.escape(item.get('name')) + '$', '$options': 'i'}})
                        # fallback to substring match if exact not found
                        if prod is None:
                            prod = mongo.db.products.find_one({'name': {'$regex': re.escape(item.get('name')), '$options': 'i'}})

                    # enrich from product if found
                    if prod is not None:
                        # Set image first (always enrich image if available from product)
                        try:
                            if not item.get('image'):  # Only set if item doesn't already have an image
                                if prod.get('image'):
                                    item['image'] = prod.get('image')
                                elif prod.get('images') and isinstance(prod.get('images'), list) and len(prod.get('images')):
                                    item['image'] = prod.get('images')[0]
                        except Exception:
                            pass
                        
                        # determine price from product if available
                        cheapest = prod.get('cheapest') or {}
                        price_field = cheapest.get('price') if isinstance(cheapest, dict) else prod.get('price')
                        if price_field is None:
                            try:
                                stores_list = prod.get('stores', [])
                                if stores_list and isinstance(stores_list, list):
                                    price_field = stores_list[0].get('price')
                            except Exception:
                                price_field = None
                        # normalize to numeric unit price if found
                        if price_field is not None:
                            try:
                                if isinstance(price_field, (int, float)):
                                    unit_price = float(price_field)
                                else:
                                    cleaned = re.sub(r"[^0-9.]", "", str(price_field))
                                    unit_price = float(cleaned) if cleaned else 0.0
                            except Exception:
                                unit_price = 0.0
                            # set/overwrite item price with product unit price (store as Decimal128)
                            try:
                                item['price'] = Decimal128(f"{unit_price:.2f}")
                            except Exception:
                                item['price'] = float(unit_price)
                        # ensure the item contains the product id so server-side aggregation can group correctly
                        try:
                            if prod.get('_id'):
                                item['id'] = str(prod.get('_id'))
                            elif prod.get('id'):
                                item['id'] = str(prod.get('id'))
                        except Exception:
                            pass
            except Exception:
                # enrichment should never block adding; ignore errors
                pass

            # Use the multi-list structure - add to active list
            from models.users_model import get_user_lists, add_item_to_list, create_shopping_list, set_active_list
            
            # Get user's lists
            lists_data = get_user_lists(email) or {'lists': [], 'active_list_id': None}
            active_list_id = lists_data.get('active_list_id')
            
            # If no active list, create a default one
            if not active_list_id:
                lists = lists_data.get('lists', [])
                if lists:
                    active_list_id = lists[0].get('id')
                    set_active_list(email, active_list_id)
                else:
                    # Create a default list
                    active_list_id = create_shopping_list(email, 'My List')
                    if active_list_id:
                        set_active_list(email, active_list_id)
            
            # Add item to the active list
            if active_list_id:
                success = add_item_to_list(email, active_list_id, item)
                # Get updated count
                lists_data = get_user_lists(email) or {'lists': [], 'active_list_id': None}
                active_list = next((lst for lst in lists_data.get('lists', []) if lst.get('id') == active_list_id), None)
                if active_list:
                    shopping_count = _unpurchased_count(active_list.get('items', []))
                else:
                    shopping_count = 0
            else:
                success = False
                shopping_count = 0
        else:
            # Fallback for non-DB mode
            success = users_model.add_to_shopping_list(email, item)
            try:
                user_doc = users_model.get_user_by_email(email)
                shopping_count = _unpurchased_count(user_doc.get('shopping_list', [])) if user_doc else 0
            except Exception:
                shopping_count = 0
        return jsonify({'success': bool(success), 'count': shopping_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/shopping-list/remove', methods=['POST'])
def remove_shopping_item():
    email = _get_user_email()
    if not email:
        return jsonify({'error': 'no_user_available'}), 400
    data = request.get_json() or request.form
    item = data.get('item')
    if not item:
        return jsonify({'error': 'no_item_provided'}), 400
    try:
        if _has_db():
            # Try removing plain string entries first, then objects with a `name` field
            res = mongo.db.users.update_one({'email': email}, {'$pull': {'shopping_list': item}})
            if getattr(res, 'modified_count', 0) > 0:
                success = True
            else:
                res2 = mongo.db.users.update_one({'email': email}, {'$pull': {'shopping_list': {'name': item}}})
                success = getattr(res2, 'modified_count', 0) > 0
        else:
            success = users_model.remove_from_shopping_list(email, item)
        return jsonify({'success': bool(success)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@auth_bp.route('/shopping-list/update', methods=['POST'])
def update_shopping_list_api():
    """Accept JSON payload: { items: [ {name: str, purchased: bool, qty: int, price: float, image: str}, ... ] }
    Persists the ordered list of full item objects (keeps price/image/qty/purchased).
    Backwards-compatible with older string-only lists.
    """
    email = _get_user_email()
    if not email:
        return jsonify({'error': 'no_user_available'}), 400
    data = request.get_json() or {}
    items = data.get('items')
    if not isinstance(items, list):
        return jsonify({'error': 'invalid_items'}), 400
    # For persistence we store the full item objects (dicts) when provided,
    # but allow older string-only entries as well.
    to_store = []
    for it in items:
        if isinstance(it, dict):
            # normalize keys: ensure name exists
            if 'name' not in it and 'title' in it:
                it['name'] = it.get('title')
            to_store.append(it)
        else:
            to_store.append(str(it))

    try:
        if _has_db():
            mongo.db.users.update_one({'email': email}, {'$set': {'shopping_list': to_store}}, upsert=True)
        else:
            users_model.update_shopping_list(email, to_store)
        return jsonify({'success': True, 'items': to_store})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/shopping-list/clear', methods=['POST'])
def clear_shopping_list():
    email = _get_user_email()
    if not email:
        return jsonify({'error': 'no_user_available'}), 400
    try:
        if _has_db():
            mongo.db.users.update_one({'email': email}, {'$set': {'shopping_list': []}}, upsert=True)
        else:
            users_model.update_shopping_list(email, [])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.home'))


@auth_bp.route('/profile/update', methods=['POST'])
def api_update_profile():
    if 'user' not in session:
        return jsonify({'error': 'not_authenticated'}), 401
    email = session['user']
    data = request.get_json() or request.form or {}
    phone = data.get('phone')
    address = data.get('address')
    try:
        if _has_db():
            mongo.db.users.update_one({'email': email}, {'$set': {'phone': phone, 'address': address}}, upsert=True)
        else:
            # fallback to in-memory models.users if available
            try:
                from models import models as mock_models
                if getattr(mock_models, 'users', None) is None:
                    mock_models.users = {}
                u = mock_models.users.get(email) or {}
                u['email'] = email
                if phone is not None:
                    u['phone'] = phone
                if address is not None:
                    u['address'] = address
                mock_models.users[email] = u
            except Exception:
                pass
        return jsonify({'success': True, 'phone': phone, 'address': address})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
