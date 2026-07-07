from flask import jsonify, session, request
from .. import main_bp
from models.users_model import (
    create_shopping_list,
    set_active_list,
    rename_shopping_list,
    delete_shopping_list,
    update_list_items,
    mark_items_as_seen,
    remove_item_from_list,
    get_user_lists,
    add_item_to_list,
    set_list_icon,
    users_model
)
from models.products_model import products_model
from utils import helpers
import uuid
from flask import url_for

@main_bp.route('/api/list/create', methods=['POST'])
def create_shopping_list_api():
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        list_name = data.get('name', '').strip()
        list_icon = (data.get('icon') or 'basket').strip()
        if not list_name:
            return jsonify({'success': False, 'error': 'List name is required'}), 400

        new_list_id = create_shopping_list(user_email, list_name, list_icon)
        if new_list_id:
            set_active_list(user_email, new_list_id)
            return jsonify({'success': True, 'list_id': new_list_id})
        return jsonify({'success': False, 'error': 'Failed to create list'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/rename', methods=['POST'])
def rename_shopping_list_api():
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        list_id = data.get('list_id')
        new_name = data.get('name', '').strip()
        if not list_id or not new_name:
            return jsonify({'success': False, 'error': 'List ID and name are required'}), 400
        
        success = rename_shopping_list(user_email, list_id, new_name)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/set-icon', methods=['POST'])
def set_list_icon_api():
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        data = request.get_json()
        list_id = data.get('list_id')
        icon = (data.get('icon') or '').strip()
        if not list_id or not icon:
            return jsonify({'success': False, 'error': 'List ID and icon are required'}), 400
        success = set_list_icon(user_email, list_id, icon)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/delete', methods=['POST'])
def delete_shopping_list_api():
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        list_id = data.get('list_id')
        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400
        
        success = delete_shopping_list(user_email, list_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/set-active', methods=['POST'])
def set_active_list_api():
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        list_id = data.get('list_id')
        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400
        
        success = set_active_list(user_email, list_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/duplicate', methods=['POST'])
def duplicate_shopping_list_api():
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        list_id = data.get('list_id')
        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400
        
        lists_data = get_user_lists(user_email)
        source_list = next((lst for lst in lists_data['lists'] if lst['id'] == list_id), None)
        if not source_list:
            return jsonify({'success': False, 'error': 'List not found'}), 404
        
        new_name = f"{source_list['name']} (Copy)"
        new_list_id = create_shopping_list(user_email, new_name)
        if new_list_id:
            items = source_list.get('items', [])
            update_list_items(user_email, new_list_id, items)
            return jsonify({'success': True, 'list_id': new_list_id})
        return jsonify({'success': False, 'error': 'Failed to create list'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/update-items', methods=['POST'])
def update_list_items_api():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        data = request.get_json()
        items = data.get('items', [])
        list_id = data.get('list_id')  # prefer explicit list_id from client
        if not list_id:
            lists_data = get_user_lists(user_email)
            list_id = lists_data.get('active_list_id')
        if not list_id: return jsonify({'success': False, 'error': 'No list specified'}), 400
        success = update_list_items(user_email, list_id, items)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/mark-seen/<list_id>', methods=['POST'])
def mark_list_seen(list_id):
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        success = mark_items_as_seen(user_email, list_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/remove-item', methods=['POST'])
def remove_item_from_list_api():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        data = request.get_json()
        item_name = data.get('item_name')
        if not item_name: return jsonify({'success': False, 'error': 'Item name is required'}), 400
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        if not active_list_id: return jsonify({'success': False, 'error': 'No active list'}), 400
        success = remove_item_from_list(user_email, active_list_id, item_name)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/clear-completed', methods=['POST'])
def clear_completed_items_api():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        if not active_list_id: return jsonify({'success': False, 'error': 'No active list'}), 400
        active_list = next((lst for lst in lists_data['lists'] if lst['id'] == active_list_id), None)
        if not active_list: return jsonify({'success': False, 'error': 'List not found'}), 404
        items = active_list.get('items', [])
        remaining_items = [item for item in items if not (isinstance(item, dict) and item.get('purchased'))]
        success = update_list_items(user_email, active_list_id, remaining_items)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/clear-all', methods=['POST'])
def clear_all_items_api():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        if not active_list_id: return jsonify({'success': False, 'error': 'No active list'}), 400
        success = update_list_items(user_email, active_list_id, [])
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/move-item', methods=['POST'])
def move_item_to_list_api():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        data = request.get_json()
        item_name = data.get('item_name')
        target_list_id = data.get('target_list_id')
        if not item_name or not target_list_id:
            return jsonify({'success': False, 'error': 'Item name and target list are required'}), 400
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        if not active_list_id: return jsonify({'success': False, 'error': 'No active list'}), 400
        active_list = next((lst for lst in lists_data['lists'] if lst['id'] == active_list_id), None)
        if not active_list: return jsonify({'success': False, 'error': 'List not found'}), 404
        item_to_move = None
        for item in active_list.get('items', []):
            if isinstance(item, dict) and item.get('name') == item_name:
                item_to_move = item
                break
            elif isinstance(item, str) and item == item_name:
                item_to_move = item
                break
        if not item_to_move: return jsonify({'success': False, 'error': 'Item not found'}), 404
        success = add_item_to_list(user_email, target_list_id, item_to_move)
        if success:
            success = remove_item_from_list(user_email, active_list_id, item_name)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/add-item', methods=['POST'])
def add_item_to_active_list_api():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        data = request.get_json()
        item = data.get('item')
        target_list_id = data.get('list_id')
        if not item: return jsonify({'success': False, 'error': 'Item is required'}), 400
        lists_data = get_user_lists(user_email)
        if not target_list_id:
            target_list_id = lists_data.get('active_list_id')
        if not target_list_id: return jsonify({'success': False, 'error': 'No list specified'}), 400
        success = add_item_to_list(user_email, target_list_id, item)
        updated_lists = get_user_lists(user_email) if success else lists_data
        sanitized_lists = helpers.sanitize_mongo_doc(updated_lists)
        def _unpurchased_total(lp):
            total = 0
            for lst in (lp.get('lists', []) or []):
                items = lst.get('items', []) or []
                total += sum(1 for it in items if not (isinstance(it, dict) and it.get('purchased')))
            return total
        return jsonify({'success': success, 'count': _unpurchased_total(sanitized_lists)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/get-lists', methods=['GET'])
def get_lists_api():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        lists_data = get_user_lists(user_email)
        return jsonify({'success': True, 'lists': helpers.sanitize_mongo_doc(lists_data.get('lists', []))})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/<list_id>/items', methods=['GET'])
def get_list_items_api(list_id):
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        lists_data = get_user_lists(user_email)
        target_list = next((l for l in lists_data.get('lists', []) if l.get('id') == list_id), None)
        if not target_list: return jsonify({'success': False, 'error': 'List not found'}), 404
        raw_items = target_list.get('items', [])

        # ── Bulk-hydrate all products referenced by this list ──────────────
        from models.postgres_models import Product
        pid_set = set()
        for entry in raw_items:
            if isinstance(entry, dict):
                pid = entry.get('product_id') or entry.get('productId')
                try:
                    if pid: pid_set.add(int(pid))
                except (ValueError, TypeError):
                    pass
        product_map = {}
        if pid_set:
            rows = Product.query.filter(Product.id.in_(list(pid_set))).all()
            for doc in products_model._hydrate_products_bulk(rows):
                product_map[str(doc.get('id'))] = doc

        def find_product_by_name(name):
            if not name: return None
            docs = products_model.search_by_name(name, limit=1)
            return docs[0] if docs else None

        placeholder_url = url_for('static', filename='placeholder.svg')
        enriched_items = []
        for entry in raw_items:
            if isinstance(entry, dict):
                name = entry.get('name') or ''
                img_val = entry.get('image') or ''
                product_id = entry.get('product_id') or entry.get('productId')
                stored_price = entry.get('price_val') or entry.get('price') or 0
                stored_store = entry.get('store') or ''
            else:
                name = str(entry)
                img_val = ''
                product_id = None
                stored_price = 0
                stored_store = ''

            product = product_map.get(str(product_id)) if product_id else None
            if not product:
                product = find_product_by_name(name)
                if product and not product_id:
                    product_id = product.get('id') or product.get('_id')

            if not img_val and product:
                img_val = product.get('image') or ''
            if not img_val:
                img_val = placeholder_url

            # Per-store prices for comparison column / popover
            store_prices = []
            cheapest_price = None
            cheapest_store = ''
            if product:
                for s in (product.get('stores') or []):
                    s_price = s.get('price')
                    s_name = s.get('store') or s.get('name') or ''
                    if s_price is None or not s_name:
                        continue
                    store_prices.append({'store': s_name, 'price': float(s_price)})
                    if cheapest_price is None or float(s_price) < cheapest_price:
                        cheapest_price = float(s_price)
                        cheapest_store = s_name

            db_price = float(product.get('price') or 0) if product else 0
            db_store = (product.get('store') or '') if product else ''
            final_price = cheapest_price if cheapest_price is not None else (
                float(stored_price) if stored_price and float(stored_price) > 0 else db_price)
            final_store = cheapest_store or stored_store or db_store

            if isinstance(entry, dict):
                enriched = dict(entry)
            else:
                enriched = {'name': name, 'qty': 1}
            enriched['image'] = img_val
            enriched['price_val'] = final_price
            enriched['price'] = final_price
            enriched['store'] = final_store
            enriched['store_prices'] = store_prices
            if product:
                enriched['brand'] = product.get('brand') or ''
                # Size/unit from product catalog
                enriched['size'] = product.get('sizeNormalized')
                enriched['unit'] = product.get('unitSize') or ''
                # Per-store unit price (e.g. €2.18/kg) — use store-level if available
                for s in (product.get('stores') or []):
                    if s.get('store') == final_store and s.get('unit_price') and s.get('unit_price_unit'):
                        if not enriched.get('size'):
                            # Derive size from unit price if size_normalized is missing
                            enriched['unit_price_per'] = float(s['unit_price'])
                            enriched['unit_price_unit'] = s['unit_price_unit']
                        break
            if product_id:
                enriched['product_id'] = str(product_id)
                enriched['productId'] = str(product_id)
            enriched_items.append(enriched)

        return jsonify({
            'success': True, 'list_id': list_id, 'name': target_list.get('name'),
            'icon': target_list.get('icon', 'basket'),
            'items': enriched_items, 'created_at': target_list.get('created_at'),
            'collaborators': target_list.get('collaborators', []),
            'is_shared': target_list.get('is_shared', False),
            'owner_email': target_list.get('owner_email')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/share', methods=['POST'])
def share_list_api():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        data = request.get_json() or {}
        list_id = data.get('list_id')
        target_email = data.get('target_email')
        if not list_id: return jsonify({'success': False, 'error': 'List ID is required'}), 400
        if target_email:
            role = data.get('role', 'view')
            success = users_model.share_list_with_user(user_email, list_id, target_email, role)
            if success:
                import urllib.parse
                from models.notifications_model import notifications_model
                notifications_model.create_notification({
                    'user_email': target_email, 'type': 'list_share', 'title': 'New Shared List!',
                    'message': f'Exciting news! {user_email} has invited you to collaborate on a shopping list. Click to accept!',
                    'action_url': f'/list/accept_share?list_id={list_id}&owner={urllib.parse.quote(user_email)}'
                })
            return jsonify({'success': success})
        else:
            from models.postgres_models import ShoppingList, db as sa_db
            from models.users_model import get_user_by_email
            user = get_user_by_email(user_email) or {}
            lst = ShoppingList.query.filter_by(list_id=list_id, user_id=user_email).first()
            if not lst: return jsonify({'success': False, 'error': 'List not found'}), 404
            share_code = lst.share_code or uuid.uuid4().hex[:10]
            lst.shared = True
            lst.share_code = share_code
            sa_db.session.commit()
            return jsonify({'success': True, 'share_code': share_code})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/unshare', methods=['POST'])
def unshare_list_api():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        data = request.get_json()
        list_id = data.get('list_id')
        target_email = data.get('target_email')
        success = users_model.remove_collaborator(user_email, list_id, target_email)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/<list_id>/activity', methods=['GET'])
def get_list_activity_api(list_id):
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        from models.postgres_models import ShoppingList, ListItem
        from models.users_model import _get_user_obj
        user = _get_user_obj(user_email)
        if not user: return jsonify({'success': False, 'error': 'User not found'}), 404
        lst = ShoppingList.query.filter_by(list_id=list_id).first()
        if not lst: return jsonify({'success': False, 'error': 'List not found'}), 404
        recent = ListItem.query.filter_by(list_id=lst.id).order_by(ListItem.added_at.desc()).limit(10).all()
        activity = []
        for item in recent:
            activity.append({
                'name': item.product_name or 'Unknown item',
                'added_at': item.added_at.isoformat() if item.added_at else None,
                'qty': int(item.quantity or 1),
                'checked': bool(item.checked)
            })
        return jsonify({'success': True, 'activity': activity})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/by-share/<share_code>', methods=['GET'])
def get_shared_list_api(share_code):
    try:
        from models.postgres_models import ShoppingList
        lst = ShoppingList.query.filter_by(share_code=share_code, shared=True).first()
        if not lst: return jsonify({'success': False, 'error': 'List not found'}), 404
        lst_dict = lst.to_dict()
        return jsonify({'success': True, 'list': helpers.sanitize_mongo_doc({
            'id': lst_dict.get('listId'), 'name': lst_dict.get('name'), 'items': lst_dict.get('items', []),
            'totalPrice': lst_dict.get('totalPrice', 0), 'shared': lst_dict.get('shared', False),
            'shareCode': lst_dict.get('shareCode'), 'updated_at': lst_dict.get('updated_at'),
        })})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
