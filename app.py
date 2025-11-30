from flask import Flask, jsonify
import os
from routes import main_bp, auth_bp
from routes.admin_routes import admin_bp
from utils.db import mongo

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# MongoDB configuration
# Use `MONGO_URI` environment variable when available (Atlas or custom),
# otherwise default to a local DB named `smart_grocery`.
# Read MongoDB connection from environment so credentials are not hardcoded.
# The app will use the environment variable `MONGO_URI` when present and
# fall back to a local MongoDB instance for development.
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/smart_grocery')

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

if __name__ == '__main__':
    app.run(debug=True)
