from flask import jsonify, session, request, redirect, url_for, render_template
from .. import main_bp
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.quantity_discounts_model import quantity_discounts_model
from models.notifications_model import notifications_model, get_user_notifications, mark_as_read
from models.users_model import get_user_by_email, users_model
from datetime import datetime, timezone, timedelta

@main_bp.route('/notifications')
def notifications_page():
    user_email = session.get('user')
    if not user_email: return redirect(url_for('auth.login'))
    try: notifications_model.cleanup_old_notifications(7)
    except: pass
    persistent_notifications = get_user_notifications(user_email, unread_only=False, limit=50)
    ignored_types = ['deal_alert', 'new_deal', 'price_drop']
    notifications = [n for n in persistent_notifications if n.get('type') not in ignored_types]
    current_unread_count = len([n for n in notifications if not n.get('read')])

    def get_naive_date(d):
        if d is None: return datetime.min
        if isinstance(d, str):
            try: return datetime.fromisoformat(d.replace('Z', '+00:00')).replace(tzinfo=None)
            except: return datetime.min
        if isinstance(d, datetime) and d.tzinfo is not None: return d.replace(tzinfo=None)
        if isinstance(d, datetime): return d
        return datetime.min

    try:
        latest_deals_drop = featured_deals_model.get_latest_deals(limit=10)
        for d in latest_deals_drop:
            d_id = str(d.get('id') or d.get('_id'))
            offer_text = d.get('discount_label') or d.get('offer') or d.get('offer_text')
            if not offer_text and d.get('discount_percent'): offer_text = f"{d.get('discount_percent')}% OFF"
            n = {
                'id': f"suggestion_fd_{d_id}", 'type': 'price_drop',
                'title': f"Price Drop: {d.get('title') or d.get('product_name') or d.get('name')}",
                'message': d.get('description') or "Check out this amazing offer available now!",
                'created_at': get_naive_date(d.get('created_at')), 'read': False, 'deal_id': d_id,
                'product_name': d.get('title') or d.get('product_name') or d.get('name'),
                'product_image': d.get('image') or d.get('image_url'), 'store_name': d.get('store'),
                'price': d.get('price') or d.get('new_price'), 'old_price': d.get('original_price') or d.get('old_price'),
                'offer_name': offer_text, 'action_url': '#'
            }
            notifications.append(n)
            current_unread_count += 1

        latest_multibuy = multibuy_offers_model.get_latest_offers(limit=5)
        for m_offer in latest_multibuy:
            m_id = str(m_offer.get('id') or m_offer.get('_id'))
            offer_text = m_offer.get('title')
            if offer_text == "Special Offer" or not offer_text or m_offer.get('buy_quantity'):
                buy = m_offer.get('buy_quantity') or m_offer.get('min_quantity'); get_q = m_offer.get('free_quantity')
                if buy and get_q: offer_text = f"Buy {buy} Get {get_q} Free"
                elif buy: offer_text = f"Buy {buy}+ Deal"
            n = {
                'id': f"suggestion_multi_{m_id}", 'type': 'deal_alert', 'title': f"Multibuy Offer",
                'message': "Buy more, save more with this special offer!",
                'created_at': get_naive_date(m_offer.get('created_at')), 'read': False, 'deal_id': m_id,
                'product_name': m_offer.get('title') or m_offer.get('product_name'),
                'product_image': m_offer.get('image'), 'store_name': m_offer.get('store'),
                'price': m_offer.get('price'), 'old_price': m_offer.get('original_price'),
                'offer_name': offer_text, 'action_url': '#'
            }
            notifications.append(n)
            current_unread_count += 1

        latest_qty = quantity_discounts_model.get_latest_discounts(limit=3)
        for q_disc in latest_qty:
            q_id = str(q_disc.get('id') or q_disc.get('_id'))
            offer_text = "Bulk Savings"
            tiers = q_disc.get('tiers') or q_disc.get('discount_tiers') or []
            if tiers:
                t = tiers[0]
                qty = t.get('quantity') or t.get('min_qty'); disc = t.get('discount') or t.get('discount_percentage') or t.get('discount_percent')
                if qty and disc: offer_text = f"Buy {qty}+ Save {disc}%"
            n = {
                'id': f"suggestion_qty_{q_id}", 'type': 'deal_alert', 'title': "Quantity Discount",
                'message': "Stock up and save with volume discounts!",
                'created_at': get_naive_date(q_disc.get('created_at')), 'read': False, 'deal_id': q_id,
                'product_name': q_disc.get('product_name'), 'product_image': q_disc.get('image'),
                'store_name': q_disc.get('store'), 'price': q_disc.get('base_price') or q_disc.get('price'),
                'offer_name': offer_text, 'action_url': '#'
            }
            notifications.append(n)
            current_unread_count += 1
        notifications.sort(key=lambda x: get_naive_date(x.get('created_at')), reverse=True)
    except: pass

    try:
        user = get_user_by_email(user_email)
        read_dynamic_ids = set(user.get('read_dynamic_notifications', [])) if user else set()
        for n in notifications:
            if n['id'].startswith('suggestion_') and n['id'] in read_dynamic_ids: n['read'] = True
    except: pass
    unread_count = len([n for n in notifications if not n.get('read')])
    return render_template('notifications.html', notifications=notifications, unread_count=unread_count)

