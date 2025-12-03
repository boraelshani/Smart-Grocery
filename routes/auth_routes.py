from flask import render_template, request, redirect, url_for, session, jsonify, current_app
from . import auth_bp
import re
from bson.decimal128 import Decimal128
from models.models import get_user_by_email
from models import models as m
from models import users_model as users_model
from utils.db import mongo


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        # use users_model.authenticate which checks hashed passwords
        ok = users_model.authenticate(email, password)
        if ok:
            session['user'] = email
            return redirect(url_for('main.home'))
        else:
            # return the entered email back so the user doesn't need to retype it
            return render_template('login.html', error="Invalid credentials", email=email)
    return render_template('login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    # Simple signup flow: create user doc and sign them in.
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            return render_template('signup.html', error='Please provide email and password', name=name, email=email)
        # check existing
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
            'total_cost': 0.0
        }
        try:
            users_model.create_user(user_doc)
        except Exception:
            # fall back to in-memory helper
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
        if mongo is not None and getattr(mongo, 'db', None) is not None:
            mongo.db.users.update_one({'email': email}, {'$set': {'shopping_list': new_list}})
        else:
            # fallback: update via users_model helper
            users_model.update_shopping_list(email, new_list)
    except Exception:
        pass
    return redirect(url_for('main.profile'))



@auth_bp.route('/shopping-list/add', methods=['POST'])
def add_shopping_item():
    # allow fallback to in-memory default user when not authenticated
    # use the same fallback user as the main routes ('user1@example.com') when present
    fallback = 'user1@example.com' if getattr(m, 'users', None) and 'user1@example.com' in m.users else (next(iter(m.users.keys())) if getattr(m, 'users', None) else None)
    email = session.get('user') or fallback
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
    try:
        if mongo is not None and getattr(mongo, 'db', None) is not None:
            # If item is an object and missing a usable unit price, try to enrich it
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

                    # determine price from product if available
                    if prod is not None:
                        # try common fields
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

            # persist the item by fetching the user doc and setting the list explicitly
            user_doc = mongo.db.users.find_one({'email': email})
            if not user_doc:
                # create new user doc with shopping_list
                mongo.db.users.insert_one({'email': email, 'shopping_list': [item], 'total_cost': 0.0})
                success = True
            else:
                sl = user_doc.get('shopping_list', []) or []
                sl.append(item)
                res = mongo.db.users.update_one({'email': email}, {'$set': {'shopping_list': sl}})
                success = getattr(res, 'modified_count', 0) > 0
        else:
            success = users_model.add_to_shopping_list(email, item)
        return jsonify({'success': bool(success)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/shopping-list/remove', methods=['POST'])
def remove_shopping_item():
    # allow fallback to in-memory default user when not authenticated
    # use the same fallback user as the main routes ('user1@example.com') when present
    fallback = 'user1@example.com' if getattr(m, 'users', None) and 'user1@example.com' in m.users else (next(iter(m.users.keys())) if getattr(m, 'users', None) else None)
    email = session.get('user') or fallback
    if not email:
        return jsonify({'error': 'no_user_available'}), 400
    data = request.get_json() or request.form
    item = data.get('item')
    if not item:
        return jsonify({'error': 'no_item_provided'}), 400
    try:
        if mongo is not None and getattr(mongo, 'db', None) is not None:
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
    # allow fallback to in-memory default user when not authenticated
    # use the same fallback user as the main routes ('user1@example.com') when present
    fallback = 'user1@example.com' if getattr(m, 'users', None) and 'user1@example.com' in m.users else (next(iter(m.users.keys())) if getattr(m, 'users', None) else None)
    email = session.get('user') or fallback
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
        if mongo is not None and getattr(mongo, 'db', None) is not None:
            mongo.db.users.update_one({'email': email}, {'$set': {'shopping_list': to_store}}, upsert=True)
        else:
            users_model.update_shopping_list(email, to_store)
        return jsonify({'success': True, 'items': to_store})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/shopping-list/clear', methods=['POST'])
def clear_shopping_list():
    # Clear entire shopping list for current user (or fallback)
    fallback = 'user1@example.com' if getattr(m, 'users', None) and 'user1@example.com' in m.users else (next(iter(m.users.keys())) if getattr(m, 'users', None) else None)
    email = session.get('user') or fallback
    if not email:
        return jsonify({'error': 'no_user_available'}), 400
    try:
        if mongo is not None and getattr(mongo, 'db', None) is not None:
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
