from flask import render_template, request, redirect, url_for, session, jsonify, flash, current_app
from . import auth_bp
import os
import re
from models.users_model import users_model, update_user_profile
from models.products_model import products_model
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.notifications_model import notifications_model
from utils import helpers
from comparison.cheapest_finder import get_cheapest_from_product

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']; password = request.form['password']
        if users_model.authenticate(email, password):
            token = helpers.generate_jwt(email)
            if request.is_json or request.accept_mimetypes.best == 'application/json':
                return jsonify({'token': token, 'email': email}), 200
            session['user'] = email
            notifs = notifications_model.get_user_notifications(email, unread_only=True)
            toast_ids = []
            for n in notifs:
                if n.get('type') == 'list_share' and not n.get('is_toasted'):
                    flash(n.get('message', 'A new list was shared!'), 'info')
                    toast_ids.append(n.get('id'))
            if toast_ids:
                try:
                    from models.postgres_models import Notification, db as sa_db

                    notif_rows = (
                        Notification.query.filter(Notification.id.in_([int(i) for i in toast_ids if str(i).isdigit()]))
                        .all()
                    )
                    for notif_row in notif_rows:
                        notif_row.is_toasted = True
                    if notif_rows:
                        sa_db.session.commit()
                except Exception:
                    pass
            resp = redirect(url_for('main.home'))
            resp.set_cookie('auth_token', token, httponly=True, samesite='Lax', secure=bool(os.environ.get('COOKIE_SECURE')))
            return resp
        if request.is_json or request.accept_mimetypes.best == 'application/json':
            return jsonify({'error': 'Invalid credentials'}), 401
        return render_template('login.html', error="Invalid credentials", email=email)
    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name'); email = request.form.get('email'); password = request.form.get('password')
        if not email or not password: return render_template('signup.html', error='Missing fields', name=name, email=email)
        if users_model.get_user_by_email(email): return render_template('signup.html', error='Email registered', name=name, email=email)
        user_doc = {'email': email, 'password': password, 'name': name or email, 'shopping_list': [], 'total_cost': 0.0, 'seen_deals': []}
        try: users_model.create_user(user_doc)
        except: return render_template('signup.html', error='Creation failed', name=name, email=email)
        session['user'] = email
        return redirect(url_for('main.home'))
    return render_template('signup.html')

@auth_bp.route('/shopping-list/add', methods=['POST'])
def add_shopping_item():
    email = helpers.get_user_email()
    if not email: return jsonify({'error': 'no_user'}), 400
    data = request.get_json() or request.form; item = data.get('item')
    if not isinstance(item, dict) and item:
        try:
            import json; parsed = json.loads(item)
            if isinstance(parsed, dict): item = parsed
        except: item = {'name': str(item)}
    if not item: return jsonify({'error': 'no_item'}), 400
    try:
        if isinstance(item, dict):
            pid = item.get('id') or item.get('product_id')
            prod = products_model.get_product_by_id(str(pid)) if pid else products_model.get_product_by_name(item.get('name'))
            if prod:
                if not item.get('image'): item['image'] = prod.get('image')
                cheapest = get_cheapest_from_product(prod); pval = cheapest.get('price') if isinstance(cheapest, dict) else prod.get('price')
                if pval is not None:
                    try: up = float(re.sub(r"[^0-9.]", "", str(pval))) if not isinstance(pval, (int, float)) else float(pval)
                    except: up = 0.0
                    item['price'] = up
                item['id'] = str(prod.get('id') or prod.get('_id'))
    except: pass
    from models.users_model import get_user_lists, add_item_to_list, create_shopping_list, set_active_list
    lists_data = get_user_lists(email) or {'lists': [], 'active_list_id': None}
    active_id = lists_data.get('active_list_id')
    if not active_id:
        lists = lists_data.get('lists', [])
        if lists: active_id = lists[0].get('id'); set_active_list(email, active_id)
        else: active_id = create_shopping_list(email, 'My List'); set_active_list(email, active_id)
    if active_id:
        success = add_item_to_list(email, active_id, item)
        updated = get_user_lists(email); active_list = next((l for l in updated.get('lists', []) if l.get('id') == active_id), None)
        count = sum(1 for it in (active_list.get('items', []) if active_list else []) if not (isinstance(it, dict) and it.get('purchased')))
        return jsonify({'success': bool(success), 'count': count})
    return jsonify({'success': False}), 500

@auth_bp.route('/shopping-list/remove', methods=['POST'])
def remove_shopping_item():
    email = helpers.get_user_email(); data = request.get_json() or request.form; item = data.get('item')
    if not email or not item: return jsonify({'error': 'invalid'}), 400
    success = users_model.remove_from_shopping_list(email, item)
    return jsonify({'success': bool(success)})

@auth_bp.route('/shopping-list/update', methods=['POST'])
def update_shopping_list_api():
    email = helpers.get_user_email(); data = request.get_json() or {}; items = data.get('items')
    if not email or not isinstance(items, list): return jsonify({'error': 'invalid'}), 400
    users_model.update_shopping_list(email, items)
    return jsonify({'success': True, 'items': items})

@auth_bp.route('/shopping-list/clear', methods=['POST'])
def clear_shopping_list():
    email = helpers.get_user_email()
    if not email: return jsonify({'error': 'invalid'}), 400
    users_model.update_shopping_list(email, [])
    return jsonify({'success': True})

@auth_bp.route('/logout')
def logout():
    session.clear(); resp = redirect(url_for('main.home'))
    try: resp.delete_cookie('auth_token')
    except: pass
    return resp

@auth_bp.route('/profile/update', methods=['POST'])
def api_update_profile():
    email = helpers.get_user_email()
    if not email: return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json() if request.is_json else request.form
    update_data = {k: data.get(k) for k in ['phone', 'address', 'avatar', 'name'] if data.get(k) is not None}
    success = update_user_profile(email, update_data)
    return jsonify({'success': bool(success), **update_data}) if success else (jsonify({'error': 'failed'}), 500)
