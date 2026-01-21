"""
═══════════════════════════════════════════════════════════════════════════
AUTHENTICATION ROUTES
═══════════════════════════════════════════════════════════════════════════
Handles user login, signup, logout, and session management.
Also includes shopping list API endpoints for adding/removing items.
"""

from flask import render_template, request, redirect, url_for, session, jsonify, current_app
from . import auth_bp
import re
import os
from bson import Decimal128
from models import models as m
from models.users_model import users_model
from models.products_model import products_model
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from utils import helpers


# ═══════════════════════════════════════════════════════════════════════════
# LOGIN & SIGNUP ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login with email and password.
    
    Operations:
    1. REQUEST HANDLING: Accepts both GET (form display) and POST (submission).
    2. CREDENTIAL VERIFICATION: Calls `users_model.authenticate()` to check hash/plaintext.
    3. ACCESS TOKEN GENERATION: Creates a JWT (JSON Web Token) for secure API access.
    4. SESSION ESTABLISHMENT: Sets a secure HTTP-only cookie to maintain login state.
    
    POST: Authenticates user.
    GET: Renders login.html.
    """
    if request.method == 'POST':
        # 1. EXTRACT CREDENTIALS
        # Pull data from the form submission
        email = request.form['email']
        password = request.form['password']
        
        # Log attempts (excluding password for security)
        print(f'[LOGIN] Attempt for email={email}')
        
        # 2. VERIFY CREDENTIALS
        # Delegate to the model layer (users_model.py) which handles bcrypt hashing logic.
        ok = users_model.authenticate(email, password)
        print(f'[LOGIN] auth result={ok}')
        
        if ok:
            # 3. GENERATE TOKEN (JWT)
            # This token securely encodes the user's identity and is signed by the server's secret key.
            token = helpers.generate_jwt(email)
            
            # 4. HANDLE API CLIENTS (Mobile App / AJAX)
            # If the request specifically asked for JSON, return the token directly.
            if request.is_json or request.accept_mimetypes.best == 'application/json':
                return jsonify({'token': token, 'email': email}), 200

            # 5. HANDLE BROWSER CLIENTS
            # Store primary identifier in Flask's session object (server-side signed cookie).
            session['user'] = email  
            
            # Prepare redirect response to the home page
            resp = redirect(url_for('main.home'))
            
            # Set a secondary 'auth_token' cookie for client-side JS or API usage if needed.
            # 'httponly=True' prevents XSS scripts from stealing the cookie.
            # 'samesite=Lax' provides CSRF protection.
            # 'secure=True' ensures cookie is only sent over HTTPS (in production).
            resp.set_cookie(
                'auth_token',
                token,
                httponly=True,
                samesite='Lax',
                secure=bool(os.environ.get('COOKIE_SECURE'))
            )
            return resp
        else:
            # 6. HANDLE FAILURE
            # Return email back to the template so the user doesn't have to re-type it.
            # (Good UX practice)
            
            if request.is_json or request.accept_mimetypes.best == 'application/json':
                return jsonify({'error': 'Invalid credentials'}), 401
                
            # Render page again with error message
            return render_template('login.html', error="Invalid credentials", email=email)
            
    # GET request: Just show the empty form
    return render_template('login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    Handle new user registration.
    
    Process Flow:
    1. Input Extraction: Get name, email, password from form.
    2. Validation: Check for empty fields.
    3. Duplicate Check: Query DB to ensure email is unique.
    4. Account Creation: Insert new document into 'users' collection via logic in `create_user`.
    5. Auto-Login: Set session immediately so user doesn't have to log in subsequently.
    
    Returns:
        Redirects to home on success, re-renders signup template on error.
    """
    if request.method == 'POST':
        # 1. EXTRACT FORM DATA
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        print(f'[SIGNUP] Registration attempt for email={email}')
        
        # 2. BASIC VALIDATION
        # Ensure mandatory fields are present
        if not email or not password:
            return render_template('signup.html', error='Please provide email and password', name=name, email=email)

        # 3. DATA INTEGRITY CHECK
        # Query the database (via model) to prevent duplicate accounts.
        existing = None
        try:
            existing = users_model.get_user_by_email(email)
        except Exception:
            # If DB error, assume None to avoid blocking user (risky but fail-open) or handle error
            existing = None
            
        if existing:
            # User already exists
            return render_template('signup.html', error='Email already registered', name=name, email=email)

        # 4. PREPARE USER DOCUMENT
        # This dictionary mirrors the structure found in MongoDB 'users' collection.
        user_doc = {
            'email': email,
            'password': password,   # Will be hashed by create_user()
            'name': name or email,  # Fallback to email if name provided is empty
            'shopping_list': [],    # Initialize empty list
            'total_cost': 0.0,
            'seen_deals': []        # Track notifications user has dismissed
        }
        
        # 5. CREATE ACCOUNT
        # We wrap in a retry loop for resilience (e.g. temporary network blip)
        try:
            users_model.create_user(user_doc)
        except Exception:
            # Retry logic: Try once more immediately
            try:
                print("[SIGNUP] First attempt failed, retrying...")
                users_model.create_user(user_doc)
            except Exception as e:
                # Permanent failure
                print(f"[SIGNUP] Critical failure creating user: {e}")
                return render_template('signup.html', error='Could not create user account. Please try again later.', name=name, email=email)

        # 6. AUTO-LOGIN
        # Set session variable directly so user is immediately logged in
        session['user'] = email
        return redirect(url_for('main.home'))

    # GET request: Show registration form
    return render_template('signup.html')


