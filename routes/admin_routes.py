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

# Log the blueprint setup
# 'url_prefix' ensures all routes here start with /admin
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _require_token():
    """
    HELPER: Token Verification
    --------------------------
    A private helper to secure admin routes.
    
    Logic:
    1. Check if 'ADMIN_TOKEN' is configured (env var or app config).
    2. If NOT configured, assume development mode/unsecured and allow access (Return None).
    3. If configured, check for 'X-Admin-Token' in request headers.
    4. If header matches token => Allow.
    5. If header mismatch => Return 403 Forbidden.
    
    Returns:
        None if access granted.
        Tuple (JSON response, 403) if access denied.
    """
    token = current_app.config.get('ADMIN_TOKEN') or None
    if not token:
        # Security Warning: No token required if variable not set!
        return None
        
    hdr = request.headers.get('X-Admin-Token')
    if not hdr or hdr != token:
        return jsonify({'status': 'error', 'detail': 'missing or invalid admin token'}), 403
    return None


@admin_bp.route('/product', methods=['POST'])
def add_or_update_product():
    """
    Upsert (Update or Insert) a single product document.

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
      "qty": 1,
      "_id": "OPTIONAL_ID_FOR_UPDATES"
    }

    Logic:
    1. Verify Admin Token.
    2. Validate JSON payload.
    3. Determine uniqueness key: Use 'name' or '_id'.
    4. Call Model to perform upsert.
    5. If New Product -> Broadcast 'New Product' notification.
    6. If Price Drop -> Broadcast 'Price Drop' notification.
    """
    # 1. SECURITY CHECK
    err = _require_token()
    if err:
        return err

    # 2. INPUT VALIDATION
    if not request.is_json:
        return jsonify({'status': 'error', 'detail': 'expected JSON body'}), 400

    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({'status': 'error', 'detail': 'invalid JSON body'}), 400

    # 3. DETERMINE LOOKUP KEY
    # We need to know which document to update. 
    # Prefer 'name' (user friendly unique key) or '_id' (system unique key).
    key = None
    if data.get('name'):
        key = {'name': data['name']}
    elif data.get('_id'):
        key = {'_id': data['_id']}
    else:
        return jsonify({'status': 'error', 'detail': 'provide at least a "name" or "_id" field'}), 400

    # Clean the data: remove '_id' from the update payload to prevent
    # "Modifying the immutable _id" errors from MongoDB.
    set_doc = {k: v for k, v in data.items() if k != '_id'}

    try:
        # 4. PRE-CHECK FOR NOTIFICATIONS (Get existing state)
        old_price = None
        existing_product = None
        
        # Try to find the product before we change it
        if data.get('name'):
            existing_product = products_model.get_product_by_name(data.get('name'))
        
        if not existing_product and data.get('_id'):
             existing_product = products_model.get_product_by_id(str(data.get('_id')))
             
        if existing_product:
            old_price = existing_product.get('price_val')

        # 5. EXECUTE UPSERT via Model
        res = products_model.upsert_product(key, set_doc)
        
        # Determine if it was an INSERT (new) or UPDATE (existing)
        action = 'updated'
        product_id = existing_product.get('id') if existing_product else None
        
        # upserted_id is only present if a new document was created
        if res.get('upserted_id'):
            action = 'created'
            product_id = str(res.get('upserted_id'))
            
            # 6a. BROADCAST: NEW PRODUCT
            # Notify users that a new item is available
            notifications_model.broadcast_notification({
                'type': 'deal_alert', # Uses deal_alert type for rich styling
                'title': f"New Product: {set_doc.get('name')}",
                'message': f"Available now! {set_doc.get('name')} has been added to our catalog.",
                'product_id': product_id,
                'priority': 'normal',
                # redundant data for rich card immediate rendering without DB lookup
                'product_name': set_doc.get('name'),
                'product_image': set_doc.get('image'),
                'price': set_doc.get('price_val'), 
                'store_name': 'New Arrival'
            })
            
        elif old_price and set_doc.get('price_val') and float(set_doc.get('price_val')) < float(old_price):
            # 6b. BROADCAST: PRICE DROP
            # Only if price is lower than before
            diff = float(old_price) - float(set_doc.get('price_val'))
            notifications_model.broadcast_notification({
                'type': 'price_drop',
                'title': f"Price Drop: {set_doc.get('name')}",
                'message': f"Great news! The price dropped by €{diff:.2f}.",
                'product_id': product_id,
                'priority': 'high',
                'price': set_doc.get('price_val'),
                'old_price': old_price,
                # Context data for notification card
                'product_name': set_doc.get('name'),
                'product_image': set_doc.get('image')
            })

        return jsonify({'status': 'ok', 'action': action, 'id': product_id}), 201 if action == 'created' else 200
        
    except Exception as e:
        # Catch DB errors and return 500
        return jsonify({'status': 'error', 'detail': str(e)}), 500


@admin_bp.route('/dbinfo', methods=['GET'])
def db_info():
    """
    Get Database Statistics.
    
    Returns:
        JSON object containing counts of products, users, deals, etc.
        Useful for admin dashboard widgets.
        
    Security:
        Protected by ADMIN_TOKEN.
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
    """
    Add a new featured deal manually.
    
    Trigger:
    - User/Admin submits form to promote a product.
    
    Side Effects:
    - Inserts record into 'featured_deals' collection.
    - Sends a HIGH PRIORITY push notification to all users.
    """
    err = _require_token()
    if err:
        return err

    if not request.is_json:
        return jsonify({'status': 'error', 'detail': 'expected JSON body'}), 400

    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify({'status': 'error', 'detail': 'missing "title" in deal data'}), 400

    try:
        # 1. Insert into DB
        from models.featured_deals_model import FeaturedDealsModel
        fdm = FeaturedDealsModel()
        deal_id = fdm.insert_deal(data)

        # 2. BROADCAST NOTIFICATION
        # Grab the global NotificationsModel instance
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
