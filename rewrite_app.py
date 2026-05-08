import re

with open("app.py", "r") as f:
    app_py = f.read()

# 1. Remove mongo index creations and mock user seeding
app_py = re.sub(r"# Ensure users.email has a unique index.*?try:.*?(?=# Register blueprints)", "", app_py, flags=re.DOTALL)

# 2. Rewrite inject_navbar_data to use Postgres
navbar_replacement = """
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
"""
app_py = re.sub(r"@app\.context_processor.*?return \{.*?'mega_menu': mega_menu_data,\n    \}", navbar_replacement, app_py, flags=re.DOTALL)

# 3. Replace health and debug mongo endpoints (bottom of file)
health_replace = """
@app.route('/health')
def health():
    try:
        from models.postgres_models import db
        db.engine.execute('SELECT 1')
        return jsonify({'status': 'ok', 'postgres': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'postgres': 'disconnected', 'detail': str(e)}), 500
"""

app_py = re.sub(r"@app\.route\('/health'\).*?return jsonify.*?500", health_replace, app_py, flags=re.DOTALL)

# Remove debug_mongo entirely
app_py = re.sub(r"@app\.route\('/debug-mongo'\).*?return jsonify\(info\), 200", "", app_py, flags=re.DOTALL)

with open("app.py", "w") as f:
    f.write(app_py)
