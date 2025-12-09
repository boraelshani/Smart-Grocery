from flask import Flask, jsonify, session, request
import os
import certifi
from dotenv import load_dotenv, find_dotenv

# 1. LOAD CONFIG: Read environment variables from .env file
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

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# MongoDB configuration
raw_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/smart_grocery')
# Sanitize URI if it contains angle brackets
if '<' in raw_uri or '>' in raw_uri:
    raw_uri = raw_uri.replace('<', '').replace('>', '')

app.config['MONGO_URI'] = raw_uri

# Set default database name if URI doesn't specify one
if '/' not in raw_uri.split('@')[-1].rstrip('/'):
    app.config.setdefault('MONGO_DBNAME', 'smart_grocery')

# Initialize PyMongo with the Flask app
mongo.init_app(app)

# Now import the blueprints (after PyMongo initialized) so routes can safely access `mongo`
from routes import main_bp, auth_bp
from routes.admin_routes import admin_bp

# Log connection info
try:
    if getattr(mongo, 'db', None) is not None:
        db_name = app.config.get('MONGO_DBNAME') or getattr(mongo.db, 'name', None)
        print(f'INFO: Connected to MongoDB database: {db_name}')
except Exception as e:
    print(f'INFO: MongoDB connection check failed: {e}')

# Ensure users.email has a unique index to prevent duplicate accounts when using MongoDB
try:
    if getattr(mongo, 'db', None) is not None:
        mongo.db.users.create_index('email', unique=True)
except Exception:
    pass

# Seed mock users if database is empty
try:
    if getattr(mongo, 'db', None) is not None and mongo.db.users.count_documents({}) == 0:
        from models import models as mock_models
        if isinstance(getattr(mock_models, 'users', None), dict):
            users_to_insert = [{**u, 'email': email} for email, u in mock_models.users.items()]
            if users_to_insert:
                mongo.db.users.insert_many(users_to_insert)
except Exception:
    pass

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)


@app.context_processor
def inject_shopping_list_count():
    """Expose a shopping list count for nav badges; only shows count for new items since last viewing."""
    count = 0
    try:
        email = session.get('user')
        if email:
            from models.users_model import get_user_lists
            data = get_user_lists(email) or {}
            lists = data.get('lists', []) or []
            total = 0
            for lst in lists:
                items = lst.get('items', []) or []
                total += sum(1 for it in items if not (isinstance(it, dict) and it.get('purchased')))
            
            # Only show badge if count has increased since last viewing
            last_viewed = session.get('last_viewed_list_count', 0)
            if total > last_viewed:
                count = total - last_viewed
            else:
                count = 0
    except Exception:
        count = 0
    return {'shopping_list_count': count}


# Template helper: return image URL as-is (processed image functionality removed)
def prefer_processed(image_url: str | None) -> str | None:
    """Return the image URL unchanged. Previously handled processed images."""
    return image_url

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


if __name__ == '__main__':
    app.run(debug=True)