@auth_bp.route('/shopping-list/add', methods=['POST'])
def add_shopping_item():
    email = helpers.get_user_email()
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
        if m.HAS_DB:
            # If item is an object and missing a usable unit price or image, try to enrich it using Models
            try:
                if isinstance(item, dict):
                    # prefer product id if provided
                    prod = None
                    prod_id = item.get('id') or item.get('product_id')
                    if prod_id:
                        prod = products_model.get_product_by_id(str(prod_id))
                    
                    # fallback: try matching by name
                    if prod is None and item.get('name'):
                        prod = products_model.get_product_by_name(item.get('name'))

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
                            item['id'] = str(prod.get('id') or prod.get('_id'))
                        except Exception:
                            pass
                    
                    # If product not found or still missing image, try to enrich from deals collections
                    try:
                        if not item.get('image'):
                            deal_doc = None
                            # Try featured_deals using model
                            pid = item.get('id') or item.get('product_id')
                            if pid:
                                deal_doc = featured_deals_model.get_deal_by_id(str(pid))
                            if deal_doc is None and item.get('name'):
                                deal_doc = featured_deals_model.get_deal_by_title(item.get('name'))
                            
                            # Try multibuy_offers if not found using model
                            if deal_doc is None:
                                if pid:
                                    deal_doc = multibuy_offers_model.get_offer_by_id(str(pid))
                                if deal_doc is None and item.get('name'):
                                    # Multibuy offers might not have title-based lookup but we can search by list if needed
                                    # For now assume id is preferred
                                    pass
                                    deal_doc = None
                            # Set image from deal if available
                            if deal_doc:
                                try:
                                    if deal_doc.get('image'):
                                        item['image'] = deal_doc.get('image')
                                    elif deal_doc.get('product_image'):
                                        item['image'] = deal_doc.get('product_image')
                                except Exception:
                                    pass
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
    email = helpers.get_user_email()
    if not email:
        return jsonify({'error': 'no_user_available'}), 400
    data = request.get_json() or request.form
    item = data.get('item')
    if not item:
        return jsonify({'error': 'no_item_provided'}), 400
    try:
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
    email = helpers.get_user_email()
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
        users_model.update_shopping_list(email, to_store)
        return jsonify({'success': True, 'items': to_store})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/shopping-list/clear', methods=['POST'])
def clear_shopping_list():
    email = helpers.get_user_email()
    if not email:
        return jsonify({'error': 'no_user_available'}), 400
    try:
        users_model.update_shopping_list(email, [])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/logout')
def logout():
    session.clear()
    resp = redirect(url_for('main.home'))
    try:
        resp.delete_cookie('auth_token')
    except Exception:
        pass
    return resp


@auth_bp.route('/profile/update', methods=['POST'])
def api_update_profile():
    email = helpers.get_user_email()
    if not email:
        return jsonify({'error': 'not_authenticated'}), 401
        
    data = {}
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
        
    phone = data.get('phone')
    address = data.get('address')
    avatar = data.get('avatar')
    name = data.get('name')
    
    update_data = {}
    if phone is not None: update_data['phone'] = phone
    if address is not None: update_data['address'] = address
    if avatar is not None: update_data['avatar'] = avatar
    if name is not None: update_data['name'] = name

    try:
        from models.users_model import update_user_profile
        success = update_user_profile(email, update_data)
        
        if success:
            return jsonify({'success': True, **update_data})
        else:
            return jsonify({'error': 'Failed to update profile'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
