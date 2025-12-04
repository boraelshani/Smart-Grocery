from flask import Flask, jsonify
import os
from dotenv import load_dotenv
from dotenv import load_dotenv
from routes import main_bp, auth_bp
from routes.admin_routes import admin_bp
from utils.db import mongo
import certifi

# Load .env so MONGO_URI can be provided there during development
load_dotenv()

# Ensure SSL_CERT_FILE is set for pymongo TLS if not already
if not os.environ.get('SSL_CERT_FILE'):
    os.environ['SSL_CERT_FILE'] = certifi.where()

# App setup
# Load environment variables from .env (if present)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# MongoDB configuration: prefer env var (from .env), fall back to local
raw_uri = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'
# sanitize common mistake: users sometimes paste URI with angle-brackets
if '<' in raw_uri or '>' in raw_uri:
    cleaned = raw_uri.replace('<', '').replace('>', '')
    # do not overwrite user's env permanently; just use cleaned value for app
    app.config['MONGO_URI'] = cleaned
    # also set environment so other modules that read os.getenv get the cleaned URI
    os.environ['MONGO_URI'] = cleaned
    # print masked host for debugging
    try:
        host = cleaned.split('@', 1)[1].split('/', 1)[0]
    except Exception:
        host = cleaned
    print(f"Warning: MONGO_URI contained angle-brackets; using cleaned host={host}")
else:
    app.config['MONGO_URI'] = raw_uri
    os.environ['MONGO_URI'] = raw_uri

# Initialize PyMongo with the Flask app
mongo.init_app(app)

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
    app.run(debug=True)
