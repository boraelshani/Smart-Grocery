from flask import Blueprint, request, jsonify, current_app
from utils.db import mongo

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
        res = mongo.db.products.update_one(key, {'$set': set_doc}, upsert=True)
        if getattr(res, 'upserted_id', None):
            return jsonify({'status': 'ok', 'action': 'created', 'id': str(res.upserted_id)}), 201
        else:
            return jsonify({'status': 'ok', 'action': 'updated'}), 200
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
        # prefer Flask-PyMongo db if available
        if getattr(mongo, 'db', None) is not None:
            db = mongo.db
        else:
            from pymongo import MongoClient
            uri = current_app.config.get('MONGO_URI')
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            # pick DB from URI if present
            db = client.get_database()

        name = getattr(db, 'name', None) or current_app.config.get('MONGO_URI')
        cols = db.list_collection_names()
        counts = {c: db[c].count_documents({}) for c in cols}
        return jsonify({'db_name': name, 'collections': counts}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'detail': str(e)}), 500
