from flask import session, redirect, url_for, jsonify, current_app
from models.users_model import get_user_by_email

def _admin_emails():
    raw = current_app.config.get("ADMIN_EMAILS", "") or ""
    return {item.strip().lower() for item in str(raw).split(",") if item.strip()}

def _is_admin_user(email):
    if not email:
        return False
    if email.lower() in _admin_emails():
        return True
    user = get_user_by_email(email) or {}
    return bool(user.get("is_admin") or user.get("isAdmin"))

def require_admin():
    email = session.get("user")
    if not email:
        return False, redirect(url_for("auth.login"))
    if not _is_admin_user(email):
        return False, (jsonify({"status": "error", "detail": "admin required"}), 403)
    return True, email
