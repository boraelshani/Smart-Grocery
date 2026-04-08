import re
from flask import render_template, session, request, redirect, url_for, current_app
from .. import main_bp
from models.products_model import products_model
from models.multibuy_offers_model import multibuy_offers_model
from models.quantity_discounts_model import quantity_discounts_model
from utils import helpers
from bson.decimal128 import Decimal128

@main_bp.route('/shopping-list')
def shopping_list():
    """Display and manage the user's shopping lists."""
    user_email = session.get('user')
    if not user_email:
        return redirect(url_for('auth.login'))

    from models.users_model import get_user_lists, get_user_by_email
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

@main_bp.route('/profile')
def profile():
    user_email = session.get('user')
    if not user_email: return redirect(url_for('auth.login'))
    from models.users_model import get_user_by_email
    user_data = get_user_by_email(user_email)
    return render_template('profile.html', user_data=helpers.sanitize_mongo_doc(user_data))

@main_bp.route('/profile/favorites')
def profile_favorites():
    user_email = session.get('user')
    if not user_email: return redirect(url_for('auth.login'))
    from models.favorites_model import favorites_model
    favs = favorites_model.get_user_favorites(user_email)
    return render_template('account_favorites.html', favorites=helpers.sanitize_mongo_doc(favs), account_section='favorites')

@main_bp.route('/profile/settings')
def profile_settings():
    return render_template('account_settings.html', account_section='settings')

@main_bp.route('/profile/preferences')
def profile_preferences():
    return render_template('account_preferences.html', account_section='preferences')

@main_bp.route('/update-stores', methods=['POST'])
def update_stores():
    user_email = helpers.get_user_email()
    if not user_email: return redirect(url_for('auth.login'))
    selected_stores = request.form.getlist('stores')
    from models.users_model import update_user
    update_user(user_email, {'preferred_stores': selected_stores})
    return redirect(url_for('main.profile'))

@main_bp.route('/update-categories', methods=['POST'])
def update_categories():
    user_email = helpers.get_user_email()
    if not user_email: return redirect(url_for('auth.login'))
    selected_categories = request.form.getlist('categories')
    from models.users_model import update_user
    update_user(user_email, {'preferred_categories': selected_categories})
    return redirect(url_for('main.profile'))
