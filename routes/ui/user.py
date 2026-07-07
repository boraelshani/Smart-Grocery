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

    # Bulk-hydrate all products referenced across lists (for cheapest-mix pricing)
    from models.postgres_models import Product
    all_pids = set()
    for lst in all_lists:
        for item in lst.get('items', []):
            if isinstance(item, dict):
                pid = item.get('product_id') or item.get('productId')
                try:
                    if pid: all_pids.add(int(pid))
                except (ValueError, TypeError):
                    pass
    product_map = {}
    if all_pids:
        try:
            rows = Product.query.filter(Product.id.in_(list(all_pids))).all()
            for doc in products_model._hydrate_products_bulk(rows):
                product_map[str(doc.get('id'))] = doc
        except Exception as e:
            print(f'WARNING: bulk hydrate failed: {e}')

    # Per-list stats: cheapest mix total, bought count, store count
    for lst in all_lists:
        items = lst.get('items', [])
        total = 0.0
        bought = 0
        stores_seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get('purchased') or item.get('checked'):
                bought += 1
            q = 1
            try: q = int(item.get('qty') or item.get('quantity') or 1)
            except: pass
            pid = str(item.get('product_id') or item.get('productId') or '')
            product = product_map.get(pid)
            unit = 0.0
            if product:
                prices = [float(s['price']) for s in (product.get('stores') or []) if s.get('price') is not None]
                if prices:
                    unit = min(prices)
                for s in (product.get('stores') or []):
                    if s.get('store'): stores_seen.add(s['store'])
            if not unit:
                try: unit = float(str(item.get('price', 0)).replace('€','').strip() or 0)
                except: unit = 0.0
            total += unit * q
        lst['estimated_total'] = f'€{total:.2f}'
        lst['cheapest_total'] = total
        lst['bought_count'] = bought
        lst['store_count'] = len(stores_seen)

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
    user_data = get_user_by_email(user_email) or {}
    try:
        user_data['favorites'] = favorites_model.get_user_favorites(user_email)
    except Exception:
        user_data['favorites'] = []
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
