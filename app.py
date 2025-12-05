from flask import Flask, jsonify
import os
import certifi
from dotenv import load_dotenv, find_dotenv

# Load .env as early as possible so any modules imported afterwards see the variables
dotenv_path = find_dotenv('.env', usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path, override=True)
    print(f'INFO: Loaded .env from {dotenv_path}')
else:
    print('INFO: No .env file found in project root')

# Ensure SSL_CERT_FILE is set for pymongo TLS if not already
if not os.environ.get('SSL_CERT_FILE'):
    os.environ['SSL_CERT_FILE'] = certifi.where()

from utils.db import mongo
import hashlib
from flask import url_for

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# MongoDB configuration: prefer MONGO_URI from the .env we just loaded (if present),
# otherwise fall back to process environment or local MongoDB.
dotenv_uri = None
try:
    # if .env exists and provided MONGO_URI, prefer that (we loaded it with override=True above)
    dotenv_uri = os.environ.get('MONGO_URI')
except Exception:
    dotenv_uri = None

raw_uri = dotenv_uri or os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'
# sanitize common mistake: users sometimes paste URI with angle-brackets
if '<' in raw_uri or '>' in raw_uri:
    cleaned = raw_uri.replace('<', '').replace('>', '')
    # use cleaned value for app config but do NOT overwrite the process environment
    app.config['MONGO_URI'] = cleaned
    # print masked host for debugging
    try:
        host = cleaned.split('@', 1)[1].split('/', 1)[0]
    except Exception:
        host = cleaned
    print(f"Warning: MONGO_URI contained angle-brackets; using cleaned host={host}")
else:
    app.config['MONGO_URI'] = raw_uri

uri = app.config.get('MONGO_URI') or os.environ.get('MONGO_URI')
if uri:
    try:
        if uri.rstrip().endswith('/') or '/' not in uri.split('@')[-1]:
            app.config.setdefault('MONGO_DBNAME', 'smart_grocery')
            print('INFO: MONGO_URI had no DB path; setting MONGO_DBNAME=smart_grocery')
    except Exception:
        pass

# Initialize PyMongo with the Flask app
mongo.init_app(app)

# Now import the blueprints (after PyMongo initialized) so routes can safely access `mongo`
from routes import main_bp, auth_bp
from routes.admin_routes import admin_bp

# Log which DB and collections we're connected to (helpful to debug wrong DB selection)
try:
    # prefer explicit MONGO_DBNAME config, otherwise inspect the client's default DB
    db_name = app.config.get('MONGO_DBNAME') or (getattr(mongo, 'db', None) and getattr(mongo.db, 'name', None))
    print(f'INFO: Using MONGO_URI={app.config.get("MONGO_URI")}, MONGO_DBNAME={db_name}')
    if getattr(mongo, 'db', None) is not None:
        try:
            cols = mongo.db.list_collection_names()
            print('INFO: Collections in DB:', cols)
            for c in cols:
                try:
                    cnt = mongo.db[c].count_documents({})
                except Exception as e:
                    cnt = f'error:{e}'
                print(f'  - {c}: {cnt}')
        except Exception as e:
            print('INFO: Could not list collections:', e)
except Exception as e:
    print('INFO: MongoDB introspection failed at startup:', e)

# Ensure users.email has a unique index to prevent duplicate accounts when using MongoDB
try:
    if getattr(mongo, 'db', None) is not None:
        mongo.db.users.create_index('email', unique=True)
except Exception:
    pass

# If Mongo is available and users collection is empty, seed mock users from models.models
try:
    from models import models as mock_models
    if getattr(mongo, 'db', None) is not None:
        try:
            users_count = mongo.db.users.count_documents({})
            if users_count == 0 and isinstance(getattr(mock_models, 'users', None), dict):
                to_insert = []
                for email, u in mock_models.users.items():
                    # copy dict and ensure email present
                    doc = dict(u)
                    doc.setdefault('email', email)
                    to_insert.append(doc)
                if to_insert:
                    mongo.db.users.insert_many(to_insert)
        except Exception:
            # ignore DB seeding errors in development
            pass
except Exception:
    pass

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)


# Template helper: prefer a processed local image if available (static/processed/<sha1>.webp)
def processed_image_url(image_url: str | None) -> str | None:
    if not image_url:
        return None
    try:
        key = hashlib.sha1(image_url.encode('utf-8')).hexdigest() + '.webp'
        path = os.path.join(app.root_path, 'static', 'processed', key)
        if os.path.exists(path):
            return url_for('static', filename=f'processed/{key}')
    except Exception:
        pass
    return None

# convenience wrapper for templates: returns processed URL if exists, otherwise returns original image_url
def prefer_processed(image_url: str | None) -> str | None:
    return processed_image_url(image_url) or image_url

app.jinja_env.globals['processed_image_url'] = processed_image_url
app.jinja_env.globals['prefer_processed'] = prefer_processed

# Error Handling
@app.errorhandler(404)
def not_found(error):
    from flask import render_template
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    from flask import render_template
    return render_template('500.html'), 500


# Health check endpoint to verify MongoDB connectivity
@app.route('/health')
def health():
    try:
        # Prefer the Flask-PyMongo instance if available
        if getattr(mongo, 'db', None) is not None:
            mongo.db.command('ping')
        else:
            # Fallback: try a direct pymongo connection using the configured URI
            from pymongo import MongoClient
            uri = app.config.get('MONGO_URI')
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
        return jsonify({'status': 'ok', 'mongo': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'mongo': 'disconnected', 'detail': str(e)}), 500


@app.route('/debug-mongo')
def debug_mongo():
    # Return config and client info so we can tell which host/DB the app connected to
    info = {'app_config_mongo_uri': app.config.get('MONGO_URI'), 'app_config_dbname': app.config.get('MONGO_DBNAME')}
    try:
        if getattr(mongo, 'db', None) is not None:
            info['mongo_db_name'] = getattr(mongo.db, 'name', None)
            try:
                # try to reach the server and show the client addresses
                client = getattr(mongo, 'cx', None) or getattr(mongo, 'client', None) or getattr(mongo, '_client', None)
                if client is None:
                    try:
                        client = mongo.db.client
                    except Exception:
                        client = None
                if client is not None:
                    try:
                        # list hosts/servers
                        info['client_info'] = str(getattr(client, 'address', getattr(client, 'hosts', getattr(client, 'nodes', None))))
                    except Exception as ex:
                        info['client_info_error'] = str(ex)
            except Exception:
                pass
    except Exception as e:
        info['error'] = str(e)
    return jsonify(info)

# Temporary test route to insert a small document into Atlas for verification
@app.route('/add-test')
def add_test():
    try:
        test_data = {"name": "Test Product", "price": 9.99}
        res = mongo.db.products.insert_one(test_data)
        return jsonify({'success': True, 'inserted_id': str(res.inserted_id)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run()