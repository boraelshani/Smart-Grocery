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

# No longer importing mongo
# from utils.db import mongo, sanitize_uri

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

# Fetch the PostgreSQL URI from environment variables with a fallback (though Neon should always be defined in .env)
raw_uri = os.environ.get('SQLALCHEMY_DATABASE_URI')
if not raw_uri:
    print("WARNING: SQLALCHEMY_DATABASE_URI is not set in the environment.")
    raw_uri = "sqlite:///:memory:"

app.config['SQLALCHEMY_DATABASE_URI'] = raw_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

try:
    from models.postgres_models import db
    db.init_app(app)
    
    with app.app_context():
        # Verify the connection immediately
        db.engine.connect()
        print("INFO: PostgreSQL connection verified.")
except Exception as e:
    print(f'WARNING: PostgreSQL initialization or connection failed: {e}')
    print('INFO: Running in fallback mode.')

# Now import the blueprints
from routes import main_bp, auth_bp, admin_bp, api_bp, compare_engine_bp, recipe_bp

# Register blueprints - these organize routes into logical groups (Main, Auth, Admin)
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(compare_engine_bp, url_prefix='/api/compare')
app.register_blueprint(recipe_bp)



@app.context_processor
def inject_navbar_data():
    shopping_list_count = 0
    unread_notifications_count = 0
    current_user_nav = None
    is_admin_nav = False
    try:
        email = session.get('user')
        if email:
            cache_entry = _navbar_cache.get(email)
            now_ts = time.time()
            if cache_entry and cache_entry.get('expires_at', 0) > now_ts:
                cached = cache_entry.get('value', {})
                try:
                    from utils.menu_data import get_mega_menu
                    mega_menu_data = get_mega_menu()
                except Exception:
                    mega_menu_data = {"categories": {}, "brands": [], "images": {}, "fallback_image": ""}
                
                return {
                    'shopping_list_count': int(cached.get('shopping_list_count', 0)),
                    'unread_notifications_count': int(cached.get('unread_notifications_count', 0)),
                    'current_user_nav': cached.get('current_user_nav'),
                    'is_admin_nav': bool(cached.get('is_admin_nav', False)),
                    'mega_menu': mega_menu_data,
                }

            from models.postgres_models import db, User, ShoppingList
            user = User.query.filter_by(email=email).first()

            if user:
                display_name = (user.name or email.split('@')[0]).strip()
                initials = ''.join(part[:1] for part in display_name.split()[:2]).upper() or display_name[:1].upper()
                current_user_nav = {
                    'email': user.email,
                    'name': user.name or '',
                    'display_name': display_name,
                    'avatar': user.avatar or '',
                    'initials': initials,
                }
                admin_emails = {e.strip().lower() for e in str(app.config.get('ADMIN_EMAILS', '')).split(',') if e.strip()}
                is_admin_nav = (email.lower() in admin_emails)

                # TODO: add notification model if added later
                
                # Fetch lists count
                shopping_list_count = len(user.shopping_lists)

                _navbar_cache[email] = {
                    'expires_at': now_ts + _NAVBAR_CACHE_TTL_SEC,
                    'value': {
                        'shopping_list_count': shopping_list_count,
                        'unread_notifications_count': unread_notifications_count,
                        'current_user_nav': current_user_nav,
                        'is_admin_nav': is_admin_nav,
                    },
                }
    except Exception as e:
        print(f"Navbar injection error: {e}")
        
    try:
        from utils.menu_data import get_mega_menu
        mega_menu_data = get_mega_menu()
    except Exception:
        mega_menu_data = {"categories": {}, "brands": [], "images": {}, "fallback_image": ""}

    return {
        'shopping_list_count': shopping_list_count,
        'unread_notifications_count': unread_notifications_count,
        'current_user_nav': current_user_nav,
        'is_admin_nav': is_admin_nav,
        'mega_menu': mega_menu_data,
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
        from models.postgres_models import db
        db.engine.execute('SELECT 1')
        return jsonify({'status': 'ok', 'postgres': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'postgres': 'disconnected', 'detail': str(e)}), 500



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
    app.run(debug=True, use_reloader=False, port=5001)
