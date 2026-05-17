import re
from flask import render_template, session, request, redirect, url_for, current_app
from .. import main_bp
from models.products_model import products_model
from models.multibuy_offers_model import multibuy_offers_model
from models.quantity_discounts_model import quantity_discounts_model
from models.stores_model import stores_model
from utils import helpers
from models.users_model import get_user_lists, get_user_by_email, update_user
from models.favorites_model import favorites_model


@main_bp.route('/shopping-list')
def shopping_list():
    """Display and manage the user's shopping lists."""
    user_email = helpers.get_user_email()
    if not user_email:
        return redirect(url_for('auth.login'))

    
    lists_data = get_user_lists(user_email) or {'lists': [], 'active_list_id': None}
    all_lists = lists_data.get('lists', [])
    active_list_id = lists_data.get('active_list_id')
    user_data = get_user_by_email(user_email) or {}

    # Simple estimation and labeling
    for lst in all_lists:
        items = lst.get('items', [])
        total = 0.0
        for item in items:
            p = item.get('price', 0)
            q = item.get('qty', 1)
            try: total += float(str(p).replace('€','').strip()) * int(q)
            except: pass
        lst['estimated_total'] = f'€{total:.2f}'

    active_list = next((l for l in all_lists if str(l.get('id')) == str(active_list_id)), all_lists[0] if all_lists else None)
    
    return render_template('shopping_list.html', 
                         user_data=helpers.sanitize_mongo_doc(user_data), 
                         items=active_list.get('items', []) if active_list else [], 
                         all_lists=helpers.sanitize_mongo_doc(all_lists), 
                         active_list=helpers.sanitize_mongo_doc(active_list))

@main_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    user_email = helpers.get_user_email()
    if not user_email: return redirect(url_for('auth.login'))
    if request.method == 'POST':
        update_data = {
            'name': request.form.get('name'),
            'phone': request.form.get('phone_number'),
            'address': request.form.get('address'),
            'avatar': request.form.get('avatar')
        }
        update_data = {k: v for k, v in update_data.items() if v is not None}
        update_user(user_email, update_data)
        tab = request.form.get('tab', 'overview')
        return redirect(url_for('main.profile') + f'?tab={tab}')
    user_data = get_user_by_email(user_email)
    stores = stores_model.list_stores()
    category_options = helpers.get_category_options()
    return render_template('profile.html', user_data=helpers.sanitize_mongo_doc(user_data), stores=stores, category_options=category_options)

@main_bp.route('/profile/favorites')
def profile_favorites():
    user_email = helpers.get_user_email()
    if not user_email: return redirect(url_for('auth.login'))
    return redirect(url_for('main.profile') + '?tab=favorites')

@main_bp.route('/profile/settings', methods=['GET', 'POST'])
def profile_settings():
    user_email = helpers.get_user_email()
    if not user_email: return redirect(url_for('auth.login'))
    if request.method == 'POST':
        update_data = {
            'name': request.form.get('name'),
            'phone': request.form.get('phone_number'),
            'address': request.form.get('address'),
            'avatar': request.form.get('avatar')
        }
        update_data = {k: v for k, v in update_data.items() if v is not None}
        update_user(user_email, update_data)
    return redirect(url_for('main.profile') + '?tab=settings')

@main_bp.route('/profile/preferences')
def profile_preferences():
    user_email = helpers.get_user_email()
    if not user_email: return redirect(url_for('auth.login'))
    return redirect(url_for('main.profile') + '?tab=preferences')

@main_bp.route('/update-stores', methods=['POST'])
def update_stores():
    user_email = helpers.get_user_email()
    if not user_email: return redirect(url_for('auth.login'))
    selected_stores = request.form.getlist('stores')
    
    update_user(user_email, {'preferred_stores': selected_stores})
    return redirect(url_for('main.profile'))

@main_bp.route('/update-categories', methods=['POST'])
def update_categories():
    user_email = helpers.get_user_email()
    if not user_email: return redirect(url_for('auth.login'))
    selected_categories = request.form.getlist('categories')
    
    update_user(user_email, {'preferred_categories': selected_categories})
    return redirect(url_for('main.profile'))
