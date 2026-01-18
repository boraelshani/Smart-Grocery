"""
═══════════════════════════════════════════════════════════════════════════
ADMIN ROUTES - Administrative Functions
═══════════════════════════════════════════════════════════════════════════
Purpose: Handle admin-only operations and data management
Routes:
- Add/edit/delete products
- Manage featured deals
- Upload product images
- View analytics/statistics
Prefix: /admin
Security: Should be restricted to admin users only
═══════════════════════════════════════════════════════════════════════════
"""

from flask import Blueprint, request, jsonify, current_app
from models.products_model import products_model
from models.stores_model import stores_model
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.notifications_model import notifications_model

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _require_token():
    """Return None if OK, otherwise a tuple (response, status). If ADMIN_TOKEN is set in
    the environment/app config, require callers to provide header 'X-Admin-Token'."""
    token = current_app.config.get('ADMIN_TOKEN') or None
    if not token:
        return None
    hdr = request.headers.get('X-Admin-Token')
    if not hdr or hdr != token:
        return jsonify({'status': 'error', 'detail': 'missing or invalid admin token'}), 403
    return None


@admin_bp.route('/product', methods=['POST'])
def add_or_update_product():
    """Upsert a single product document.

    Expected JSON body (example):
    {
      "name": "Organic Bananas",
    "price": "€1.29",
      "price_val": 1.29,
      "image": "https://cdn.example/42e9as7nataai4a6jcufwg.jpg",
      "images": ["https://.../1.jpg"],
      "category": "Produce",
    "stores": [{"store":"FreshMart","price":"€1.29"}],
      "description": "...",
      "qty": 1
    }

    The route will use `name` as the unique key when present, otherwise `_id` if provided.
    """
    # optional token protection
    err = _require_token()
    if err:
        return err

    if not request.is_json:
        return jsonify({'status': 'error', 'detail': 'expected JSON body'}), 400

    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({'status': 'error', 'detail': 'invalid JSON body'}), 400

    # determine key
    key = None
    if data.get('name'):
        key = {'name': data['name']}
    elif data.get('_id'):
        key = {'_id': data['_id']}
    else:
        return jsonify({'status': 'error', 'detail': 'provide at least a "name" or "_id" field'}), 400

    # remove _id from set data to avoid immutable id conflicts
    set_doc = {k: v for k, v in data.items() if k != '_id'}

    try:
        # Check for price drop if product exists using model
        old_price = None
        existing_product = products_model.get_product_by_name(data.get('name')) if data.get('name') else None
        if not existing_product and data.get('_id'):
             existing_product = products_model.get_product_by_id(str(data.get('_id')))
             
        if existing_product:
            old_price = existing_product.get('price_val')

        # Use model for upsert
        res = products_model.upsert_product(key, set_doc)
        
        # Determine if it's a new product or an update
        action = 'updated'
        product_id = existing_product.get('id') if existing_product else None
        
        if res.get('upserted_id'):
            action = 'created'
            product_id = str(res.get('upserted_id'))
            
            # BROADCAST: New Product Alert using Model
            notifications_model.broadcast_notification({
                'type': 'system',
                'title': f"New Product: {set_doc.get('name')}",
                'message': f"A new product has been added to our catalog: {set_doc.get('name')} for only €{set_doc.get('price_val', 0):.2f}!",
                'product_id': product_id,
                'priority': 'normal'
            })
        elif old_price and set_doc.get('price_val') and float(set_doc.get('price_val')) < float(old_price):
            # BROADCAST: Price Drop Alert
            from models.notifications_model import NotificationsModel
            nm = NotificationsModel()
            nm.broadcast_notification({
                'type': 'price_drop',
                'title': f"Price Drop: {set_doc.get('name')}",
                'message': f"Price fell from €{old_price:.2f} to €{set_doc.get('price_val'):.2f}! Save money today.",
                'product_id': product_id,
                'priority': 'high',
                'old_price': old_price,
                'price': set_doc.get('price_val')
            })

        return jsonify({'status': 'ok', 'action': action, 'id': product_id}), 201 if action == 'created' else 200
    except Exception as e:
        return jsonify({'status': 'error', 'detail': str(e)}), 500


@admin_bp.route('/dbinfo', methods=['GET'])
def db_info():
    """Return the database name and document counts for key collections.
    Protected by ADMIN_TOKEN if set.
    """
    err = _require_token()
    if err:
        return err

    try:
        from models.models import get_db_info
        info = get_db_info()
        return jsonify(info), 200
    except Exception as e:
        return jsonify({'status': 'error', 'detail': str(e)}), 500


@admin_bp.route('/featured-deal', methods=['POST'])
def add_featured_deal():
    """Add a new featured deal and notify all users."""
    err = _require_token()
    if err:
        return err

    if not request.is_json:
        return jsonify({'status': 'error', 'detail': 'expected JSON body'}), 400

    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify({'status': 'error', 'detail': 'missing "title" in deal data'}), 400

    try:
        from models.featured_deals_model import FeaturedDealsModel
        fdm = FeaturedDealsModel()
        deal_id = fdm.insert_deal(data)

        # BROADCAST: New Deal Alert
        from models.notifications_model import NotificationsModel
        nm = NotificationsModel()
        nm.broadcast_notification({
            'type': 'deal_alert',
            'title': f"HOT DEAL: {data.get('title')}",
            'message': f"New discount available: {data.get('description', 'Check out the new deal!')}",
            'product_id': data.get('product_id'),
            'priority': 'high'
        })

        return jsonify({'status': 'ok', 'action': 'created', 'id': deal_id}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'detail': str(e)}), 500
