"""
╔══════════════════════════════════════════════════════════════════════════╗
║                    SMART GROCERY - MAIN APPLICATION                       ║
║  A Flask-based price comparison web app for grocery shopping.             ║
║  Compares product prices across multiple stores and tracks shopping lists.║
║                                                                          ║
║  Key Features:                                                           ║
║  - Flask Web Server                                                      ║
║  - MongoDB Integration (Production) with Fallback (Local)                ║
║  - User Authentication                                                   ║
║  - Blueprints for Code Organization                                      ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time

# ═══════════════════════════════════════════════════════════════════════════
# 0. SELF-REEXECUTION: Automatically use the virtual environment
# ═══════════════════════════════════════════════════════════════════════════
def ensure_venv():
    """
    Ensure the application uses the Python interpreter from the virtual environment.
    If the current interpreter is not the one in 'venv' or '.venv', it re-executes 
    the script using the correct interpreter.
    
    Why: Keeps dependencies isolated and ensures everyone runs the code with the 
    same library versions defined in requirements.txt.
    """
    # Get the absolute path of the directory where this script (app.py) is located.
    # This helps us build paths relative to the project root, no matter where the script is run from.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # We check for two common names for virtual environment folders: 'venv' and '.venv'.
    # This allows flexibility for different developers' setups.
    venv_options = ['venv', '.venv']
    
    for venv_name in venv_options:
        # Determine the expected path to the python executable within the virtual environment.
        # This differs between Windows and Unix-based systems (Linux/macOS).
        if sys.platform == "win32":
            # On Windows, the python executable is inside the 'Scripts' folder.
            venv_python = os.path.join(current_dir, venv_name, 'Scripts', 'python.exe')
        else:
            # On Linux/Mac, the python executable is inside the 'bin' folder.
            venv_python = os.path.join(current_dir, venv_name, 'bin', 'python')
        
        # Check two conditions before switching:
        # 1. Does the virtual environment python executable actually exist at that path?
        # 2. Is the currently running python interpreter (sys.executable) DIFFERENT from the venv python?
        if os.path.exists(venv_python) and sys.executable != venv_python and not os.environ.get('VENV_RESTARTED'):
            print(f"INFO: Auto-switching to virtual environment: {venv_python}")
            try:
                # Use os.execv to replace the current process image with a new process.
                # This effectively restarts the script using the correct Python interpreter.
                # The arguments passed are [venv_python, script_name, ...other_args].
                os.environ['VENV_RESTARTED'] = '1'
                os.execv(venv_python, [venv_python] + sys.argv)
            except Exception as e:
                # If something goes wrong (e.g., permission error), catch the exception 
                # and print a warning, but continue running (maybe with the system python).
                print(f"WARNING: Could not switch to venv: {e}")
            
            # If we found a valid venv and attempted to switch, we break the loop.
            # (Note: os.execv does not return if successful, so this break only runs on failure).
            break

ensure_venv()

from flask import Flask, jsonify, session, request
import certifi
from dotenv import load_dotenv, find_dotenv

# ═══════════════════════════════════════════════════════════════════════════
# 1. ENVIRONMENT SETUP: Load configuration from .env file
# ═══════════════════════════════════════════════════════════════════════════
# Find the .env file in the project directory or parent directories.
# 'usecwd=True' ensures we look starting from the current working directory.
dotenv_path = find_dotenv('.env', usecwd=True)

# If a .env file is found, load the variables into os.environ.
# 'override=True' means variables in .env will overwrite existing system environment variables.
if dotenv_path:
    load_dotenv(dotenv_path, override=True)
    print(f'INFO: Loaded .env from {dotenv_path}')
else:
    # Inform the user if no configuration file was found (defaults will be used later).
    print('INFO: No .env file found in project root')

# Ensure SSL_CERT_FILE is set for pymongo TLS if not already.
# MongoDB Atlas (cloud version) requires secure connections using SSL/TLS.
# certifi.where() provides the path to a bundle of trusted CA certificates.
if not os.environ.get('SSL_CERT_FILE'):
    os.environ['SSL_CERT_FILE'] = certifi.where()

from utils.db import mongo, sanitize_uri

# Short-lived in-memory cache for expensive navbar counters.
_NAVBAR_CACHE_TTL_SEC = 20
_navbar_cache = {}

# ═══════════════════════════════════════════════════════════════════════════
# 2. FLASK APP INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════
# Create the Flask application instance.
# __name__ is passed to let Flask know where to look for resources like templates and static files.
app = Flask(__name__)

# SECRET_KEY is crucial for security. usage:
# 1. It signs the session cookie so users can't tamper with their session data (like claiming to be logged in).
# 2. It's used for CSRF protection in forms.
# We try to get it from environment variables, but fall back to 'dev-secret-key' for local development.
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# JWT_SECRET_KEY is specifically for JSON Web Token encryption.
# This often matches the app secret key but can be separate.
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', app.secret_key)
app.config['ADMIN_EMAILS'] = os.environ.get('ADMIN_EMAILS', '')
app.config['ENABLE_HOME_RECOMMENDATIONS'] = os.environ.get('ENABLE_HOME_RECOMMENDATIONS', 'false').lower() == 'true'
app.config['ENABLE_LIST_PROMO_ENRICHMENT'] = os.environ.get('ENABLE_LIST_PROMO_ENRICHMENT', 'false').lower() == 'true'
app.config['ENABLE_LIST_MARK_SEEN_ON_RENDER'] = os.environ.get('ENABLE_LIST_MARK_SEEN_ON_RENDER', 'false').lower() == 'true'

# ═══════════════════════════════════════════════════════════════════════════
# 3. MONGODB CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
# Retrieve the MongoDB connection string (URI) from environment variables.
# Format: mongodb+srv://<username>:<password>@cluster.mongodb.net/database
raw_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/smart_grocery')

# Sanitize the URI using a helper function.
# This fixes common user errors, like leaving '<password>' placeholders or extra whitespace.
app.config['MONGO_URI'] = sanitize_uri(raw_uri)


# Set default database name if the URI doesn't explicitly specify one.
# We parse the URI string; if no database name is found after the slashes/at-sign, we add 'smart_grocery'.
if '/' not in raw_uri.split('@')[-1].rstrip('/'):
    app.config.setdefault('MONGO_DBNAME', 'smart_grocery')

# Initialize PyMongo with the Flask app.
# We wrap this in a try-except block to handle connection failures gracefully.
# This allows the app to start in "Offline/Fallback Mode" if the database is unreachable.
try:
    # Set a timeout for the initial connection attempt (5000ms = 5 seconds).
    # This prevents the app from hanging indefinitely if the network is down.
    app.config['MONGO_CONNECTTIMEOUTMS'] = 5000 
    
    # Set a timeout for selecting a server (finding a master node in a replica set).
    app.config['MONGO_SERVERSELECTIONTIMEOUTMS'] = 5000
    
    # Bind the PyMongo instance to our Flask app.
    mongo.init_app(app)
    
    # Verify the connection immediately within the application context.
    with app.app_context():
        # Check if the 'db' attribute was successfully attached to the mongo object.
        if mongo.db is not None:
            # Execute the 'ping' command. This is a lightweight command to check connectivity.
            # If this raises an exception, we know we can't talk to the database.
            mongo.db.command('ping')
            print("INFO: MongoDB connection verified.")
except Exception as e:
    # If any error occurs during setup or ping, print it and warn about fallback mode.
    # The app will continue running, but will likely use local JSON files instead of the database.
    print(f'WARNING: MongoDB initialization or connection failed: {e}')
    print('INFO: Running in fallback mode with local JSON data.')

# Now import the blueprints (after PyMongo attempted initialization)
from routes import main_bp, auth_bp, admin_bp, compare_engine_bp, recipe_bp

# Log connection info
try:
    # getattr(mongo, 'db', None) checks if the database connection was successful.
    if getattr(mongo, 'db', None) is not None:
        db_name = app.config.get('MONGO_DBNAME') or getattr(mongo.db, 'name', None)
        print(f'INFO: Connected to MongoDB database: {db_name}')
except Exception as e:
    print(f'INFO: MongoDB connection check failed: {e}')

# Ensure users.email has a unique index to prevent duplicate accounts when using MongoDB
try:
    if getattr(mongo, 'db', None) is not None:
        mongo.db.users.create_index('email', unique=True)
        mongo.db.notifications.create_index([
            ('user_email', 1),
            ('read', 1),
            ('created_at', -1),
        ])
        mongo.db.lists.create_index([
            ('userId', 1),
            ('updatedAt', -1),
        ])
        mongo.db.lists.create_index([
            ('userId', 1),
            ('items.is_new', 1),
        ])
except Exception:
    pass

# Seed mock users if database is empty - helpful for first-time setup
try:
    if getattr(mongo, 'db', None) is not None and mongo.db.users.count_documents({}) == 0:
        from models import models as mock_models
        # Iterate through our mock data and insert it into the real DB
        if isinstance(getattr(mock_models, 'users', None), dict):
            users_to_insert = [{**u, 'email': email} for email, u in mock_models.users.items()]
            if users_to_insert:
                mongo.db.users.insert_many(users_to_insert)
except Exception:
    pass

# Register blueprints - these organize routes into logical groups (Main, Auth, Admin)
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(compare_engine_bp, url_prefix='/api/compare')
app.register_blueprint(recipe_bp)


@app.context_processor
def inject_navbar_data():
    """
    Expose dynamic navbar data to all templates automatically.
    
    Returns:
        dict: containing 'shopping_list_count' and 'unread_notifications_count'
              available in every Jinja2 template.
    """
    shopping_list_count = 0
    unread_notifications_count = 0
    current_user_nav = None
    is_admin_nav = False
    try:
        email = session.get('user')
        if email:
            # Fast path: use very short cache to avoid repeating heavy DB reads
            # on rapid refreshes and frequent AJAX-triggered page renders.
            cache_entry = _navbar_cache.get(email)
            now_ts = time.time()
            if cache_entry and cache_entry.get('expires_at', 0) > now_ts:
                cached = cache_entry.get('value', {})
                return {
                    'shopping_list_count': int(cached.get('shopping_list_count', 0)),
                    'unread_notifications_count': int(cached.get('unread_notifications_count', 0)),
                    'current_user_nav': cached.get('current_user_nav'),
                    'is_admin_nav': bool(cached.get('is_admin_nav', False)),
                }

            user = {}
            if getattr(mongo, 'db', None) is not None:
                user = mongo.db.users.find_one(
                    {'email': email},
                    {
                        '_id': 0,
                        'email': 1,
                        'userId': 1,
                        'name': 1,
                        'avatar': 1,
                        'is_admin': 1,
                    },
                ) or {}

            display_name = (user.get('name') or email.split('@')[0]).strip()
            initials = ''.join(part[:1] for part in display_name.split()[:2]).upper() or display_name[:1].upper()
            current_user_nav = {
                'email': email,
                'name': user.get('name') or '',
                'display_name': display_name,
                'avatar': user.get('avatar') or '',
                'initials': initials,
            }

            admin_emails = {e.strip().lower() for e in str(app.config.get('ADMIN_EMAILS', '')).split(',') if e.strip()}
            is_admin_nav = bool(user.get('is_admin')) or (email.lower() in admin_emails)

            if getattr(mongo, 'db', None) is not None:
                from datetime import datetime, timedelta
                unread_notifications_count = mongo.db.notifications.count_documents({
                    'user_email': email,
                    'read': False,
                    'created_at': {'$gte': datetime.utcnow() - timedelta(days=7)},
                })

                owner_key = str(user.get('userId') or email)
                agg = list(mongo.db.lists.aggregate([
                    {'$match': {'userId': owner_key}},
                    {'$unwind': '$items'},
                    {'$match': {'items.is_new': True}},
                    {'$count': 'count'},
                ]))
                shopping_list_count = int((agg[0] if agg else {}).get('count', 0))

            _navbar_cache[email] = {
                'expires_at': now_ts + _NAVBAR_CACHE_TTL_SEC,
                'value': {
                    'shopping_list_count': shopping_list_count,
                    'unread_notifications_count': unread_notifications_count,
                    'current_user_nav': current_user_nav,
                    'is_admin_nav': is_admin_nav,
                },
            }
    except Exception:
        # Fail silently to avoid breaking the entire page if notification count fails
        pass
        
    return {
        'shopping_list_count': shopping_list_count,
        'unread_notifications_count': unread_notifications_count,
        'current_user_nav': current_user_nav,
        'is_admin_nav': is_admin_nav,
    }


# Template helper: return image URL as-is (processed image functionality removed)
def prefer_processed(image_url: str | None) -> str | None:
    """Return the image URL unchanged. Previously handled processed images."""
    return image_url

app.jinja_env.globals['prefer_processed'] = prefer_processed


# Error Handling
# These handlers catch HTTP errors and render friendly HTML pages
@app.errorhandler(404)
def not_found(error):
    from flask import render_template
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    from flask import render_template
    return render_template('500.html'), 500


# Health check endpoint to verify MongoDB connectivity (Equivalent to a Heartbeat)
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
    """
    Debug route to inspect MongoDB connection details.
    Useful for troubleshooting connection issues in different environments.
    """
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
    # use_reloader=False prevents WinError 10038 on some Windows environments
    app.run(debug=True, use_reloader=False, port=5000)
