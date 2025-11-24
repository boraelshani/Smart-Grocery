from flask import render_template, request, redirect, url_for, session, jsonify
from . import auth_bp
from models.models import get_user_by_email, create_user
from models import models as m
from models import users_model as users_model
from utils.db import mongo


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = get_user_by_email(email)
        if user and user.get('password') == password:
            session['user'] = email
            return redirect(url_for('main.home'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        existing = get_user_by_email(email)
        if not existing:
            user_doc = {"email": email, "password": password, "name": name, "shopping_list": [], "total_cost": 0.0}
            create_user(user_doc)
            session['user'] = email
            return redirect(url_for('main.home'))
        else:
            return render_template('signup.html', error="Email already exists")
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
    if not item:
        return jsonify({'error': 'no_item_provided'}), 400
    try:
        if mongo is not None and getattr(mongo, 'db', None) is not None:
            # use upsert to ensure user doc exists
            res = mongo.db.users.update_one({'email': email}, {'$push': {'shopping_list': item}}, upsert=True)
            # success if modified or upserted
            success = (getattr(res, 'modified_count', 0) > 0) or (getattr(res, 'upserted_id', None) is not None)
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
    """Accept JSON payload: { items: [ {name: str, purchased: bool, qty: int, price: float}, ... ] }
    Persists the ordered list of item names (simple representation) using users_model.update_shopping_list.
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
    # For persistence we store list of item names in order
    names = [it.get('name') if isinstance(it, dict) else str(it) for it in items]
    try:
        if mongo is not None and getattr(mongo, 'db', None) is not None:
            mongo.db.users.update_one({'email': email}, {'$set': {'shopping_list': names}}, upsert=True)
        else:
            users_model.update_shopping_list(email, names)
        return jsonify({'success': True, 'items': names})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.home'))