@main_bp.route('/api/notifications/<notification_id>', methods=['DELETE'])
def delete_notification(notification_id):
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'error': 'Not logged in'}), 401
        if notification_id.startswith('suggestion_'): return jsonify({'success': True})
        from models.notifications_model import delete_notification as dn
        success = dn(notification_id, user_email)
        return jsonify({'success': bool(success)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/notifications/unshown', methods=['GET'])
def get_unshown_notifications():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'notifications': []})
        all_notifs = get_user_notifications(user_email, unread_only=True, limit=10)
        new_deal_notifs = [n for n in all_notifs if n.get('type') == 'new_deal']
        return jsonify({'notifications': new_deal_notifs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/notifications/mark-read', methods=['POST'])
def mark_notifications_read():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'error': 'Not logged in'}), 401
        data = request.get_json()
        notification_ids = data.get('notification_ids', [])
        if not notification_ids or not isinstance(notification_ids, list): return jsonify({'error': 'IDs required'}), 400
        success_count = 0
        ids_to_mark = []; dynamic_ids = []
        for nid in notification_ids:
            if str(nid).startswith('suggestion_'): dynamic_ids.append(str(nid))
            else: ids_to_mark.append(nid)
        if dynamic_ids:
            try:
                users_model.mark_dynamic_notifications_read(user_email, dynamic_ids)
                success_count += len(dynamic_ids)
            except: pass
        if ids_to_mark:
            for nid in ids_to_mark:
                if mark_as_read(nid, user_email): success_count += 1
        return jsonify({'success': True, 'marked_count': success_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_read():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'error': 'Not logged in'}), 401
        notifications_model.mark_all_as_read(user_email)
        try:
            dynamic_ids = []
            fds = featured_deals_model.get_latest_deals(limit=10)
            dynamic_ids.extend([f"suggestion_fd_{str(d.get('id'))}" for d in fds])
            mbs = multibuy_offers_model.get_latest_offers(limit=5)
            dynamic_ids.extend([f"suggestion_multi_{str(mo.get('id'))}" for mo in mbs])
            qds = quantity_discounts_model.get_latest_discounts(limit=3)
            dynamic_ids.extend([f"suggestion_qty_{str(q.get('id'))}" for q in qds])
            if dynamic_ids:
                users_model.mark_dynamic_notifications_read(user_email, dynamic_ids)
        except: pass
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/notifications/clear-all', methods=['DELETE'])
def clear_all_notifications():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'error': 'Not logged in'}), 401
        success = notifications_model.delete_all_notifications(user_email)
        return jsonify({'success': bool(success)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
